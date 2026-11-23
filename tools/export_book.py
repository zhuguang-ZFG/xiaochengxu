# -*- coding: utf-8 -*-
"""把知识库导出为本地 PDF 与 EPUB（tools/export_book.py）。

为什么有这个脚本：仓库是按网页阅读组织的（每篇一个 Markdown + 相对链接 +
外挂视频），但读者常想要一本「能带走」的书——离线、顺序阅读、可标注。
本脚本把 34 篇文档按教学顺序合并成一本电子书，产物只落在本地 `dist/book/`
（已 gitignore：电子书是构建产物，不进版本库；源文件才是唯一的真）。

两种产物：
- PDF：先用 markdown 库把每章转 HTML、拼成整本（封面/版权/前言/使用说明/
  带页码目录、部分与章起页、页眉页脚），再调 Edge 无头模式打印。目录页码
  靠三遍打印收敛（占位 → 测页 → 回填校验），任何章节定位失败直接报错。
  Chromium 打印不生成大纲，打完再用 PyMuPDF 写入「部分 → 章 → 小节」
  三级书签与元数据——没有书签的几百页 PDF 基本没法翻。
- EPUB 3：手写打包（mimetype + container.xml + OPF + 每章一个 XHTML），
  nav 目录三级（部分 → 章 → 小节）+ landmarks，封面与元数据齐全，
  不依赖 calibre/ebook-convert。

用法：
  python tools/export_book.py               # PDF + EPUB 都生成
  python tools/export_book.py --pdf-only    # 只要 PDF
  python tools/export_book.py --epub-only   # 只要 EPUB

依赖：`pip install markdown pymupdf`；PDF 另需本机 Edge（路径可用环境变量
EDGE_PATH 覆盖）。
"""
import argparse
import datetime
import html as html_lib
import mimetypes
import os
import pathlib
import re
import shutil
import subprocess
import sys
import uuid
import zipfile
from dataclasses import dataclass, field
from urllib.parse import unquote
from xml.etree import ElementTree

import markdown
from browser import find_edge
import mermaid_source

ROOT = pathlib.Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
OUT = ROOT / "dist" / "book"

BOOK_TITLE = "小程序开发之路"
BOOK_SUBTITLE = "从认识小程序到上线发布的原生开发教程"
BOOK_URL = "https://github.com/zhuguang-ZFG/xiaochengxu"

# 教学顺序：元文章在前，教学链按目录序号。与 README 表格/学习路径总览一致。
CHAPTER_DIRS = [
    DOCS / "00-学习路线",
    DOCS / "01-入门", DOCS / "02-基础", DOCS / "03-进阶",
    DOCS / "04-云开发", DOCS / "05-发布", DOCS / "06-实战",
    DOCS / "07-安全与生产", DOCS / "08-资源",
]

MD_EXTENSIONS = ["extra", "sane_lists", "admonition"]

# 阅读顺序即教学顺序。parts 的分组与 README 的学习路径总览一致：
# 00 是全书的前置说明，01-04 是四段主课，05-06 是收尾，07-08 是上线后的加读与附录。
PARTS_SPEC = [
    ("开始之前", ("00-学习路线",),
     "先看学习路径、API 速查与 FAQ，知道这本书怎么用。"),
    ("认知与准备", ("01-入门",),
     "认识小程序、搭好环境、看懂项目结构，写出第一个页面。"),
    ("基础", ("02-基础",),
     "WXML、WXSS、JS 与生命周期——小程序的四块地基。"),
    ("进阶", ("03-进阶",),
     "组件、网络、性能、媒体、授权、支付、调试等实战能力。"),
    ("云开发、实战与发布", ("04-云开发", "05-发布", "06-实战"),
     "用云开发完成后端，把三个实战项目跑通并上线。"),
    ("安全与生产", ("07-安全与生产",),
     "上线不是终点：堵住信任边界上的漏洞，建立能定位、能回滚、能复盘的线上机制。"),
    ("附录", ("08-资源",),
     "官方文档、社区与常用工具，随查随用。"),
]

BOOK_AUTHOR = "zhuguang-ZFG 与开源贡献者"
BOOK_RIGHTS = "Apache License 2.0"
BOOK_EDITION = "第一版"


@dataclass
class Heading:
    level: int
    title: str          # 去掉行内 Markdown 后的可读标题
    raw_title: str      # 原始标题行
    id: str             # 全书唯一：ch08-s03
    slug: str           # 按网页规则生成的锚点

    @property
    def label(self):
        return self.title


@dataclass(frozen=True)
class Figure:
    chapter_no: int
    no: int
    id: str
    caption: str
    source: str
    path: pathlib.Path

    @property
    def label(self):
        return f"图 {self.chapter_no}-{self.no}"


@dataclass(frozen=True)
class Table:
    chapter_no: int
    no: int
    id: str
    caption: str

    @property
    def label(self):
        return f"表 {self.chapter_no}-{self.no}"


@dataclass
class Chapter:
    no: int
    path: pathlib.Path
    meta: dict
    title: str
    h1: str
    headings: list = field(default_factory=list)
    part_title: str = ""
    body: str = ""
    figures: list = field(default_factory=list)
    tables: list = field(default_factory=list)
    _anchor_index: dict = field(default_factory=dict, repr=False)
    _ambiguous: set = field(default_factory=set, repr=False)

    @property
    def description(self):
        return self.meta.get("description", "")

    @property
    def epub_file(self):
        return f"ch{self.no:02d}.xhtml"

    @property
    def pdf_anchor(self):
        return f"ch{self.no:02d}"

    @property
    def sections(self):
        return [h for h in self.headings if h.level == 2]

    @property
    def subsections(self):
        return [h for h in self.headings if h.level == 3]

    def resolve_anchor(self, fragment):
        """把作者写的锚点解析成全书唯一 id。

        旧文章里同一标题出现过两种锚点写法（空白删除、空白变连字符），
        所以按「去掉所有标点与空白」归一化后匹配，而不是只比 slug。
        """
        key = normalize_anchor(fragment)
        if not key:
            return None
        if key in self._ambiguous:
            raise ValueError(f"{self.path.name} 的锚点 #{fragment} 命中多个小节")
        return self._anchor_index.get(key)


@dataclass
class Part:
    no: int
    title: str
    description: str
    chapters: list


@dataclass
class Book:
    chapters: list
    parts: list
    _by_path: dict = field(default_factory=dict, repr=False)
    _figures_by_id: dict = field(default_factory=dict, repr=False)
    _figures_by_path: dict = field(default_factory=dict, repr=False)
    _tables_by_id: dict = field(default_factory=dict, repr=False)

    def __post_init__(self):
        self._by_path = {ch.path.resolve(): ch for ch in self.chapters}
        for ch in self.chapters:
            for fig in ch.figures:
                self._figures_by_id[fig.id] = fig
                self._figures_by_path[fig.path.resolve()] = fig
            for table in ch.tables:
                self._tables_by_id[table.id] = table

    @property
    def figures(self):
        return [fig for ch in self.chapters for fig in ch.figures]

    @property
    def tables(self):
        return [table for ch in self.chapters for table in ch.tables]

    def chapter_by_path(self, path):
        key = pathlib.Path(path).resolve()
        if key not in self._by_path:
            raise KeyError(f"不是本书章节：{path}")
        return self._by_path[key]

    def get_chapter(self, path):
        return self._by_path.get(pathlib.Path(path).resolve())

    def figure_by_id(self, fig_id):
        return self._figures_by_id.get(fig_id)

    def figure_for_path(self, path):
        return self._figures_by_path.get(pathlib.Path(path).resolve())

    def chapter_by_no(self, no):
        for ch in self.chapters:
            if ch.no == no:
                return ch
        raise KeyError(f"没有第 {no} 章")

    def resolve_anchor(self, source, fragment):
        """先在本章找，再在全书找唯一目标。

        文章里有一处把跨章引用写成了页内锚点（云开发入门 → 云数据库的
        「权限设置」），源文件不改，导出时按全书唯一标题补正。
        """
        target = source.resolve_anchor(fragment)
        if target is not None:
            return source, target
        matches = []
        for ch in self.chapters:
            target_id = ch.resolve_anchor(fragment)
            if target_id is not None:
                matches.append((ch, target_id))
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            raise ValueError(
                f"锚点 #{fragment} 在全书命中多个章节："
                f"{', '.join(ch.path.name for ch, _ in matches)}")
        return None


def strip_code_fences(text):
    """移除围栏代码块，供标题/锚点扫描使用（代码里的 # 不是标题）。"""
    return re.sub(r"```.*?```", "", text, flags=re.S)


def strip_inline_markdown(text):
    text = re.sub(r"!\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"`([^`]*)`", r"\1", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = text.replace("**", "").replace("__", "").replace("~~", "")
    text = text.replace("*", "").replace("_", "")
    return text.strip()


def slugify_heading(text):
    """GitHub 风格的中文锚点：空白转连字符，标点直接去掉。"""
    text = strip_inline_markdown(text).lower()
    chars = []
    for ch in text:
        if ch.isspace():
            chars.append("-")
        elif ch.isalnum() or ch == "-":
            chars.append(ch)
    slug = "".join(chars)
    slug = re.sub(r"^-+|-+$", "", slug)
    return slug or "section"


def normalize_anchor(text):
    """锚点归一化：URL 解码后去掉所有标点、空白与下划线。

    这样 #登录态wxlogin全流程 和 #登录态：wx.login 全流程 能对上；
    #常见错误--避坑 和 #常见错误 / 避坑 也能对上。
    """
    text = unquote(str(text))
    text = strip_inline_markdown(text).lower()
    return re.sub(r"[\W_]+", "", text, flags=re.UNICODE)


def parse_front_matter(text):
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    meta = {}
    if m:
        for line in m.group(1).splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                meta[k.strip()] = v.strip()
    return meta


def strip_front_matter(text):
    return re.sub(r"^---\n.*?\n---\n", "", text, count=1, flags=re.S)


def extract_h1(text):
    body = strip_code_fences(text)
    m = re.search(r"^#\s+(.+)$", body, re.M)
    return strip_inline_markdown(m.group(1)) if m else ""


def parse_headings(body, chapter_no):
    """扫描 H2/H3 并分配全书唯一 id。

    标题只用 markdown 库渲染，但 id 由我们自己给，保证：
    - PDF 内部链接与 EPUB 目录指向同一套 id；
    - 同名小节（每章都有「验证」「随堂测验」）不会串章。
    """
    body = strip_code_fences(strip_front_matter(body))
    headings = []
    for i, m in enumerate(re.finditer(r"^(#{2,3})\s+(.+?)\s*$", body, re.M)):
        raw = m.group(2).strip()
        display = strip_inline_markdown(raw)
        level = len(m.group(1))
        headings.append(Heading(
            level=level, title=display, raw_title=raw,
            id=f"ch{chapter_no:02d}-s{i:02d}", slug=slugify_heading(display)))
    return headings


def build_anchor_index(headings):
    index, ambiguous = {}, set()
    for h in headings:
        keys = {normalize_anchor(h.title), normalize_anchor(h.raw_title),
                normalize_anchor(h.slug)}
        for key in keys:
            if not key:
                continue
            if key in index and index[key] != h.id:
                ambiguous.add(key)
            else:
                index[key] = h.id
    return index, ambiguous


IMAGE_LINE_RE = re.compile(
    r"""^!\[([^\]]*)\]\(([^)\s]+)(?:\s+["'][^"']*["'])?\)\s*$""")
TABLE_CAPTION_RE = re.compile(r"^表：(.+?)\s*$")
TABLE_HEADER_RE = re.compile(r"^\|.*\|\s*$")
TABLE_RULE_RE = re.compile(r"^\|[\s:|-]+\|\s*$")
FENCE_LINE_RE = re.compile(r"^\s{0,3}```")


def prose_lines(text):
    """逐行给出围栏代码块之外的 (行号, 内容)。"""
    in_fence = False
    for line_no, line in enumerate(text.splitlines(), 1):
        if FENCE_LINE_RE.match(line):
            in_fence = not in_fence
            continue
        if not in_fence:
            yield line_no, line


def scan_figures(chapter, body):
    """按出现顺序登记本章独占图片；题注取 alt，缺题注直接拒绝。"""
    figures = []
    for line_no, line in prose_lines(body):
        m = IMAGE_LINE_RE.match(line)
        if not m:
            continue
        caption = strip_inline_markdown(m.group(1))
        if not caption:
            raise ValueError(
                f"{chapter.path.name}:{line_no} 图片缺少题注（alt）")
        source = m.group(2)
        no = len(figures) + 1
        figures.append(Figure(
            chapter_no=chapter.no, no=no,
            id=f"ch{chapter.no:02d}-f{no:02d}", caption=caption,
            source=source,
            path=(chapter.path.parent / unquote(source)).resolve()))
    return figures


def scan_tables(chapter, body):
    """登记带「表：」题注的表格；题注必须紧跟表头与分隔行。"""
    lines = list(prose_lines(body))
    tables = []
    for idx, (line_no, line) in enumerate(lines):
        m = TABLE_CAPTION_RE.match(line)
        if not m:
            continue
        j = idx + 1
        while j < len(lines) and not lines[j][1].strip():
            j += 1
        if (j + 1 >= len(lines)
                or not TABLE_HEADER_RE.match(lines[j][1])
                or not TABLE_RULE_RE.match(lines[j + 1][1])):
            raise ValueError(
                f"{chapter.path.name}:{line_no}「表：」题注后必须紧跟表格")
        no = len(tables) + 1
        tables.append(Table(
            chapter_no=chapter.no, no=no,
            id=f"ch{chapter.no:02d}-t{no:02d}",
            caption=strip_inline_markdown(m.group(1))))
    return tables


def collect_book():
    """扫描 34 篇文章，组成七部分的书稿模型。

    章节号是按教学顺序连续编号的（不是目录里的 01/02），所以文内
    「第 8 章」与跨章链接、PDF 书签、EPUB 文件名都用同一个编号。
    """
    chapters, parts, no = [], [], 0
    for part_no, (part_title, dirs, part_desc) in enumerate(PARTS_SPEC, 1):
        part_chapters = []
        for dir_name in dirs:
            for f in sorted((DOCS / dir_name).glob("*.md")):
                if not re.match(r"^\d\d-", f.name):
                    continue
                no += 1
                raw = f.read_text(encoding="utf-8")
                meta = parse_front_matter(raw)
                body = strip_front_matter(raw)
                body, _ = mermaid_source.materialize(body, f)
                h1 = extract_h1(body)
                title = meta.get("title") or h1 or f.stem
                headings = parse_headings(body, no)
                ch = Chapter(no=no, path=f, meta=meta, title=title, h1=h1,
                             headings=headings, part_title=part_title,
                             body=body)
                ch._anchor_index, ch._ambiguous = build_anchor_index(headings)
                ch.figures = scan_figures(ch, body)
                ch.tables = scan_tables(ch, body)
                part_chapters.append(ch)
                chapters.append(ch)
        parts.append(Part(part_no, part_title, part_desc, part_chapters))
    return Book(chapters, parts)


def strip_duplicate_h1(md_text, title):
    """删掉正文开头与章节标题相同的 H1（章节页已经渲染了一次）。"""
    m = re.search(r"^#\s+(.+)$", md_text, re.M)
    if not m:
        return md_text
    if strip_inline_markdown(m.group(1)) != strip_inline_markdown(title):
        return md_text
    end = m.end()
    if md_text.startswith("\n", end):
        end += 1
    return md_text[:m.start()] + md_text[end:]


def convert_checkboxes(md_text):
    """把 Markdown 任务列表换成印刷体能显示的方框。"""
    md_text = re.sub(r"^(\s*)- \[ \] ", r"\1- □ ", md_text, flags=re.M)
    md_text = re.sub(r"^(\s*)- \[[xX]\] ", r"\1- ■ ", md_text, flags=re.M)
    return md_text


def separate_lists(md_text):
    """列表紧贴上一段时 Markdown 会把选项并进问句，补一个空行。"""
    lines = md_text.split("\n")
    out = []
    for line in lines:
        if (re.match(r"^[-*+] ", line) and out and out[-1].strip()
                and not out[-1][:1].isspace()
                and not re.match(r"^[-*+] |^\d+\. ", out[-1])):
            out.append("")
        out.append(line)
    return "\n".join(out)


def _glyph_replace(text):
    text = text.replace("\ufe0f", "")
    text = text.replace("📺 ", "").replace("📺", "")
    return (text.replace("✅", "√").replace("❌", "×")
            .replace("⚠", "注意："))


def replace_glyphs(text):
    return _glyph_replace(text).strip()


def apply_outside_code(md_text, func):
    """只对围栏代码块之外的文字做替换，避免改坏示例代码。"""
    parts = re.split(r"(```.*?```)", md_text, flags=re.S)
    return "".join(p if p.startswith("```") else func(p) for p in parts)


def wrap_figures(html_text, figures):
    """把独占一段的图片包成带图号的 figure。

    图片必须先在扫描阶段登记（图录由 Markdown 的独占图片行生成）；
    正文里出现未登记的独占图片、或图录里的图片没渲染出来，都直接报错，
    避免电子书里出现没有编号、无法交叉引用的孤儿图。
    """
    by_source = {fig.source: fig for fig in figures}
    used = set()

    def make(m):
        inner = m.group(1)
        src_m = re.search(r'\bsrc="([^"]*)"', inner)
        src = html_lib.unescape(src_m.group(1)) if src_m else ""
        fig = by_source.get(src)
        if fig is None:
            raise ValueError(
                f"独占图片 {src or '(无 src)'} 不在图录中，请检查图片行是否独占一行")
        used.add(fig.id)
        caption = html_lib.escape(fig.caption, quote=False)
        return (f'<figure id="{fig.id}">{inner}'
                f'<figcaption><span class="fig-label">{fig.label}</span>'
                f"　{caption}</figcaption></figure>")

    html_text = re.sub(
        r"<p>\s*(<a\b[^>]*>\s*<img\b[^>]*>\s*</a>)\s*</p>", make, html_text,
        flags=re.S)
    html_text = re.sub(
        r"<p>\s*(<img\b[^>]*>)\s*</p>", make, html_text, flags=re.S)
    missing = [fig.label for fig in figures if fig.id not in used]
    if missing:
        raise ValueError(f"图录中的图片没有出现在正文：{'、'.join(missing)}")
    return html_text


TABLE_BLOCK_RE = re.compile(
    r"<p>\s*表：\s*(.*?)</p>\s*(<table\b.*?</table>)", re.S)


def wrap_tables(html_text, tables):
    """把「表：」题注段落与其后的表格包成带表号的 table-block。"""
    used = 0

    def make(m):
        nonlocal used
        if used >= len(tables):
            raise ValueError("正文表格多于已登记的表题")
        table = tables[used]
        used += 1
        caption = html_lib.escape(table.caption, quote=False)
        return (f'<div class="table-block" id="{table.id}">'
                f'<div class="table-caption"><span class="table-label">'
                f"{table.label}</span>　{caption}</div>"
                f"{m.group(2)}</div>")

    out = TABLE_BLOCK_RE.sub(make, html_text)
    if used < len(tables):
        table = tables[used]
        raise ValueError(
            f"表题多于实际表格：缺少「{table.label}　{table.caption}」")
    return out


def label_figure_links(html_text, book):
    """图链接前面补上「图 N-M」，读者不必点开才知道指向哪张图。"""
    def repl(m):
        attrs, inner = m.group(1), m.group(2)
        href_m = re.search(r'\bhref="([^"]*)"', attrs)
        if not href_m or "#" not in href_m.group(1):
            return m.group(0)
        fig = book.figure_by_id(href_m.group(1).rpartition("#")[2])
        if fig is None:
            return m.group(0)
        if re.search(r"图\s*\d+\s*-\s*\d+", inner):
            return m.group(0)
        return f"<a{attrs}>{fig.label}　{inner}</a>"

    return re.sub(r"<a\b([^>]*)>(.*?)</a>", repl, html_text, flags=re.S)


def rewrite_href(href, source, book, mode):
    """把 Markdown 相对链接改写为 PDF/EPUB 内部链接或 GitHub 外链。

    PDF 内部链接保持 #id；EPUB 必须带文件名。书外文件统一指向 GitHub
    blob，视频也用 GitHub 播放器——电子书离线时至少链接仍然可点。
    """
    if mode not in ("pdf", "epub"):
        raise ValueError(f"未知导出模式：{mode}")
    href = href.strip()
    if not href:
        return href
    if href.startswith(("http://", "https://", "mailto:", "tel:", "data:")):
        return href

    if href.startswith("#"):
        fragment = href[1:]
        found = book.resolve_anchor(source, fragment)
        if found is None:
            raise ValueError(f"{source.path.name} 的锚点 #{fragment} 无目标")
        target_ch, target_id = found
        return (f"#{target_id}" if mode == "pdf"
                else f"{target_ch.epub_file}#{target_id}")

    path_part, _, fragment = href.partition("#")
    target = (source.path.parent / unquote(path_part)).resolve()
    chapter = book.get_chapter(target)
    if chapter is not None:
        if fragment:
            target_id = chapter.resolve_anchor(fragment)
            if target_id is None:
                raise ValueError(
                    f"{source.path.name} 指向 {chapter.path.name} 的锚点 "
                    f"#{fragment} 无目标")
            return (f"#{target_id}" if mode == "pdf"
                    else f"{chapter.epub_file}#{target_id}")
        return f"#{chapter.pdf_anchor}" if mode == "pdf" else chapter.epub_file

    figure = book.figure_for_path(target)
    if figure is not None:
        owner = book.chapter_by_no(figure.chapter_no)
        return (f"#{figure.id}" if mode == "pdf"
                else f"{owner.epub_file}#{figure.id}")

    try:
        rel = target.relative_to(ROOT).as_posix()
    except ValueError:
        return href
    kind = "tree" if target.is_dir() else "blob"
    url = f"{BOOK_URL}/{kind}/main/{rel}"
    return f"{url}#{fragment}" if fragment else url


def promote_video_note(html_text):
    """把含「配套视频」的引用块换成纸质可读的提示块，其余引用块不动。"""
    def repl(m):
        inner = m.group(1)
        if "配套视频" not in inner:
            return m.group(0)
        return f'<div class="video-note">{inner.strip()}</div>'

    return re.sub(r"<blockquote>(.*?)</blockquote>", repl, html_text, flags=re.S)


def render_chapter_body(chapter, book, mode, gif_cache=None, image_sink=None,
                        image_prefix=""):
    """把一章 Markdown 渲染成可直接装进 PDF/EPUB 的正文 HTML。"""
    body = chapter.body
    body = strip_duplicate_h1(body, chapter.title)
    body = apply_outside_code(body, separate_lists)
    body = apply_outside_code(body, convert_checkboxes)
    html_text = _glyph_replace(md_to_html(body))

    heading_queue = iter(chapter.headings)

    def add_id(m):
        try:
            heading = next(heading_queue)
        except StopIteration:
            raise ValueError(f"{chapter.path.name} 渲染出的标题多于解析结果") from None
        if heading.level != int(m.group(1)):
            raise ValueError(f"{chapter.path.name} 标题层级错位：{heading.title}")
        return (f'<h{heading.level} id="{heading.id}">'
                f'{m.group(2)}</h{heading.level}>')

    html_text = re.sub(r"<h([23])>(.*?)</h\1>", add_id, html_text, flags=re.S)
    try:
        next(heading_queue)
    except StopIteration:
        pass
    else:
        raise ValueError(f"{chapter.path.name} 有标题没渲染出来")

    def rewrite_link(m):
        pre, href, post = m.group(1), m.group(2), m.group(3)
        new = rewrite_href(href, chapter, book, mode)
        internal = new.startswith("#") or new.startswith(chapter.epub_file)
        cls = ' class="xref"' if internal and new != href else ""
        other = (pre + post).strip()
        rest = f" {other}" if other else ""
        return f'<a{cls}{rest} href="{new}">'

    html_text = re.sub(
        r'<a\b([^>]*?)\bhref="([^"]*)"([^>]*)>', rewrite_link, html_text)

    html_text = label_figure_links(html_text, book)

    html_text = promote_video_note(html_text)

    html_text = wrap_tables(html_text, chapter.tables)
    html_text = wrap_figures(html_text, chapter.figures)

    html_text, resolved = fix_image_srcs(
        html_text, chapter.path, to_uri=(mode == "pdf"), gif_cache=gif_cache,
        prefix=image_prefix)
    if image_sink is not None:
        image_sink.update(resolved)
    return html_text


def fill_toc_page_numbers(html_text, page_map):
    """第二遍打印前，把目录里的占位符替换成第一遍测出的页码。"""
    def repl(m):
        attrs = m.group(1)
        key_m = re.search(r'data-toc-key="([^"]+)"', attrs)
        key = key_m.group(1)
        if key not in page_map:
            raise ValueError(f"目录缺少 {key} 的页码")
        return f'<span{attrs}>{page_map[key]}</span>'

    return re.sub(
        r'<span([^>]*\bdata-toc-key="[^"]+"[^>]*)>.*?</span>', repl, html_text)


# 封面用 Pillow 程序化生成：同一版本永远得到同一张图，不依赖设计师文件。
_COVER_FONT_CANDIDATES = {
    "serif": [
        "C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/simsun.ttc",
        "/usr/share/fonts/opentype/noto/NotoSerifCJK-Regular.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
        "/System/Library/Fonts/PingFang.ttc",
    ],
    "sans_bold": [
        "C:/Windows/Fonts/msyhbd.ttc", "C:/Windows/Fonts/simhei.ttf",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
        "/System/Library/Fonts/PingFang.ttc",
    ],
}


def _cover_font(size, bold=False):
    from PIL import ImageFont
    for candidate in _COVER_FONT_CANDIDATES["sans_bold" if bold else "serif"]:
        if pathlib.Path(candidate).is_file():
            try:
                return ImageFont.truetype(candidate, size)
            except OSError:
                continue
    return ImageFont.load_default()


def build_cover_png(path, size=(1240, 1754)):
    """生成暖纸色、绿色路径线的封面，尺寸与内容完全可复现。"""
    from PIL import Image, ImageDraw

    w, h = size
    paper = (246, 241, 228)
    ink = (30, 36, 32)
    green = (7, 193, 96)
    muted = (104, 112, 104)
    line_color = (222, 214, 193)
    img = Image.new("RGB", (w, h), paper)
    draw = ImageDraw.Draw(img)

    margin = int(w * 0.075)
    draw.rectangle([margin, margin, w - margin, h - margin],
                   outline=line_color, width=max(1, int(w * 0.0016)))
    draw.rectangle([0, 0, int(w * 0.012), h], fill=green)

    top_font = _cover_font(max(10, int(h * 0.016)), bold=True)
    draw.text((margin, int(h * 0.075)), "开源共建 · 微信小程序教程",
              font=top_font, fill=(12, 122, 68))

    title_size = int(h * 0.074)
    title_font = _cover_font(title_size, bold=True)
    while title_size > 10:
        if draw.textlength(BOOK_TITLE, font=title_font) <= w - 2 * margin:
            break
        title_size -= 2
        title_font = _cover_font(title_size, bold=True)
    draw.text((w / 2, int(h * 0.31)), BOOK_TITLE, font=title_font,
              fill=ink, anchor="mm")

    draw.line([margin, int(h * 0.395), w - margin, int(h * 0.395)],
              fill=green, width=max(2, int(h * 0.002)))

    sub_font = _cover_font(max(10, int(h * 0.024)))
    draw.text((w / 2, int(h * 0.445)), BOOK_SUBTITLE, font=sub_font,
              fill=(66, 72, 68), anchor="mm")

    # 五阶段学习路径：一条手绘感的线 + 五个节点。
    path_y = int(h * 0.61)
    xs = [margin + int((w - 2 * margin) * i / 4) for i in range(5)]
    points = []
    for i, x in enumerate(xs):
        points.append((x, path_y + int(h * 0.018) * (1 if i % 2 else -1)))
    draw.line(points, fill=green, width=max(2, int(h * 0.0035)), joint="curve")
    stage_font = _cover_font(max(9, int(h * 0.015)), bold=True)
    stages = ["认知", "基础", "进阶", "云开发", "上线"]
    radius = max(4, int(h * 0.009))
    for i, ((x, y), label) in enumerate(zip(points, stages)):
        draw.ellipse([x - radius, y - radius, x + radius, y + radius],
                     fill=paper, outline=green, width=max(2, int(h * 0.0022)))
        draw.text((x, y + int(h * 0.035)), label, font=stage_font,
                  fill=muted, anchor="mm")

    author_font = _cover_font(max(9, int(h * 0.016)))
    small_font = _cover_font(max(8, int(h * 0.0125)))
    draw.text((w / 2, int(h * 0.845)), BOOK_AUTHOR, font=author_font,
              fill=ink, anchor="mm")
    draw.text((w / 2, int(h * 0.885)),
              f"{BOOK_EDITION} · {BOOK_RIGHTS} · 开源共建",
              font=small_font, fill=muted, anchor="mm")
    draw.line([w * 0.38, h * 0.915, w * 0.62, h * 0.915],
              fill=green, width=max(2, int(h * 0.0018)))

    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, format="PNG", optimize=False)


def md_to_html(md_text, expand_details=True):
    """Markdown → HTML。三处预处理：

    - 残留的 mermaid 围栏直接报错——导出前应先经过 mermaid_source.materialize，
      悄悄降级成一行说明会让读者丢失整张图；
    - 测验的 <details> 是原始 HTML 块，块内默认不跑 markdown——答案里的
      `**B**.` 不加粗、`<text>` 会被当成真标签（良构 XML 直接报错）。
      所以把每个 details 块抠出来，内层单独过一遍 markdown 再拼回去；
    - 电子书没有「点击展开」，details 在打印/EPUB 里默认收起＝答案丢失，
      默认展开为带边框的答案块。
    """
    if re.search(r"^\s{0,3}```mermaid\s*$", md_text, re.M):
        raise ValueError("正文里还有未处理的 Mermaid 块（标记缺失或未物化）")

    def _details(m):
        inner = markdown.markdown(m.group(2).strip(), extensions=MD_EXTENSIONS)
        summary = m.group(1).strip()
        label = "参考答案" if "答案" in summary else summary
        if expand_details:
            return (f'<div class="qa"><div class="qa-label">{label}</div>\n'
                    f'{inner}\n</div>')
        return f'<details><summary>{label}</summary>\n{inner}\n</details>'

    md_text = re.sub(r"<details>\s*<summary>(.*?)</summary>(.*?)</details>",
                     _details, md_text, flags=re.S)
    return markdown.markdown(md_text, extensions=MD_EXTENSIONS)


def gif_representative_frame(gif_path, cache_dir):
    """取 GIF 动画 60% 进度处的帧存成 PNG（打印 PDF 只能定格一帧）。

    第 0 帧往往是入场动画前的空底图，直接印出去读者会以为图挂了——
    取中后段的帧最能代表这张图想讲的东西。确定性：同 GIF 同帧号同像素。
    """
    from PIL import Image
    cache_dir.mkdir(parents=True, exist_ok=True)
    out = cache_dir / f"{gif_path.stem}-{gif_path.stat().st_size // 1024}kb.png"
    if not out.is_file():
        with Image.open(gif_path) as im:
            n = getattr(im, "n_frames", 1)
            im.seek(int(n * 0.6))
            im.convert("RGB").save(out)
    return out


def fix_image_srcs(html, md_path, to_uri, gif_cache=None, prefix=""):
    """把相对图片路径重写为可定位的形式。

    python-markdown 输出形如 <img alt="…" src="…" />，src 不一定紧跟 img，
    所以必须按属性匹配而不是按标签开头匹配。
    to_uri=True：转 file:// 绝对 URI（PDF 的单页 HTML 用）；gif_cache 给出时，
    GIF 换成预渲染的代表帧 PNG（打印 PDF 定格一帧，见 gif_representative_frame）。
    to_uri=False：返回 (html, {旧路径: 新文件名})，图片由调用方拷进 EPUB。
    """
    resolved = {}

    def repl(m):
        src = m.group(2)
        if src.startswith(("http://", "https://", "file://", "data:")):
            return m.group(0)
        target = (md_path.parent / src).resolve()
        if not target.is_file():
            return m.group(0)  # 断链交给 check_repo 管，这里原样保留
        if gif_cache is not None and target.suffix.lower() == ".gif":
            target = gif_representative_frame(target, gif_cache)
        if to_uri:
            return m.group(1) + target.as_uri() + m.group(3)
        key = f"{prefix}img-{len(resolved) + 1}{target.suffix.lower()}"
        resolved[key] = target
        return m.group(1) + key + m.group(3)

    return re.sub(r'(<img[^>]*?\bsrc=")([^"]+)(")', repl, html), resolved


def _norm(s):
    """PDF 文本定位用：去掉空白与行内代码记号再做包含匹配。"""
    return re.sub(r"[\s`*_]+", "", s)


def _cn_number(n):
    return "零一二三四五六七八九十"[n] if 0 <= n <= 10 else str(n)


def _e(text):
    return html_lib.escape(str(text), quote=True)


def _meta_line(ch):
    values = [ch.meta.get(k, "").strip()
              for k in ("category", "difficulty", "reading_time")]
    return " · ".join(v for v in values if v)


def _title_section():
    return f"""<section class="front title-page">
<p class="title-top">开源共建 · 实战型教程</p>
<h1 class="book-title">{_e(BOOK_TITLE)}</h1>
<p class="book-subtitle">{_e(BOOK_SUBTITLE)}</p>
<div class="title-line"></div>
<p class="title-author">{_e(BOOK_AUTHOR)}</p>
<p class="title-edition">{_e(BOOK_EDITION)}</p>
<p class="title-url">{_e(BOOK_URL)}</p>
</section>"""


def _copyright_section():
    today = datetime.date.today().isoformat()
    return f"""<section class="front copyright-page">
<h1 class="front-title">图书信息</h1>
<dl class="meta-list">
<dt>书名</dt><dd>{_e(BOOK_TITLE)}</dd>
<dt>副标题</dt><dd>{_e(BOOK_SUBTITLE)}</dd>
<dt>作者</dt><dd>{_e(BOOK_AUTHOR)}</dd>
<dt>版本</dt><dd>{_e(BOOK_EDITION)}</dd>
<dt>许可</dt><dd>{_e(BOOK_RIGHTS)}</dd>
<dt>源码</dt><dd>{_e(BOOK_URL)}</dd>
<dt>导出</dt><dd>{today}</dd>
</dl>
<p>本书由仓库中的 Markdown 文章自动排版生成，属于开源电子书，不用于商业销售。</p>
<p>文中的代码、截图与手绘插图来自同一仓库；发现文字或链接问题，欢迎在源码仓库提交 issue。</p>
</section>"""


def _preface_section(book):
    return f"""<section class="front preface">
<h1 class="front-title">前言</h1>
<p>这是一本从开源仓库自动排版出来的小程序教程。全书 {len(book.chapters)} 章、
{sum(len(ch.sections) for ch in book.chapters)} 个小节，按零基础读者的学习顺序组织：
先认识小程序，再打基础，随后进入网络、性能、云开发、实战与发布。</p>
<p>每一章都从「为什么读这篇」开始，正文之后有常见错误、随堂测验、验证清单和
延伸阅读。随堂测验的答案已经展开，方便离线阅读；验证清单用方框标出，可以打印出来逐项勾选。</p>
<p>本书适合作为课程教材、自学手册和团队内训材料。阅读时建议打开配套仓库，
对照可运行示例与配套视频；纸书或离线设备上，正文里的链接仍然可以点击。</p>
<p>源文件才是这本书唯一的真。电子书是构建产物，排版脚本、文章与插图都在
{_e(BOOK_URL)} 公开维护。</p>
</section>"""


def _howto_section(book):
    items = "".join(
        f"<li><strong>{_e(p.title)}</strong>：{_e(p.description)}"
        f"（{len(p.chapters)} 章）</li>" for p in book.parts)
    return f"""<section class="front howto">
<h1 class="front-title">如何使用本书</h1>
<p>全书分为 {len(book.parts)} 个部分。第一次阅读建议按顺序推进；已经有基础的读者
可以直接从「进阶」或「云开发、实战与发布」开始。</p>
<ol class="howto-parts">{items}</ol>
<p>每章的固定结构：为什么读这篇 → 正文与示例 → 常见错误 / 避坑 → 随堂测验 →
验证 → 延伸阅读。先读导读判断是否需要这一章，再用验证清单确认自己真的会了。</p>
<p>代码块中的省略号表示与主题无关的代码；遇到长代码时，先看注释标出的关键行。
视频在 GitHub 播放器中在线观看，电子书正文保留了视频的说明与集数。</p>
</section>"""


def _toc_line(title, key, href, level, num=""):
    cls = {1: "toc-part", 2: "toc-ch", 3: "toc-sec"}[level]
    num_html = f'<span class="toc-num">{num}</span>' if num else ""
    return (f'<div class="toc-line {cls}">{num_html}'
            f'<a class="toc-title" href="{href}">{_e(title)}</a>'
            f'<span class="toc-dots"></span>'
            f'<span class="toc-page" data-toc-key="{key}">000</span></div>')


def _pdf_toc_html(book):
    rows = []
    for part in book.parts:
        rows.append(_toc_line(part.title, f"part{part.no}",
                              f"#part{part.no}", 1))
        for ch in part.chapters:
            rows.append(_toc_line(ch.title, ch.pdf_anchor,
                                  f"#{ch.pdf_anchor}", 2, f"{ch.no:02d}"))
            for heading in ch.sections:
                rows.append(_toc_line(heading.title, heading.id,
                                      f"#{heading.id}", 3))
    return f"""<section class="toc">
<h1 class="toc-heading">目录</h1>
<p class="toc-intro">页码为 PDF 实际页序；点击标题可跳到对应章节。</p>
{''.join(rows)}
</section>"""


def _pdf_list_line(label, caption, key, href):
    return (f'<div class="toc-line list-line">'
            f'<span class="list-label">{_e(label)}</span>'
            f'<a class="toc-title" href="{href}">{_e(caption)}</a>'
            f'<span class="toc-dots"></span>'
            f'<span class="toc-page" data-toc-key="{key}">000</span></div>')


def _pdf_lists_html(book):
    figures = "".join(
        _pdf_list_line(fig.label, fig.caption, f"fig-{fig.id}", f"#{fig.id}")
        for fig in book.figures)
    tables = "".join(
        _pdf_list_line(table.label, table.caption, f"tab-{table.id}",
                       f"#{table.id}")
        for table in book.tables)
    return f"""<section class="toc figure-list" id="figures-list">
<h1 class="toc-heading">插图目录</h1>
<p class="toc-intro">按章顺序列出全书 {len(book.figures)} 张插图；点击标题可跳到对应图。</p>
{figures}
</section>
<section class="toc table-list" id="tables-list">
<h1 class="toc-heading">表格目录</h1>
<p class="toc-intro">按章顺序列出全书 {len(book.tables)} 张表格；点击标题可跳到对应表。</p>
{tables}
</section>"""


def _pdf_part_html(part):
    return f"""<section class="part-page" id="part{part.no}">
<p class="part-kicker">PART {part.no:02d}</p>
<p class="part-no">第{_cn_number(part.no)}部分</p>
<h1 class="part-title">{_e(part.title)}</h1>
<p class="part-desc">{_e(part.description)}</p>
<p class="part-count">本部分共 {len(part.chapters)} 章</p>
</section>"""


def _pdf_chapter_html(ch, book, gif_cache):
    body = render_chapter_body(ch, book, "pdf", gif_cache=gif_cache)
    return f"""<section class="chapter" id="{ch.pdf_anchor}">
<p class="chapter-kicker">{_e(ch.part_title)}</p>
<p class="chapter-no">第 {ch.no} 章</p>
<h1 class="chapter-title">{_e(ch.title)}</h1>
<p class="chapter-desc">{_e(ch.description)}</p>
<div class="chapter-meta">{_e(_meta_line(ch))}</div>
<div class="chapter-body">{body}</div>
</section>"""


PDF_CSS = r"""
@page {
  size: A4;
  margin: 22mm 20mm 20mm 20mm;
  @top-left { content: "小程序开发之路"; font-family: "Microsoft YaHei", sans-serif;
              font-size: 8pt; color: #8a8f8b; }
  @top-right { content: string(chapter); font-family: "Microsoft YaHei", sans-serif;
               font-size: 8pt; color: #8a8f8b; }
  @bottom-center { content: counter(page); font-family: "Microsoft YaHei", sans-serif;
                   font-size: 9pt; color: #777; }
}
@page cover {
  size: A4; margin: 0;
  @top-left { content: none; } @top-right { content: none; } @bottom-center { content: none; }
}
@page front {
  @top-left { content: none; } @top-right { content: none; }
  @bottom-center { content: counter(page); font-family: "Microsoft YaHei", sans-serif;
                   font-size: 9pt; color: #777; }
}
@page :first {
  margin: 0;
  @top-left { content: none; } @top-right { content: none; } @bottom-center { content: none; }
}
html { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
html, body { margin: 0; padding: 0; }
body {
  font-family: "Source Han Serif SC", "Noto Serif CJK SC", "Songti SC", "SimSun", serif;
  font-size: 10.5pt; line-height: 1.8; color: #1f2421; text-align: justify;
}
a { color: #0b7a45; text-decoration: none; }
.cover { page: cover; width: 210mm; height: 297mm; overflow: hidden; }
.cover img { display: block; width: 210mm; height: 297mm; object-fit: cover; }
.front { page: front; break-before: page; }
.title-page { text-align: center; padding-top: 55mm; }
.title-top { font-family: "Microsoft YaHei", sans-serif; font-size: 10pt;
             letter-spacing: 3pt; color: #0b7a45; margin: 0 0 12mm; }
.book-title { font-family: "Microsoft YaHei", sans-serif; font-size: 36pt;
              letter-spacing: 2pt; margin: 0 0 6mm; color: #141a16; }
.book-subtitle { font-size: 14pt; color: #555; margin: 0; }
.title-line { width: 40mm; height: 1.2mm; background: #07c160; margin: 12mm auto; }
.title-author { font-size: 12pt; margin: 0 0 2mm; }
.title-edition, .title-url { color: #777; font-size: 9.5pt; margin: 0; }
.copyright-page { padding-top: 20mm; }
.front-title { font-family: "Microsoft YaHei", sans-serif; font-size: 22pt;
               margin: 0 0 8mm; padding-bottom: 3mm; border-bottom: 2px solid #07c160; }
.meta-list { display: grid; grid-template-columns: 24mm 1fr; row-gap: 2.5mm;
             font-size: 10pt; margin: 8mm 0 12mm; }
.meta-list dt { color: #777; }
.meta-list dd { margin: 0; }
.preface p, .howto p { text-indent: 2em; margin: 0 0 0.55em; }
.howto-parts { margin: 4mm 0 6mm; padding-left: 8mm; }
.howto-parts li { margin: 2.5mm 0; }
.toc { break-before: page; }
.toc-heading { string-set: chapter "目录"; font-family: "Microsoft YaHei", sans-serif;
               font-size: 22pt; margin: 0 0 3mm; padding-bottom: 3mm;
               border-bottom: 2px solid #07c160; }
.toc-intro { color: #777; font-size: 9pt; margin: 0 0 4mm; text-indent: 0; }
.toc-line { display: flex; align-items: baseline; font-size: 9.5pt; line-height: 1.55; }
.toc-part { margin-top: 4mm; padding-bottom: 1mm; font-family: "Microsoft YaHei", sans-serif;
            font-size: 11pt; font-weight: bold; color: #0b7a45;
            border-bottom: 0.4pt solid #cfe8d9; }
.toc-ch { margin-top: 1.2mm; font-weight: 600; }
.toc-sec { padding-left: 8mm; color: #555; font-size: 9pt; }
.toc-num { width: 8mm; flex: none; color: #8a8f8b; font-variant-numeric: tabular-nums; }
.toc-title { color: inherit; text-decoration: none; flex: 0 1 auto; min-width: 0;
             overflow-wrap: anywhere; }
.toc-dots { flex: 1 1 auto; border-bottom: 0.4pt dotted #b9b9b9; margin: 0 2mm 1mm;
            min-width: 8mm; }
.toc-page { width: 10mm; flex: none; text-align: right; display: inline-block;
            font-variant-numeric: tabular-nums; }
.figure-list .toc-heading { string-set: chapter "插图目录"; }
.table-list .toc-heading { string-set: chapter "表格目录"; }
.list-label { width: 18mm; flex: none; color: #0b7a45; font-weight: 600;
              font-variant-numeric: tabular-nums; }
.part-page { break-before: page; padding-top: 68mm; }
.part-kicker { font-family: "Microsoft YaHei", sans-serif; color: #8a8f8b;
               font-size: 9pt; letter-spacing: 2pt; margin: 0 0 3mm; }
.part-no { font-family: "Microsoft YaHei", sans-serif; color: #07a05a;
           font-size: 11pt; font-weight: bold; letter-spacing: 2pt; margin: 0 0 2mm; }
.part-title { string-set: chapter content(); font-family: "Microsoft YaHei", sans-serif;
              font-size: 34pt; line-height: 1.25; margin: 0 0 7mm; }
.part-desc { font-size: 12pt; color: #555; line-height: 1.8; margin: 0 0 8mm; }
.part-count { font-size: 9pt; color: #888; border-top: 0.5pt solid #d8e8de;
              padding-top: 3mm; }
.chapter { break-before: page; }
.chapter-kicker { font-family: "Microsoft YaHei", sans-serif; color: #0b7a45;
                  font-size: 9.5pt; letter-spacing: 1pt; margin: 0 0 5mm; }
.chapter-no { font-family: "Microsoft YaHei", sans-serif; color: #07a05a;
              font-weight: bold; font-size: 11pt; letter-spacing: 2pt; margin: 0 0 1.5mm; }
.chapter-title { string-set: chapter content(); font-family: "Microsoft YaHei", sans-serif;
                 font-size: 24pt; line-height: 1.25; margin: 0 0 4mm; }
.chapter-desc { font-size: 11pt; color: #555; line-height: 1.7; margin: 0 0 4mm; }
.chapter-meta { font-size: 9pt; color: #888; border-top: 0.5pt solid #d8e8de;
                border-bottom: 0.5pt solid #d8e8de; padding: 2mm 0; margin: 0 0 7mm; }
.chapter-body p { margin: 0 0 0.35em; text-indent: 2em; orphans: 2; widows: 2; }
.chapter-body h2 { font-family: "Microsoft YaHei", sans-serif; font-size: 14.5pt;
                   line-height: 1.4; margin: 8mm 0 3mm; padding-left: 3mm;
                   border-left: 4px solid #07c160; break-after: avoid; }
.chapter-body h3 { font-family: "Microsoft YaHei", sans-serif; font-size: 12pt;
                   margin: 6mm 0 2mm; break-after: avoid; }
ul, ol { margin: 2mm 0 3mm; padding-left: 7mm; }
li { margin: 1mm 0; text-align: justify; }
li p { text-indent: 0; margin: 0; }
code { font-family: "Cascadia Mono", Consolas, "Courier New", monospace;
       font-size: 9pt; background: #f3f6f4; padding: 0 1.5px; border-radius: 2px; }
pre { font-family: "Cascadia Mono", Consolas, "Courier New", monospace;
      font-size: 8.6pt; line-height: 1.55; background: #f7f9f8;
      border-left: 3px solid #07c160; padding: 3mm 4mm; margin: 3mm 0 4mm;
      white-space: pre-wrap; word-wrap: break-word; break-inside: avoid; }
pre code { background: none; padding: 0; font-size: inherit; }
blockquote { margin: 3mm 0; padding: 2.5mm 4mm; border-left: 3px solid #ffd666;
             background: #fffdf2; color: #4d4d4d; }
blockquote p { text-indent: 0; margin: 0; }
.video-note { background: #fffdf2; border-left: 3px solid #ffd666;
              padding: 2.5mm 4mm; margin: 3mm 0; font-size: 9.5pt; break-inside: avoid; }
.video-note p { text-indent: 0; margin: 0; }
.qa { background: #f5fbf7; border-left: 3px solid #07c160; padding: 3mm 4mm;
      margin: 4mm 0; font-size: 9.8pt; break-inside: avoid; }
.qa-label { font-family: "Microsoft YaHei", sans-serif; font-weight: bold;
            color: #0b7a45; margin-bottom: 1.5mm; }
.qa p { text-indent: 0; margin: 0 0 1mm; }
table { width: 100%; border-collapse: collapse; font-size: 9pt;
        margin: 3mm 0 4mm; break-inside: auto; }
thead { display: table-header-group; }
tr { break-inside: avoid; }
th, td { border: 0.5pt solid #d5ddd8; padding: 1.5mm 2mm; text-align: left;
         vertical-align: top; }
th { background: #eef8f2; font-family: "Microsoft YaHei", sans-serif; }
figure { margin: 3mm 0; text-align: center; break-inside: avoid; }
figure img { max-width: 100%; max-height: 90mm; }
figcaption { font-size: 9pt; color: #555; margin-top: 1.5mm; text-align: center; }
.fig-label, .table-label { font-family: "Microsoft YaHei", sans-serif;
                           font-weight: bold; color: #0b7a45; }
.table-block { margin: 3mm 0 4mm; }
.table-caption { font-size: 9pt; color: #555; margin: 0 0 1.2mm; text-align: center; }
.table-block table { margin: 0; }
img { max-width: 100%; }
hr { border: none; border-top: 0.5pt solid #d5ddd8; margin: 5mm 0; }
"""


def build_pdf_html(book, cover_path, gif_cache):
    cover_uri = cover_path.resolve().as_uri()
    body = [
        f'<section class="cover"><img src="{cover_uri}" alt="封面" /></section>',
        _title_section(), _copyright_section(), _preface_section(book),
        _howto_section(book), _pdf_toc_html(book), _pdf_lists_html(book),
    ]
    for part in book.parts:
        body.append(_pdf_part_html(part))
        for ch in part.chapters:
            body.append(_pdf_chapter_html(ch, book, gif_cache))
    return f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<title>{_e(BOOK_TITLE)}</title>
<style>{PDF_CSS}</style></head>
<body>{''.join(body)}</body></html>"""


def print_pdf(html_path, pdf_path):
    edge = find_edge()
    if not edge:
        raise SystemExit("找不到 Edge，无法打印 PDF（可用环境变量 EDGE_PATH 指定路径）")
    if pdf_path.exists():
        pdf_path.unlink()
    cmd = [edge, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
           "--virtual-time-budget=5000",
           f"--print-to-pdf={pdf_path}", html_path.resolve().as_uri()]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if not pdf_path.is_file() or pdf_path.stat().st_size < 50_000:
        detail = (result.stderr or result.stdout or "")[-800:]
        raise SystemExit(f"PDF 打印失败：{detail}")


def _page_heading_lines(doc):
    pages = []
    for page in doc:
        lines = []
        for block in page.get_text("dict").get("blocks", []):
            for line in block.get("lines", []):
                spans = line.get("spans", [])
                if not spans:
                    continue
                text = "".join(span.get("text", "") for span in spans)
                if not text.strip():
                    continue
                size = max(span.get("size", 0) for span in spans)
                lines.append((_norm(text), size))
        pages.append(lines)
    return pages


def _find_page(norm_pages, needle, start=0, end=None):
    end = len(norm_pages) if end is None else end
    needle = _norm(needle)
    for i in range(start, end):
        if needle in norm_pages[i]:
            return i
    return None


def _find_heading_page(heading_lines, title, start, end, min_size,
                       max_size=1000, required_text=None, norm_pages=None):
    needle = _norm(title)
    prefix = needle[:12]
    for i in range(start, end):
        if required_text is not None and norm_pages is not None:
            if _norm(required_text) not in norm_pages[i]:
                continue
        for text, size in heading_lines[i]:
            if not (min_size <= size <= max_size):
                continue
            if needle in text or (len(prefix) >= 6 and prefix in text):
                return i
    return None


def locate_pdf_pages(pdf_path, book):
    """从第一遍 PDF 提取每章/每节的物理页码（1 开始）。

    章节用大字号标题定位，小节只认 13–18pt 的标题行——这样正文里
    提到某个小节名时，不会把目录页码指到错误的页。
    """
    import fitz
    doc = fitz.open(str(pdf_path))
    try:
        norm_pages = [_norm(doc[i].get_text()) for i in range(doc.page_count)]
        heading_lines = _page_heading_lines(doc)
        total = doc.page_count

        preface = _find_heading_page(heading_lines, "前言", 0, total, 17,
                                     norm_pages=norm_pages)
        toc = _find_heading_page(heading_lines, "目录", (preface or 0) + 1,
                                 total, 17, norm_pages=norm_pages)
        if preface is None or toc is None:
            raise ValueError("PDF 里找不到前言或目录页")

        figures_list = _find_heading_page(
            heading_lines, "插图目录", toc + 1, total, 17,
            norm_pages=norm_pages)
        tables_list = _find_heading_page(
            heading_lines, "表格目录", (figures_list or toc) + 1, total, 17,
            norm_pages=norm_pages)
        if figures_list is None or tables_list is None:
            raise ValueError("PDF 里找不到插图目录或表格目录")

        page_map = {"preface": preface + 1, "toc": toc + 1,
                    "figures-list": figures_list + 1,
                    "tables-list": tables_list + 1}
        cursor = tables_list + 1
        for part in book.parts:
            part_page = _find_page(norm_pages, f"第{_cn_number(part.no)}部分",
                                   cursor)
            if part_page is None:
                raise ValueError(f"PDF 里找不到第{part.no}部分的分隔页")
            page_map[f"part{part.no}"] = part_page + 1
            cursor = part_page + 1
            for ch in part.chapters:
                page = _find_heading_page(
                    heading_lines, ch.title, cursor, total, 17,
                    required_text=f"第{ch.no}章", norm_pages=norm_pages)
                if page is None:
                    raise ValueError(f"PDF 里找不到第 {ch.no} 章 {ch.title}")
                page_map[ch.pdf_anchor] = page + 1
                cursor = page + 1

        for ch in book.chapters:
            start = page_map[ch.pdf_anchor] - 1
            next_starts = [page_map[c.pdf_anchor] - 1
                           for c in book.chapters if c.no > ch.no]
            end = min(next_starts) if next_starts else total
            for heading in ch.sections:
                page = _find_heading_page(
                    heading_lines, heading.title, start, end, 13, 18,
                    norm_pages=norm_pages)
                if page is None:
                    page = _find_page(norm_pages, heading.title, start, end)
                if page is None:
                    raise ValueError(
                        f"PDF 里找不到第 {ch.no} 章的小节「{heading.title}」")
                page_map[heading.id] = page + 1

            for fig in ch.figures:
                page = _find_heading_page(
                    heading_lines, fig.label, start, end, 8, 9.6,
                    norm_pages=norm_pages)
                if page is None:
                    page = _find_page(norm_pages, fig.label, start, end)
                if page is None:
                    raise ValueError(
                        f"PDF 里找不到第 {ch.no} 章的插图「{fig.label}」")
                page_map[f"fig-{fig.id}"] = page + 1

            for table in ch.tables:
                page = _find_heading_page(
                    heading_lines, table.label, start, end, 8, 9.6,
                    norm_pages=norm_pages)
                if page is None:
                    page = _find_page(norm_pages, table.label, start, end)
                if page is None:
                    raise ValueError(
                        f"PDF 里找不到第 {ch.no} 章的表格「{table.label}」")
                page_map[f"tab-{table.id}"] = page + 1
        return page_map
    finally:
        doc.close()


def add_pdf_structure(pdf_path, book, page_map):
    import fitz
    doc = fitz.open(str(pdf_path))
    try:
        toc = [[1, "封面", 1]]
        if "preface" in page_map:
            toc.append([1, "前言", page_map["preface"]])
        if "toc" in page_map:
            toc.append([1, "目录", page_map["toc"]])
        for key, title in (("figures-list", "插图目录"), ("tables-list", "表格目录")):
            if key in page_map:
                toc.append([1, title, page_map[key]])
        for part in book.parts:
            toc.append([1, f"第{_cn_number(part.no)}部分 {part.title}",
                        page_map[f"part{part.no}"]])
            for ch in part.chapters:
                toc.append([2, f"第 {ch.no} 章 {ch.title}",
                            page_map[ch.pdf_anchor]])
                for heading in ch.sections:
                    toc.append([3, heading.title, page_map[heading.id]])
        doc.set_toc(toc)
        today = datetime.date.today().isoformat()
        doc.set_metadata({
            "title": BOOK_TITLE,
            "author": BOOK_AUTHOR,
            "subject": BOOK_SUBTITLE,
            "keywords": "微信小程序, 小程序开发, 云开发, 前端教程",
            "creator": "tools/export_book.py",
            "producer": "Microsoft Edge + PyMuPDF",
            "creationDate": f"D:{today.replace('-', '')}000000Z",
            "modDate": f"D:{today.replace('-', '')}000000Z",
        })
        tmp = pdf_path.with_name(pdf_path.stem + "-structured.pdf")
        if tmp.exists():
            tmp.unlink()
        doc.save(str(tmp), garbage=3, deflate=True)
    finally:
        doc.close()
    shutil.move(tmp, pdf_path)
    return len(toc)


def build_pdf(book, out_dir):
    """三遍打印：测页码 → 回填目录 → 校验分页稳定 → 写书签与元数据。"""
    out_dir.mkdir(parents=True, exist_ok=True)
    cover_path = out_dir / "cover.png"
    build_cover_png(cover_path)
    gif_cache = out_dir / "gif-frames"
    base_html = build_pdf_html(book, cover_path, gif_cache)
    html_path = out_dir / "book.html"
    final_pdf = out_dir / f"{BOOK_TITLE}.pdf"

    page_map = {}
    for attempt in range(1, 4):
        if page_map:
            html_path.write_text(
                fill_toc_page_numbers(base_html, page_map), encoding="utf-8")
        else:
            html_path.write_text(base_html, encoding="utf-8")
        pass_pdf = out_dir / f"book-pass{attempt}.pdf"
        print(f"PDF 第 {attempt} 遍打印…")
        print_pdf(html_path, pass_pdf)
        new_map = locate_pdf_pages(pass_pdf, book)
        if page_map and new_map == page_map:
            shutil.move(pass_pdf, final_pdf)
            bookmarks = add_pdf_structure(final_pdf, book, page_map)
            for old in out_dir.glob("book-pass*.pdf"):
                old.unlink()
            import fitz
            with fitz.open(str(final_pdf)) as doc:
                pages = doc.page_count
            print(f"PDF: {final_pdf}（{pages} 页，{bookmarks} 条书签）")
            return final_pdf
        page_map = new_map
    raise SystemExit("目录页码在 3 遍打印后仍不稳定，请检查会动态变高的内容")


def _epub_wrap(title, body, epub_type=None):
    section_attr = f' epub:type="{epub_type}"' if epub_type else ""
    return f"""<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops"
      xml:lang="zh-CN" lang="zh-CN">
<head><meta charset="utf-8"/><title>{_e(title)}</title>
<link rel="stylesheet" type="text/css" href="style.css"/></head>
<body><section{section_attr}>{body}</section></body></html>"""


def _epub_part_body(part):
    return f"""<div class="part-page">
<p class="part-kicker">PART {part.no:02d}</p>
<p class="part-no">第{_cn_number(part.no)}部分</p>
<h1 class="part-title">{_e(part.title)}</h1>
<p class="part-desc">{_e(part.description)}</p>
<p class="part-count">本部分共 {len(part.chapters)} 章</p>
</div>"""


def _epub_chapter_html(ch, book, body):
    header = f"""<header class="chapter-head">
<p class="chapter-part">{_e(ch.part_title)}</p>
<p class="chapter-no">第 {ch.no} 章</p>
<h1 class="chapter-title">{_e(ch.title)}</h1>
<p class="chapter-desc">{_e(ch.description)}</p>
<p class="chapter-meta">{_e(_meta_line(ch))}</p>
</header>"""
    xhtml = _epub_wrap(f"第 {ch.no} 章 {ch.title}", f"{header}{body}", "chapter")
    ElementTree.fromstring(xhtml)
    return xhtml


def _epub_list_body(book, items):
    rows = "".join(
        f'<li><a href="ch{item.chapter_no:02d}.xhtml#{item.id}">'
        f"{item.label}　{_e(item.caption)}</a></li>" for item in items)
    return f'<ol class="figure-list">{rows}</ol>'


def _epub_nav_html(book):
    parts = []
    for part in book.parts:
        chapters = []
        for ch in part.chapters:
            sections = "".join(
                f'<li><a href="{ch.epub_file}#{h.id}">{_e(h.title)}</a></li>'
                for h in ch.sections)
            chapters.append(
                f'<li><a href="{ch.epub_file}">{ch.no}. {_e(ch.title)}</a>'
                f'<ol>{sections}</ol></li>')
        parts.append(
            f'<li><a href="part{part.no:02d}.xhtml">{_e(part.title)}</a>'
            f'<ol>{"".join(chapters)}</ol></li>')
    lists = ('<li><a href="figures.xhtml">插图目录</a></li>'
             '<li><a href="tables.xhtml">表格目录</a></li>')
    body = f"""<nav epub:type="toc" id="toc"><h1>目录</h1><ol>{''.join(parts)}{lists}</ol></nav>
<nav epub:type="landmarks" id="landmarks" hidden="hidden"><h2>导航</h2><ol>
<li><a epub:type="cover" href="cover.xhtml">封面</a></li>
<li><a epub:type="toc" href="nav.xhtml">目录</a></li>
<li><a epub:type="loi" href="figures.xhtml">插图目录</a></li>
<li><a epub:type="lot" href="tables.xhtml">表格目录</a></li>
<li><a epub:type="bodymatter" href="part01.xhtml">正文</a></li>
</ol></nav>"""
    xhtml = _epub_wrap("目录", body)
    ElementTree.fromstring(xhtml)
    return xhtml


def _add_image_sizes(html_text, image_paths):
    from PIL import Image

    def repl(m):
        tag, src = m.group(0), m.group(1)
        if "width=" in tag:
            return tag
        src_path = image_paths.get(src)
        if src_path is None:
            return tag
        try:
            with Image.open(src_path) as im:
                width, height = im.size
        except Exception:
            return tag
        return tag.replace(f'src="{src}"',
                           f'src="{src}" width="{width}" height="{height}"', 1)

    return re.sub(r'<img\b[^>]*\bsrc="([^"]+)"[^>]*>', repl, html_text)


EPUB_CSS = """html { font-size: 100%; }
body { font-family: "Source Han Serif SC", "Noto Serif CJK SC", "Songti SC", SimSun, serif;
       line-height: 1.75; margin: 0 4%; color: #1f2421; background: transparent; }
a { color: #0b7a45; text-decoration: none; }
p { margin: 0.45em 0; text-indent: 2em; }
h2 { font-family: "Microsoft YaHei", "PingFang SC", sans-serif; font-size: 1.25em;
     line-height: 1.4; margin: 1.6em 0 0.5em; padding-left: 0.4em;
     border-left: 4px solid #07c160; page-break-after: avoid; }
h3 { font-family: "Microsoft YaHei", "PingFang SC", sans-serif; font-size: 1.08em;
     margin: 1.2em 0 0.4em; page-break-after: avoid; }
ul, ol { margin: 0.6em 0 0.8em; padding-left: 1.4em; }
li { margin: 0.2em 0; }
li p, blockquote p, .qa p, .video-note p, figcaption { text-indent: 0; }
code { font-family: "Cascadia Mono", Consolas, "Courier New", monospace;
       font-size: 0.88em; background: #f2f5f3; padding: 0 0.15em; border-radius: 2px; }
pre { font-family: "Cascadia Mono", Consolas, "Courier New", monospace;
      font-size: 0.82em; line-height: 1.5; background: #f7f9f8;
      border-left: 3px solid #07c160; padding: 0.6em 0.8em; margin: 0.8em 0;
      white-space: pre-wrap; word-wrap: break-word; page-break-inside: avoid; }
pre code { background: none; padding: 0; font-size: inherit; }
blockquote { margin: 0.8em 0; padding: 0.4em 0.8em; border-left: 3px solid #ffd666;
             background: #fffdf2; color: #4d4d4d; }
.video-note { margin: 0.8em 0; padding: 0.4em 0.8em; border-left: 3px solid #ffd666;
              background: #fffdf2; font-size: 0.92em; }
.qa { margin: 0.9em 0; padding: 0.5em 0.8em; border-left: 3px solid #07c160;
      background: #f5fbf7; font-size: 0.95em; page-break-inside: avoid; }
.qa-label { font-family: "Microsoft YaHei", "PingFang SC", sans-serif;
            font-weight: bold; color: #0b7a45; margin-bottom: 0.2em; }
table { width: 100%; border-collapse: collapse; font-size: 0.85em; margin: 0.8em 0; }
th, td { border: 1px solid #d5ddd8; padding: 0.3em 0.5em; text-align: left;
         vertical-align: top; }
th { background: #eef8f2; font-family: "Microsoft YaHei", "PingFang SC", sans-serif; }
figure { margin: 1em 0; text-align: center; page-break-inside: avoid; }
img { max-width: 100%; height: auto; }
figcaption { font-size: 0.82em; color: #555; margin-top: 0.3em; }
.fig-label, .table-label { font-family: "Microsoft YaHei", "PingFang SC", sans-serif;
                           font-weight: bold; color: #0b7a45; }
.table-block { margin: 0.8em 0; }
.table-caption { font-size: 0.82em; color: #555; text-align: center; }
.table-block table { margin: 0.3em 0 0; }
.figure-list { padding-left: 1.4em; }
.figure-list li { margin: 0.35em 0; }
hr { border: none; border-top: 1px solid #d5ddd8; margin: 1.2em 0; }
.front { margin: 10% 6%; }
.front-title { font-family: "Microsoft YaHei", "PingFang SC", sans-serif;
               font-size: 1.6em; margin: 0 0 0.8em; padding-bottom: 0.4em;
               border-bottom: 2px solid #07c160; }
.book-title { font-family: "Microsoft YaHei", "PingFang SC", sans-serif;
              font-size: 2.2em; text-align: center; margin: 1em 0 0.4em; }
.book-subtitle { text-align: center; color: #555; }
.title-top, .title-author, .title-edition, .title-url { text-align: center; }
.title-top { color: #0b7a45; letter-spacing: 0.15em; }
.title-line { width: 30%; height: 3px; background: #07c160; margin: 1.4em auto; }
.meta-list { display: grid; grid-template-columns: 5em 1fr; row-gap: 0.5em; }
.meta-list dt { color: #777; }
.meta-list dd { margin: 0; }
.howto-parts { padding-left: 1.4em; }
.howto-parts li { margin: 0.5em 0; }
.part-page { margin: 22% 6% 0; }
.part-kicker, .part-no { font-family: "Microsoft YaHei", "PingFang SC", sans-serif;
                         color: #0b7a45; }
.part-kicker { font-size: 0.85em; letter-spacing: 0.2em; }
.part-no { font-weight: bold; }
.part-title { font-family: "Microsoft YaHei", "PingFang SC", sans-serif;
              font-size: 2em; line-height: 1.3; }
.part-desc { color: #555; font-size: 1.05em; }
.part-count { color: #888; font-size: 0.85em; border-top: 1px solid #d8e8de;
              padding-top: 0.6em; }
.chapter-head { margin: 0 0 1.5em; }
.chapter-part { font-family: "Microsoft YaHei", "PingFang SC", sans-serif;
                color: #0b7a45; font-size: 0.85em; letter-spacing: 0.08em; }
.chapter-no { font-family: "Microsoft YaHei", "PingFang SC", sans-serif;
              color: #07a05a; font-weight: bold; font-size: 0.9em;
              letter-spacing: 0.1em; }
.chapter-title { font-family: "Microsoft YaHei", "PingFang SC", sans-serif;
                 font-size: 1.6em; line-height: 1.3; margin: 0.2em 0 0.5em; }
.chapter-desc { color: #555; }
.chapter-meta { color: #777; font-size: 0.85em; border-top: 1px solid #d8e8de;
                border-bottom: 1px solid #d8e8de; padding: 0.4em 0; }
.cover { margin: 0; padding: 0; text-align: center; }
.cover img { max-width: 100%; max-height: 100%; }
@media (prefers-color-scheme: dark) {
  body { color: #ddd; }
  a { color: #6fd39a; }
  blockquote, .video-note { background: #221f16; border-color: #b58a2a; color: #ddd; }
  .qa { background: #16231c; border-color: #07c160; }
  code, pre { background: #1d2420; color: #e6e6e6; }
  th { background: #1d2b23; }
  th, td { border-color: #3a4a40; }
  .chapter-desc, .chapter-meta, figcaption, .part-desc, .part-count { color: #aaa; }
  .chapter-meta, .part-count { border-color: #3a4a40; }
}"""


def build_epub(book, out_dir):
    """手写 EPUB 3：固定 mimetype、三级 nav、landmarks、封面与元数据。"""
    out_dir.mkdir(parents=True, exist_ok=True)
    cover_path = out_dir / "cover.png"
    build_cover_png(cover_path)

    book_uuid = uuid.uuid5(uuid.NAMESPACE_URL, BOOK_URL)
    today = datetime.date.today().isoformat()
    modified = datetime.datetime.now(datetime.timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ")

    manifest, spine, files = [], [], {}
    image_registry = {}
    image_paths = {}

    def add_manifest(item_id, href, media_type, properties=""):
        prop = f' properties="{properties}"' if properties else ""
        manifest.append(
            f'<item id="{item_id}" href="{href}" media-type="{media_type}"{prop}/>')

    add_manifest("cover-img", "images/cover.png", "image/png", "cover-image")
    add_manifest("css", "style.css", "text/css")
    add_manifest("nav", "nav.xhtml", "application/xhtml+xml", "nav")
    files["images/cover.png"] = cover_path.read_bytes()
    files["style.css"] = EPUB_CSS

    def add_doc(item_id, filename, title, body, epub_type=None):
        xhtml = _epub_wrap(title, body, epub_type)
        ElementTree.fromstring(xhtml)
        files[filename] = xhtml
        add_manifest(item_id, filename, "application/xhtml+xml")
        spine.append(item_id)

    add_doc("cover", "cover.xhtml", "封面",
            '<img src="images/cover.png" alt="封面" />', "cover")
    add_doc("title", "title.xhtml", BOOK_TITLE, _title_section())
    add_doc("copyright", "copyright.xhtml", "图书信息", _copyright_section())
    add_doc("preface", "preface.xhtml", "前言", _preface_section(book))
    add_doc("howto", "howto.xhtml", "如何使用本书", _howto_section(book))
    files["nav.xhtml"] = _epub_nav_html(book)
    spine.append("nav")
    add_doc("figures", "figures.xhtml", "插图目录",
            f"<h1>插图目录</h1>{_epub_list_body(book, book.figures)}", "loi")
    add_doc("tables", "tables.xhtml", "表格目录",
            f"<h1>表格目录</h1>{_epub_list_body(book, book.tables)}", "lot")

    for part in book.parts:
        part_id = f"part{part.no:02d}"
        add_doc(part_id, f"{part_id}.xhtml", part.title,
                _epub_part_body(part), "part")
        for ch in part.chapters:
            sink = {}
            body = render_chapter_body(
                ch, book, "epub", image_sink=sink,
                image_prefix=f"ch{ch.no:02d}-")
            for placeholder, src in sink.items():
                if src not in image_registry:
                    arc = f"images/bookimg-{len(image_registry) + 1}{src.suffix.lower()}"
                    image_registry[src] = arc
                    image_paths[arc] = src
                    media = mimetypes.guess_type(src.name)[0] or "application/octet-stream"
                    add_manifest(f"img{len(image_registry)}", arc, media)
                    files[arc] = src.read_bytes()
                body = body.replace(f'src="{placeholder}"',
                                    f'src="{image_registry[src]}"')
            body = _add_image_sizes(body, image_paths)
            ch_id = f"ch{ch.no:02d}"
            files[f"{ch_id}.xhtml"] = _epub_chapter_html(ch, book, body)
            add_manifest(ch_id, f"{ch_id}.xhtml", "application/xhtml+xml")
            spine.append(ch_id)

    opf = f"""<?xml version="1.0" encoding="utf-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0"
         unique-identifier="bookid" xml:lang="zh-CN">
<metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
<dc:identifier id="bookid">urn:uuid:{book_uuid}</dc:identifier>
<dc:title>{_e(BOOK_TITLE)}</dc:title>
<dc:creator>{_e(BOOK_AUTHOR)}</dc:creator>
<dc:language>zh-CN</dc:language>
<dc:publisher>开源共建</dc:publisher>
<dc:date>{today}</dc:date>
<dc:rights>{_e(BOOK_RIGHTS)}</dc:rights>
<dc:description>{_e(BOOK_SUBTITLE)}</dc:description>
<dc:source>{_e(BOOK_URL)}</dc:source>
<dc:subject>微信小程序</dc:subject>
<dc:subject>小程序开发</dc:subject>
<dc:subject>云开发</dc:subject>
<dc:subject>前端教程</dc:subject>
<meta property="dcterms:modified">{modified}</meta>
<meta name="cover" content="cover-img"/>
</metadata>
<manifest>
{chr(10).join(manifest)}
</manifest>
<spine>
{chr(10).join(f'<itemref idref="{item}"/>' for item in spine)}
</spine>
</package>"""
    ElementTree.fromstring(opf)
    files["OEBPS/content.opf"] = opf
    files["META-INF/container.xml"] = """<?xml version="1.0" encoding="utf-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
<rootfiles><rootfile full-path="OEBPS/content.opf"
 media-type="application/oebps-package+xml"/></rootfiles>
</container>"""
    ElementTree.fromstring(files["META-INF/container.xml"])

    epub_path = out_dir / f"{BOOK_TITLE}.epub"
    with zipfile.ZipFile(epub_path, "w") as z:
        z.writestr(zipfile.ZipInfo("mimetype"), "application/epub+zip",
                   zipfile.ZIP_STORED)
        z.writestr("META-INF/container.xml", files.pop("META-INF/container.xml"),
                   zipfile.ZIP_DEFLATED)
        z.writestr("OEBPS/content.opf", files.pop("OEBPS/content.opf"),
                   zipfile.ZIP_DEFLATED)
        for name, data in files.items():
            z.writestr(f"OEBPS/{name}", data, zipfile.ZIP_DEFLATED)
    print(f"EPUB: {epub_path}（{epub_path.stat().st_size // 1024} KB，"
          f"{len(book.chapters)} 章 + {len(image_registry)} 图）")
    return epub_path


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf-only", action="store_true")
    ap.add_argument("--epub-only", action="store_true")
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    book = collect_book()
    print(f"共 {len(book.chapters)} 章，{len(book.parts)} 个部分，输出目录 {OUT}")
    if not args.epub_only:
        build_pdf(book, OUT)
    if not args.pdf_only:
        build_epub(book, OUT)


if __name__ == "__main__":
    main()
