# -*- coding: utf-8 -*-
"""手绘风插图生成（与动画/示意图管线同一套超采样与字体约定）。

为什么有这一套：库里其余视觉资产都是「圆角卡片 + 精确几何」的产品风，
通篇一种笔性会显得冷。手绘风插图纸底暖、线条抖、带二次描线的铅笔感，
用在章节开头当「章节手账」，与产品风示意图互为补充。

确定性约束（check_assets_fresh.py 会重跑本脚本逐字节比对）：
- 全部随机性来自按图固定的 `random.Random(seed)`，不用 time / os.urandom；
- 抖动是确定函数（正弦叠加 + 固定相位），同 seed 同像素；
- 字体沿用 render.font()，平台差异与其它资产一致（CI 在 windows-latest 跑）。

用法：python tools/gen_handdrawn.py
产物：docs/assets/hd-*.png
"""
import math
import pathlib
import random
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from PIL import Image, ImageDraw  # noqa: E402
from render import ASSETS, font, font_b, S  # noqa: E402

# 纸与墨：暖白纸、深炭墨，主色沿用仓库调色板（略降饱和，贴合铅笔感）
PAPER = (251, 249, 243)
INK = (62, 60, 68)
INK_SOFT = (120, 117, 124)
GREEN = (6, 168, 84)
BLUE = (34, 106, 226)
ORANGE = (235, 118, 12)
RED = (226, 74, 74)
PURPLE = (128, 88, 200)
YELLOW = (222, 168, 20)


def _mix(a, b, t):
    return tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3))


class Sketch:
    """逻辑坐标画布（内部 2x 超采样），提供手绘基元。

    所有基元都吃逻辑坐标，内部乘 S；抖动幅度也按逻辑像素给。
    """

    def __init__(self, w, h, seed):
        self.w, self.h = w, h
        self.img = Image.new("RGB", (w * S, h * S), PAPER)
        self.d = ImageDraw.Draw(self.img)
        self.rng = random.Random(seed)

    # ---------- 底层笔画 ----------
    def _poly(self, pts, color, width):
        self.d.line([(x * S, y * S) for x, y in pts], fill=color,
                    width=max(1, round(width * S)), joint="curve")

    def stroke(self, p0, p1, color=INK, width=1.6, amp=1.8, passes=2):
        """抖动直线。passes=2 时补一条淡一点的二次描线（铅笔来回感）。"""
        x0, y0 = p0
        x1, y1 = p1
        dx, dy = x1 - x0, y1 - y0
        dist = math.hypot(dx, dy)
        if dist < 2:
            return
        n = max(6, int(dist / 12))
        ux, uy = -dy / dist, dx / dist  # 垂直方向
        f1 = self.rng.uniform(1.0, 2.0)
        f2 = self.rng.uniform(2.2, 3.4)
        ph1, ph2 = self.rng.uniform(0, 6.28), self.rng.uniform(0, 6.28)
        a = amp * self.rng.uniform(0.7, 1.0)

        def jitter_pts(mix_ink, amp_mul):
            pts = []
            for i in range(n + 1):
                t = i / n
                off = a * amp_mul * (0.65 * math.sin(math.pi * f1 * t + ph1)
                                     + 0.35 * math.sin(math.pi * f2 * t + ph2))
                pts.append((x0 + dx * t + ux * off, y0 + dy * t + uy * off))
            # 端点回到原位，笔画才接得上
            pts[0] = (x0, y0)
            pts[-1] = (x1, y1)
            return pts

        self._poly(jitter_pts(0, 1.0), color, width)
        if passes > 1:
            self._poly(jitter_pts(1, 0.9), _mix(color, PAPER, 0.62), width * 0.8)

    def dashed(self, p0, p1, color=INK_SOFT, width=1.3, dash=6, gap=5):
        x0, y0 = p0
        x1, y1 = p1
        dist = math.hypot(x1 - x0, y1 - y0)
        if dist < 2:
            return
        ux, uy = (x1 - x0) / dist, (y1 - y0) / dist
        t = 0.0
        while t < dist:
            t2 = min(t + dash, dist)
            self.stroke((x0 + ux * t, y0 + uy * t), (x0 + ux * t2, y0 + uy * t2),
                        color=color, width=width, amp=1.2, passes=1)
            t = t2 + gap

    def rect(self, box, color=INK, width=1.6, overshoot=2.5, fill=None, r=0):
        """手绘矩形：四角轻微错位 + 出头；fill 为底的圆角矩形先画（浅色底）。"""
        x0, y0, x1, y1 = box
        if fill is not None:
            self.d.rounded_rectangle([v * S for v in box], radius=r * S, fill=fill)
        j = lambda: self.rng.uniform(-1.6, 1.6)  # noqa: E731
        o = overshoot * self.rng.uniform(0.7, 1.2)
        pts = [(x0 + j(), y0 + j()), (x1 + j(), y0 + j()),
               (x1 + j(), y1 + j()), (x0 + j(), y1 + j()), (x0 + j(), y0 + j())]
        for a, b in zip(pts, pts[1:]):
            # 水平/垂直边各带出头
            horiz = abs(b[1] - a[1]) < 2
            if horiz:
                sgn = 1 if b[0] > a[0] else -1
                self.stroke((a[0] - sgn * o, a[1]), (b[0] + sgn * o, b[1]),
                            color=color, width=width, amp=1.2)
            else:
                sgn = 1 if b[1] > a[1] else -1
                self.stroke((a[0], a[1] - sgn * o), (b[0], b[1] + sgn * o),
                            color=color, width=width, amp=1.2)

    def circle(self, cx, cy, r, color=INK, width=1.6, fill=None, passes=2):
        """抖动圆：半径乘确定性噪声，收口留一点重叠。"""
        if fill is not None:
            self.d.ellipse([(cx - r) * S, (cy - r) * S, (cx + r) * S, (cy + r) * S], fill=fill)
        f1 = self.rng.uniform(2.0, 3.0)
        f2 = self.rng.uniform(4.0, 5.5)
        ph1, ph2 = self.rng.uniform(0, 6.28), self.rng.uniform(0, 6.28)
        for p in range(passes):
            mul = 1.0 if p == 0 else 0.55
            col = color if p == 0 else _mix(color, PAPER, 0.62)
            pts = []
            n = max(24, int(2 * math.pi * r / 4))
            for i in range(n + 3):
                th = 2 * math.pi * i / n
                rr = r * (1 + 0.028 * math.sin(f1 * th + ph1)
                          + 0.016 * math.sin(f2 * th + ph2)) * mul
                pts.append((cx + rr * math.cos(th), cy + rr * math.sin(th)))
            self._poly(pts, col, width if p == 0 else width * 0.8)

    def arc(self, cx, cy, r, a0, a1, color=INK, width=1.6, passes=2):
        """抖动圆弧（角度制弧度，a0→a1 逆时针为正方向）。"""
        f1 = self.rng.uniform(2.0, 3.0)
        ph1 = self.rng.uniform(0, 6.28)
        n = max(16, int(abs(a1 - a0) * r / 4))
        for p in range(passes):
            col = color if p == 0 else _mix(color, PAPER, 0.62)
            pts = []
            for i in range(n + 1):
                th = a0 + (a1 - a0) * i / n
                rr = r * (1 + 0.028 * math.sin(f1 * th + ph1)) * (1.0 if p == 0 else 0.55)
                pts.append((cx + rr * math.cos(th), cy + rr * math.sin(th)))
            self._poly(pts, col, width if p == 0 else width * 0.8)

    def arrow(self, p0, p1, color=INK, width=1.6, head=7.0):
        self.stroke(p0, p1, color=color, width=width)
        x0, y0 = p0
        x1, y1 = p1
        dist = math.hypot(x1 - x0, y1 - y0)
        ux, uy = (x1 - x0) / dist, (y1 - y0) / dist
        for ang in (2.6, -2.6):
            hx = x1 - head * (ux * math.cos(ang) - uy * math.sin(ang))
            hy = y1 - head * (uy * math.cos(ang) + ux * math.sin(ang))
            self.stroke((x1, y1), (hx, hy), color=color, width=width, amp=0.8, passes=1)

    def underline(self, cx, y, s, size=15, color=INK, width=1.4, bold=False):
        """标签下的手绘着重线（宽度按同一字重度量，别短一截）。"""
        f = font_b(size) if (bold or size >= 16) else font(size)
        w = self.d.textlength(s, font=f) / S
        self.stroke((cx - w / 2 - 3, y), (cx + w / 2 + 4, y + self.rng.uniform(-0.8, 0.8)),
                    color=color, width=width, passes=1)

    # ---------- 文本 ----------
    def text(self, x, y, s, size=15, color=INK, bold=False):
        f = font_b(size) if bold else font(size)
        self.d.text((x * S, y * S), s, font=f, fill=color)

    def text_c(self, cx, y, s, size=15, color=INK, bold=False):
        f = font_b(size) if bold else font(size)
        w = self.d.textlength(s, font=f) / S
        self.d.text(((cx - w / 2) * S, y * S), s, font=f, fill=color)
        return w

    # ---------- 复合小件 ----------
    def flag(self, cx, cy, label, color):
        """站点小旗：杆 + 三角旗 + 底部圈。"""
        self.circle(cx, cy, 5.5, color=color, width=1.5, fill=_mix(color, PAPER, 0.82))
        self.stroke((cx, cy - 4), (cx, cy - 26), color=color, width=1.5, amp=1.0)
        top = cy - 26
        tri = [(cx, top), (cx + 16, top + 5 + self.rng.uniform(-1, 1)), (cx, top + 11)]
        self.d.polygon([(x * S, y * S) for x, y in tri], fill=color)
        self.stroke((cx, top), (cx, top + 11), color=_mix(color, PAPER, 0.35), width=1.0, amp=0.5, passes=1)
        self.text_c(cx, cy + 10, label, 13, INK, bold=True)

    def sparkle(self, cx, cy, color=YELLOW, r=6):
        """四角星光涂鸦。"""
        for ang in (0, math.pi / 2, math.pi, 3 * math.pi / 2):
            self.stroke((cx + 1.4 * math.cos(ang), cy + 1.4 * math.sin(ang)),
                        (cx + r * math.cos(ang), cy + r * math.sin(ang)),
                        color=color, width=1.4, amp=0.5, passes=1)

    def check(self, cx, cy, color=GREEN, s=5.0):
        """手绘对勾。"""
        self.stroke((cx - s, cy + 0.5 * s), (cx - 0.25 * s, cy + s * 0.9), color=color, width=1.8, amp=0.6, passes=1)
        self.stroke((cx - 0.25 * s, cy + s * 0.9), (cx + s, cy - s * 0.8), color=color, width=1.8, amp=0.6, passes=1)

    def save(self, name):
        out = ASSETS / name
        self.img.resize((self.w, self.h), Image.LANCZOS).save(out, optimize=True)
        print(f"{name}: {out.stat().st_size} bytes")


# ============ 01 hd-path.png：学习路径（蜿蜒山路 + 五面旗） ============
def gen_path():
    sk = Sketch(880, 430, seed=101)
    rng = sk.rng
    # 蜿蜒主路：从左下到右上，三段折返
    path = [(70, 360), (240, 300), (300, 210), (430, 250), (560, 180), (640, 120), (790, 130)]
    for a, b in zip(path, path[1:]):
        sk.stroke(a, b, color=INK, width=2.2, amp=2.2)
    # 路边短线当草
    for bx, by in [(150, 352), (360, 262), (500, 205), (700, 158)]:
        for ang in (-0.5, 0.15, 0.7):
            sk.stroke((bx, by), (bx + 7 * math.sin(ang), by - 8 * math.cos(ang)),
                      color=_mix(GREEN, PAPER, 0.25), width=1.2, amp=0.7, passes=1)
    stations = [("① 认知", (70, 360), BLUE), ("② 准备", (300, 210), GREEN),
                ("③ 基础", (430, 250), ORANGE), ("④ 进阶", (560, 180), PURPLE),
                ("⑤ 实战发布", (790, 130), RED)]
    for label, (x, y), col in stations:
        sk.flag(x, y - 8, label, col)
    # 终点小火箭
    rx, ry = 838, 74
    sk.stroke((rx, ry), (rx, ry - 34), color=RED, width=2.0)            # 箭身
    sk.stroke((rx, ry - 34), (rx - 8, ry - 46), color=RED, width=2.0)   # 尖
    sk.stroke((rx, ry - 34), (rx + 8, ry - 46), color=RED, width=2.0)
    sk.stroke((rx - 8, ry - 10), (rx - 13, ry + 4), color=RED, width=1.6)  # 尾翼
    sk.stroke((rx + 8, ry - 10), (rx + 13, ry + 4), color=RED, width=1.6)
    sk.circle(rx, ry - 22, 4, color=RED, width=1.3)                     # 舷窗
    # 尾焰
    for i, ln in enumerate((10, 14, 9)):
        sk.stroke((rx - 4 + i * 4, ry + 6), (rx - 4 + i * 4, ry + 6 + ln),
                  color=ORANGE, width=1.4, amp=0.8, passes=1)
    # 起点小人（站到路径上，别压住旗子）
    px, py = 128, 336
    sk.circle(px, py - 22, 8, color=INK, width=1.6)
    sk.stroke((px, py - 14), (px, py + 2), color=INK, width=1.6)
    sk.stroke((px, py - 8), (px - 10, py - 2), color=INK, width=1.4)
    sk.stroke((px, py - 8), (px + 10, py - 12), color=INK, width=1.4)
    sk.stroke((px, py + 2), (px - 7, py + 12), color=INK, width=1.4)
    sk.stroke((px, py + 2), (px + 7, py + 12), color=INK, width=1.4)
    # 终点小火箭（单遍描线，避免反复描显得潦草）
    rx, ry = 838, 88
    sk.stroke((rx - 8, ry + 18), (rx - 8, ry - 12), color=RED, width=1.8, passes=1)
    sk.stroke((rx + 8, ry + 18), (rx + 8, ry - 12), color=RED, width=1.8, passes=1)
    sk.stroke((rx - 8, ry - 12), (rx, ry - 30), color=RED, width=1.8, passes=1)
    sk.stroke((rx + 8, ry - 12), (rx, ry - 30), color=RED, width=1.8, passes=1)
    sk.stroke((rx - 8, ry + 18), (rx + 8, ry + 18), color=RED, width=1.8, passes=1)
    sk.circle(rx, ry - 2, 4.5, color=RED, width=1.3, passes=1)
    sk.stroke((rx - 8, ry + 6), (rx - 15, ry + 22), color=RED, width=1.6, passes=1)
    sk.stroke((rx - 15, ry + 22), (rx - 4, ry + 18), color=RED, width=1.6, passes=1)
    sk.stroke((rx + 8, ry + 6), (rx + 15, ry + 22), color=RED, width=1.6, passes=1)
    sk.stroke((rx + 15, ry + 22), (rx + 4, ry + 18), color=RED, width=1.6, passes=1)
    for i, ln in enumerate((8, 12, 8)):                                # 尾焰
        sk.stroke((rx - 5 + i * 5, ry + 22), (rx - 5 + i * 5, ry + 22 + ln),
                  color=ORANGE, width=1.5, amp=0.7, passes=1)
    sk.sparkle(430, 96)
    sk.sparkle(160, 200, color=YELLOW, r=5)
    sk.text_c(440, 402, "从认识小程序到上线发布，一条人人都能走的路", 15, _mix(INK, PAPER, 0.25))
    sk.save("hd-path.png")


# ============ 02 hd-lang.png：三件套（手机 + 三块积木） ============
def gen_lang():
    sk = Sketch(820, 430, seed=202)
    # 手机（左）
    sk.rect((86, 60, 306, 370), color=INK, width=2.0, r=22, fill=(255, 255, 255))
    sk.stroke((168, 76), (224, 76), color=INK_SOFT, width=2.2, amp=0.8)  # 听筒
    # 屏里三行：骨架/皮肤/神经 的隐喻贴条
    bars = [(116, 130, (255, 214, 150)), (116, 190, (168, 224, 190)), (116, 250, (176, 200, 245))]
    for bx, by, col in bars:
        sk.rect((bx, by, bx + 160, by + 40), color=_mix(INK, PAPER, 0.2), width=1.4, r=8, fill=_mix(col, PAPER, 0.35))
    sk.text_c(196, 141, "WXML", 14, INK, bold=True)
    sk.text_c(196, 201, "WXSS", 14, INK, bold=True)
    sk.text_c(196, 261, "JS", 14, INK, bold=True)
    sk.text_c(196, 322, "预览", 13, INK_SOFT)
    # 三块积木（右）：骨架 / 皮肤 / 大脑，箭头一起指进右边的小手机
    blocks = [("骨架 · WXML", "描述页面有什么", (255, 214, 150), 96),
              ("皮肤 · WXSS", "决定长什么样", (168, 224, 190), 196),
              ("大脑 · JS", "负责动手干活", (176, 200, 245), 296)]
    for label, sub, col, y in blocks:
        sk.rect((386, y, 668, y + 78), color=_mix(INK, PAPER, 0.15), width=1.8, r=12, fill=_mix(col, PAPER, 0.55))
        sk.text(410, y + 14, label, 16, INK, bold=True)
        sk.text(410, y + 44, sub, 13, _mix(INK, PAPER, 0.35))
        sk.arrow((678, y + 39), (724, 212 + (y - 196) * 0.36), color=INK_SOFT, width=1.3, head=6)
    # 目标：拼在一起才是一个能跑的小程序
    sk.rect((734, 152, 800, 272), color=INK, width=1.8, r=12, fill=(255, 255, 255))
    sk.stroke((756, 164), (778, 164), color=INK_SOFT, width=1.6, amp=0.6, passes=1)
    sk.circle(767, 214, 9, color=GREEN, width=1.4, fill=_mix(GREEN, PAPER, 0.7))
    sk.text_c(767, 286, "一个能跑的小程序", 12, INK_SOFT)
    # 手写注解
    sk.text(96, 384, "JSON 不画界面——它负责登记页面与全局配置", 13, INK_SOFT)
    sk.sparkle(742, 84)
    sk.save("hd-lang.png")


# ============ 03 hd-setdata.png：双线程送快递 ============
def gen_setdata():
    sk = Sketch(840, 400, seed=303)
    # 两个线程blob
    sk.rect((60, 110, 320, 290), color=INK, width=2.0, r=18, fill=_mix((176, 200, 245), PAPER, 0.72))
    sk.rect((520, 110, 780, 290), color=INK, width=2.0, r=18, fill=_mix((255, 214, 150), PAPER, 0.72))
    sk.text_c(190, 140, "逻辑层", 18, INK, bold=True)
    sk.underline(190, 166, "逻辑层", 18, color=BLUE)
    sk.text_c(190, 196, "你的 JS 在这里跑", 13, _mix(INK, PAPER, 0.3))
    sk.text_c(650, 140, "渲染层", 18, INK, bold=True)
    sk.underline(650, 166, "渲染层", 18, color=ORANGE)
    sk.text_c(650, 196, "页面在这里画出来", 13, _mix(INK, PAPER, 0.3))
    # setData 快递：去程实线箭头 + 标签，回程虚线箭头
    sk.arrow((330, 168), (510, 168), color=INK, width=2.0, head=9)
    sk.rect((370, 120, 470, 152), color=INK, width=1.4, r=8, fill=(255, 255, 255))
    sk.text_c(420, 126, "setData", 14, INK, bold=True)
    sk.dashed((510, 232), (330, 232), color=INK_SOFT, width=1.5)
    sk.stroke((352, 224), (338, 232), color=INK_SOFT, width=1.5, passes=1)
    sk.stroke((352, 240), (338, 232), color=INK_SOFT, width=1.5, passes=1)
    sk.text_c(420, 240, "事件、触摸往回传", 13, INK_SOFT)
    # 中转站：微信客户端小房子（补上门窗，别只是一个方块）
    sk.rect((386, 300, 454, 344), color=INK, width=1.5, r=6, fill=_mix(GREEN, PAPER, 0.75))
    sk.stroke((380, 304), (420, 284), color=INK, width=1.5)
    sk.stroke((420, 284), (460, 304), color=INK, width=1.5)
    sk.stroke((410, 344), (410, 326), color=INK, width=1.3, amp=0.6, passes=1)   # 门框左
    sk.stroke((430, 344), (430, 326), color=INK, width=1.3, amp=0.6, passes=1)   # 门框右
    sk.circle(420, 336, 2.2, color=INK, width=0.9, passes=1)                     # 门把手
    sk.rect((394, 306, 406, 318), color=INK, width=1.0, overshoot=1.2, fill=(255, 255, 255))
    sk.stroke((400, 306), (400, 318), color=INK_SOFT, width=0.9, amp=0.4, passes=1)  # 十字窗
    sk.stroke((394, 312), (406, 312), color=INK_SOFT, width=0.9, amp=0.4, passes=1)
    sk.text_c(420, 352, "数据不共享，靠微信客户端中转", 13, _mix(INK, PAPER, 0.3))
    sk.text(70, 60, "为什么不能直接改 DOM？两层中间隔了一道墙。", 15, INK, bold=True)
    sk.sparkle(508, 70, color=GREEN, r=5)
    sk.save("hd-setdata.png")


# ============ 04 hd-cloud.png：云开发三抽屉 ============
def gen_cloud():
    sk = Sketch(820, 420, seed=404)
    # 云朵：整条闭合轮廓一次描完（三上凸、平底），内部不补线
    cx, cy = 410, 118
    sil = [(cx - 100, cy + 44), (cx - 104, cy + 18), (cx - 84, cy - 4), (cx - 62, cy - 8),
           (cx - 52, cy - 34), (cx - 26, cy - 48), (cx + 4, cy - 44), (cx + 22, cy - 58),
           (cx + 52, cy - 54), (cx + 68, cy - 34), (cx + 92, cy - 28), (cx + 106, cy - 6),
           (cx + 104, cy + 20), (cx + 108, cy + 44), (cx - 100, cy + 44)]
    fill_layer = ImageDraw.Draw(sk.img)
    fill_layer.polygon([(x * S, y * S) for x, y in sil], fill=(255, 255, 255))
    pts = []
    for i in range(len(sil) - 1):
        x0, y0 = sil[i]
        x1, y1 = sil[i + 1]
        seg = max(4, int(math.hypot(x1 - x0, y1 - y0) / 8))
        for k in range(seg):
            t = k / seg
            pts.append((x0 + (x1 - x0) * t + sk.rng.uniform(-1.2, 1.2),
                        y0 + (y1 - y0) * t + sk.rng.uniform(-1.2, 1.2)))
    sk._poly(pts + [sil[0]], INK, 2.0)
    sk._poly(pts, _mix(INK, PAPER, 0.62), 1.4)
    sk.text_c(cx, cy - 4, "云开发", 18, INK, bold=True)
    # 三个抽屉
    drawers = [("云函数", "后端代码放上云", 120), ("云数据库", "数据直接读写", 330), ("云存储", "文件上传下载", 540)]
    for label, sub, x in drawers:
        sk.rect((x, 250, x + 160, 330), color=INK, width=1.8, r=10, fill=_mix(BLUE, PAPER, 0.82))
        sk.stroke((x + 14, 268), (x + 146, 268), color=INK_SOFT, width=1.2, amp=0.8, passes=1)  # 抽屉缝
        sk.circle(x + 80, 292, 5, color=INK, width=1.3, fill=_mix(YELLOW, PAPER, 0.4))          # 把手
        sk.text_c(x + 80, 300, label, 15, INK, bold=True)
        sk.text_c(x + 80, 336, sub, 12, INK_SOFT)
        sk.dashed((x + 80, 236), (x + 80, 196), color=INK_SOFT, width=1.3)
        sk.stroke((x + 76, 206), (x + 80, 197), color=INK_SOFT, width=1.2, passes=1)
        sk.stroke((x + 84, 206), (x + 80, 197), color=INK_SOFT, width=1.2, passes=1)
    # 左侧小程序小方块接入
    sk.rect((60, 96, 150, 156), color=INK, width=1.8, r=10, fill=_mix(GREEN, PAPER, 0.7))
    sk.text_c(105, 116, "小程序", 14, INK, bold=True)
    sk.arrow((152, 118), (286, 108), color=INK, width=1.6, head=7)
    sk.text(72, 178, "不用自己买服务器", 13, INK_SOFT)
    sk.sparkle(690, 70)
    sk.save("hd-cloud.png")


# ============ 05 hd-debug.png：放大镜找虫子 ============
def gen_debug():
    sk = Sketch(800, 420, seed=505)
    # 代码窗口
    sk.rect((70, 70, 430, 350), color=INK, width=2.0, r=12, fill=(255, 255, 255))
    sk.stroke((70, 108), (430, 108), color=INK_SOFT, width=1.4, amp=0.8, passes=1)
    sk.circle(92, 89, 5, color=RED, width=1.2)
    sk.circle(114, 89, 5, color=YELLOW, width=1.2)
    sk.circle(136, 89, 5, color=GREEN, width=1.2)
    # 代码行：彩色短横（带缩进层级，别太稀疏）
    rows = [(134, 134, 90, BLUE), (164, 162, 60, ORANGE), (134, 190, 90, INK_SOFT),
            (194, 218, 96, RED), (164, 246, 60, INK_SOFT), (134, 274, 76, BLUE),
            (164, 302, 60, PURPLE), (134, 330, 90, INK_SOFT)]
    for x, y, wln, col in rows:
        sk.stroke((x, y), (x + wln, y), color=_mix(col, PAPER, 0.25), width=2.4, amp=0.7, passes=1)
        sk.circle(x - 14, y, 1.4, color=INK_SOFT, width=0.8, passes=1)  # 行号点
    # 虫子趴在 RED 那行末尾（补两根触角）
    bx, by = 356, 218
    sk.circle(bx, by, 9, color=RED, width=1.6, fill=_mix(RED, PAPER, 0.75))
    for ang in (-1.1, -0.5, 0.5, 1.1):
        sk.stroke((bx + 8 * math.cos(ang), by + 8 * math.sin(ang)),
                  (bx + 15 * math.cos(ang), by + 15 * math.sin(ang)), color=RED, width=1.2, amp=0.4, passes=1)
    sk.stroke((bx - 7, by - 8), (bx - 13, by - 14), color=RED, width=1.1, amp=0.4, passes=1)   # 触角
    sk.stroke((bx - 4, by - 9), (bx - 7, by - 16), color=RED, width=1.1, amp=0.4, passes=1)
    # 放大镜压在虫子上（手柄一根粗杆 + 环口一圈箍）
    mx, my = 380, 180
    sk.circle(mx, my, 52, color=INK, width=2.4, fill=None)
    sk.stroke((mx + 38, my + 38), (mx + 74, my + 74), color=INK, width=3.2, amp=0.8, passes=1)
    sk.stroke((mx + 34, my + 42), (mx + 44, my + 32), color=INK, width=2.6, amp=0.5, passes=1)
    # Console 面板
    sk.rect((500, 150, 740, 300), color=INK, width=1.8, r=10, fill=(255, 255, 255))
    sk.text(518, 164, "Console", 13, INK_SOFT)
    sk.stroke((500, 190), (740, 190), color=INK_SOFT, width=1.2, amp=0.7, passes=1)
    sk.text(518, 202, "TypeError: …", 13, RED)
    sk.text(518, 228, "at page.onLoad", 12, INK_SOFT)
    sk.check(526, 264, color=GREEN, s=6)
    sk.text(542, 256, "复现 → 定位 → 修 → 回归", 13, INK)
    sk.text(500, 96, "先问证据，再谈猜测", 16, INK, bold=True)
    sk.underline(560, 118, "先问证据，再谈猜测", 16, color=BLUE)
    sk.text(500, 330, "报错信息里的第一行，通常就是答案。", 13, INK_SOFT)
    sk.save("hd-debug.png")


# ============ 06 hd-rocket.png：上线发布的三道闸 ============
def gen_rocket():
    sk = Sketch(860, 430, seed=606)
    # 三道闸门
    gates = [("上传代码", "体验版先给自己人用", 120, GREEN), ("提交审核", "类目资质别填错", 400, ORANGE), ("全网发布", "分批放量看监控", 680, RED)]
    for label, sub, x, col in gates:
        sk.rect((x, 150, x + 140, 250), color=INK, width=2.0, r=12, fill=_mix(col, PAPER, 0.78))
        sk.stroke((x + 22, 178), (x + 118, 178), color=INK_SOFT, width=1.3, amp=0.8, passes=1)
        sk.text_c(x + 70, 192, label, 16, INK, bold=True)
        sk.text_c(x + 70, 264, sub, 12, INK_SOFT)
    for x0, x1 in ((264, 396), (544, 676)):
        sk.arrow((x0, 200), (x1, 200), color=INK, width=1.8, head=8)
    # 火箭飞出右上
    rx, ry = 790, 84
    sk.stroke((rx, ry + 26), (rx, ry - 14), color=RED, width=2.2)
    sk.stroke((rx, ry - 14), (rx - 9, ry - 30), color=RED, width=2.0)
    sk.stroke((rx, ry - 14), (rx + 9, ry - 30), color=RED, width=2.0)
    sk.circle(rx, ry + 2, 4.5, color=RED, width=1.3)
    for ang in (-2.3, -2.9):
        sk.stroke((rx - 2, ry + 20), (rx - 13 * math.cos(ang), ry + 20 - 10 * math.sin(ang)),
                  color=RED, width=1.5, amp=0.6, passes=1)
    for i, ln in enumerate((8, 12, 7)):
        sk.stroke((rx - 5 + i * 5, ry + 30), (rx - 5 + i * 5, ry + 30 + ln), color=ORANGE, width=1.5, amp=0.8, passes=1)
    # 地面线
    sk.stroke((80, 366), (780, 366), color=INK, width=1.8, amp=1.6)
    sk.text_c(430, 386, "发布不是终点——上线后还要盯数据、接反馈", 14, _mix(INK, PAPER, 0.2))
    sk.text(104, 96, "先过三道闸，再飞", 17, INK, bold=True)
    sk.underline(170, 120, "先过三道闸，再飞", 17, color=GREEN)
    sk.sparkle(300, 80)
    sk.save("hd-rocket.png")


# ============ 07 hd-quiz.png：随堂测验的草稿纸 ============
def gen_quiz():
    sk = Sketch(720, 400, seed=707)
    # 草稿纸
    sk.rect((120, 60, 560, 344), color=INK, width=2.0, r=6, fill=(255, 255, 255))
    for y in (120, 176, 232, 288):
        sk.stroke((146, y), (534, y), color=_mix(INK, PAPER, 0.78), width=1.1, amp=0.7, passes=1)
    sk.text(146, 84, "随堂测验", 18, INK, bold=True)
    sk.underline(190, 108, "随堂测验", 18, color=GREEN)
    items = [(136, 142, True), (136, 198, True), (136, 254, False), (136, 310, False)]
    for x, y, done in items:
        sk.rect((x, y, x + 22, y + 22), color=INK, width=1.4, overshoot=1.6, fill=(255, 255, 255))
        if done:
            sk.check(x + 11, y + 11, color=GREEN, s=7)
    sk.text(176, 142, "场景题：先想清楚再选", 14, INK)
    sk.text(176, 198, "答案在 <details> 里，别偷看", 14, INK)
    sk.text(176, 254, "错一道，回正文找依据", 14, INK)
    sk.text(176, 310, "全对再进下一篇", 14, INK)
    # 铅笔（右下）：笔杆双线 + 笔尖三角，斜着搁着
    px, py = 566, 296
    ang = 0.5
    dx, dy = math.cos(ang), math.sin(ang)
    nx, ny = -dy, dx
    sk.stroke((px + nx * 4, py + ny * 4), (px + 84 * dx + nx * 4, py + 84 * dy + ny * 4),
              color=ORANGE, width=1.6, amp=0.5, passes=1)
    sk.stroke((px - nx * 4, py - ny * 4), (px + 84 * dx - nx * 4, py + 84 * dy - ny * 4),
              color=ORANGE, width=1.6, amp=0.5, passes=1)
    tipx, tipy = px + 84 * dx, py + 84 * dy
    sk.d.polygon([( tipx * S, tipy * S),
                  ((tipx + 14 * dx + nx * 4) * S, (tipy + 14 * dy + ny * 4) * S),
                  ((tipx + 14 * dx - nx * 4) * S, (tipy + 14 * dy - ny * 4) * S)], fill=(243, 226, 196))
    sk.stroke((tipx + 14 * dx + nx * 1.2, tipy + 14 * dy + ny * 1.2),
              (tipx + 18 * dx, tipy + 18 * dy), color=INK, width=2.2, amp=0.3, passes=1)
    sk.stroke((tipx + 14 * dx - nx * 1.2, tipy + 14 * dy - ny * 1.2),
              (tipx + 18 * dx, tipy + 18 * dy), color=INK, width=2.2, amp=0.3, passes=1)
    # 尾橡皮
    sk.stroke((px + nx * 4, py + ny * 4), (px - nx * 4, py - ny * 4), color=RED, width=3.0, amp=0.4, passes=1)
    sk.text(536, 66, "做题比划线有用", 15, INK, bold=True)
    sk.underline(584, 88, "做题比划线有用", 15, color=ORANGE)
    sk.sparkle(520, 96, color=YELLOW, r=5)
    sk.save("hd-quiz.png")


# ============ 08 hd-phone.png：小程序是什么（即点即用） ============
def gen_phone():
    sk = Sketch(800, 420, seed=808)
    sk.text(300, 56, "无需下载安装，即点即用", 17, INK, bold=True)
    sk.underline(388, 80, "无需下载安装，即点即用", 17, color=GREEN, bold=True)
    # 左：一台手机，屏里是小程序宫格与「最近使用」条
    sk.rect((70, 110, 280, 380), color=INK, width=2.0, r=20, fill=(255, 255, 255))
    sk.stroke((150, 126), (200, 126), color=INK_SOFT, width=2.2, amp=0.8)
    tiles = [(100, 156), (170, 156), (100, 222), (170, 222)]
    for (tx, ty), col in zip(tiles, [GREEN, BLUE, ORANGE, PURPLE]):
        sk.rect((tx, ty, tx + 52, ty + 52), color=_mix(INK, PAPER, 0.2), width=1.3,
                r=10, fill=_mix(col, PAPER, 0.72))
        sk.circle(tx + 26, ty + 20, 6, color=_mix(col, PAPER, 0.2), width=1.2, passes=1)
        sk.stroke((tx + 14, ty + 38), (tx + 38, ty + 38), color=INK_SOFT, width=1.4, amp=0.5, passes=1)
    sk.rect((100, 292, 250, 326), color=INK_SOFT, width=1.2, r=8, fill=_mix(YELLOW, PAPER, 0.75))
    sk.text_c(175, 300, "最近使用", 12, INK_SOFT)
    # 右：三个入口气泡，箭头指回手机——入口都在微信里
    sk.text(360, 96, "三个入口，都在微信里", 13, INK_SOFT)
    for label, by in (("扫码", 120), ("搜索", 180), ("分享卡片", 240)):
        sk.rect((360, by, 490, by + 42), color=INK, width=1.5, r=12, fill=(255, 255, 255))
        sk.text_c(425, by + 13, label, 14, INK)
        sk.arrow((354, by + 21), (296, by + 21), color=INK_SOFT, width=1.4, head=6)
    # 用完即走
    sk.arrow((286, 350), (400, 350), color=GREEN, width=1.8, head=8)
    sk.text(412, 342, "用完关掉，不占桌面", 14, INK)
    sk.sparkle(560, 90)
    sk.save("hd-phone.png")


# ============ 09 hd-env.png：环境准备（开发者工具三步跑通） ============
def gen_env():
    sk = Sketch(840, 430, seed=909)
    sk.text(84, 52, "注册 → 装工具 → 编译，三分钟见 Hello World", 17, INK, bold=True)
    sk.underline(318, 76, "注册 → 装工具 → 编译，三分钟见 Hello World", 17, color=BLUE, bold=True)
    # 开发者工具窗口
    sk.rect((80, 100, 520, 330), color=INK, width=2.0, r=12, fill=(255, 255, 255))
    sk.stroke((80, 136), (520, 136), color=INK_SOFT, width=1.4, amp=0.8, passes=1)
    sk.circle(100, 118, 5, color=RED, width=1.2, passes=1)
    sk.circle(120, 118, 5, color=YELLOW, width=1.2, passes=1)
    sk.circle(140, 118, 5, color=GREEN, width=1.2, passes=1)
    # 工具条：绿色「编译」胶囊
    sk.rect((168, 106, 236, 130), color=INK, width=1.2, r=6, fill=_mix(GREEN, PAPER, 0.3))
    sk.text_c(202, 111, "编译", 13, (255, 255, 255), bold=True)
    # 三栏：文件树 / 代码 / 模拟器
    sk.stroke((268, 136), (268, 330), color=_mix(INK, PAPER, 0.7), width=1.0, amp=0.5, passes=1)
    sk.stroke((388, 136), (388, 330), color=_mix(INK, PAPER, 0.7), width=1.0, amp=0.5, passes=1)
    for i, y in enumerate((156, 178, 200, 222, 244)):
        sk.stroke((96, y), (96 + (44 if i % 2 else 58), y), color=INK_SOFT, width=1.6, amp=0.6, passes=1)
    for y, x, wln, col in ((160, 284, 78, BLUE), (186, 284, 60, INK_SOFT), (212, 302, 66, ORANGE),
                           (238, 284, 60, INK_SOFT), (264, 284, 78, GREEN)):
        sk.stroke((x, y), (x + wln, y), color=_mix(col, PAPER, 0.25), width=2.2, amp=0.6, passes=1)
    sk.rect((404, 158, 500, 312), color=INK, width=1.6, r=10, fill=_mix(BLUE, PAPER, 0.88))
    sk.text_c(452, 226, "模拟器", 13, INK_SOFT)
    sk.text_c(452, 290, "Hello World", 12, INK, bold=True)
    # 右下：真机预览（二维码 → 手机）
    sk.rect((580, 160, 668, 248), color=INK, width=1.8, overshoot=2.0, fill=(255, 255, 255))
    for qx, qy in ((596, 176), (612, 192), (628, 176), (596, 208), (640, 216), (612, 224)):
        sk.rect((qx, qy, qx + 10, qy + 10), color=INK, width=0.9, overshoot=0.8, fill=INK)
    sk.arrow((676, 204), (724, 204), color=INK, width=1.6, head=7)
    sk.rect((730, 150, 806, 258), color=INK, width=1.8, r=12, fill=_mix(GREEN, PAPER, 0.8))
    sk.text_c(768, 196, "真机", 13, INK, bold=True)
    sk.text(580, 280, "扫码预览：手机上跑的就是", 13, INK_SOFT)
    sk.text(580, 302, "编辑器里这一份代码", 13, INK_SOFT)
    sk.text(84, 356, "坑先说破：模拟器「正常」不等于真机「正常」，编译按钮救不了没填的 AppID", 13, INK_SOFT)
    sk.sparkle(560, 84)
    sk.save("hd-env.png")


# ============ 10 hd-structure.png：项目结构（页面 = 同名四件套） ============
def gen_structure():
    sk = Sketch(860, 470, seed=1010)
    sk.text(84, 48, "一个页面 = 同名四件套，谁都不能少", 17, INK, bold=True)
    sk.underline(262, 72, "一个页面 = 同名四件套，谁都不能少", 17, color=ORANGE, bold=True)
    # 根目录
    sk.rect((84, 104, 216, 138), color=INK, width=1.6, r=6, fill=_mix(YELLOW, PAPER, 0.55))
    sk.text_c(150, 112, "my-app", 14, INK, bold=True)
    # 主干
    sk.stroke((104, 138), (104, 384), color=INK_SOFT, width=1.3, amp=0.8)
    # 一级：pages（带子树）+ 三个全局文件
    sk.stroke((104, 176), (136, 176), color=INK_SOFT, width=1.2, amp=0.6, passes=1)
    sk.rect((138, 160, 224, 192), color=INK, width=1.3, r=6, fill=_mix(GREEN, PAPER, 0.7))
    sk.text_c(181, 167, "pages", 13, INK)
    # index/ 与四件套（缩进到 x246 起，避开 app.* 行）
    sk.stroke((160, 192), (160, 224), color=INK_SOFT, width=1.2, amp=0.6, passes=1)
    sk.stroke((160, 224), (178, 224), color=INK_SOFT, width=1.2, amp=0.6, passes=1)
    sk.rect((178, 208, 266, 240), color=INK, width=1.3, r=6, fill=_mix(GREEN, PAPER, 0.7))
    sk.text_c(222, 215, "index/", 13, INK)
    sk.stroke((246, 240), (246, 388), color=INK_SOFT, width=1.2, amp=0.8)
    files = [("index.wxml", 250, "结构：写标签"), ("index.wxss", 286, "样式：管长相"),
             ("index.js", 322, "逻辑：管数据"), ("index.json", 358, "配置：报页面")]
    for fname, y, note in files:
        sk.stroke((246, y + 14), (258, y + 14), color=INK_SOFT, width=1.2, amp=0.6, passes=1)
        sk.rect((258, y, 388, y + 28), color=INK, width=1.3, r=6, fill=(255, 255, 255))
        sk.text_c(323, y + 7, fname, 13, INK)
        sk.arrow((396, y + 14), (432, y + 14), color=INK_SOFT, width=1.1, head=5)
        sk.text(442, y + 7, note, 13, INK)
    # 全局三件
    for label, y in (("app.js", 292), ("app.json", 328), ("app.wxss", 364)):
        sk.stroke((104, y + 16), (136, y + 16), color=INK_SOFT, width=1.2, amp=0.6, passes=1)
        sk.rect((138, y, 238, y + 32), color=INK, width=1.3, r=6, fill=_mix(BLUE, PAPER, 0.85))
        sk.text_c(188, y + 8, label, 13, INK)
    sk.text(84, 416, "app.json 是总入口：少登记一个页面，编译直接报错；四个文件必须同名放在同一目录", 13, INK_SOFT)
    sk.sparkle(760, 92)
    sk.save("hd-structure.png")


# ============ 11 hd-wxml.png：WXML（标签搭骨架，花括号插数据） ============
def gen_wxml():
    sk = Sketch(820, 420, seed=1111)
    sk.text(84, 52, "标签搭骨架，花括号插数据", 17, INK, bold=True)
    sk.underline(196, 76, "标签搭骨架，花括号插数据", 17, color=BLUE, bold=True)
    # 手机屏里的列表项骨架
    sk.rect((80, 110, 300, 360), color=INK, width=2.0, r=20, fill=(255, 255, 255))
    sk.stroke((162, 126), (218, 126), color=INK_SOFT, width=2.2, amp=0.8)
    sk.rect((104, 156, 276, 300), color=INK, width=1.5, r=10, fill=_mix(BLUE, PAPER, 0.92))
    sk.rect((116, 168, 168, 220), color=INK, width=1.2, r=8, fill=_mix(YELLOW, PAPER, 0.6))  # 图位
    sk.circle(136, 184, 5, color=ORANGE, width=1.2, passes=1)                                # 小太阳
    sk.stroke((120, 210), (136, 196), color=ORANGE, width=1.3, amp=0.6, passes=1)            # 小山
    sk.stroke((136, 210), (160, 188), color=ORANGE, width=1.3, amp=0.6, passes=1)
    sk.rect((180, 172, 264, 190), color=INK, width=1.1, r=5, fill=_mix(GREEN, PAPER, 0.5))
    sk.text_c(222, 173, "{{title}}", 11, INK, bold=True)
    sk.stroke((180, 202), (260, 202), color=INK_SOFT, width=1.6, amp=0.6, passes=1)
    sk.stroke((180, 216), (236, 216), color=INK_SOFT, width=1.6, amp=0.6, passes=1)
    sk.text_c(190, 316, "wx:for 列表", 12, INK_SOFT)
    sk.text_c(190, 338, "{{ }} 插数据", 12, INK_SOFT)
    # 右侧注解
    sk.text(380, 110, "WXML 只管「有什么」，", 15, INK)
    sk.text(380, 136, "长什么样归 WXSS，", 15, INK)
    sk.text(380, 162, "数据从 JS 里来。", 15, INK)
    sk.text(380, 214, "它不是 HTML：", 14, INK, bold=True)
    sk.text(380, 240, "没有 div/section，", 13, INK_SOFT)
    sk.text(380, 262, "只有 view/text/image", 13, INK_SOFT)
    sk.text(380, 284, "这些写好的组件。", 13, INK_SOFT)
    sk.text(380, 330, "双向不自由：视图不能反写数据，", 13, INK_SOFT)
    sk.text(380, 352, "要改就老老实实 setData。", 13, INK_SOFT)
    sk.sparkle(320, 96)
    sk.save("hd-wxml.png")


# ============ 12 hd-lifecycle.png：页面生命周期（一条线读完） ============
def gen_lifecycle():
    sk = Sketch(860, 400, seed=1212)
    sk.text(84, 48, "页面的一生，一条线读完", 17, INK, bold=True)
    sk.underline(196, 72, "页面的一生，一条线读完", 17, color=PURPLE, bold=True)
    nodes = [("onLoad", 110, "拿参数，一次"), ("onShow", 262, "每次出现都跑"),
             ("onReady", 414, "首渲染完，能量尺寸"), ("onUnload", 700, "销毁，收尾")]
    for label, x, sub in nodes:
        sk.rect((x, 128, x + 132, 184), color=INK, width=1.8, r=12,
                fill=_mix(PURPLE, PAPER, 0.8))
        sk.text_c(x + 66, 140, label, 15, INK, bold=True)
        sk.text_c(x + 66, 196, sub, 12, INK_SOFT)
    for x0, x1 in ((246, 258), (398, 410), (550, 696)):
        sk.arrow((x0, 156), (x1, 156), color=INK, width=1.7, head=8)
    # 隐藏/回前台分支：去程向下，回程绕上方回到 onShow
    sk.rect((300, 268, 460, 316), color=INK, width=1.6, r=10, fill=_mix(BLUE, PAPER, 0.85))
    sk.text_c(380, 279, "onHide", 14, INK, bold=True)
    sk.text_c(380, 324, "切后台暂停，别死循环", 12, INK_SOFT)
    sk.stroke((328, 188), (328, 264), color=BLUE, width=1.5, amp=0.8)
    sk.stroke((320, 256), (328, 265), color=BLUE, width=1.4, amp=0.5, passes=1)
    sk.stroke((336, 256), (328, 265), color=BLUE, width=1.4, amp=0.5, passes=1)
    sk.arrow((466, 292), (556, 292), color=BLUE, width=1.4, head=6)
    sk.stroke((556, 292), (556, 100), color=BLUE, width=1.4, amp=0.8)
    sk.stroke((556, 100), (328, 100), color=BLUE, width=1.4, amp=0.8)
    sk.stroke((328, 100), (328, 122), color=BLUE, width=1.4, amp=0.6)
    sk.stroke((320, 114), (328, 124), color=BLUE, width=1.3, amp=0.5, passes=1)
    sk.stroke((336, 114), (328, 124), color=BLUE, width=1.3, amp=0.5, passes=1)
    sk.text(400, 82, "回前台再走 onShow", 12, BLUE)
    sk.text(110, 250, "顺序不看背的，", 14, INK, bold=True)
    sk.text(110, 274, "看它服务什么：", 14, INK, bold=True)
    sk.text(110, 298, "onLoad 拿一次参数，", 13, INK_SOFT)
    sk.text(110, 320, "onShow 反复进出，", 13, INK_SOFT)
    sk.text(110, 342, "onReady 才能问布局。", 13, INK_SOFT)
    sk.text(560, 356, "注册在 Page({...}) 里的同名方法就是钩子", 13, INK_SOFT)
    sk.sparkle(780, 84)
    sk.save("hd-lifecycle.png")


# ============ 13 hd-component.png：自定义组件（数据往下，事件往上） ============
def gen_component():
    sk = Sketch(860, 420, seed=1313)
    sk.text(84, 48, "数据往下走，事件往上报", 17, INK, bold=True)
    sk.underline(196, 72, "数据往下走，事件往上报", 17, color=GREEN, bold=True)
    # 父（页面）包着子（组件）
    sk.rect((110, 110, 430, 340), color=INK, width=2.0, r=14, fill=_mix(BLUE, PAPER, 0.9))
    sk.text(126, 122, "页面（父）", 14, INK, bold=True)
    sk.rect((170, 170, 370, 300), color=INK, width=1.8, r=12, fill=_mix(GREEN, PAPER, 0.78))
    sk.text_c(270, 182, "组件（子）", 14, INK, bold=True)
    sk.text_c(270, 214, "properties 只读", 13, INK_SOFT)
    sk.text_c(270, 236, "自己管自己的 data", 13, INK_SOFT)
    sk.text_c(270, 258, "不偷改父的值", 13, INK_SOFT)
    sk.circle(270, 282, 5, color=GREEN, width=1.3, passes=1)
    # 两条通道（贴着框内边走，标签跟在箭头旁）
    sk.arrow((200, 148), (200, 168), color=BLUE, width=1.8, head=7)
    sk.text(210, 140, "properties · 父传子", 12, BLUE, bold=True)
    sk.arrow((400, 302), (400, 148), color=ORANGE, width=1.8, head=7)
    sk.text(410, 210, "triggerEvent", 12, ORANGE, bold=True)
    sk.text(410, 230, "（子说：用户点了！）", 11, INK_SOFT)
    # 右侧要点
    sk.text(540, 116, "组件不是小页面：", 15, INK, bold=True)
    sk.underline(626, 140, "组件不是小页面：", 15, color=ORANGE, bold=True)
    for i, s in enumerate(("数据只进不出的部分用 properties 声明", "想改父的值？发事件让父自己改",
                           "样式默认隔离，别指望外层选择器")):
        sk.check(552, 178 + i * 34, color=GREEN, s=5)
        sk.text(568, 168 + i * 34, s, 13, INK)
    sk.text(540, 292, "拆的时机：一个 wxml 超过两屏、", 13, INK_SOFT)
    sk.text(540, 314, "或同一段 UI 出现两次，就值得拆。", 13, INK_SOFT)
    sk.sparkle(780, 92)
    sk.save("hd-component.png")


# ============ 14 hd-network.png：网络请求（一次往返） ============
def gen_network():
    sk = Sketch(860, 420, seed=1414)
    sk.text(84, 48, "域名先登记，请求才出发", 17, INK, bold=True)
    sk.underline(212, 72, "域名先登记，请求才出发", 17, color=BLUE, bold=True)
    # 手机 → 白名单闸门 → 服务器
    sk.rect((84, 140, 200, 300), color=INK, width=2.0, r=16, fill=(255, 255, 255))
    sk.text_c(142, 210, "手机里的小程序", 12, INK_SOFT)
    sk.rect((84, 160, 200, 196), color=INK, width=1.2, r=8, fill=_mix(GREEN, PAPER, 0.6))
    sk.text_c(142, 167, "wx.request", 13, INK, bold=True)
    sk.rect((330, 130, 500, 250), color=INK, width=1.8, r=12, fill=_mix(ORANGE, PAPER, 0.8))
    sk.text_c(415, 142, "域名白名单", 15, INK, bold=True)
    sk.text_c(415, 172, "request 合法域名", 12, INK_SOFT)
    sk.text_c(415, 192, "https 且先在后台登记", 12, INK_SOFT)
    sk.circle(415, 222, 7, color=ORANGE, width=1.4, fill=_mix(YELLOW, PAPER, 0.4))  # 锁孔
    # 服务器塔
    sk.rect((660, 120, 780, 310), color=INK, width=2.0, r=10, fill=(255, 255, 255))
    for y in (150, 190, 230, 270):
        sk.stroke((676, y), (764, y), color=INK_SOFT, width=1.5, amp=0.7, passes=1)
    sk.stroke((720, 120), (720, 92), color=INK, width=1.6, amp=0.6)                    # 天线
    sk.circle(720, 86, 4, color=RED, width=1.3, passes=1)
    sk.text_c(720, 322, "服务器", 13, INK)
    # 去程 / 回程（回程虚线绕开白名单闸门，分两段指回手机）
    sk.arrow((206, 180), (324, 180), color=INK, width=1.8, head=8)
    sk.rect((238, 148, 300, 172), color=INK, width=1.2, r=6, fill=(255, 255, 255))
    sk.text_c(269, 152, "请求", 12, INK, bold=True)
    sk.dashed((656, 240), (506, 240), color=INK_SOFT, width=1.5)
    sk.stroke((516, 232), (505, 240), color=INK_SOFT, width=1.4, amp=0.4, passes=1)
    sk.stroke((516, 248), (505, 240), color=INK_SOFT, width=1.4, amp=0.4, passes=1)
    sk.dashed((326, 240), (212, 240), color=INK_SOFT, width=1.5)
    sk.stroke((222, 232), (211, 240), color=INK_SOFT, width=1.4, amp=0.4, passes=1)
    sk.stroke((222, 248), (211, 240), color=INK_SOFT, width=1.4, amp=0.4, passes=1)
    sk.rect((360, 226, 430, 254), color=INK, width=1.2, r=6, fill=_mix(BLUE, PAPER, 0.5))
    sk.text_c(395, 231, "响应", 12, INK, bold=True)
    # 底部提示
    sk.text(84, 344, "开发者工具里能关掉域名校验——真机关不掉，", 13, INK_SOFT)
    sk.text(84, 366, "所以白名单要在真机上线前配好。", 13, INK_SOFT)
    sk.text(540, 344, "登录态：wx.login 换 code，", 13, INK_SOFT)
    sk.text(540, 366, "服务端换 session，别存前端。", 13, INK_SOFT)
    sk.sparkle(600, 90)
    sk.save("hd-network.png")


# ============ 15 hd-pay.png：微信支付（付钱快，对账靠回调） ============
def gen_pay():
    sk = Sketch(860, 420, seed=1515)
    sk.text(84, 48, "用户付得快，回调要对得上", 17, INK, bold=True)
    sk.underline(212, 72, "用户付得快，回调要对得上", 17, color=GREEN, bold=True)
    # 手机支付键盘
    sk.rect((84, 110, 260, 350), color=INK, width=2.0, r=18, fill=(255, 255, 255))
    sk.text_c(172, 126, "收银台", 14, INK, bold=True)
    sk.text_c(172, 152, "￥ 99.00", 18, RED, bold=True)
    for r in range(2):
        for c in range(3):
            sk.circle(118 + c * 54, 200 + r * 44, 8, color=INK_SOFT, width=1.3, passes=1)
    sk.rect((116, 284, 228, 316), color=INK, width=1.3, r=8, fill=_mix(GREEN, PAPER, 0.35))
    sk.text_c(172, 291, "确认支付", 13, (255, 255, 255), bold=True)
    sk.check(146, 332, color=GREEN, s=5)
    sk.text_c(206, 324, "支付成功", 12, INK_SOFT)
    # 中间：微信支付平台
    sk.circle(430, 190, 46, color=INK, width=2.0, fill=_mix(GREEN, PAPER, 0.82))
    sk.text_c(430, 176, "微信", 14, INK, bold=True)
    sk.text_c(430, 198, "支付", 14, INK, bold=True)
    # 右：商户后台（回调 + 幂等）
    sk.rect((600, 120, 800, 320), color=INK, width=2.0, r=12, fill=(255, 255, 255))
    sk.text_c(700, 134, "商户后台", 14, INK, bold=True)
    items = [("收到回调", "验签别跳过"), ("先查单再改状态", "回调会重发多次"), ("同一单只处理一次", "幂等是底线")]
    for i, (head, sub) in enumerate(items):
        y = 164 + i * 52
        sk.check(618, y + 9, color=GREEN, s=5)
        sk.text(636, y, head, 13, INK, bold=True)
        sk.text(636, y + 20, sub, 11, INK_SOFT)
    # 两条通道：付款去程 / 回调通知
    sk.arrow((266, 200), (378, 200), color=INK, width=1.8, head=8)
    sk.arrow((480, 190), (596, 190), color=ORANGE, width=1.8, head=8)
    sk.text(500, 164, "回调通知", 12, ORANGE, bold=True)
    sk.dashed((760, 326), (760, 372), color=INK_SOFT, width=1.4)
    sk.stroke((748, 366), (760, 375), color=INK_SOFT, width=1.3, passes=1)
    sk.stroke((772, 366), (760, 375), color=INK_SOFT, width=1.3, passes=1)
    sk.text_c(760, 384, "没回 200？它还会再来", 12, INK_SOFT)
    sk.text(84, 384, "前端只负责调起 wx.requestPayment，", 13, INK_SOFT)
    sk.text(420, 384, "钱对不对账，看服务端。", 13, INK_SOFT)
    sk.save("hd-pay.png")


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    gen_path()
    gen_lang()
    gen_setdata()
    gen_cloud()
    gen_debug()
    gen_rocket()
    gen_quiz()
    gen_phone()
    gen_env()
    gen_structure()
    gen_wxml()
    gen_lifecycle()
    gen_component()
    gen_network()
    gen_pay()
    print("done")
