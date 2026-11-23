# -*- coding: utf-8 -*-
"""gen_mermaid.py 的自测（标准库 unittest + Pillow）。

生成器本身只是「把标记里的源码交给 mermaid-cli，再把结果归一化成可复现
的 PNG」。这里不跑真正的 mmdc：CI 的资产比对会真跑。自测守五件事：

- 命令必须走 tools/mermaid 下锁定的 mmdc，不经 npx 重新解析依赖；
- mermaid-cli / mermaid / puppeteer 与浏览器版本都由常量与 lockfile 锁定；
- Puppeteer 只用锁定版本的 Chrome for Testing，且禁止它顺手下载 Chromium；
- 透明像素合成到白底，同一输入两次输出字节一致；
- 输出只能落在 docs/assets/，避免标记把文件写到任意位置。
"""
import hashlib
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

TOOLS = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
from PIL import Image  # noqa: E402

import gen_mermaid as gm  # noqa: E402
import mermaid_source as ms  # noqa: E402

MERMAID_DIR = TOOLS / "mermaid"


def make_block(tmp, asset="assets/diagram-x.png", source="flowchart LR\n  A --> B",
               caption="图题"):
    md = pathlib.Path(tmp) / "docs" / "03-进阶" / "demo.md"
    md.parent.mkdir(parents=True, exist_ok=True)
    text = (f"<!-- figure: ../{asset} | {caption} -->\n"
            f"```mermaid\n{source}\n```\n")
    md.write_text(text, encoding="utf-8")
    return ms.parse_text(text, md)[0]


class ConsoleEncodingTest(unittest.TestCase):
    def test_cp1252_控制台下打印中文不崩(self):
        """CI 的 Windows runner 用 cp1252 管道；渲染完成后打印中文路径崩过一次。"""
        env = dict(os.environ, PYTHONIOENCODING="cp1252", PYTHONUTF8="0")
        code = ("import gen_mermaid\n"
                "print('  生成 docs/assets/diagram-x.png')\n")
        proc = subprocess.run(
            [sys.executable, "-c", code],
            cwd=pathlib.Path(__file__).resolve().parent,
            env=env, capture_output=True)
        self.assertEqual(proc.returncode, 0,
                         proc.stderr.decode("utf-8", "replace"))
        self.assertIn("生成", proc.stdout.decode("utf-8"))


class CommandTest(unittest.TestCase):
    def test_命令走本地锁定的_mmdc_而不是_npx(self):
        cmd = gm.build_cmd("in.mmd", "out.png", "m.json", "p.json")
        self.assertTrue(pathlib.Path(cmd[0]).name.lower().startswith("node"))
        cli = pathlib.Path(next(part for part in cmd
                                if str(part).endswith("cli.js")))
        self.assertIn("node_modules", cli.parts)
        self.assertIn("mermaid-cli", cli.parts)
        lowered = [part.lower() for part in cmd]
        self.assertNotIn("npx", lowered)
        self.assertNotIn("--yes", lowered)

    def test_启动_mmdc_前先加载字体固定钩子(self):
        """时序图会同时用 sans-serif 和主题字体量文字并取较大者。

        CI 与本机的 Arial 版本不同，两条测量分支会选到不同结果，坐标随之
        漂移。钩子必须在 mmdc 之前加载，把通用 sans-serif 映射到主题字体。
        """
        cmd = gm.build_cmd("in.mmd", "out.png", "m.json", "p.json")
        self.assertEqual(cmd[1], "--import")
        self.assertEqual(cmd[2], gm.PIN_SANS_SERIF.as_uri())
        self.assertTrue(gm.PIN_SANS_SERIF.is_file())
        self.assertEqual(pathlib.Path(cmd[3]).name, "cli.js")

    def test_依赖与浏览器版本全部精确锁定(self):
        self.assertEqual(gm.PINNED_MERMAID_CLI, "11.4.2")
        self.assertEqual(gm.PINNED_MERMAID, "11.17.2")
        self.assertEqual(gm.PINNED_PUPPETEER, "23.11.1")
        self.assertEqual(gm.PINNED_BROWSER, "157.0.8103.78")
        self.assertEqual(gm.PINNED_DEPS, {
            "@mermaid-js/mermaid-cli": "11.4.2",
            "mermaid": "11.17.2",
            "puppeteer": "23.11.1",
        })

    def test_命令固定白底_2x_与输入输出(self):
        cmd = gm.build_cmd("in.mmd", "out.png", "m.json", "p.json")
        self.assertEqual(cmd[cmd.index("-b") + 1], "white")
        self.assertEqual(cmd[cmd.index("-s") + 1], "2")
        self.assertEqual(cmd[cmd.index("-i") + 1], "in.mmd")
        self.assertEqual(cmd[cmd.index("-o") + 1], "out.png")


class ConfigTest(unittest.TestCase):
    def test_puppeteer_用给定_chrome_路径且无头(self):
        with tempfile.TemporaryDirectory() as td:
            _, ppt = gm.write_configs(td, "C:/Chrome/chrome.exe")
            data = json.loads(pathlib.Path(ppt).read_text(encoding="utf-8"))
            self.assertEqual(data["executablePath"], "C:/Chrome/chrome.exe")
            self.assertEqual(data["headless"], "new")
            self.assertIn("--no-sandbox", data["args"])

    def test_mermaid_主题与字体固定(self):
        self.assertEqual(gm.MERMAID_CONFIG["theme"], "base")
        font = gm.MERMAID_CONFIG["themeVariables"]["fontFamily"]
        self.assertIn("Microsoft YaHei", font)
        self.assertFalse(gm.MERMAID_CONFIG["flowchart"]["htmlLabels"])
        # 配置必须能原样序列化，避免 set 之类不可写 JSON 的值混进来
        json.dumps(gm.MERMAID_CONFIG)


class ThemeFontTest(unittest.TestCase):
    def test_取主题字体栈的第一个字体(self):
        self.assertEqual(gm.theme_font_family(), "Microsoft YaHei")
        config = {"themeVariables": {"fontFamily": ' "Noto Sans SC" , sans-serif '}}
        self.assertEqual(gm.theme_font_family(config), "Noto Sans SC")

    def test_主题字体缺失时拒绝渲染(self):
        with self.assertRaises(SystemExit):
            gm.theme_font_family(
                {"themeVariables": {"fontFamily": " , sans-serif"}})


class PinnedEnvironmentTest(unittest.TestCase):
    def test_package_json_精确锁定依赖(self):
        data = json.loads(
            (MERMAID_DIR / "package.json").read_text(encoding="utf-8"))
        self.assertEqual(data["dependencies"], gm.PINNED_DEPS)
        for spec in data["dependencies"].values():
            self.assertRegex(spec, r"^\d+\.\d+\.\d+$")

    def test_package_lock_与_pins_一致(self):
        data = json.loads(
            (MERMAID_DIR / "package-lock.json").read_text(encoding="utf-8"))
        for name, version in gm.PINNED_DEPS.items():
            entry = data["packages"]["node_modules/" + name]
            self.assertEqual(entry["version"], version)

    def test_浏览器安装脚本与固定版本一致(self):
        data = json.loads(
            (MERMAID_DIR / "package.json").read_text(encoding="utf-8"))
        script = data["scripts"]["install-browser"]
        # 必须走包装脚本：@puppeteer/browsers 的解压步骤拒绝相对路径，
        # 直接把 --path .browser 交给它会在 CI 首次安装时崩掉。
        self.assertEqual(script, f"node install-browser.js {gm.PINNED_BROWSER}")
        self.assertNotIn("latest", script)
        wrapper = (MERMAID_DIR / "install-browser.js").read_text(encoding="utf-8")
        self.assertIn('path.join(dir, ".browser")', wrapper)
        self.assertIn('"--path"', wrapper)
        self.assertIn("@puppeteer/browsers", wrapper)

    def test_浏览器安装目录必须解析成绝对路径(self):
        """browsers 的解压步骤拒绝相对路径：CI 首次安装会直接崩在 extract-zip。"""
        wrapper = json.dumps(str(MERMAID_DIR / "install-browser.js"))
        workdir = json.dumps(tempfile.gettempdir())
        code = (
            f"const {{browserArgs}} = require({wrapper});"
            f"const args = browserArgs('{gm.PINNED_BROWSER}', {workdir});"
            "const i = args.indexOf('--path');"
            "process.stdout.write(args[i + 1]);"
        )
        proc = subprocess.run(
            [shutil.which("node") or "node", "-e", code],
            capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        target = pathlib.Path(proc.stdout)
        self.assertTrue(target.is_absolute(), proc.stdout)
        self.assertEqual(target.name, ".browser")

    def test_依赖版本不符时拒绝渲染(self):
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            for name, version in gm.PINNED_DEPS.items():
                pkg = root / "node_modules" / name / "package.json"
                pkg.parent.mkdir(parents=True)
                pkg.write_text(json.dumps({"name": name, "version": version}),
                               encoding="utf-8")
            gm.check_pinned_deps(root)
            pkg = root / "node_modules" / "mermaid" / "package.json"
            pkg.write_text(json.dumps({"name": "mermaid", "version": "11.0.0"}),
                           encoding="utf-8")
            with self.assertRaises(SystemExit) as ctx:
                gm.check_pinned_deps(root)
            self.assertIn("mermaid", str(ctx.exception))

    def test_缺少本地依赖时给出安装命令(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(SystemExit) as ctx:
                gm.check_pinned_deps(td)
            msg = str(ctx.exception)
            self.assertIn("npm ci --ignore-scripts --prefix tools/mermaid", msg)
            self.assertIn("npm run install-browser --prefix tools/mermaid", msg)

    def test_浏览器发现只接受锁定版本(self):
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            # 版本号故意排在 157 前面：若发现逻辑不筛版本，会先返回它
            other = root / "chrome" / "win64-100.0.0" / "chrome-win64" / "chrome.exe"
            other.parent.mkdir(parents=True)
            other.write_bytes(b"")
            pinned = (root / "chrome" / "win64-157.0.8103.78"
                      / "chrome-win64" / "chrome.exe")
            pinned.parent.mkdir(parents=True)
            pinned.write_bytes(b"")
            self.assertEqual(pathlib.Path(gm.find_pinned_chrome(root, env={})),
                             pinned)

    def test_浏览器环境变量必须指向锁定版本(self):
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            other = root / "chrome.exe"
            other.write_bytes(b"")
            with self.assertRaises(SystemExit):
                gm.find_pinned_chrome(root, env={"MERMAID_BROWSER_PATH": str(other)})
            self.assertIsNone(gm.find_pinned_chrome(root, env={}))


class NormalizeTest(unittest.TestCase):
    def test_透明区合成白底(self):
        with tempfile.TemporaryDirectory() as td:
            src = pathlib.Path(td) / "src.png"
            dst = pathlib.Path(td) / "dst.png"
            img = Image.new("RGBA", (4, 4), (0, 0, 0, 0))
            img.putpixel((0, 0), (255, 0, 0, 255))
            img.save(src)
            gm.normalize_png(src, dst)
            with Image.open(dst) as out:
                self.assertEqual(out.mode, "RGB")
                self.assertEqual(out.getpixel((3, 3)), (255, 255, 255))
                self.assertEqual(out.getpixel((0, 0)), (255, 0, 0))

    def test_同一输入两次输出字节一致(self):
        with tempfile.TemporaryDirectory() as td:
            src = pathlib.Path(td) / "src.png"
            a = pathlib.Path(td) / "a.png"
            b = pathlib.Path(td) / "b.png"
            Image.new("RGB", (8, 8), (200, 220, 240)).save(src)
            gm.normalize_png(src, a)
            gm.normalize_png(src, b)
            self.assertEqual(hashlib.md5(a.read_bytes()).hexdigest(),
                             hashlib.md5(b.read_bytes()).hexdigest())


class SourceScopeTest(unittest.TestCase):
    def test_写作契约里的示例不参与扫描(self):
        """契约正文要展示未标记的 Mermaid 例子；它不是待生成资产。

        gen_mermaid 与 check_repo 必须用同一份扫描范围（排除 _契约.md），
        否则契约里的教学示例会让生成脚本直接报「未标记」而无法运行。
        """
        with tempfile.TemporaryDirectory() as td:
            docs = pathlib.Path(td)
            (docs / "_契约.md").write_text(
                "```mermaid\nflowchart LR\n  A --> B\n```\n", encoding="utf-8")
            article = docs / "01-入门" / "demo.md"
            article.parent.mkdir()
            article.write_text(
                "<!-- figure: ../assets/diagram-x.png | 图题 -->\n"
                "```mermaid\nflowchart LR\n  A --> B\n```\n",
                encoding="utf-8")
            self.assertEqual(gm.source_files(docs), [article])


class RenderAllTest(unittest.TestCase):
    def test_逐个渲染并写入资产路径(self):
        with tempfile.TemporaryDirectory() as td:
            block = make_block(td)
            raw_written = []

            def fake_run(cmd, **kwargs):
                out = pathlib.Path(cmd[cmd.index("-o") + 1])
                Image.new("RGBA", (6, 6), (0, 0, 0, 0)).save(out)
                raw_written.append(out)
                mmd = pathlib.Path(cmd[cmd.index("-i") + 1])
                self.assertEqual(mmd.read_text(encoding="utf-8").strip(),
                                 "flowchart LR\n  A --> B")
                self.assertEqual(kwargs["env"][gm.SANS_SERIF_ENV],
                                 "Microsoft YaHei")

            gm.render_all([block], td, "C:/Chrome/chrome.exe", run=fake_run)
            self.assertTrue(block.asset_path.is_file())
            with Image.open(block.asset_path) as out:
                self.assertEqual(out.mode, "RGB")
                self.assertEqual(out.size, (6, 6))
            self.assertEqual(len(raw_written), 1)

    def test_输出必须在_docs_assets_下(self):
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td) / "docs" / "assets"
            gm.check_output_path(root / "ok.png", assets_root=root)
            with self.assertRaises(SystemExit):
                gm.check_output_path(pathlib.Path(td) / "docs" / "bad.png",
                                     assets_root=root)
            with self.assertRaises(SystemExit):
                gm.check_output_path(root.parent / "assets2" / "x.png",
                                     assets_root=root)


if __name__ == "__main__":
    unittest.main(verbosity=2)
