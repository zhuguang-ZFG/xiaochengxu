# -*- coding: utf-8 -*-
"""把知识库导出为本地 PDF 与 EPUB（tools/export_book.py）。

为什么有这个脚本：仓库是按网页阅读组织的（每篇一个 Markdown + 相对链接 +
外挂视频），但读者常想要一本「能带走」的书——离线、顺序阅读、可标注。
本脚本把 32 篇文档按教学顺序合并成一本电子书，产物只落在本地 `dist/book/`
（已 gitignore：电子书是构建产物，不进版本库；源文件才是唯一的真）。

两种产物：
- PDF：先用 markdown 库把每章转 HTML、拼成一整本（带封面/目录/章节样式），
  再调 Edge 无头模式打印。Chromium 打印不生成 PDF 大纲，所以打完再用
  PyMuPDF 把「章 → 节」两级书签写进文件——没有书签的 240 页 PDF 基本没法翻。
- EPUB 3：手写打包（mimetype + container.xml + OPF + 每章一个 XHTML），
  nav 目录做成两级（章内含小节锚点），不依赖 calibre/ebook-convert。

用法：
  python tools/export_book.py               # PDF + EPUB 都生成
  python tools/export_book.py --pdf-only    # 只要 PDF
  python tools/export_book.py --epub-only   # 只要 EPUB

依赖：`pip install markdown pymupdf`；PDF 另需本机 Edge（路径可用环境变量
EDGE_PATH 覆盖）。
"""
import argparse
import datetime
import pathlib
import re
import shutil
import subprocess
import sys
import uuid
import zipfile
from xml.etree import ElementTree

import markdown

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
    DOCS / "04-云开发", DOCS / "05-发布", DOCS / "06-实战", DOCS / "07-资源",
]

MD_EXTENSIONS = ["extra", "sane_lists", "admonition"]


def collect_chapters():
    """按教学顺序收集章节：(序号, md路径, 元数据dict)。"""
    chapters = []
    for d in CHAPTER_DIRS:
        for f in sorted(d.glob("*.md")):
            m = re.match(r"^(\d\d)-", f.name)
            if not m:
                continue  # _契约.md 之类非教学文件不进书
            meta = parse_front_matter(f.read_text(encoding="utf-8"))
            chapters.append((len(chapters) + 1, f, meta))
    return chapters


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


def md_to_html(md_text, expand_details=True):
    """Markdown → HTML。三处预处理：

    - mermaid 围栏浏览器画不了，替换成一行说明；
    - 测验的 <details> 是原始 HTML 块，块内默认不跑 markdown——答案里的
      `**B**.` 不加粗、`<text>` 会被当成真标签（良构 XML 直接报错）。
      所以把每个 details 块抠出来，内层单独过一遍 markdown 再拼回去；
    - 电子书没有「点击展开」，details 在打印/EPUB 里默认收起＝答案丢失，
      默认展开为带边框的答案块。
    """
    md_text = re.sub(
        r"```mermaid\n.*?\n```",
        "> 注：此处是一张 Mermaid 流程图，网页版与仓库中可看到渲染结果，电子书版以文字步骤为准。",
        md_text, flags=re.S)

    def _details(m):
        inner = markdown.markdown(m.group(2).strip(), extensions=MD_EXTENSIONS)
        if expand_details:
            return (f'<div class="qa"><div class="qa-label">{m.group(1)}</div>\n'
                    f'{inner}\n</div>')
        return f'<details><summary>{m.group(1)}</summary>\n{inner}\n</details>'

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


def fix_image_srcs(html, md_path, to_uri, gif_cache=None):
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
        key = f"img-{len(resolved) + 1}{target.suffix.lower()}"
        resolved[key] = target
        return m.group(1) + key + m.group(3)

    return re.sub(r'(<img[^>]*?\bsrc=")([^"]+)(")', repl, html), resolved


def _norm(s):
    """书签定位用：去掉空白与行内代码记号，拿 PDF 提取文本做包含匹配。"""
    return re.sub(r"[\s`*]+", "", s)


def _h2_sections(raw_md):
    return re.findall(r"^## (.+)$", raw_md, re.M)


def add_pdf_outline(pdf_path, chapters):
    """把「章 → 节」两级书签写进 PDF。

    Chromium --print-to-pdf 不产大纲；逐页提取文本做定位（标题若因折行
    断开，空白归一化后仍能命中）。页码随章节游标单调递增，同名小节
    （如「验证」「随堂测验」每章都有）不会串章。
    """
    import fitz
    doc = fitz.open(str(pdf_path))
    norm_pages = [_norm(doc[i].get_text()) for i in range(doc.page_count)]
    toc = [[1, "封面", 1]]
    toc.append([1, "目录", next((i + 1 for i, t in enumerate(norm_pages) if "目录" in t[:60]), 2)])
    starts, cursor = [], 0
    for no, _title, _sec in chapters:
        marker = _norm(f"第{no}章")
        start = next(i for i in range(cursor, doc.page_count) if marker in norm_pages[i])
        starts.append(start)
        cursor = start + 1
    bounds = starts[1:] + [doc.page_count]
    for (no, title, sections), start, nxt in zip(chapters, starts, bounds):
        toc.append([1, f"第 {no} 章 {title}", start + 1])
        for sec in sections:
            pg = next((i for i in range(start, nxt) if _norm(sec) in norm_pages[i]), None)
            if pg is not None:
                toc.append([2, sec.replace("`", ""), pg + 1])
    doc.set_toc(toc)
    tmp = pdf_path.with_name(pdf_path.stem + "-toc.pdf")
    doc.save(str(tmp), garbage=3, deflate=True)
    doc.close()
    shutil.move(tmp, pdf_path)
    print(f"书签: {len(toc)} 条（{len(chapters)} 章 + {len(toc) - len(chapters) - 2} 节）")


CHAPTER_TMPL = """<div class="chapter">
<div class="chapter-no">第 {no} 章</div>
<h1>{title}</h1>
<div class="chapter-meta">{category} · 难度 {difficulty} · 约 {reading_time}</div>
{body}
</div>"""


def build_pdf(chapters, out_dir):
    """拼单页 HTML → Edge 无头打印 PDF → 写两级书签。"""
    parts, ch_meta = [], []
    gif_cache = out_dir / "gif-frames"
    for no, f, meta in chapters:
        raw = strip_front_matter(f.read_text(encoding="utf-8"))
        html, _ = fix_image_srcs(md_to_html(raw), f, to_uri=True, gif_cache=gif_cache)
        ch_meta.append((no, meta.get("title", f.stem), _h2_sections(raw)))
        parts.append(CHAPTER_TMPL.format(
            no=no, title=meta.get("title", f.stem), body=html,
            category=meta.get("category", ""), difficulty=meta.get("difficulty", ""),
            reading_time=meta.get("reading_time", "")))
    today = datetime.date.today().isoformat()
    html_doc = f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8"><title>{BOOK_TITLE}</title>
<style>
@page {{ size: A4; margin: 18mm 16mm; }}
body {{ font-family: "Microsoft YaHei", "PingFang SC", "Noto Sans CJK SC", sans-serif;
       font-size: 10.5pt; line-height: 1.75; color: #1a1a1a; }}
.cover {{ page-break-after: always; text-align: center; padding-top: 60mm; }}
.cover h1 {{ font-size: 30pt; margin: 0 0 6mm; }}
.cover .sub {{ font-size: 14pt; color: #555; margin-bottom: 14mm; }}
.cover img {{ max-width: 82%; }}
.cover .meta {{ margin-top: 16mm; color: #777; font-size: 10pt; }}
.toc {{ page-break-after: always; }}
.toc h2 {{ font-size: 16pt; border-bottom: 2px solid #07c160; padding-bottom: 2mm; }}
.toc ol {{ line-height: 1.75; columns: 2; column-gap: 10mm; }}
.chapter {{ page-break-before: always; }}
.chapter-no {{ color: #07c160; font-weight: bold; letter-spacing: 2px; }}
.chapter-meta {{ color: #888; font-size: 9pt; margin-bottom: 6mm; }}
h1 {{ font-size: 19pt; margin: 1mm 0 2mm; }}
h2 {{ font-size: 14.5pt; margin-top: 8mm; border-left: 4px solid #07c160; padding-left: 3mm; }}
h3 {{ font-size: 12pt; margin-top: 6mm; }}
.qa {{ border: 1px dashed #bbb; background: #fbfbf6; border-radius: 4px;
       padding: 2mm 4mm; margin: 3mm 0; }}
.qa-label {{ font-weight: bold; color: #07a05a; }}
code {{ font-family: Consolas, "Courier New", monospace; background: #f4f4f4;
        padding: 0 3px; border-radius: 3px; font-size: 9pt; }}
pre {{ background: #f7f7f7; border: 1px solid #e3e3e3; border-radius: 6px;
       padding: 8px 10px; overflow-x: hidden; white-space: pre-wrap; }}
pre code {{ background: none; padding: 0; }}
blockquote {{ border-left: 4px solid #ffd666; background: #fffdf2;
              margin: 4mm 0; padding: 2mm 4mm; color: #555; }}
table {{ border-collapse: collapse; width: 100%; font-size: 9.5pt; }}
th, td {{ border: 1px solid #ddd; padding: 3px 6px; text-align: left; }}
th {{ background: #f2fbf5; }}
img {{ max-width: 100%; max-height: 84mm; }}
.qa {{ page-break-inside: avoid; }}
</style></head><body>
<div class="cover">
<h1>{BOOK_TITLE}</h1>
<div class="sub">{BOOK_SUBTITLE}</div>
<img src="{(DOCS / "assets" / "hero-knowledge.png").resolve().as_uri()}" alt="hero">
<div class="meta">开源共建 · {BOOK_URL}<br>导出于 {today}</div>
</div>
<div class="toc"><h2>目录</h2><ol>
{''.join(f'<li>{m.get("title", f.stem)}</li>' for _, f, m in chapters)}
</ol></div>
{''.join(parts)}
</body></html>"""

    html_path = out_dir / "book.html"
    html_path.write_text(html_doc, encoding="utf-8")
    edge = shutil.which("msedge") or pathlib.Path(
        "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe")
    if not pathlib.Path(edge).is_file():
        raise SystemExit("找不到 Edge，无法打印 PDF（可用环境变量 EDGE_PATH 指定路径）")
    edge = str(pathlib.Path(edge))
    tmp_pdf = out_dir / "book-tmp.pdf"
    final_pdf = out_dir / f"{BOOK_TITLE}.pdf"
    cmd = [edge, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
           f"--print-to-pdf={tmp_pdf}", html_path.resolve().as_uri()]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if not tmp_pdf.is_file() or tmp_pdf.stat().st_size < 50_000:
        raise SystemExit(f"PDF 打印失败：{r.stderr[-500:] if r.stderr else r.stdout[-500:]}")
    shutil.move(tmp_pdf, final_pdf)
    add_pdf_outline(final_pdf, ch_meta)
    print(f"PDF: {final_pdf}（{final_pdf.stat().st_size // 1024} KB）")


XHTML_TMPL = """<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops">
<head><title>{title}</title><link rel="stylesheet" type="text/css" href="style.css"/></head>
<body>
<section epub:type="chapter">
<div class="chapter-no">第 {no} 章</div>
<h1>{title}</h1>
<div class="chapter-meta">{category} · 难度 {difficulty} · 约 {reading_time}</div>
{body}
</section>
</body></html>"""


def build_epub(chapters, out_dir):
    """手写 EPUB 3 包：mimetype 先写且不压缩（规范要求）。"""
    book_uuid = uuid.uuid5(uuid.NAMESPACE_URL, BOOK_URL)
    today = datetime.date.today().isoformat()

    manifest, spine, nav_lis, files = [], [], [], {}
    img_registry = {}  # 源绝对路径 → epub 内文件名（跨章去重）

    def register_images(resolved):
        out = {}
        for name, src in resolved.items():
            if src not in img_registry:
                img_registry[src] = f"images/bookimg-{len(img_registry) + 1}{src.suffix.lower()}"
            out[name] = img_registry[src]
        return out

    for no, f, meta in chapters:
        raw = strip_front_matter(f.read_text(encoding="utf-8"))
        html, resolved = fix_image_srcs(md_to_html(raw), f, to_uri=False)
        for old, new in register_images(resolved).items():
            html = re.sub(rf'src="{re.escape(old)}"', f'src="{new}"', html)
        # 小节锚点 + 两级目录：每章的 h2 依次挂 id，nav 里嵌一层 ol
        sec_ids = []

        def _id_h2(m):
            sec_ids.append(m.group(1))
            return f'<h2 id="s{len(sec_ids) - 1}">{m.group(1)}</h2>'

        html = re.sub(r"<h2>(.*?)</h2>", _id_h2, html)
        title = meta.get("title", f.stem)
        xhtml = XHTML_TMPL.format(no=no, title=title, body=html,
                                  category=meta.get("category", ""),
                                  difficulty=meta.get("difficulty", ""),
                                  reading_time=meta.get("reading_time", ""))
        ElementTree.fromstring(xhtml)  # EPUB 内容文档必须是良构 XML，坏就当场报
        fname = f"ch{no:02d}.xhtml"
        files[fname] = xhtml
        manifest.append(f'<item id="ch{no:02d}" href="{fname}" media-type="application/xhtml+xml"/>')
        spine.append(f'<itemref idref="ch{no:02d}"/>')
        subs = "".join(f'<li><a href="{fname}#s{i}">{s.replace("`", "")}</a></li>'
                       for i, s in enumerate(sec_ids))
        nested = f"<ol>{subs}</ol>" if subs else ""
        nav_lis.append(f'<li><a href="{fname}">{no}. {title}</a>{nested}</li>')

    for src, arc in img_registry.items():
        files[arc] = src.read_bytes()
        media = {"png": "image/png", ".gif": "image/gif"}.get(
            src.suffix.lower().lstrip("."), "image/gif" if src.suffix.lower() == ".gif" else "image/png")
        manifest.append(f'<item id="i{arc.split("-")[-1].split(".")[0]}" href="{arc}" media-type="{media}"/>')

    files["style.css"] = CSS
    manifest.append('<item id="css" href="style.css" media-type="text/css"/>')
    files["nav.xhtml"] = NAV_TMPL.format(lis="\n".join(nav_lis))
    manifest.append('<item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>')

    hero = (DOCS / "assets" / "hero-knowledge.png").read_bytes()
    files["images/cover.png"] = hero
    manifest.append('<item id="cover-img" href="images/cover.png" media-type="image/png" properties="cover-image"/>')
    files["cover.xhtml"] = COVER_TMPL
    manifest.append('<item id="cover" href="cover.xhtml" media-type="application/xhtml+xml"/>')
    spine.insert(0, '<itemref idref="cover"/>')

    opf = OPF_TMPL.format(uuid=book_uuid, today=today,
                          manifest="\n".join(manifest), spine="\n".join(spine))

    epub_path = out_dir / f"{BOOK_TITLE}.epub"
    with zipfile.ZipFile(epub_path, "w") as z:
        z.writestr(zipfile.ZipInfo("mimetype"), "application/epub+zip", zipfile.ZIP_STORED)
        z.writestr("META-INF/container.xml", CONTAINER, zipfile.ZIP_DEFLATED)
        z.writestr("OEBPS/content.opf", opf, zipfile.ZIP_DEFLATED)
        for name, data in files.items():
            z.writestr(f"OEBPS/{name}", data, zipfile.ZIP_DEFLATED)
    print(f"EPUB: {epub_path}（{epub_path.stat().st_size // 1024} KB，{len(chapters)} 章 + {len(img_registry)} 图）")


CSS = """body { font-family: serif; line-height: 1.7; margin: 0.5em 1em; color: #1a1a1a; }
.chapter-no { color: #07c160; font-weight: bold; margin-top: 1.5em; }
.chapter-meta { color: #888; font-size: 0.85em; margin-bottom: 1em; }
.qa { border: 1px dashed #bbb; background: #fbfbf6; padding: 0.4em 0.8em; margin: 0.6em 0; }
.qa-label { font-weight: bold; color: #07a05a; }
h1 { font-size: 1.5em; margin: 0.2em 0 0.5em; }
h2 { font-size: 1.2em; border-left: 4px solid #07c160; padding-left: 0.4em; margin-top: 1.4em; }
code, pre { font-family: monospace; font-size: 0.85em; }
pre { background: #f7f7f7; border: 1px solid #e3e3e3; padding: 0.5em; white-space: pre-wrap; word-wrap: break-word; }
blockquote { border-left: 4px solid #ffd666; background: #fffdf2; margin: 0.8em 0; padding: 0.4em 0.8em; color: #555; }
table { border-collapse: collapse; width: 100%; font-size: 0.85em; }
th, td { border: 1px solid #ddd; padding: 3px 6px; text-align: left; }
img { max-width: 100%; }"""

NAV_TMPL = """<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops">
<head><title>目录</title></head>
<body><nav epub:type="toc" id="toc"><h2>目录</h2><ol>
{lis}
</ol></nav></body></html>"""

COVER_TMPL = """<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml">
<head><title>封面</title></head>
<body style="text-align:center; margin-top:6em;">
<h1>小程序开发之路</h1>
<p>从认识小程序到上线发布的原生开发教程</p>
<img src="images/cover.png" alt="cover" style="max-width:90%;"/>
<p style="color:#777;">开源共建 · https://github.com/zhuguang-ZFG/xiaochengxu</p>
</body></html>"""

OPF_TMPL = """<?xml version="1.0" encoding="utf-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="bookid">
<meta name="cover" content="cover-img"/>
<metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
<dc:identifier id="bookid">urn:uuid:{uuid}</dc:identifier>
<dc:title>{title}</dc:title>
<dc:creator>zhuguang-ZFG 与开源贡献者</dc:creator>
<dc:language>zh-CN</dc:language>
<dc:description>{subtitle}</dc:description>
<dc:source>{url}</dc:source>
<meta property="dcterms:modified">{today}T00:00:00Z</meta>
</metadata>
<manifest>
{manifest}
</manifest>
<spine>
{spine}
</spine>
</package>""".replace("{title}", BOOK_TITLE).replace("{subtitle}", BOOK_SUBTITLE).replace("{url}", BOOK_URL)

CONTAINER = """<?xml version="1.0" encoding="utf-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
<rootfiles><rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/></rootfiles>
</container>"""


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf-only", action="store_true")
    ap.add_argument("--epub-only", action="store_true")
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    chapters = collect_chapters()
    print(f"共 {len(chapters)} 章，输出目录 {OUT}")
    if not args.epub_only:
        build_pdf(chapters, OUT)
    if not args.pdf_only:
        build_epub(chapters, OUT)


if __name__ == "__main__":
    main()
