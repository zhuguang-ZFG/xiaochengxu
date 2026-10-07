# -*- coding: utf-8 -*-
"""
小程序知识库视觉资产生成脚本（可复现）。

设计原则（解决"图片粗糙"问题）：
1. 超采样抗锯齿：所有绘制在 2x 画布完成，最终 LANCZOS 降采样，消除锯齿。
2. 帧间插值过渡：动画由关键帧 + 补间帧生成（位移/透明度/缩放），而非整屏替换。
3. 真实 UI 细节：微信官方绿、圆角阴影、按压态、点击波纹、转场滑动。
4. GIF 调色板优化：256 色自适应量化，控制单文件体积。

用法：python tools/gen_assets.py
输出：docs/assets/*.gif  docs/assets/*.png
"""
import math
import pathlib
from PIL import Image, ImageDraw, ImageFont

ASSETS = pathlib.Path(__file__).resolve().parent.parent / "docs" / "assets"
ASSETS.mkdir(parents=True, exist_ok=True)

# ---------- 配色（微信官方视觉） ----------
GREEN = (7, 193, 96)
GREEN_DARK = (6, 168, 84)
BG = (237, 237, 237)
WHITE = (255, 255, 255)
DARK = (26, 26, 26)
GRAY = (152, 152, 152)
GRAY_L = (233, 233, 233)
RED = (250, 81, 81)
BLUE = (22, 93, 255)
ORANGE = (255, 125, 0)
PURPLE = (140, 90, 220)
NAV_BG = (247, 247, 247)

S = 2                       # 超采样倍率
SW, SH = 375 * S, 667 * S   # 物理画布

FONT = r"C:\Windows\Fonts\msyh.ttc"
FONT_B = r"C:\Windows\Fonts\msyhbd.ttc"


def font(size):
    return ImageFont.truetype(FONT, size * S)


def font_b(size):
    return ImageFont.truetype(FONT_B, size * S)


def new_screen():
    img = Image.new("RGB", (SW, SH), BG)
    return img, ImageDraw.Draw(img)


def rrect(d, box, radius, fill=None, outline=None, width=1):
    """逻辑坐标圆角矩形"""
    d.rounded_rectangle([v * S for v in box], radius=radius * S,
                        fill=fill, outline=outline, width=width * S)


def txt(d, xy, s, f, fill):
    """逻辑坐标文本"""
    d.text((xy[0] * S, xy[1] * S), s, font=f, fill=fill)


def text_w(d, s, f):
    return d.textlength(s, font=f) / S


def text_c(d, cx, y, s, f, fill):
    """水平居中文本（cx 为逻辑坐标中心）"""
    d.text(((cx - text_w(d, s, f) / 2) * S, y * S), s, font=f, fill=fill)


def status_bar(d, dark=True):
    c = DARK if dark else WHITE
    txt(d, (16, 8), "9:41", font(11), c)
    d.rectangle([SW - 78, 12 * S, SW - 54, 20 * S], outline=c, width=1)
    d.rectangle([SW - 76, 14 * S, SW - 66, 18 * S], fill=c)
    for i in range(4):
        d.rectangle([SW - 48 + i * 4, (16 - i * 2) * S, SW - 44 + i * 4, 20 * S], fill=c)


def nav_bar(d, title, back=False):
    d.rectangle([0, 0, SW, 88 * S], fill=NAV_BG)
    d.line([0, 88 * S, SW, 88 * S], fill=(228, 228, 228), width=1)
    text_c(d, 375 / 2, 50, title, font_b(17), DARK)
    if back:
        d.line([20 * S, 44 * S, 32 * S, 32 * S], fill=DARK, width=2 * S)
        d.line([20 * S, 44 * S, 32 * S, 56 * S], fill=DARK, width=2 * S)


def shadow(d, box, radius, spread=2):
    """像素级柔和阴影（贴到目标画布）"""
    img = d._image
    x0, y0, x1, y1 = [v * S for v in box]
    for i in range(spread, 0, -1):
        layer = Image.new("RGBA", (SW, SH), (0, 0, 0, 0))
        ld = ImageDraw.Draw(layer)
        pad = i * 2
        ld.rounded_rectangle([x0 - pad, y0 - pad, x1 + pad, y1 + pad],
                             radius=radius * S + pad, fill=(0, 0, 0, 22))
        img.paste(layer, (0, 0), layer)


def card(d, box, radius=12, fill=WHITE, border=None):
    shadow(d, box, radius)
    rrect(d, box, radius, fill=fill, outline=border, width=2 if border else 1)


def ripple(img, cx, cy, t, rmul=34, alpha0=150):
    """点击波纹（逻辑坐标），t 0→1"""
    r = 6 + t * rmul
    a = int(alpha0 * (1 - t))
    if a <= 0:
        return
    layer = Image.new("RGBA", (SW, SH), (0, 0, 0, 0))
    ld = ImageDraw.Draw(layer)
    ld.ellipse([(cx - r) * S, (cy - r) * S, (cx + r) * S, (cy + r) * S],
               outline=(255, 255, 255, a), width=int(2.5 * S))
    img.paste(layer, (0, 0), layer)


def phone_frame(screen_img):
    pad = 13
    W = SW + pad * 2 * S
    H = SH + pad * 2 * S + 15 * S
    img = Image.new("RGB", (W, H), (246, 246, 247))
    d = ImageDraw.Draw(img)
    bd = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    bdraw = ImageDraw.Draw(bd)
    bdraw.rounded_rectangle([5 * S, 7 * S, W - 5 * S, H - 3 * S], radius=24 * S, fill=(0, 0, 0, 70))
    img.paste(bd, (0, 0), bd)
    d.rounded_rectangle([0, 0, W, H - 6 * S], radius=24 * S, fill=(18, 18, 20))
    nw = 60
    d.rounded_rectangle([(W - nw * S) // 2, 6 * S, (W + nw * S) // 2, 20 * S], radius=7 * S, fill=(0, 0, 0))
    img.paste(screen_img, (pad * S, pad * S))
    bw = 65
    d.rounded_rectangle([(W - bw * S) // 2, H - 9 * S, (W + bw * S) // 2, H - 4 * S], radius=2 * S, fill=(165, 165, 165))
    return img.resize((W // S, H // S), Image.LANCZOS)


def quantize_shared(frames, colors=128):
    """所有帧共享一个调色板。

    逐帧独立自适应量化（ADAPTIVE）会让每帧调色板不同，GIF 无法做帧间差分，
    导致渐变补间帧体积爆炸。共享调色板后，静态区域在帧间可复用，体积大幅下降。
    """
    rgb = [f.convert("RGB") for f in frames]
    pal_img = rgb[0].quantize(colors=colors, method=Image.Quantize.MEDIANCUT)
    return [f.quantize(palette=pal_img, dither=Image.Dither.NONE) for f in rgb]


def emit(frames, durations, name, colors=256):
    framed = [phone_frame(f) for f in frames]
    pals = quantize_shared(framed, colors)
    out = ASSETS / name
    pals[0].save(out, save_all=True, append_images=pals[1:], duration=durations,
                 loop=0, optimize=True)
    print(f"{name}: {out.stat().st_size} bytes, {len(framed)} frames")


def build(kfs, hold=950, tween=4, tdur=80, colors=128, name=""):
    """关键帧 → 补间序列并直接输出。

    在相邻关键帧之间插入 tween-1 帧交叉淡化过渡，消除"整屏跳变"的幻灯片感。
    kfs: 关键帧列表（同尺寸 RGB）
    hold: 每个关键帧停留时长(ms)
    """
    out = ASSETS / name
    for tw in (tween, 3, 2):
        frames, durs = [], []
        for i in range(len(kfs) - 1):
            frames.append(kfs[i]); durs.append(hold)
            for k in range(1, tw):
                frames.append(Image.blend(kfs[i], kfs[i + 1], ease(k / tw))); durs.append(tdur)
        frames.append(kfs[-1]); durs.append(int(hold * 1.3))
        for colors in (colors, 96, 64, 48, 32):
            pals = quantize_shared(frames, colors)
            pals[0].save(out, save_all=True, append_images=pals[1:], duration=durs, loop=0, optimize=True)
            if out.stat().st_size <= 200 * 1024 or colors == 32:
                break
        if out.stat().st_size <= 200 * 1024:
            break
    print(f"{name}: {out.stat().st_size} bytes, {len(frames)} frames (tween={tw}, {colors}c)")


def slide_tween(img_a, img_b, n=6, dx=0, dy=0):
    """带位移的过渡：A 滑出同时 B 滑入（比纯淡化更能表达"移动"）"""
    frames = []
    for i in range(1, n):
        t = ease(i / n)
        a = img_a.transform(img_a.size, Image.AFFINE,
                            (1, 0, -dx * t, 0, 1, -dy * t), resample=Image.BILINEAR)
        b = img_b.transform(img_b.size, Image.AFFINE,
                            (1, 0, dx * (1 - t), 0, 1, dy * (1 - t)), resample=Image.BILINEAR)
        frames.append(Image.blend(a, b, t))
    return frames


def retween_gif(name, tween=5, hold=1000, tdur=75, colors=96):
    """对已生成的 GIF 做补间后处理：把每帧视为关键帧，帧间插入交叉淡化过渡帧。

    用途：批量把"静态帧切换"动画升级为含过渡的真动画。
    """
    src = Image.open(ASSETS / name)
    kfs = []
    n = 0
    try:
        while True:
            src.seek(n)
            kfs.append(src.convert("RGB"))
            n += 1
    except EOFError:
        pass
    if len(kfs) < 2:
        return
    out = ASSETS / name
    # 自适应：先试多补间帧+多色，超限则降补间帧数、再降色数
    for tw in (tween, max(3, tween - 1), 3):
        frames, durs = [], []
        for i in range(len(kfs) - 1):
            frames.append(kfs[i]); durs.append(hold)
            for k in range(1, tw):
                frames.append(Image.blend(kfs[i], kfs[i + 1], ease(k / tw)))
                durs.append(tdur)
        frames.append(kfs[-1]); durs.append(int(hold * 1.4))
        for colors in (96, 64, 48, 32):
            pals = quantize_shared(frames, colors)
            pals[0].save(out, save_all=True, append_images=pals[1:], duration=durs, loop=0, optimize=True)
            if out.stat().st_size <= 200 * 1024 or colors == 32:
                break
        if out.stat().st_size <= 200 * 1024:
            break
    print(f"{name}: {out.stat().st_size} bytes, {len(frames)} frames (tween={tw}, {colors} colors)")


def ease(t):
    return t * t * (3 - 2 * t)


def ease_out(t):
    return 1 - (1 - t) ** 3


def lerp(a, b, t):
    return a + (b - a) * t
