# -*- coding: utf-8 -*-
"""gen_mermaid.py 的自测（标准库 unittest + Pillow）。

生成器本身只是「把标记里的源码交给 mermaid-cli，再把结果归一化成可复现
的 PNG」。这里不跑真正的 npx：CI 的资产比对会真跑。自测守四件事：

- 命令必须带锁定版本、白底、2x，Windows 上要经 cmd 调 npx；
- Puppeteer 用本机 Edge，且禁止它顺手下载 Chromium；
- 透明像素合成到白底，同一输入两次输出字节一致；
- 输出只能落在 docs/assets/，避免标记把文件写到任意位置。
"""
import hashlib
import json
import os
import pathlib
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

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from PIL import Image  # noqa: E402

import gen_mermaid as gm  # noqa: E402
import mermaid_source as ms  # noqa: E402


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
    def test_windows_上经_cmd_调_npx(self):
        self.assertEqual(gm.npx_prefix(platform="win32"),
                         ["cmd", "/c", "npx"])
        self.assertEqual(gm.npx_prefix(platform="linux"), ["npx"])

    def test_命令锁定_cli_版本且白底_2x(self):
        cmd = gm.build_cmd("in.mmd", "out.png", "m.json", "p.json",
                           platform="linux")
        self.assertIn(gm.PINNED_CLI, cmd)
        self.assertEqual(gm.PINNED_CLI, "@mermaid-js/mermaid-cli@11.4.2")
        self.assertEqual(cmd[cmd.index("-b") + 1], "white")
        self.assertEqual(cmd[cmd.index("-s") + 1], "2")
        self.assertEqual(cmd[cmd.index("-i") + 1], "in.mmd")
        self.assertEqual(cmd[cmd.index("-o") + 1], "out.png")
        self.assertIn("mmdc", cmd)


class ConfigTest(unittest.TestCase):
    def test_puppeteer_用给定_edge_且不下载_chromium(self):
        with tempfile.TemporaryDirectory() as td:
            _, ppt = gm.write_configs(td, "C:/Edge/msedge.exe")
            data = json.loads(pathlib.Path(ppt).read_text(encoding="utf-8"))
            self.assertEqual(data["executablePath"], "C:/Edge/msedge.exe")
            self.assertIn("--no-sandbox", data["args"])

    def test_mermaid_主题与字体固定(self):
        self.assertEqual(gm.MERMAID_CONFIG["theme"], "base")
        font = gm.MERMAID_CONFIG["themeVariables"]["fontFamily"]
        self.assertIn("Microsoft YaHei", font)
        self.assertFalse(gm.MERMAID_CONFIG["flowchart"]["htmlLabels"])
        # 配置必须能原样序列化，避免 set 之类不可写 JSON 的值混进来
        json.dumps(gm.MERMAID_CONFIG)


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

            gm.render_all([block], td, "C:/Edge/msedge.exe", run=fake_run)
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
