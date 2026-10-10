# -*- coding: utf-8 -*-
"""画面文字的自测：字幕折行 + 字形覆盖。

跑法：`python tools/test_gen_videos.py`

字幕是视频里唯一的文字层。折行写错不会抛异常，只会把 `cloud.getWXContext()`
从中间劈成「cloud.getWXCon / text()」——屏幕上凭空出现一个不存在的 API 名，
或者出现「一整行只有一个词」的孤行。这类缺陷只能靠不变量断言守着：
v2.4.3 之前它已经漏出去一次，13 集视频都带着那帧画面。


另一半是字形：`tools/render.py` 解析到的中文字体（Windows 雅黑 / macOS 苹方 /
Linux Noto）**没有** `✓ ✗ ✅ ❌ 👆 ▶` 这些字形，画上屏幕就是一个空心方块。
这不是猜的：用 `.notdef`（U+10FFFF，必然没有字形）的位图当参照比对过，
「模拟器：成功 ✓」「👆 点击组件」这些文案已经在 GIF 里当了很久豆腐块。

两项都不渲染视频（渲染由 check_assets_fresh.py 逐字节比对负责）。

已提交视频的容器完整性（有没有 moov）由 `check_repo.py` 的 `check_video_assets`
负责，本文件不重复：那里的用例在临时目录里搭迷你仓库，不依赖真实资产目录。
"""
import pathlib
import re
import sys
import unittest

TOOLS = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))

import gen_videos as gv  # noqa: E402

# 字幕从 x=62 起画，右边留 40；SS 是超采样倍数，所以宽度用物理像素算
MAX_PX = (gv.W - 62 - 40) * gv.SS

# 一行结尾是标识符字符、下一行开头又是标识符字符 ⇒ 十有八九是把名字劈开了
IDENT_TAIL = re.compile(r"[A-Za-z0-9)_]$")
IDENT_HEAD = re.compile(r"^[A-Za-z0-9(+_.\[]")

CASES = [
    "统一身份：cloud.getWXContext() 免鉴权拿 openid",
    "对比：小程序 vs H5 网页 vs 原生 App",
    "组件通信全景：properties + triggerEvent + selectComponent",
    "setData 只做数据搬运，跨线程通信耗时与数据量成正比",
    "wx.request 的 timeout 默认 60s，云调用 cloud.callFunction 不受该配置影响",
    "a+b*c 与 (a+b)*c 在 setData 路径 data.list[0].text 里的写法差异",
    "排错是进阶必备技能，越早练越好",
]


def width(s):
    return gv.fb(30).getlength(s)


def norm(s):
    return s.replace(" ", "").replace("\n", "")


class WrapLines(unittest.TestCase):
    def test_never_splits_an_identifier(self):
        """折行点不许落在标识符中间（这是 v2.4.3 修掉的那个真实缺陷）。"""
        for text in CASES:
            lines = gv._wrap_lines(text, 30)
            for a, b in zip(lines, lines[1:]):
                self.assertFalse(
                    IDENT_TAIL.search(a) and IDENT_HEAD.match(b),
                    f"标识符被劈开: …{a[-16:]} | {b[:16]}…")

    def test_content_survives(self):
        for text in CASES:
            self.assertEqual(norm("".join(gv._wrap_lines(text, 30))), norm(text))

    def test_fits_available_width(self):
        """超出可用宽度只允许一种例外：单个不可拆的标识符本身就更宽。"""
        for text in CASES:
            for ln in gv._wrap_lines(text, 30):
                if width(ln) > MAX_PX:
                    self.assertEqual(len(gv._ATOM_RE.findall(ln.strip())), 1,
                                     f"这行本可以再折: {ln!r} ({width(ln):.0f}px)")

    def test_fits_then_single(self):
        """放得下的文本必须就是一行——这是「行数最少」最直接的形状。

        用例不写死「这条该折成几行」：字体度量按平台不同（Windows 雅黑 / Linux
        Noto），改成「量出来放得下 ⇒ 只许一行」后，断言与被量的字体无关。
        """
        for text in CASES:
            if width(text) > MAX_PX:
                continue
            self.assertEqual(len(gv._wrap_lines(text, 30)), 1,
                             f"{width(text):.0f}px 放得下却折了行: {text!r}")

    def test_lines_are_not_mergeable(self):
        """行数必须已经最少：相邻两行能合并成一行的，就不该先拆开。

        只把「最宽行」当代价时会退化成一行的一个字（那时最宽行已是最小值）——
        这个断言正是那版的照妖镜。
        """
        for text in CASES:
            lines = list(gv._wrap_lines(text, 30))
            for a, b in zip(lines, lines[1:]):
                self.assertGreater(width(a + " " + b), MAX_PX,
                                   f"两行本可合并: {a!r} + {b!r}")

    def test_no_orphan_line(self):
        """两行以上时不许出现「一行只剩零头」。"""
        for text in CASES:
            lines = list(gv._wrap_lines(text, 30))
            if len(lines) < 2:
                continue
            ws = [width(x) for x in lines]
            self.assertGreater(min(ws), 0.35 * max(ws),
                               f"孤行: {lines}")

    def test_explicit_break_is_kept(self):
        self.assertEqual(list(gv._wrap_lines("甲甲甲\n乙乙乙", 30)), ["甲甲甲", "乙乙乙"])

    def test_degenerate_inputs(self):
        self.assertEqual(gv._wrap_lines("", 30), ())
        self.assertEqual(gv._wrap_lines("   ", 30), ())
        long_id = "前缀" + "someVeryLongCloudFunctionNameThatNeverFitsOneLineBecauseItKeepsGoing"
        lines = list(gv._wrap_lines(long_id, 30))
        self.assertTrue(any("someVeryLongCloudFunctionName" in ln for ln in lines), lines)


class GlyphCoverage(unittest.TestCase):
    """生成脚本里不许出现渲染字体画不出来的字符。"""

    # 实测在 pinned 字体（Windows 微软雅黑，资产就是它渲染的）下走 .notdef 的字符。
    # 这是一份**denylist 文本**，不要求它在别的字体下也缺字形：Linux 的 Noto CJK
    # 是有 ✓ ✗ ▶ 的，若断言「这些字符在当前字体里必须缺」会在 validate 作业
    # （ubuntu + fonts-noto-cjk）误报。
    MISSING = "✓✔✗✕✅❌👆👇▶◀▸♥❤✨🔥📱💡🚀"
    # 任何中文字体都画得出来的字符，用来证明探针没坏
    PRESENT = "正常中文 abc123 →←↑↓√×●○★☆·※"
    FILES = ("gen_videos.py", "gen_animations.py", "gen_diagrams.py",
             "gen_statics.py", "render.py")

    def test_probe_is_not_vacuous(self):
        """先证明 `gen_videos._missing_glyphs` 认得出豆腐块：否则「扫不出问题」
        只是探针坏了，和「自测没跑起来」是同一类假通过。

        用 U+10FFFE 当探针：它是**必然未分配**的码位（任何字体都走 .notdef），
        且与实现内部拿来做参照的 U+10FFFF 是两个不同码位——自己和自己比会
        恒真，那就又成了一次假通过。这条断言与字体无关，Linux 上同样成立。
        """
        UNASSIGNED = "\U0010FFFE"     # 与内部参照 U+10FFFF 不同，避免自证
        self.assertEqual(gv._missing_glyphs(UNASSIGNED), (UNASSIGNED,),
                         "探针认不出必然缺字形的码位，下面的扫描不可信")
        self.assertEqual(gv._missing_glyphs(self.PRESENT), (),
                         "探针把画得出的字符判成了豆腐块")
        self.assertEqual(gv._missing_glyphs("正常中文 abc123"), ())

    def test_generators_avoid_missing_glyphs(self):
        """扫**字面量**里的豆腐块字符，不扫注释与文档字符串。

        注释/文档字符串解释「哪些字符画不出来」时必然要写出这些字符本身
        （`_missing_glyphs` 的 docstring 就是），把它们也算违规会让解释
        无从落笔。真正会上屏的是字符串字面量，用 AST 精确取。
        """
        import ast
        bad = []
        for name in self.FILES:
            src = (TOOLS / name).read_text(encoding="utf-8")
            tree = ast.parse(src)
            docstrings = set()
            for node in ast.walk(tree):
                if not isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef,
                                         ast.AsyncFunctionDef)):
                    continue
                body = getattr(node, "body", None)
                if body and isinstance(body[0], ast.Expr) \
                        and isinstance(body[0].value, ast.Constant) \
                        and isinstance(body[0].value.value, str):
                    docstrings.add(id(body[0].value))
            for node in ast.walk(tree):
                if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
                    continue
                if id(node) in docstrings:
                    continue
                for ch in self.MISSING:
                    if ch in node.value:
                        bad.append(f"{name}:{node.lineno}: {ch!r} 上屏字面量里 "
                                   f"{node.value.strip()[:50]!r}")
        self.assertEqual(bad, [], f"画出来是空心方块，换成本文件 PRESENT 里的字符: {bad}")

    def test_glyph_scan_is_not_vacuous(self):
        """先证明「扫字面量」这一步真的会命中：否则扫出空列表只说明扫描没生效。

        这段源文本里 `✓` 在注释、`'✗'` 在字符串字面量，正确的实现只报后者。
        """
        import ast
        src = "def f():\n    # 注释里的 ✓ 不算\n    return '✗'\n"
        tree = ast.parse(src)
        hits = [ch for node in ast.walk(tree)
                if isinstance(node, ast.Constant) and isinstance(node.value, str)
                for ch in self.MISSING if ch in node.value]
        self.assertEqual(hits, ["✗"], "字面量扫描没按预期工作")

class AtomicRenderOutput(unittest.TestCase):
    """渲染中途失败，不许在 docs/assets 里留下半成品。

    这是 4 集 48 字节空壳的根因：`render_mp4` 过去直接把输出路径交给 ffmpeg，
    进程被 kill 时文件已经建出来了，只剩一个 ftyp+mdat 头——体积检查放行、
    播放器打不开。现在写临时文件、成功才落地，所以仓库里那一集要么是没动过的
    完整旧版，要么是全新的完整新版。
    """

    @staticmethod
    def _frames(n, blow_up_after=None):
        from PIL import Image
        for i in range(n):
            if blow_up_after is not None and i >= blow_up_after:
                raise RuntimeError("模拟渲染进程被中断")
            yield Image.new("RGB", (32, 32), (i * 7 % 256, 0, 0))

    def setUp(self):
        import tempfile
        if self._ffmpeg_missing():
            self.skipTest("没有 imageio-ffmpeg，无法真的跑一遍合成")
        self.td = tempfile.TemporaryDirectory()
        self.addCleanup(self.td.cleanup)
        self.dir = pathlib.Path(self.td.name)
        self._orig = gv.VIDEO_DIR
        gv.VIDEO_DIR = self.dir
        self.addCleanup(setattr, gv, "VIDEO_DIR", self._orig)

    @staticmethod
    def _ffmpeg_missing():
        try:
            import imageio_ffmpeg  # noqa: F401
            return False
        except Exception:
            return True

    def test_success_lands_one_complete_file(self):
        gv.render_mp4(self._frames(6), "video-99-ok")
        produced = sorted(p.name for p in self.dir.iterdir())
        self.assertEqual(produced, ["video-99-ok.mp4"],
                         f"成功渲染只应留下成片，实际: {produced}")
        data = (self.dir / "video-99-ok.mp4").read_bytes()
        self.assertIn(b"moov", data, "成片没有 moov，等于不可播")

    def test_interruption_leaves_previous_asset_untouched(self):
        keep = self.dir / "video-99-cut.mp4"
        keep.write_bytes(b"PREVIOUS-GOOD-VERSION")
        with self.assertRaises(RuntimeError):
            gv.render_mp4(self._frames(6, blow_up_after=2), "video-99-cut")
        self.assertEqual(keep.read_bytes(), b"PREVIOUS-GOOD-VERSION",
                         "渲染被打断却改写了已提交的那一集——空壳就是这么来的")
        self.assertEqual(sorted(p.name for p in self.dir.iterdir()),
                         ["video-99-cut.mp4"], f"临时文件漏在资产目录里: "
                         f"{sorted(p.name for p in self.dir.iterdir())}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
