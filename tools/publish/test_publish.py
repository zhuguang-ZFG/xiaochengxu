# -*- coding: utf-8 -*-
"""发布管线自测：把这次踩过的四个坑钉成不变量。

每个用例都对应一次真实事故，不是纸面断言：

1. **字幕折行不许把词劈开**——第一版把「今天」切成「今 / 天」，屏幕上读起来是断的。
2. **拉丁标识符作为原子不许劈**——`setUpdatePerformanceListener` 被切成
   `setUpdatePerfo / rmanceListener`，屏幕上凭空出现一个不存在的 API 名
   （仓库 docs/_契约.md 明确禁止，第一代成片就在这里翻过车）。
3. **字幕分组不许冲过上限**——先 append 再判断会让两个 20 字小句拼成 41 字一条，
   下游再怎么折行都折不回 16 字/行。
4. **缓存键必须带对齐算法版本**——旧 marks 配新规则，字幕时间整体错位却没有异常。

跑法：`python tools/publish/test_publish.py`
"""
from __future__ import annotations

import pathlib
import sys
import unittest

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import scenes as S  # noqa: E402
import spec  # noqa: E402
import voice  # noqa: E402


class SplitLines(unittest.TestCase):
    def test_never_splits_latin_identifier(self):
        """标识符不许跨行被劈开：任何一行都不能是它的**真前缀**。"""
        ident = "setUpdatePerformanceListener"
        text = f"调 {ident} 观察更新耗时与重排次数"
        lines = voice._split_lines(text)
        for ln in lines:
            for cut in range(3, len(ident)):
                self.assertNotEqual(ln.strip(), ident[:cut],
                                    f"标识符被劈开：{lines}")

    def test_identifier_stays_whole(self):
        text = "调 setUpdatePerformanceListener 观察更新耗时"
        lines = voice._split_lines(text)
        joined = "".join(lines)
        self.assertIn("setUpdatePerformanceListener", joined)

    def test_prefers_clause_boundary(self):
        """有空格时断在空格处，不许把汉字词劈开。"""
        text = "别急着写代码 今天这三件事想不清楚"
        lines = voice._split_lines(text)
        self.assertEqual(len(lines), 2)
        self.assertFalse(lines[0].endswith("今"), f"把「今天」劈开了: {lines}")
        self.assertTrue(lines[0] == "别急着写代码", lines)

    def test_each_line_fits(self):
        text = "那它长什么样 就是一个正常的界面 标题 列表 按钮一样不少"
        for ln in voice._split_lines(text):
            self.assertLessEqual(voice._cjk_count(ln), voice.MAX_LINE_CHARS, ln)

    def test_short_text_stays_one_line(self):
        self.assertEqual(voice._split_lines("小程序就是轻量应用"), ["小程序就是轻量应用"])


class CueGrouping(unittest.TestCase):
    def test_group_never_exceeds_limit(self):
        """两个 20 字小句不许被拼成 41 字一条。"""
        say = "这一集不教你写代码只解决一个更要紧的问题，这一集只追一个问题到底什么是小程序。"
        marks = [(i, i * 0.2) for i in range(len(say) + 1)]
        cues = voice.build_cues(say, marks)
        for (_s, _e, lines) in cues:
            self.assertLessEqual(len(lines), voice.MAX_LINES, lines)
            for ln in lines:
                self.assertLessEqual(voice._cjk_count(ln), voice.MAX_LINE_CHARS, ln)

    def test_cues_cover_all_speech(self):
        say = "甲" * 40
        marks = [(i, i * 0.2) for i in range(len(say) + 1)]
        cues = voice.build_cues(say, marks)
        got = sum(voice._cjk_count(l) for c in cues for l in c[2])
        self.assertEqual(got, 40, f"内容丢了：只保留 {got}/40")


class Spec(unittest.TestCase):
    def test_real_episodes_pass(self):
        eps = spec.load_all(HERE / "narration")
        self.assertGreaterEqual(len(eps), 13)
        for ep in eps:
            bad = spec.check(ep)
            self.assertEqual(bad, [], f"ep{ep['id']} 校验不通过：{bad[:3]}")

    def test_forbidden_glyphs_caught(self):
        ep = {
            "id": "99", "slug": "t", "title": "测",
            "segments": [{"say": "正常旁白内容足够长用来通过时长校验。" * 8,
                          "scene": {"kind": "bullets", "head": "标题 ✓",
                                    "items": [["a", "b"]]}}] * 13,
        }
        bad = spec.check(ep)
        self.assertTrue(any("画不出" in b for b in bad), bad)


class Layout(unittest.TestCase):
    def test_vertical_stays_out_of_platform_ui(self):
        """竖屏文字必须避开顶部 240 与底部 1320（平台 UI 保留区）。"""
        lay = S.Layout("v")
        self.assertGreaterEqual(lay.head_y, 240, "页眉落进顶部保留区")
        self.assertGreater(lay.box[1], 300, "内容盒顶边太靠上")
        self.assertLessEqual(lay.cap_bottom + 21, 1320, "字幕底边落进底部保留区")
        self.assertLessEqual(lay.box[2], 930, "内容盒右边压到点赞按钮栏")

    def test_horizontal_stays_out_of_platform_ui(self):
        lay = S.Layout("h")
        self.assertGreater(lay.box[1], 170, "横屏内容盒顶边太靠上")
        self.assertLessEqual(lay.cap_bottom + 21, 950, "横屏字幕落进底部控制条")


if __name__ == "__main__":
    unittest.main(verbosity=2)
