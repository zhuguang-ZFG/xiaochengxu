# -*- coding: utf-8 -*-
"""export_book.py 的自测（标准库 unittest + Pillow）。

守护的是「书稿层」的不变量：标题不重复、书内链接全部可跳、锚点能解析、
符号能打印、图有说明、封面可复现。EPUB 成品在临时目录真打一次包再校验结构；
PDF 成品校验需要本机 Edge 与 PyMuPDF（约 1 分钟），缺任意一项自动跳过。

用法：
    python tools/test_export_book.py
    python -m unittest discover -s tools -p "test_export_book.py"
"""
import hashlib
import io
import pathlib
import re
import sys
import tempfile
import unittest
import zipfile
from urllib.parse import unquote
from xml.etree import ElementTree

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import export_book as eb  # noqa: E402


class BookModelTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.book = eb.collect_book()

    def test_32_章按五部分组织(self):
        self.assertEqual(len(self.book.chapters), 32)
        self.assertEqual([len(p.chapters) for p in self.book.parts], [3, 4, 4, 12, 9])
        self.assertEqual([p.title for p in self.book.parts],
                         ["开始之前", "认知与准备", "基础", "进阶", "云开发、实战与发布"])

    def test_每章标题与_H1_一致(self):
        for ch in self.book.chapters:
            self.assertEqual(ch.title, ch.h1, ch.path.as_posix())

    def test_小节数量与层级(self):
        h2 = sum(1 for ch in self.book.chapters for h in ch.headings if h.level == 2)
        h3 = sum(1 for ch in self.book.chapters for h in ch.headings if h.level == 3)
        self.assertEqual((h2, h3), (342, 107))
        for ch in self.book.chapters:
            ids = [h.id for h in ch.headings]
            self.assertEqual(len(ids), len(set(ids)), f"{ch.path} 有重复 id")

    def test_32_个页内锚点全部能解析(self):
        count = 0
        for ch in self.book.chapters:
            raw = ch.path.read_text(encoding="utf-8")
            for frag in re.findall(r"\]\(#([^)]+)\)", raw):
                found = self.book.resolve_anchor(ch, frag)
                self.assertIsNotNone(found, f"{ch.path} 的锚点 #{frag} 无目标")
                count += 1
        self.assertEqual(count, 32)

    def test_章号与路径稳定(self):
        wxml = self.book.chapter_by_path(eb.DOCS / "02-基础" / "01-WXML数据绑定与渲染.md")
        self.assertEqual(wxml.no, 8)
        self.assertEqual(wxml.title, "WXML 数据绑定与渲染")


class SlugTest(unittest.TestCase):
    def test_空白转连字符并去掉标点(self):
        self.assertEqual(eb.slugify_heading("常见错误 / 避坑"), "常见错误--避坑")
        self.assertEqual(eb.slugify_heading("2.1 为什么是「临时链接」"), "21-为什么是临时链接")
        self.assertEqual(eb.slugify_heading("参数传递与返回值"), "参数传递与返回值")

    def test_兼容已写死的无连字符锚点(self):
        # 正文里已有的锚点是 #登录态wxlogin全流程（空白被直接删掉），
        # 解析时要能兼容，不能要求作者回头改链接。
        self.assertEqual(eb.normalize_anchor("登录态wxlogin全流程"),
                         eb.normalize_anchor("登录态：wx.login 全流程"))


class TextTransformTest(unittest.TestCase):
    def test_标题定位归一化忽略行内代码下划线(self):
        self.assertEqual(eb._norm("四、结果回调：`pay_cb` 云函数"),
                         eb._norm("四、结果回调：paycb 云函数"))
        self.assertEqual(eb._norm("第 **2** 章"), "第2章")

    def test_删除与标题重复的首个_H1(self):
        md = "# 标题\n\n正文\n\n# 另一个标题\n"
        self.assertEqual(eb.strip_duplicate_h1(md, "标题"),
                         "\n正文\n\n# 另一个标题\n")
        self.assertEqual(eb.strip_duplicate_h1(md, "不同"), md)

    def test_复选框转为可打印方框(self):
        self.assertEqual(eb.convert_checkboxes("- [ ] 未完成\n- [x] 已完成\n"),
                         "- □ 未完成\n- ■ 已完成\n")

    def test_表情符号转为字体画得出的字符(self):
        self.assertEqual(eb.replace_glyphs("📺 配套视频 ✅ ❌ ⚠️"),
                         "配套视频 √ × 注意：")

    def test_图片包成_figure_并保留_alt_作说明(self):
        html = '<p><img alt="知识图谱" src="x.png" /></p>'
        out = eb.wrap_figures(html)
        self.assertIn("<figure>", out)
        self.assertIn("<figcaption>知识图谱</figcaption>", out)
        self.assertNotIn("<p><img", out)

    def test_无_alt_的图不生成空说明(self):
        out = eb.wrap_figures('<p><img src="x.png" /></p>')
        self.assertIn("<figure>", out)
        self.assertNotIn("<figcaption>", out)

    def test_视频块只转换自己那一块(self):
        html = ('<blockquote>\n<p>一句话定义</p>\n</blockquote>\n'
                '<h2>中间小节</h2>\n'
                '<p>中间正文</p>\n'
                '<blockquote>\n<p>配套视频 · 第 2 集</p>\n</blockquote>\n')
        out = eb.promote_video_note(html)
        self.assertIn("<blockquote>\n<p>一句话定义</p>\n</blockquote>", out)
        self.assertIn('<div class="video-note"><p>配套视频 · 第 2 集</p></div>', out)
        self.assertIn("<h2>中间小节</h2>", out)
        self.assertEqual(out.count("<blockquote>"), 1)
        self.assertEqual(out.count("</blockquote>"), 1)

    def test_紧贴问句的选项列表补空行(self):
        md = "**Q1**: 问题？\n- [ ] A\n- [ ] B\n\n正文\n"
        self.assertEqual(eb.separate_lists(md),
                         "**Q1**: 问题？\n\n- [ ] A\n- [ ] B\n\n正文\n")
        # 已经是列表的缩进续行，不能被误拆成两个列表
        md2 = "- 第一项\n  续行\n- 第二项\n"
        self.assertEqual(eb.separate_lists(md2), md2)


class LinkRewriteTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.book = eb.collect_book()
        cls.ch = cls.book.chapter_by_path(eb.DOCS / "02-基础" / "01-WXML数据绑定与渲染.md")

    def test_跨章链接指向章首(self):
        href = eb.rewrite_href("../01-入门/03-项目结构.md", self.ch, self.book, "pdf")
        self.assertEqual(href, "#ch06")
        href = eb.rewrite_href("../01-入门/03-项目结构.md", self.ch, self.book, "epub")
        self.assertEqual(href, "ch06.xhtml")

    def test_页内锚点指向小节_id(self):
        ch24 = self.book.chapter_by_path(eb.DOCS / "04-云开发" / "01-云开发入门.md")
        frag = "常见错误--避坑"
        target = ch24.resolve_anchor(frag)
        self.assertIsNotNone(target)
        self.assertEqual(eb.rewrite_href(f"#{frag}", ch24, self.book, "pdf"),
                         f"#{target}")
        self.assertEqual(eb.rewrite_href(f"#{frag}", ch24, self.book, "epub"),
                         f"ch24.xhtml#{target}")

    def test_书外_markdown_链接改为仓库外链(self):
        href = eb.rewrite_href("../../README.md", self.ch, self.book, "pdf")
        self.assertEqual(href, f"{eb.BOOK_URL}/blob/main/README.md")

    def test_视频链接改为在线观看(self):
        href = eb.rewrite_href("../assets/videos/video-04-wxml.mp4", self.ch, self.book, "epub")
        self.assertEqual(href, f"{eb.BOOK_URL}/blob/main/docs/assets/videos/video-04-wxml.mp4")

    def test_外部链接原样保留(self):
        url = "https://developers.weixin.qq.com/miniprogram/dev/framework/"
        self.assertEqual(eb.rewrite_href(url, self.ch, self.book, "pdf"), url)

    def test_渲染后的正文没有_md_死链(self):
        html = eb.render_chapter_body(self.ch, self.book, "epub")
        self.assertNotRegex(html, r'href="[^"]*\.md(?:#[^"]*)?"')
        self.assertIn('href="ch06.xhtml"', html)


class ChapterRenderTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.book = eb.collect_book()
        cls.ch = cls.book.chapter_by_path(eb.DOCS / "02-基础" / "01-WXML数据绑定与渲染.md")
        cls.html = eb.render_chapter_body(cls.ch, cls.book, "pdf")

    def test_正文不再重复章节标题(self):
        self.assertNotIn("<h1", self.html)

    def test_小节挂上全书唯一_id(self):
        self.assertIn(f'id="{self.ch.sections[0].id}"', self.html)
        self.assertTrue(all(s.id.startswith("ch08-s") for s in self.ch.sections))

    def test_测验答案展开且不再有_details(self):
        self.assertNotIn("<details>", self.html)
        self.assertIn("参考答案", self.html)

    def test_视频引用变成纸质可读的提示块(self):
        self.assertIn('class="video-note"', self.html)
        self.assertIn("配套视频", self.html)

    def test_复选框与特殊符号已可打印(self):
        self.assertIn("□", self.html)
        for bad in ("📺", "✅", "❌", "⚠", "️"):
            self.assertNotIn(bad, self.html)

    def test_代码注释里的标记也已可打印(self):
        js = self.book.chapter_by_path(
            eb.DOCS / "02-基础" / "03-JS逻辑层与数据驱动.md")
        html = eb.render_chapter_body(js, self.book, "epub")
        for bad in ("✅", "❌"):
            self.assertNotIn(bad, html)
        self.assertIn("√", html)
        self.assertIn("×", html)

    def test_测验选项渲染成列表而不是并入问句(self):
        self.assertIn("<li>□ A.", self.html)
        self.assertNotIn(" - □ A.", self.html)
        self.assertNotIn(" - □ B.", self.html)

    def test_图片带说明且路径可用(self):
        self.assertIn("<figure>", self.html)
        self.assertIn("<figcaption>", self.html)


class TocFillTest(unittest.TestCase):
    def test_按_key_回填页码(self):
        html = ('<li><span data-toc-key="ch01">000</span></li>'
                '<li><span data-toc-key="ch02">000</span></li>')
        out = eb.fill_toc_page_numbers(html, {"ch01": 12, "ch02": 3})
        self.assertIn(">12<", out)
        self.assertIn(">3<", out)
        self.assertNotIn("000", out)

    def test_缺页码必须报错而不是留占位(self):
        with self.assertRaises(ValueError):
            eb.fill_toc_page_numbers('<span data-toc-key="ch09">000</span>', {})


class CoverTest(unittest.TestCase):
    def test_封面尺寸与可复现(self):
        with tempfile.TemporaryDirectory() as tmp:
            a = pathlib.Path(tmp) / "a.png"
            b = pathlib.Path(tmp) / "b.png"
            eb.build_cover_png(a, (600, 900))
            eb.build_cover_png(b, (600, 900))
            from PIL import Image
            with Image.open(a) as img:
                self.assertEqual(img.size, (600, 900))
            self.assertEqual(hashlib.md5(a.read_bytes()).hexdigest(),
                             hashlib.md5(b.read_bytes()).hexdigest())


XHTML = "{http://www.w3.org/1999/xhtml}"
OPS = "{http://www.idpf.org/2007/ops}"
OPF = "{http://www.idpf.org/2007/opf}"
DC = "{http://purl.org/dc/elements/1.1/}"


def _ol_depth(ol):
    lis = ol.findall(XHTML + "li")
    children = [sub for li in lis for sub in li.findall(XHTML + "ol")]
    return 1 + max((_ol_depth(sub) for sub in children), default=0)


class EpubBuildTest(unittest.TestCase):
    """真打一次 EPUB 包，校验成品而不是中间 HTML。"""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.book = eb.collect_book()
        cls.epub = eb.build_epub(cls.book, pathlib.Path(cls.tmp.name))
        cls.zf = zipfile.ZipFile(cls.epub)
        cls.names = cls.zf.namelist()
        cls.anchors = {}
        for name in cls.names:
            if not name.endswith(".xhtml"):
                continue
            root = ElementTree.fromstring(cls.zf.read(name))
            cls.anchors[name] = {el.get("id") for el in root.iter() if el.get("id")}

    @classmethod
    def tearDownClass(cls):
        cls.zf.close()
        cls.tmp.cleanup()

    def test_mimetype_首条且不压缩(self):
        first = self.zf.infolist()[0]
        self.assertEqual(first.filename, "mimetype")
        self.assertEqual(first.compress_type, zipfile.ZIP_STORED)
        self.assertEqual(self.zf.read("mimetype"), b"application/epub+zip")

    def test_全部_xml_格式合法(self):
        xml_files = [n for n in self.names
                     if n.endswith((".xhtml", ".opf", ".xml"))]
        self.assertGreaterEqual(len(xml_files), 43)
        for name in xml_files:
            ElementTree.fromstring(self.zf.read(name))

    def test_三级目录与_landmarks(self):
        root = ElementTree.fromstring(self.zf.read("OEBPS/nav.xhtml"))
        navs = {nav.get(OPS + "type"): nav for nav in root.iter(XHTML + "nav")}
        self.assertEqual(set(navs), {"toc", "landmarks"})
        self.assertEqual(_ol_depth(navs["toc"].find(XHTML + "ol")), 3)
        kinds = {a.get(OPS + "type") for a in navs["landmarks"].iter(XHTML + "a")}
        self.assertEqual(kinds, {"cover", "toc", "bodymatter"})

    def test_内部链接全部有目标(self):
        dead = []
        for name, ids in self.anchors.items():
            root = ElementTree.fromstring(self.zf.read(name))
            for a in root.iter(XHTML + "a"):
                href = a.get("href")
                if not href or re.match(r"^[a-z]+:", href):
                    continue
                path, _, frag = href.partition("#")
                target = f"OEBPS/{unquote(path)}" if path else name
                if path and target not in self.anchors:
                    dead.append((name, href, "文件不存在"))
                elif frag and unquote(frag) not in self.anchors.get(target, set()):
                    dead.append((name, href, "锚点不存在"))
        self.assertEqual(dead, [])

    def test_没有指向_md_的链接(self):
        bad = [a.get("href")
               for name in self.anchors
               for a in ElementTree.fromstring(self.zf.read(name)).iter(XHTML + "a")
               if not re.match(r"^[a-z]+:", a.get("href", ""))
               and re.search(r"\.md(?:#|$)", a.get("href", ""))]
        self.assertEqual(bad, [])

    def test_元数据与封面(self):
        root = ElementTree.fromstring(self.zf.read("OEBPS/content.opf"))
        meta = root.find(f".//{OPF}metadata")
        self.assertEqual(meta.findtext(f"{DC}title"), eb.BOOK_TITLE)
        self.assertEqual(meta.findtext(f"{DC}creator"), eb.BOOK_AUTHOR)
        self.assertEqual(meta.findtext(f"{DC}language"), "zh-CN")
        self.assertTrue(meta.findtext(f"{DC}identifier").startswith("urn:uuid:"))
        self.assertRegex(meta.findtext(f"{DC}date"), r"^\d{4}-\d{2}-\d{2}$")
        modified = [m for m in meta.findall(f"{OPF}meta")
                    if m.get("property") == "dcterms:modified"]
        self.assertEqual(len(modified), 1)
        cover = [item for item in root.findall(f".//{OPF}manifest/{OPF}item")
                 if "cover-image" in (item.get("properties") or "")]
        self.assertEqual([item.get("href") for item in cover], ["images/cover.png"])

    def test_清单与脊柱覆盖全书(self):
        root = ElementTree.fromstring(self.zf.read("OEBPS/content.opf"))
        manifest = {item.get("id"): item.get("href")
                    for item in root.findall(f".//{OPF}manifest/{OPF}item")}
        spine = [item.get("idref")
                 for item in root.findall(f".//{OPF}spine/{OPF}itemref")]
        self.assertEqual(spine[0], "cover")
        self.assertIn("nav", spine)
        self.assertEqual(spine[-1], f"ch{self.book.chapters[-1].no:02d}")
        self.assertEqual([i for i in spine if re.fullmatch(r"ch\d{2}", i)],
                         [f"ch{ch.no:02d}" for ch in self.book.chapters])
        for href in manifest.values():
            self.assertIn(f"OEBPS/{href}", self.names, f"清单项 {href} 未打包")
        listed = set(manifest.values())
        for name in self.names:
            if name.startswith("OEBPS/") and name.endswith(".xhtml"):
                self.assertIn(name[len("OEBPS/"):], listed, f"{name} 未进清单")

    def test_章节图片都有尺寸和文件(self):
        count = 0
        for ch in self.book.chapters:
            root = ElementTree.fromstring(
                self.zf.read(f"OEBPS/ch{ch.no:02d}.xhtml"))
            for img in root.iter(XHTML + "img"):
                count += 1
                src = img.get("src")
                self.assertTrue(img.get("width") and img.get("height"),
                                f"第 {ch.no} 章图片缺尺寸：{src}")
                self.assertIn(f"OEBPS/{src}", self.names)
        self.assertGreater(count, 60)


def _pdf_ready():
    """PDF 成品校验同时依赖 Edge 与 PyMuPDF；CI 有 Edge 但未装 PyMuPDF。"""
    if not eb.find_edge():
        return False
    try:
        import fitz  # noqa: F401
    except ImportError:
        return False
    return True


@unittest.skipUnless(_pdf_ready(), "未安装 Edge 或 PyMuPDF，跳过 PDF 成品校验")
class PdfBuildTest(unittest.TestCase):
    """真打一次 PDF（约 1 分钟），校验书签、目录页码与元数据。"""

    @classmethod
    def setUpClass(cls):
        import fitz
        cls.fitz = fitz
        cls.tmp = tempfile.TemporaryDirectory()
        cls.book = eb.collect_book()
        cls.pdf_path = eb.build_pdf(cls.book, pathlib.Path(cls.tmp.name))
        cls.doc = fitz.open(str(cls.pdf_path))
        cls.toc = cls.doc.get_toc()

    @classmethod
    def tearDownClass(cls):
        cls.doc.close()
        cls.tmp.cleanup()

    def test_页数与三级书签齐全(self):
        self.assertGreater(self.doc.page_count, 250)
        levels = {}
        for level, _, _ in self.toc:
            levels[level] = levels.get(level, 0) + 1
        self.assertEqual(levels, {1: 8, 2: 32, 3: 342})

    def test_书签页码落在范围内且逐章递增(self):
        self.assertTrue(all(1 <= page <= self.doc.page_count
                            for _, _, page in self.toc))
        chapter_pages = [page for level, _, page in self.toc if level == 2]
        self.assertTrue(all(a < b for a, b in zip(chapter_pages, chapter_pages[1:])))
        current = None
        for level, title, page in self.toc:
            if level == 2:
                current = page
            elif level == 3:
                self.assertGreaterEqual(page, current, f"小节「{title}」页码早于本章")

    def test_目录页码占位符已全部回填(self):
        toc_page = next(p for _, title, p in self.toc if title == "目录")
        body_page = next(p for level, title, p in self.toc
                         if level == 1 and title.startswith("第一部分"))
        self.assertLess(toc_page, body_page)
        for page_no in range(toc_page, body_page):
            text = self.doc[page_no - 1].get_text()
            self.assertNotRegex(text, r"(?<!\d)000(?!\d)",
                                f"第 {page_no} 页目录里还有占位符")

    def test_元数据与内部跳转(self):
        meta = self.doc.metadata
        self.assertEqual(meta.get("title"), eb.BOOK_TITLE)
        self.assertEqual(meta.get("author"), eb.BOOK_AUTHOR)
        internal = sum(
            1 for page in self.doc for link in page.get_links()
            if link.get("kind") in (self.fitz.LINK_GOTO, self.fitz.LINK_NAMED))
        self.assertGreater(internal, 300)


if __name__ == "__main__":
    unittest.main(verbosity=2)
