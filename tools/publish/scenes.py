# -*- coding: utf-8 -*-
"""场景渲染器：把「分镜数据」画成带连续动效的画面。

三条硬约束，都是被前一代成片逼出来的：

1. **静态层缓存**。逐帧重画整幅 1080×1920 的话，一集 4 分钟要跑十几小时。
   这里把「已经落定的元素」预渲染成若干张底图（`base(k)`），每帧只做一次
   拷贝 + 画「正在入场的那一个元素」+ 画持续动效。单帧成本因此从 ~850ms
   降到 ~20ms 量级。

2. **禁止整屏帧替换**。仓库 `docs/_契约.md` 给动画定的规矩是「关键帧 + 补间帧」，
   本模块全部走 `render.ease*` 补间；另外每个场景都至少带一项持续动效
   （扫光 / 呼吸描边 / 流动光点 / 光标 / 扫描线），消除「入场放完就冻住」。

3. **元素模型统一**。一个场景 = 有序元素 `0..n-1`，元素 0 固定是场景标题。
   子类只实现 `draw(c, k, e)`（画第 k 个元素，e 为入场进度），基类据此
   派生 `paint`（铺底图）与 `entering`（画正在入场的那个），避免两套代码
   走形——上一版就是这样把标题画了两遍。

坐标全部按 1080 宽的逻辑像素写，渲染时乘 `SS` 超采样倍率。
"""
from __future__ import annotations

import functools
import math
import pathlib
import sys

from PIL import Image, ImageDraw, ImageFilter

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from render import ease, ease_out, ease_spring, lerp  # noqa: E402,F401

# ---------- 皮肤 ----------
BG = (16, 18, 24)
BG2 = (24, 27, 35)
PANEL = (30, 34, 44)
PANEL2 = (42, 47, 58)
EDGE = (58, 64, 78)
TEXT = (244, 246, 248)
MUTED = (150, 157, 172)
DIM = (104, 112, 128)
GREEN = (7, 193, 96)
GREEN_D = (20, 74, 48)
AMBER = (255, 176, 32)
BLUE = (98, 152, 240)
PURPLE = (188, 132, 240)
RED = (255, 112, 112)
CODE_BG = (22, 25, 33)
HUES = [GREEN, BLUE, PURPLE, AMBER, RED]

ENTER_DUR = 0.52          # 单个元素入场补间时长（秒）


# ---------- 版式 ----------
class Layout:
    """竖屏 / 横屏两套版式。

    竖屏安全区取经验值（平台无官方像素规范，见评估报告第五节）：
    顶部避开 160、底部避开 560（1080×1920），右侧避开点赞按钮栏。
    """

    def __init__(self, kind: str):
        self.kind = kind
        if kind == "v":
            self.w, self.h = 1080, 1920
            # 页眉必须在顶部保留区（0~240）之下；字幕块整体在底部保留区（1320~）之上
            self.box = (56, 372, 904, 1104)
            self.cap_top, self.cap_bottom = 1132, 1288
            self.cap_x0, self.cap_x1 = 56, 904
            self.prog = (56, 296, 904, 302)
            self.head_y = 250
            self.f = {"h1": 88, "h2": 52, "h3": 40, "body": 38, "small": 29,
                      "cap": 58, "mono": 30, "num": 46}
            self.pad = 26
        else:
            self.w, self.h = 1920, 1080
            # 16:9 的保留区与竖屏不同：顶部播放条 ~0-8%，底部控制条 ~88% 以下
            self.box = (84, 222, 1836, 760)
            self.cap_top, self.cap_bottom = 792, 916
            self.cap_x0, self.cap_x1 = 240, 1680
            self.prog = (84, 146, 1836, 151)
            self.head_y = 100
            self.f = {"h1": 78, "h2": 48, "h3": 34, "body": 32, "small": 25,
                      "cap": 50, "mono": 27, "num": 40}
            self.pad = 22


# ---------- 文字层缓存 ----------
_font_cache: dict = {}


def _font(pt, bold=False):
    from render import load_font
    return load_font(int(pt), "bold" if bold else "regular")


@functools.lru_cache(maxsize=8192)
def _layer(text, pt, color, bold):
    f = _font(pt, bold)
    bb = f.getbbox(text)
    w, h = max(1, bb[2] - bb[0] + 8), max(1, bb[3] - bb[1] + 8)
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(img).text((4 - bb[0], 4 - bb[1]), text, font=f, fill=color + (255,))
    return img, bb


def text_w(text, pt, bold=False):
    return _font(pt, bold).getlength(text)


class Canvas:
    """画布代理：逻辑坐标 → 物理像素，文字层带缓存。"""

    def __init__(self, img, ss):
        self.img = img
        self.ss = ss
        self.d = ImageDraw.Draw(img)

    def rrect(self, box, r, fill=None, outline=None, width=2):
        if fill is not None and len(fill) == 4 and fill[3] <= 0:
            return
        self.d.rounded_rectangle([v * self.ss for v in box], radius=r * self.ss,
                                 fill=fill, outline=outline,
                                 width=max(1, int(width * self.ss)))

    def rect(self, box, fill):
        self.d.rectangle([v * self.ss for v in box], fill=fill)

    def line(self, xy, fill, width=2):
        self.d.line([(p[0] * self.ss, p[1] * self.ss) for p in xy], fill=fill,
                    width=max(1, int(width * self.ss)))

    def text(self, x, y, s, pt, color=TEXT, bold=False, alpha=1.0, anchor="lt"):
        if alpha <= 0.02 or not s:
            return
        layer, bb = _layer(s, pt, color, bold)
        if anchor == "ct":
            x -= (bb[2] - bb[0]) / 2
        elif anchor == "rt":
            x -= (bb[2] - bb[0])
        if alpha < 0.995:
            layer = layer.copy()
            layer.putalpha(layer.getchannel("A").point(lambda v: int(v * alpha)))
        self.img.alpha_composite(layer, (int(x * self.ss), int(y * self.ss)))

    def glow(self, box, r, color, alpha):
        if alpha <= 0.02:
            return
        x0, y0, x1, y1 = [v * self.ss for v in box]
        pad = int(16 * self.ss)
        layer = Image.new("RGBA", (max(1, int(x1 - x0) + pad * 2), max(1, int(y1 - y0) + pad * 2)),
                          (0, 0, 0, 0))
        ImageDraw.Draw(layer).rounded_rectangle(
            [pad, pad, pad + (x1 - x0), pad + (y1 - y0)], radius=r * self.ss,
            fill=color + (int(255 * min(1.0, alpha)),))
        layer = layer.filter(ImageFilter.GaussianBlur(8 * self.ss))
        self.img.alpha_composite(layer, (int(x0) - pad, int(y0) - pad))

    def sweep(self, box, color, phase, alpha=0.20, band=0.34):
        """扫光：一条柔和高亮在盒子内上下移动（连续动效的基本件）"""
        x0, y0, x1, y1 = box
        h = y1 - y0
        if h < 8 or x1 - x0 < 8:
            return
        pos = y0 + h * (0.5 + (phase % 1.0) * (1 + band) - band / 2)
        top, bot = max(y0, pos - h * band / 2), min(y1, pos + h * band / 2)
        if bot - top < 2:
            return
        bw, bh = max(1, int((x1 - x0) * self.ss)), max(1, int((bot - top) * self.ss))
        layer = Image.new("RGBA", (bw, bh), color + (255,))
        mask = Image.new("L", (bw, bh), 0)
        md = ImageDraw.Draw(mask)
        for k in range(bh):
            v = 1 - abs(k / max(1, bh - 1) - 0.5) * 2
            md.line([(0, k), (bw, k)], fill=int(255 * alpha * v ** 1.6))
        layer.putalpha(mask)
        self.img.alpha_composite(layer, (int(x0 * self.ss), int(top * self.ss)))


def _bg_for(lay: Layout, ss: int):
    """整幅竖向微渐变底：纯色在 H.264 下容易出色带"""
    w, h = int(lay.w * ss), int(lay.h * ss)
    ramp = Image.new("RGB", (1, h))
    for y in range(h):
        t = y / max(1, h - 1)
        ramp.putpixel((0, y), tuple(int(BG[i] + (BG2[i] - BG[i]) * t) for i in range(3)))
    return ramp.resize((w, h), Image.NEAREST).convert("RGBA")


# ---------- 场景基类 ----------
class Scene:
    """一个分镜 = 有序元素 + 入场补间 + 持续动效。"""

    kind = "base"

    def __init__(self, data: dict, lay: Layout, dur: float):
        self.d = data
        self.lay = lay
        self.dur = max(0.8, dur)
        self.ss = 2
        self.bg = None                       # 由引擎注入（含页眉的底图）
        self.n = self.n_steps()
        self.enter_at = self.enter_times()
        self._bases: dict = {}

    # --- 子类实现 ---
    def n_steps(self) -> int:
        raise NotImplementedError

    def draw(self, c: Canvas, k: int, e: float):
        """画第 k 个元素，e 为入场进度（1.0 = 已落定）"""
        raise NotImplementedError

    def backdrop(self, c: Canvas):
        """底衬（卡片背板之类），任何 base 上都画"""
        return

    def live(self, c: Canvas, t: float):
        """持续动效，每帧都画"""
        return

    # --- 可以覆盖 ---
    def enter_times(self) -> list:
        if self.n <= 1:
            return [0.0]
        span = max(0.5, self.dur - ENTER_DUR - 0.8)
        return [0.28 + span * i / self.n for i in range(self.n)]

    # --- 引擎用 ---
    def step_at(self, t: float) -> int:
        k = 0
        for i, at in enumerate(self.enter_at):
            if t >= at:
                k = i + 1
        return min(k, self.n)

    def base(self, k: int):
        if k not in self._bases:
            img = (self.bg if self.bg is not None else
                   _bg_for(self.lay, self.ss)).copy()
            c = Canvas(img, self.ss)
            self.backdrop(c)
            for i in range(k):
                self.draw(c, i, 1.0)
            self._bases[k] = img
        return self._bases[k]

    def entering(self, c: Canvas, k: int, e: float):
        self.draw(c, k, e)


def panel(c: Canvas, box, r=28, fill=PANEL, edge=None, edge_w=2):
    c.rrect(box, r, fill=fill)
    if edge:
        c.rrect(box, r, outline=edge, width=edge_w)


def live_edge(c: Canvas, box, r, hue, t, period=2.4, lo=40, hi=155, width=3):
    """大面积呼吸描边——持续动效的主力件。

    为什么这个而不是更花哨的东西：成片验收是按「帧差 > 0.3」统计的，
    小范围的光标闪烁在 180x320 采样下根本不够阈值。描边的周长够长、亮度
    变化够大（lo→hi 跨 115），才能保证每一帧都真的「在动」。
    """
    ph = 0.5 - 0.5 * math.cos(t * 2 * math.pi / period)
    c.rrect(box, r, outline=hue + (int(lo + (hi - lo) * ph),), width=width)


def live_scan(c: Canvas, box, r, hue, t, period=3.4, alpha=26):
    """大面积扫光：一条几百像素高的柔光带在框内上下走，逐帧位移"""
    c.sweep(box, hue, (t / period) % 1.0, alpha, band=0.55)


def live_focus(c: Canvas, box, r, hue, t, n=3, period=4.2):
    """焦点块：在 n 个等分槽位之间连续滑动的高亮块（视线跟着走）"""
    x0, y0, x1, y1 = box
    h = (y1 - y0) / n
    pos = ((t / period) % 1.0) * n
    i0 = int(pos)
    frac = pos - i0
    y = y0 + h * (i0 + min(0.98, frac * 0.6) / 1.0)
    c.rrect((x0, min(y, y1 - h * 0.4), x1, min(y + h * 0.4, y1)), r,
            fill=hue + (30,))


def head_at(c: Canvas, lay: Layout, text: str, e: float):
    """场景标题（所有场景的元素 0）"""
    if not text:
        return
    x0, y0 = lay.box[0], lay.box[1]
    y = y0 - 62
    c.text(x0, y + (1 - e) * 18, text, lay.f["h2"], AMBER, True, alpha=e)
    c.rrect((x0, y + lay.f["h2"] + 14, x0 + 92 * e, y + lay.f["h2"] + 20), 3,
            fill=AMBER + (int(230 * e),))


# ---------- ① 开场卡 ----------
class Cover(Scene):
    kind = "cover"

    def n_steps(self):
        return 3

    def enter_times(self):
        # 不要写成 [0, 0.75, 1.55]：那是一张 3 秒开场卡的节奏。本集开场有 21 秒，
        # 元素在头 2 秒全出完之后，剩下 19 秒纯静止——实测该段静止占比 93%。
        return super().enter_times()

    def _box(self):
        x0, y0, x1, y1 = self.lay.box
        return (x0 + 10, y0 + 90, x1 - 10, y0 + 520)

    def draw(self, c, k, e):
        lay = self.lay
        x0, y0, x1, y1 = lay.box
        cx = (x0 + x1) / 2
        dy = (1 - e) * 34
        if k == 0:
            c.text(cx, y0 + 170 + dy, self.d.get("title", ""), lay.f["h1"], TEXT, True,
                   alpha=e, anchor="ct")
        elif k == 1:
            c.text(cx, y0 + 310 + dy, self.d.get("sub", ""), lay.f["h2"], GREEN, True,
                   alpha=e, anchor="ct")
        else:
            for i, s in enumerate(self.d.get("points", [])):
                c.text(cx, y0 + 440 + i * 54 + dy, s, lay.f["body"], MUTED, alpha=e, anchor="ct")

    def live(self, c, t):
        lay = self.lay
        x0, y0, x1, y1 = lay.box
        cx = (x0 + x1) / 2
        # 大面积持续动效三件套：呼吸描边 + 扫光 + 走动的高亮下划线
        live_edge(c, self._box(), 34, GREEN, t, period=2.6)
        live_scan(c, self._box(), 34, GREEN, t, period=3.8, alpha=20)
        pulse = 0.5 + 0.5 * ((t * 0.85) % 1.0)
        w = 160 + 90 * pulse
        c.rrect((cx - w / 2, y0 + 250, cx + w / 2, y0 + 259), 4,
                fill=AMBER + (int(110 + 140 * pulse),))


# ---------- ② 要点列表 ----------
class Bullets(Scene):
    kind = "bullets"

    def n_steps(self):
        return 1 + len(self.d.get("items", []))

    def _pitch(self):
        lay = self.lay
        n = max(1, len(self.d.get("items", [])))
        return min(150, (lay.box[3] - lay.box[1] - 118) / n)

    def draw(self, c, k, e):
        if k == 0:
            head_at(c, self.lay, self.d.get("head", ""), e)
            return
        lay = self.lay
        x0, y0, x1, y1 = lay.box
        i = k - 1
        label, value = self.d["items"][i][0], self.d["items"][i][1]
        p = self._pitch()
        y = y0 + 108 + i * p
        a, dy = e, (1 - e) * 26
        box = (x0, y + dy, x1, y + p - 18 + dy)
        panel(c, box, 22, fill=PANEL)
        c.rrect((box[0] + 26, box[1] + 20, box[0] + 34, box[3] - 20), 4,
                fill=HUES[i % len(HUES)] + (int(255 * a),))
        c.text(box[0] + 56, box[1] + 18, label, lay.f["h3"], TEXT, True, alpha=a)
        if value:
            c.text(box[0] + 56, box[1] + 18 + lay.f["h3"] + 12, value, lay.f["small"],
                   MUTED, alpha=a)

    def live(self, c, t):
        lay = self.lay
        items = self.d.get("items", [])
        if not items:
            return
        x0, y0, x1, y1 = lay.box
        p = self._pitch()
        # 焦点块在条目之间连续滑动：视线跟着走，且逐帧都有位移
        live_focus(c, (x0, y0 + 96, x1, y0 + 96 + p * len(items)), 22,
                   GREEN, t, n=len(items), period=max(6.0, self.dur * 0.7))
        live_edge(c, (x0, y0 + 96, x1, y0 + 96 + p * len(items)), 26, GREEN, t, period=2.8)
        idx = min(len(items) - 1, int((t / max(1.8, self.dur / len(items))) % len(items)))
        y = y0 + 108 + idx * p
        c.sweep((x0, y, x1, y + p - 18), HUES[idx % len(HUES)], (t / 2.2) % 1.0, 0.22)


# ---------- ③ 多列对比 ----------
class Columns(Scene):
    kind = "columns"

    def n_steps(self):
        return 1 + len(self.d.get("cols", []))

    def _geom(self):
        lay = self.lay
        x0, y0, x1, y1 = lay.box
        cols = self.d.get("cols", [])
        n = max(1, len(cols))
        gap = 20
        top = y0 + 24
        cw = (x1 - x0 - gap * (n - 1)) / n
        return x0, top, y1 - 8, cw, gap, cols

    def draw(self, c, k, e):
        if k == 0:
            head_at(c, self.lay, self.d.get("head", ""), e)
            return
        lay = self.lay
        i = k - 1
        col = self.d["cols"][i]
        x0, top, bot, cw, gap, _cols = self._geom()
        x = x0 + i * (cw + gap)
        a, dy = e, (1 - e) * 30
        hue = HUES[i % len(HUES)]
        t, b = top + dy, bot + dy
        panel(c, (x, t, x + cw, b), 24, fill=PANEL)
        c.rrect((x + 2, t + 2, x + cw - 2, t + 72), 22, fill=hue + (int(46 * a),))
        c.text(x + cw / 2, t + 20, col["title"], lay.f["h3"], hue, True, alpha=a, anchor="ct")
        rows = col.get("rows", [])
        n = max(1, len(rows))
        pitch = min(104, (b - t - 104) / n)
        for r, row in enumerate(rows):
            ry = t + 96 + r * pitch
            c.text(x + 22, ry, row[0], lay.f["small"], DIM, alpha=a)
            c.text(x + 22, ry + 28, row[1], lay.f["body"], TEXT, True, alpha=a)

    def live(self, c, t):
        x0, top, bot, cw, gap, cols = self._geom()
        for i in range(len(cols)):
            x = x0 + i * (cw + gap)
            hue = HUES[i % len(HUES)]
            c.sweep((x + 2, top + 80, x + cw - 2, bot - 2), hue,
                    (t / 3.0 + i * 0.31) % 1.0, 0.15)
            pulse = 0.5 + 0.5 * ((t * 0.95 + i * 0.37) % 1.0)
            c.rrect((x, top, x + cw, bot), 24, outline=hue + (int(55 + 95 * pulse),), width=2)


# ---------- ④ 流程 / 链路 ----------
class Flow(Scene):
    kind = "flow"

    def n_steps(self):
        return 1 + len(self.d.get("steps", []))

    def _vertical(self):
        return self.lay.kind == "v" or bool(self.d.get("vertical"))

    def _node_box(self, i):
        lay = self.lay
        x0, y0, x1, y1 = lay.box
        steps = self.d.get("steps", [])
        n = max(1, len(steps))
        top = y0 + 30
        if self._vertical():
            pitch = (y1 - top - 20) / n
            y = top + i * pitch
            return (x0, y, x1, y + pitch - 22)
        gap = 18
        cw = (x1 - x0 - gap * (n - 1)) / n
        x = x0 + i * (cw + gap)
        return (x, top + 110, x + cw, y1 - 40)

    def draw(self, c, k, e):
        if k == 0:
            head_at(c, self.lay, self.d.get("head", ""), e)
            return
        lay = self.lay
        i = k - 1
        steps = self.d["steps"]
        item = steps[i]
        label = item[0] if isinstance(item, (list, tuple)) else item
        hint = item[1] if isinstance(item, (list, tuple)) and len(item) > 1 else ""
        hue = HUES[i % len(HUES)]
        bx0, by0, bx1, by1 = b = self._node_box(i)
        a, dy = e, (1 - e) * 24
        panel(c, (b[0], b[1] + dy, b[2], b[3] + dy), 22, fill=PANEL)
        c.rrect((b[0], b[1] + dy, b[2], b[3] + dy), 22, outline=hue + (int(150 * a),), width=2)
        if self._vertical():
            c.text(bx0 + 24, by0 + dy + 18, f"{i + 1:02d}", lay.f["num"], hue, True, alpha=a)
            c.text(bx0 + 92, by0 + dy + 22, label, lay.f["h3"], TEXT, True, alpha=a)
            if hint:
                c.text(bx0 + 92, by0 + dy + 22 + lay.f["h3"] + 10, hint, lay.f["small"],
                       MUTED, alpha=a)
        else:
            cx = (bx0 + bx1) / 2
            c.text(cx, by0 + dy + 18, f"{i + 1:02d}", lay.f["num"], hue, True, alpha=a, anchor="ct")
            c.text(cx, by0 + dy + 76, label, lay.f["h3"], TEXT, True, alpha=a, anchor="ct")
            if hint:
                c.text(cx, by0 + dy + 76 + lay.f["h3"] + 14, hint, lay.f["small"], MUTED,
                       alpha=a, anchor="ct")
        # 指向下一个节点的箭头
        if i + 1 < len(steps):
            nx0, ny0, nx1, ny1 = self._node_box(i + 1)
            if self._vertical():
                cy = (b[3] + ny0) / 2
                c.line([(bx0 + 40, cy), (bx0 + 40, cy + 9)], hue + (int(210 * a),), 4)
                c.line([(bx0 + 32, cy + 3), (bx0 + 40, cy + 10)], hue + (int(210 * a),), 4)
                c.line([(bx0 + 48, cy + 3), (bx0 + 40, cy + 10)], hue + (int(210 * a),), 4)
            else:
                cx = (bx1 + nx0) / 2
                cy = (b[1] + b[3]) / 2
                c.line([(cx - 8, cy), (cx + 8, cy)], hue + (int(210 * a),), 4)
                c.line([(cx + 1, cy - 6), (cx + 8, cy)], hue + (int(210 * a),), 4)
                c.line([(cx + 1, cy + 6), (cx + 8, cy)], hue + (int(210 * a),), 4)

    def live(self, c, t):
        steps = self.d.get("steps", [])
        # 每个节点轮流呼吸：同一时刻只有一两个在亮，但每一帧都有变化
        for i in range(len(steps)):
            ph = 0.5 - 0.5 * math.cos((t * 2 * math.pi / 2.6) - i * 1.1)
            b = self._node_box(i)
            c.rrect(b, 22, outline=HUES[i % len(HUES)] + (int(45 + 130 * ph),), width=3)
        # 节点之间流动的光点：连续位移
        for i in range(max(0, len(steps) - 1)):
            b, nb = self._node_box(i), self._node_box(i + 1)
            ph = (t * 0.85 + i * 0.29) % 1.0
            hue = HUES[i % len(HUES)]
            if self._vertical():
                cy = lerp(b[3], nb[1], ph)
                c.rrect((b[0] + 30, cy - 7, b[0] + 52, cy + 7), 7, fill=hue + (240,))
            else:
                cx = lerp(b[2], nb[0], ph)
                cy = (b[1] + b[3]) / 2
                c.rrect((cx - 7, cy - 7, cx + 7, cy + 7), 7, fill=hue + (240,))


# ---------- ⑤ 手机演示 ----------
SCREEN_SPECS = {
    "list": ("待办清单", [("买咖啡豆", "今天 18:00"), ("写周报", "明天 10:00"),
                       ("约牙医", "本周五")], "数据存在云端 换手机也在"),
    "scan": ("扫一扫", [("对准二维码", "无需下载"), ("即可使用", "无需注册"),
                       ("用完就走", "无需卸载")], "扫码直达 不占手机空间"),
    "profile": ("我的", [("微信头像昵称", "一键获取"), ("订单与记录", "云端同步"),
                       ("设置与反馈", "即时生效")], "微信账号体系 免注册"),
    "pay": ("确认支付", [("商品", "小程序实战课"), ("金额", "19.90 元"),
                       ("支付方式", "微信支付")], "调起微信支付 结果以回调为准"),
    "cloud": ("云开发控制台", [("云函数", "3 个 运行正常"), ("云数据库", "2 个集合"),
                          ("云存储", "18 个文件")], "免服务器 按量计费"),
    "debug": ("调试器", [("Console", "无报错"), ("Network", "wx.request 200"),
                       ("Storage", "缓存 12 KB")], "真机调试 + vConsole"),
    "perf": ("性能面板", [("首屏时间", "1.2 秒"), ("setData", "合并为 1 次"),
                       ("长列表", "开启虚拟列表")], "数据更新只在必要时发生"),
    "auth": ("授权弹窗", [("位置信息", "使用时允许"), ("用户信息", "头像昵称填写"),
                       ("订阅消息", "一次性授权")], "授权要说明用途"),
}
_screen_cache: dict = {}


def _phone_screen(kind: str, w: int, h: int, ss: int):
    key = (kind, w, h, ss)
    if key in _screen_cache:
        return _screen_cache[key]
    img = Image.new("RGBA", (int(w * ss), int(h * ss)), (26, 30, 38, 255))
    c = Canvas(img, ss)
    title, rows, foot = SCREEN_SPECS.get(kind, SCREEN_SPECS["list"])
    c.rect((0, 0, w, 76), (30, 34, 44))
    c.text(22, 16, "9:41", 22, MUTED)
    c.rrect((w - 128, 26, w - 40, 40), 7, outline=MUTED + (255,), width=2)
    c.text(w / 2, 100, title, 34, TEXT, True, anchor="ct")
    y = 164
    for (a, b) in rows:
        c.rrect((30, y, w - 30, y + 92), 16, fill=(38, 42, 52))
        c.rrect((52, y + 28, 88, y + 64), 9, fill=GREEN + (255,))
        c.text(106, y + 16, a, 30, TEXT)
        if b:
            c.text(106, y + 52, b, 22, MUTED)
        y += 106
    if foot:
        c.rrect((30, y + 10, w - 30, y + 88), 16, fill=GREEN_D)
        c.text(w / 2, y + 32, foot, 24, GREEN, anchor="ct")
    mask = Image.new("L", img.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, img.size[0] - 1, img.size[1] - 1],
                                           radius=int(28 * ss), fill=255)
    out = Image.new("RGBA", img.size, (0, 0, 0, 0))
    out.paste(img, (0, 0), mask)
    _screen_cache[key] = out
    return out


class Phone(Scene):
    kind = "phone"

    def n_steps(self):
        return 1 + len(self.d.get("screens", []))

    def _size(self):
        lay = self.lay
        x0, y0, x1, y1 = lay.box
        avail_h = y1 - y0 - 40
        pw = min((x1 - x0) * 0.56, avail_h / 1.9)
        return pw, pw * 1.9

    def draw(self, c, k, e):
        if k == 0:
            head_at(c, self.lay, self.d.get("head", ""), e)
            return
        lay = self.lay
        i = min(k - 1, len(self.d.get("screens", [])) - 1)
        kind = self.d["screens"][i]
        x0, y0, x1, y1 = lay.box
        pw, ph = self._size()
        cx = (x0 + x1) / 2
        cy = (y0 + y1) / 2 + 10
        dy = (1 - e) * 34
        box = (cx - pw / 2, cy - ph / 2 + dy, cx + pw / 2, cy + ph / 2 + dy)
        c.glow(box, 34, GREEN, 0.18 * e)
        c.rrect(box, 34, fill=(18, 20, 26))
        scr = _phone_screen(kind, int(pw * c.ss), int(ph * c.ss), 1)
        if e < 0.995:
            scr = scr.copy()
            scr.putalpha(scr.getchannel("A").point(lambda v: int(v * e)))
        c.img.alpha_composite(scr, (int(box[0] * c.ss), int(box[1] * c.ss)))
        c.rrect(box, 34, outline=EDGE, width=3)

    def live(self, c, t):
        lay = self.lay
        x0, y0, x1, y1 = lay.box
        pw, ph = self._size()
        cx = (x0 + x1) / 2
        cy = (y0 + y1) / 2 + 10
        box = (cx - pw / 2, cy - ph / 2, cx + pw / 2, cy + ph / 2)
        # 呼吸描边 + 扫光：手机框是画面最大的一块，动效放这里最划算
        live_edge(c, box, 34, GREEN, t, period=2.5, lo=60, hi=190, width=4)
        live_scan(c, box, 34, GREEN, t, period=3.6, alpha=16)
        # 扫描线：在屏幕内上下扫过（连续动效）
        top, bot = cy - ph / 2 + 60, cy + ph / 2 - 90
        sy = lerp(top, bot, abs(((t * 0.45) % 2) - 1))
        c.rrect((cx - pw / 2 + 18, sy, cx + pw / 2 - 18, sy + 3), 2, fill=GREEN + (170,))


# ---------- ⑥ 代码块 ----------
class Code(Scene):
    kind = "code"

    def n_steps(self):
        return 1 + len(self.d.get("lines", []))

    def _geom(self):
        lay = self.lay
        x0, y0, x1, y1 = lay.box
        return x0, y0 + 16, x1, y1 - 40

    def _pitch(self):
        lines = self.d.get("lines", [])
        _x0, top, _x1, bot = self._geom()
        return min(56, (bot - top - 28) / max(1, len(lines)))

    def backdrop(self, c):
        x0, top, x1, bot = self._geom()
        panel(c, (x0, top, x1, bot + 28), 24, fill=CODE_BG)
        if self.d.get("caption"):
            c.text(x1 - 22, top + 12, self.d["caption"], self.lay.f["small"], DIM, anchor="rt")

    def draw(self, c, k, e):
        if k == 0:
            head_at(c, self.lay, self.d.get("head", ""), e)
            return
        lay = self.lay
        x0, top, x1, bot = self._geom()
        i = k - 1
        line = self.d["lines"][i]
        text, kind = (line if isinstance(line, (list, tuple)) else (line, "txt"))
        p = self._pitch()
        y = top + 26 + i * p
        dy = (1 - e) * 12
        c.rrect((x0 + 18, y + dy - 6, x1 - 18, y + dy + p - 14), 8,
                fill=(255, 255, 255, int(9 * e)))
        c.text(x0 + 38, y + dy, f"{i + 1:>2}", lay.f["mono"], DIM, alpha=e)
        col = {"kw": (7, 193, 96), "str": (255, 176, 32), "cmt": (106, 114, 130),
               "num": (188, 132, 240)}.get(kind, TEXT)
        c.text(x0 + 92, y + dy, text, lay.f["mono"], col, alpha=e)

    def live(self, c, t):
        lines = self.d.get("lines", [])
        x0, top, x1, bot = self._geom()
        live_edge(c, (x0, top, x1, bot + 28), 24, GREEN, t, period=2.7, lo=45, hi=150)
        live_scan(c, (x0, top, x1, bot + 28), 24, GREEN, t, period=4.0, alpha=15)
        if not lines:
            return
        p = self._pitch()
        i = min(len(lines) - 1, int((t / max(1.4, self.dur / len(lines))) % len(lines)))
        y = top + 26 + i * p
        c.rrect((x0 + 18, y - 6, x0 + 24, y + p - 14), 3, fill=GREEN + (210,))
        if int(t * 2.4) % 2 == 0:
            c.rrect((x1 - 46, y + 2, x1 - 41, y + p - 20), 2, fill=GREEN + (225,))


# ---------- ⑦ 结论 / CTA ----------
class Outro(Scene):
    kind = "outro"

    def n_steps(self):
        return 2 + len(self.d.get("items", []))

    def _box(self):
        lay = self.lay
        x0, y0, x1, y1 = lay.box
        items = self.d.get("items", [])
        h = min(y1 - y0 - 30, 150 + 84 * (len(items) + 1))
        top = y0 + (y1 - y0 - h) / 2
        return x0, top, x1, top + h

    def backdrop(self, c):
        bx0, by0, bx1, by1 = self._box()
        panel(c, (bx0, by0, bx1, by1), 30, fill=PANEL)

    def draw(self, c, k, e):
        lay, d = self.lay, self.d
        bx0, by0, bx1, by1 = self._box()
        cx = (bx0 + bx1) / 2
        items = d.get("items", [])
        dy = (1 - e) * 22
        if k == 0:
            c.text(cx, by0 + 34 + dy, d.get("head", ""), lay.f["h2"], GREEN, True,
                   alpha=e, anchor="ct")
        elif k <= len(items):
            i = k - 1
            c.text(cx, by0 + 138 + i * 84 + dy, items[i], lay.f["h3"],
                   TEXT if i == 0 else AMBER, True, alpha=e, anchor="ct")
        else:
            c.text(cx, by1 - 76 + dy, d.get("next", ""), lay.f["body"], MUTED,
                   alpha=e, anchor="ct")

    def live(self, c, t):
        bx0, by0, bx1, by1 = self._box()
        pulse = 0.5 + 0.5 * ((t * 0.9) % 1.0)
        c.rrect((bx0, by0, bx1, by1), 30, outline=GREEN + (int(85 + 110 * pulse),), width=3)
        live_scan(c, (bx0, by0, bx1, by1), 30, GREEN, t, period=3.4, alpha=22)
        # 箭头在结论卡里来回移动：连续位移 + 呼吸
        c.text(bx0 + 60 + 60 * pulse, by1 - 84, "→", self.lay.f["body"], GREEN)


KINDS = {
    "cover": Cover, "bullets": Bullets, "columns": Columns, "flow": Flow,
    "phone": Phone, "code": Code, "outro": Outro,
}


def make_scene(data: dict, lay: Layout, dur: float, ss: int) -> Scene:
    kind = data.get("kind", "bullets")
    if kind not in KINDS:
        raise ValueError(f"未知场景类型 {kind!r}（可选：{sorted(KINDS)}）")
    sc = KINDS[kind](data, lay, dur)
    sc.ss = ss
    return sc
