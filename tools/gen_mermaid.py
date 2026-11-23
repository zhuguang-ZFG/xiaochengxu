# -*- coding: utf-8 -*-
"""把文档里的 Mermaid 标记渲染成 PNG（供 PDF/EPUB 与 CI 逐字节比对）。

图源仍以 Markdown 里的 Mermaid 块为准：GitHub 上直接渲染，电子书用这里的
预渲染图。渲染链固定为 mermaid-cli 的锁定版本 + 本机 Edge + 白底 2x，
再由 Pillow 合成白底、重存为确定性 PNG——浏览器吐出的字节不稳定，不能
直接入库。

用法：python tools/gen_mermaid.py
依赖：Node.js（npx）与本机 Edge；首次运行会下载锁定的 mermaid-cli。
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
import browser  # noqa: E402
import mermaid_source  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
ASSETS = DOCS / "assets"
CONTRACT_NAME = "_契约.md"


def source_files(docs_root=DOCS):
    """待渲染的 Markdown：排除写作契约，契约里的 Mermaid 是格式示例。"""
    return sorted(p for p in pathlib.Path(docs_root).rglob("*.md")
                  if p.name != CONTRACT_NAME)


PINNED_CLI = "@mermaid-js/mermaid-cli@11.4.2"

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


def npx_prefix(platform=None):
    """Windows 上 npx 是 .cmd，subprocess 直接执行不到，必须经 cmd。"""
    platform = platform or sys.platform
    if platform == "win32":
        return ["cmd", "/c", "npx"]
    return ["npx"]


def build_cmd(source, output, mermaid_cfg, puppeteer_cfg, platform=None):
    return npx_prefix(platform) + [
        "--yes", PINNED_CLI, "mmdc",
        "-i", str(source),
        "-o", str(output),
        "-c", str(mermaid_cfg),
        "-p", str(puppeteer_cfg),
        "-b", "white",
        "-s", "2",
        "-w", "1600",
    ]


def write_configs(workdir, edge):
    workdir = pathlib.Path(workdir)
    mermaid_cfg = workdir / "mermaid.json"
    puppeteer_cfg = workdir / "puppeteer.json"
    mermaid_cfg.write_text(
        json.dumps(MERMAID_CONFIG, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8")
    puppeteer_cfg.write_text(
        json.dumps({
            "executablePath": edge,
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


def render_all(blocks, workdir, edge, run=subprocess.run):
    workdir = pathlib.Path(workdir)
    mermaid_cfg, puppeteer_cfg = write_configs(workdir, edge)
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
    # 用本机 Edge，禁止 Puppeteer 另下 Chromium：版本漂移只会来自 Edge，
    # 资产比对报红时原因单一。
    os.environ.setdefault("PUPPETEER_SKIP_DOWNLOAD", "1")
    os.environ.setdefault("PUPPETEER_SKIP_CHROMIUM_DOWNLOAD", "1")

    blocks = mermaid_source.scan_paths(source_files())
    if not blocks:
        print("没有 Mermaid 标记，跳过")
        return

    edge = browser.find_edge()
    if not edge:
        raise SystemExit("找不到 Edge，无法渲染 Mermaid（可用环境变量 EDGE_PATH 指定）")
    if not shutil.which("npx"):
        raise SystemExit("找不到 npx，请先安装 Node.js")

    for block in blocks:
        check_output_path(block.asset_path)
    with tempfile.TemporaryDirectory(prefix="mermaid-") as workdir:
        render_all(blocks, workdir, edge)
    for block in blocks:
        print(f"  生成 {block.asset_path.relative_to(ROOT).as_posix()}")
    print(f"Mermaid 图生成完成（{len(blocks)} 张）")


if __name__ == "__main__":
    main()
