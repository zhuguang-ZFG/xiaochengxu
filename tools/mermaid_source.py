# -*- coding: utf-8 -*-
"""Mermaid 图源的标记解析与电子书物化。

为什么要有标记：Mermaid 块在 GitHub 上能直接渲染，但 PDF/EPUB 需要一张
确定的图片。标记把「源码」和「预渲染资产」绑在一起：

    <!-- figure: ../assets/diagram-login-flow.png | 登录态时序图 -->
    ```mermaid
    sequenceDiagram
    ...
    ```

标记必须紧邻 Mermaid 块（中间允许空行）。没有标记的 Mermaid 块在成书时
会悄悄退化成一行说明，读者看不到图；所以这里直接报错，让问题在导出前暴露。
"""
import pathlib
import re
from dataclasses import dataclass

MARKER_RE = re.compile(
    r"^\s*<!--\s*figure:\s*(\S+)\s*\|\s*(.*?)\s*-->\s*$")
MERMAID_OPEN_RE = re.compile(r"^\s{0,3}```mermaid\s*$")
FENCE_CLOSE_RE = re.compile(r"^\s{0,3}```\s*$")
FENCE_OPEN_RE = re.compile(r"^\s{0,3}```")


class MermaidError(ValueError):
    """Mermaid 标记/块不合法，或资产路径不可用。"""


@dataclass(frozen=True)
class MermaidBlock:
    path: pathlib.Path
    line_no: int
    asset_rel: str
    asset_path: pathlib.Path
    caption: str
    source: str
    start: int
    end: int


def _resolve_asset(asset_rel, path):
    p = pathlib.Path(asset_rel)
    if (p.is_absolute() or p.suffix.lower() != ".png"
            or re.match(r"^[A-Za-z]:[\\/]", asset_rel)
            or asset_rel.startswith(("/", "\\")) or "\\" in asset_rel):
        raise MermaidError(
            f"{path}: Mermaid 标记的资产必须是相对 PNG 路径，且用 / 分隔：{asset_rel}")
    return (path.parent / asset_rel).resolve()


def parse_text(text, path):
    """解析一段 Markdown，返回按出现顺序排列的 MermaidBlock。

    start/end 是标记块在原文里的字符偏移（不含块前空行，含结束围栏行的
    换行符），materialize 直接按偏移替换。围栏代码块里的标记不算数；
    未标记的 Mermaid 块、标记后没有 Mermaid 块、未闭合的 Mermaid 块都抛
    MermaidError。
    """
    path = pathlib.Path(path)
    lines = text.splitlines(keepends=True)
    offsets = []
    pos = 0
    for line in lines:
        offsets.append(pos)
        pos += len(line)
    blocks = []
    i = 0
    while i < len(lines):
        line = lines[i]
        m = MARKER_RE.match(line)
        if m:
            j = i + 1
            while j < len(lines) and not lines[j].strip():
                j += 1
            if j >= len(lines) or not MERMAID_OPEN_RE.match(lines[j]):
                raise MermaidError(
                    f"{path}:{i + 1}: figure 标记后必须紧跟 Mermaid 块")
            k = j + 1
            while k < len(lines) and not FENCE_CLOSE_RE.match(lines[k]):
                k += 1
            if k >= len(lines):
                raise MermaidError(
                    f"{path}:{i + 1}: Mermaid 块未闭合（缺少结束围栏）")
            asset_rel = m.group(1)
            caption = m.group(2).strip()
            if not caption:
                raise MermaidError(
                    f"{path}:{i + 1}: figure 标记缺少题注")
            blocks.append(MermaidBlock(
                path=path,
                line_no=i + 1,
                asset_rel=asset_rel,
                asset_path=_resolve_asset(asset_rel, path),
                caption=caption,
                source="".join(lines[j + 1:k]).rstrip("\n"),
                start=offsets[i],
                end=offsets[k] + len(lines[k]),
            ))
            i = k + 1
            continue
        if MERMAID_OPEN_RE.match(line):
            raise MermaidError(
                f"{path}:{i + 1}: 发现未标记的 Mermaid 块，"
                f"请在上方加 <!-- figure: ../assets/diagram-*.png | 图题 -->")
        if FENCE_OPEN_RE.match(line):
            k = i + 1
            while k < len(lines) and not FENCE_CLOSE_RE.match(lines[k]):
                k += 1
            i = k + 1
            continue
        i += 1
    return blocks


def parse_file(path):
    path = pathlib.Path(path)
    return parse_text(path.read_text(encoding="utf-8"), path)


def scan_paths(paths):
    """解析多个文件，并保证同一输出资产只被一个标记声明。"""
    blocks = []
    seen = {}
    for path in paths:
        for block in parse_file(path):
            if block.asset_path in seen:
                raise MermaidError(
                    f"{block.path}:{block.line_no}: Mermaid 输出资产重复："
                    f"{block.asset_rel}（已在 {seen[block.asset_path]} 声明）")
            seen[block.asset_path] = f"{block.path}:{block.line_no}"
            blocks.append(block)
    return blocks


def materialize(text, path):
    """把标记 + Mermaid 块替换成独占一段的图片 Markdown。

    返回 (新文本, blocks)。导出层随后按普通图片处理这张图，编号、图注、
    PDF/EPUB 内链都走同一条路径。
    """
    blocks = parse_text(text, path)
    if not blocks:
        return text, []
    out = []
    cursor = 0
    for block in blocks:
        chunk = text[cursor:block.start]
        out.append(chunk)
        if chunk and not chunk.endswith("\n\n"):
            out.append("\n" if chunk.endswith("\n") else "\n\n")
        caption = (block.caption.replace("\\", "\\\\")
                   .replace("[", r"\[").replace("]", r"\]"))
        out.append(f"![{caption}]({block.asset_rel})\n")
        cursor = block.end
    out.append(text[cursor:])
    return "".join(out), blocks
