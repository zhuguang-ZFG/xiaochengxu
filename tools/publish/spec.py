# -*- coding: utf-8 -*-
"""旁白稿校验：上屏之前把「画不出来 / 放不下 / 说不完」三类问题拦下来。

前一代成片吃过两次亏（都在仓库 CHANGELOG 里）：字幕把 API 名从中间劈开、
字体画不出的字符在屏幕上是空心方块。所以这里不靠人眼，全部断言化：

1. **字符**：禁用字形扫描（与 `tools/test_gen_videos.py` 同一份 denylist）。
2. **放得下**：每条上屏文字按真实字体度量，必须塞进它所在的框。
3. **说得完**：按实测语速估算总时长，3–6 分钟之外直接报错。
"""
from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import scenes as S  # noqa: E402

# 实测语速：晓晓 -2% 下 4.10 字/秒（rate_test 量过 -10% ~ +10% 六档）
# 但每段合成音频自带约 0.65s 首尾静音，所以估时长必须把「每段固定开销」算进去，
# 只按字数估会低估 5~8%，那是「校验说 5.4 分钟、成片其实 5.8 分钟」的假通过。
CHARS_PER_SEC = 4.10
SEG_OVERHEAD = 1.00        # 每段固定开销（TTS 静音尾 + 段间留白），秒
PAD = 0.35
MIN_SEC, MAX_SEC = 240.0, 358.0        # 4.0 ~ 6.0 分钟
MISSING_GLYPHS = "✓✔✗✕✅❌👆👇▶◀▸♥❤✨🔥📱💡🚀"

REQUIRED = ("id", "slug", "title", "segments")


def _strings(scene):
    """一个场景里所有会上屏的字符串"""
    out = []
    for key in ("title", "sub", "head", "note", "next", "caption"):
        if scene.get(key):
            out.append((key, scene[key]))
    for key in ("points", "items", "screens", "steps", "lines"):
        for v in scene.get(key, []) or []:
            if isinstance(v, str):
                out.append((key, v))
            elif isinstance(v, (list, tuple)):
                for x in v:
                    if isinstance(x, str):
                        out.append((key, x))
    for col in scene.get("cols", []) or []:
        out.append(("cols.title", col.get("title", "")))
        for row in col.get("rows", []) or []:
            for x in row:
                out.append(("cols.row", x))
    return out


def _fit(lay: S.Layout, scene):
    """按真实字体度量检查每块文字塞不塞得进它所在的框"""
    bad = []
    x0, y0, x1, y1 = lay.box
    kind = scene.get("kind", "bullets")
    W = x1 - x0

    def fit(text, pt, limit_px, what, where):
        w = S.text_w(text, pt) / 2 / 1.0        # pt 是 2× 空间字号，除回逻辑像素
        if w > limit_px:
            bad.append(f"{where} 的{what}放不下：{text!r} 需 {w:.0f}px / 可用 {limit_px:.0f}px")

    f = lay.f
    # text_w 内部按 2× 字号量，这里统一换算成逻辑像素比较
    def w_of(text, pt):
        return S.text_w(text, pt) / 2

    if kind == "cover":
        fit(scene.get("title", ""), f["h1"], W, "主标题", "cover")
        fit(scene.get("sub", ""), f["h2"], W, "副标题", "cover")
        for s in scene.get("points", []):
            fit(s, f["body"], W, "要点", "cover")
    elif kind == "bullets":
        for it in scene.get("items", []):
            fit(it[0], f["h3"], W - 100, "标签", "bullets")
            if len(it) > 1:
                fit(it[1], f["small"], W - 100, "说明", "bullets")
    elif kind == "columns":
        cols = scene.get("cols", [])
        n = max(1, len(cols))
        cw = (W - 20 * (n - 1)) / n - 44
        for col in cols:
            fit(col.get("title", ""), f["h3"], cw + 30, "列标题", "columns")
            for row in col.get("rows", []):
                fit(row[0], f["small"], cw, "行名", "columns")
                fit(row[1], f["body"], cw, "行值", "columns")
    elif kind == "flow":
        vertical = lay.kind == "v" or scene.get("vertical")
        steps = scene.get("steps", [])
        n = max(1, len(steps))
        limit = W - 130 if vertical else (W - 18 * (n - 1)) / n - 30
        for st in steps:
            label = st[0] if isinstance(st, (list, tuple)) else st
            hint = st[1] if isinstance(st, (list, tuple)) and len(st) > 1 else ""
            fit(label, f["h3"], limit, "节点名", "flow")
            if hint:
                fit(hint, f["small"], limit, "节点说明", "flow")
    elif kind == "outro":
        for it in scene.get("items", []):
            fit(it, f["h3"], W - 60, "结论", "outro")
        fit(scene.get("next", ""), f["body"], W - 60, "下一集", "outro")
    elif kind == "code":
        for ln in scene.get("lines", []):
            text = ln[0] if isinstance(ln, (list, tuple)) else ln
            fit(text, f["mono"], W - 140, "代码行", "code")
    return bad


def check(episode, verbose=False):
    """返回问题列表（空 = 通过）"""
    bad = []
    for k in REQUIRED:
        if not episode.get(k):
            bad.append(f"缺少字段 {k}")
    if bad:
        return bad

    segs = episode["segments"]
    chars = 0
    for i, seg in enumerate(segs, start=1):
        tag = f"ep{episode['id']} 第 {i} 段"
        say = seg.get("say", "")
        scene = seg.get("scene")
        if not say:
            bad.append(f"{tag} 没有旁白")
        if not isinstance(scene, dict):
            bad.append(f"{tag} 没有场景")
            continue
        if scene.get("kind") not in S.KINDS:
            bad.append(f"{tag} 未知场景 {scene.get('kind')!r}")
            continue
        chars += sum(1 for ch in say if ch not in "，。、；：！？ ")

        for where, s in _strings(scene):
            for ch in MISSING_GLYPHS:
                if ch in s:
                    bad.append(f"{tag} 场景 {where} 含画不出的字符 {ch!r}：{s!r}")
        if verbose:
            continue

    est = chars / CHARS_PER_SEC + SEG_OVERHEAD * len(segs)
    if not MIN_SEC <= est <= MAX_SEC:
        bad.append(f"ep{episode['id']} 估算时长 {est:.0f}s 不在 {MIN_SEC:.0f}–{MAX_SEC:.0f}s "
                   f"（{chars} 字 / {len(segs)} 段）")
    for lay in (S.Layout("v"), S.Layout("h")):
        for i, seg in enumerate(segs, start=1):
            scene = seg.get("scene") or {}
            if scene.get("kind") in S.KINDS:
                for msg in _fit(lay, scene):
                    bad.append(f"ep{episode['id']} 第 {i} 段 [{lay.kind}] {msg}")
    return bad


def estimate(episode):
    chars = sum(sum(1 for ch in s["say"] if ch not in "，。、；：！？ ")
                for s in episode["segments"])
    return chars, chars / CHARS_PER_SEC + SEG_OVERHEAD * len(episode["segments"])


def load_all(narr_dir: pathlib.Path):
    """加载 narration/ 下全部 epNN.py，按 id 排序"""
    import importlib.util
    eps = []
    for f in sorted(narr_dir.glob("ep*.py")):
        spec = importlib.util.spec_from_file_location(f"narr_{f.stem}", f)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        eps.append(mod.EPISODE)
    return sorted(eps, key=lambda e: e["id"])
