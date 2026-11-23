# -*- coding: utf-8 -*-
"""把文档里的 Mermaid 标记渲染成 PNG（供 PDF/EPUB 与 CI 逐字节比对）。

图源仍以 Markdown 里的 Mermaid 块为准：GitHub 上直接渲染，电子书用这里的
预渲染图。渲染链固定为 tools/mermaid 下锁定的 mermaid-cli + Chrome for
Testing + 白底 2x，再由 Pillow 合成白底、重存为确定性 PNG——浏览器吐出的
字节不稳定，不能直接入库。

用法：
  npm ci --ignore-scripts --prefix tools/mermaid
  npm run install-browser --prefix tools/mermaid
  python tools/gen_mermaid.py

依赖：Node.js 与上面两条命令安装的锁定依赖/浏览器。Chrome for Testing 的
版本写在 PINNED_BROWSER，必须与 tools/mermaid/package.json 的安装脚本一致；
PDF 打印仍走本机 Edge（tools/browser.py），与本脚本无关。
"""
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile

from PIL import Image

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import mermaid_source  # noqa: E402

# 与 render.py 同一类坑：Windows 管道默认 cp1252，渲染完成后打印中文路径
# 会抛 UnicodeEncodeError——资产已写好，脚本却以非零码退出。
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = pathlib.Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
ASSETS = DOCS / "assets"
CONTRACT_NAME = "_契约.md"
MERMAID_DIR = ROOT / "tools" / "mermaid"

PINNED_MERMAID_CLI = "11.4.2"
PINNED_MERMAID = "11.17.2"
PINNED_PUPPETEER = "23.11.1"
PINNED_BROWSER = "157.0.8103.79"
PINNED_DEPS = {
    "@mermaid-js/mermaid-cli": PINNED_MERMAID_CLI,
    "mermaid": PINNED_MERMAID,
    "puppeteer": PINNED_PUPPETEER,
}


def source_files(docs_root=DOCS):
    """待渲染的 Markdown：排除写作契约，契约里的 Mermaid 是格式示例。"""
    return sorted(p for p in pathlib.Path(docs_root).rglob("*.md")
                  if p.name != CONTRACT_NAME)

# 主题固定成书稿配色；htmlLabels=False 用 SVG 文本，避免 foreignObject
# 在不同浏览器版本里的排版差异。
MERMAID_CONFIG = {
    "theme": "base",
    "themeVariables": {
        "fontFamily": "Microsoft YaHei, PingFang SC, Noto Sans CJK SC, sans-serif",
        "fontSize": "16px",
        "primaryColor": "#E8F7EE",
        "primaryTextColor": "#1F2937",
        "primaryBorderColor": "#07C160",
        "lineColor": "#6B7280",
        "secondaryColor": "#FFFFFF",
        "tertiaryColor": "#FFFFFF",
    },
    "flowchart": {"htmlLabels": False, "curve": "basis"},
    "sequence": {"useMaxWidth": False},
}


def node_exe():
    return shutil.which("node") or "node"


def mmdc_js(mermaid_dir=None):
    """tools/mermaid 下锁定的 mermaid-cli 入口，绕开 npx 的 registry 解析。"""
    root = pathlib.Path(mermaid_dir or MERMAID_DIR)
    return (root / "node_modules" / "@mermaid-js" / "mermaid-cli"
            / "src" / "cli.js")


def find_pinned_chrome(browser_root=None, env=None):
    """返回锁定版本 Chrome for Testing 的可执行文件；找不到返回 None。

    .browser 是 `npm run install-browser` 的安装目录；不同平台的可执行文件名
    不同（Windows chrome.exe、Linux chrome、macOS Google Chrome for Testing）。
    只接受路径里带 PINNED_BROWSER 的文件，避免缓存里更新过的 Chrome 悄悄
    改变渲染结果。
    """
    env = os.environ if env is None else env
    override = env.get("MERMAID_BROWSER_PATH")
    if override:
        path = pathlib.Path(override)
        if path.is_file() and PINNED_BROWSER in path.as_posix():
            return str(path)
        raise SystemExit(
            f"MERMAID_BROWSER_PATH 必须指向 Chrome for Testing {PINNED_BROWSER}："
            f"{path}")
    root = pathlib.Path(browser_root or (MERMAID_DIR / ".browser"))
    for name in ("chrome.exe", "chrome", "Google Chrome for Testing"):
        for candidate in sorted(root.rglob(name)):
            if PINNED_BROWSER in candidate.as_posix() and candidate.is_file():
                return str(candidate)
    return None


def installed_versions(mermaid_dir=None):
    root = pathlib.Path(mermaid_dir or MERMAID_DIR)
    versions = {}
    missing = []
    for name in PINNED_DEPS:
        pkg = root / "node_modules" / name / "package.json"
        if not pkg.is_file():
            missing.append(name)
            continue
        versions[name] = json.loads(
            pkg.read_text(encoding="utf-8")).get("version")
    if missing:
        raise SystemExit(
            "缺少本地 Mermaid 依赖："
            + "、".join(missing)
            + "\n请先运行：\n"
              "  npm ci --ignore-scripts --prefix tools/mermaid\n"
              "  npm run install-browser --prefix tools/mermaid")
    return versions


def check_pinned_deps(mermaid_dir=None):
    versions = installed_versions(mermaid_dir)
    drift = []
    for name, want in PINNED_DEPS.items():
        got = versions.get(name)
        if got != want:
            drift.append((name, got, want))
    if drift:
        detail = "\n".join(f"   {name}: 已安装 {got}，锁定 {want}"
                           for name, got, want in drift)
        raise SystemExit(
            "本地 Mermaid 依赖与 tools/mermaid/package-lock.json 不一致：\n"
            f"{detail}\n请重新运行：\n"
            "  npm ci --ignore-scripts --prefix tools/mermaid")


def build_cmd(source, output, mermaid_cfg, puppeteer_cfg):
    return [node_exe(), str(mmdc_js())] + [
        "-i", str(source),
        "-o", str(output),
        "-c", str(mermaid_cfg),
        "-p", str(puppeteer_cfg),
        "-b", "white",
        "-s", "2",
        "-w", "1600",
    ]


def write_configs(workdir, browser):
    workdir = pathlib.Path(workdir)
    mermaid_cfg = workdir / "mermaid.json"
    puppeteer_cfg = workdir / "puppeteer.json"
    mermaid_cfg.write_text(
        json.dumps(MERMAID_CONFIG, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8")
    puppeteer_cfg.write_text(
        json.dumps({
            "executablePath": browser,
            "headless": "new",
            "args": ["--no-sandbox", "--disable-gpu",
                     "--font-render-hinting=none"],
        }, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8")
    return mermaid_cfg, puppeteer_cfg


def check_output_path(path, assets_root=ASSETS):
    path = pathlib.Path(path).resolve()
    root = pathlib.Path(assets_root).resolve()
    if root not in path.parents:
        raise SystemExit(
            f"拒绝写入 {path}：Mermaid 资产必须落在 {root} 下。"
            f"请检查 figure 标记里的路径。")


def normalize_png(src, dst):
    """合成白底并重存，抹掉浏览器 PNG 里的时间戳/调色板差异。"""
    with Image.open(src) as img:
        img.load()
        if img.mode in ("RGBA", "LA") or (
                img.mode == "P" and "transparency" in img.info):
            rgba = img.convert("RGBA")
            out = Image.new("RGB", rgba.size, (255, 255, 255))
            out.paste(rgba, mask=rgba.split()[-1])
        else:
            out = img.convert("RGB")
    dst = pathlib.Path(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_name(dst.name + ".tmp")
    out.save(tmp, format="PNG", optimize=True)
    os.replace(tmp, dst)


def render_all(blocks, workdir, browser, run=subprocess.run):
    workdir = pathlib.Path(workdir)
    mermaid_cfg, puppeteer_cfg = write_configs(workdir, browser)
    for block in blocks:
        stem = block.asset_path.stem
        source = workdir / f"{stem}.mmd"
        raw = workdir / f"{stem}.raw.png"
        source.write_text(block.source + "\n", encoding="utf-8")
        cmd = build_cmd(source, raw, mermaid_cfg, puppeteer_cfg)
        try:
            run(cmd, check=True, capture_output=True, text=True)
        except subprocess.CalledProcessError as exc:
            detail = (exc.stderr or exc.stdout or "").strip()
            raise SystemExit(
                f"{block.path}:{block.line_no} 渲染失败：{detail}") from exc
        if not raw.is_file():
            raise SystemExit(
                f"{block.path}:{block.line_no} 渲染后没有产出 PNG")
        normalize_png(raw, block.asset_path)


def main():
    # 浏览器由 install-browser 显式安装；禁止 Puppeteer 在 npm 安装阶段
    # 再下一份版本不明的 Chromium。
    os.environ.setdefault("PUPPETEER_SKIP_DOWNLOAD", "1")
    os.environ.setdefault("PUPPETEER_SKIP_CHROMIUM_DOWNLOAD", "1")

    blocks = mermaid_source.scan_paths(source_files())
    if not blocks:
        print("没有 Mermaid 标记，跳过")
        return

    check_pinned_deps()
    if not shutil.which("node"):
        raise SystemExit("找不到 node，请先安装 Node.js")
    if not mmdc_js().is_file():
        raise SystemExit(
            f"找不到本地 mermaid-cli：{mmdc_js()}\n"
            "请运行 npm ci --ignore-scripts --prefix tools/mermaid")
    chrome = find_pinned_chrome()
    if not chrome:
        raise SystemExit(
            f"找不到 Chrome for Testing {PINNED_BROWSER}。\n"
            "首次运行请执行：\n"
            "  npm ci --ignore-scripts --prefix tools/mermaid\n"
            "  npm run install-browser --prefix tools/mermaid\n"
            "也可用 MERMAID_BROWSER_PATH 指向该版本的可执行文件。")

    for block in blocks:
        check_output_path(block.asset_path)
    print(f"Mermaid 渲染环境：mermaid-cli {PINNED_MERMAID_CLI}"
          f" / mermaid {PINNED_MERMAID} / Chrome {PINNED_BROWSER}")
    with tempfile.TemporaryDirectory(prefix="mermaid-") as workdir:
        render_all(blocks, workdir, chrome)
    for block in blocks:
        print(f"  生成 {block.asset_path.relative_to(ROOT).as_posix()}")
    print(f"Mermaid 图生成完成（{len(blocks)} 张）")


if __name__ == "__main__":
    main()
