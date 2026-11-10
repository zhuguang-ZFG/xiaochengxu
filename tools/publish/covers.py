# -*- coding: utf-8 -*-
"""封面生成：一套内容导出三种比例。

平台比例为经验值（各自官方未公开像素规范，见评估报告第五节）：
  - 16:9  1920x1080  B站
  - 9:16  1080x1920  抖音
  - 3:4   1080x1440  小红书（发现页信息流就是 3:4）

版式不裁切竖屏画面，而是按每种比例**重新排版**——把同一条竖屏画面居中塞进
16:9 会空掉六成面积，那是"加黑边"，不是封面。
"""
from __future__ import annotations

import pathlib
import sys

from PIL import Image

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import scenes as S  # noqa: E402

RATIOS = {
    "16x9": (1920, 1080),
    "9x16": (1080, 1920),
    "3x4": (1080, 1440),
}


def _canvas(w, h):
    ramp = Image.new("RGB", (1, h))
    for y in range(h):
        t = y / max(1, h - 1)
        ramp.putpixel((0, y), tuple(int(S.BG[i] + (S.BG2[i] - S.BG[i]) * t) for i in range(3)))
    return ramp.resize((w, h), Image.NEAREST).convert("RGBA")


def make_cover(ep, ratio):
    """ep = EPISODE 字典；ratio ∈ RATIOS"""
    w, h = RATIOS[ratio]
    img = _canvas(w, h)
    c = S.Canvas(img, 1)
    pad = int(min(w, h) * 0.075)

    # 左上：系列名 + 集号
    c.text(pad, pad, "小程序开发之路", int(h * 0.030), S.DIM)
    label = f"第 {ep['id']} 集"
    lw = S.text_w(label, int(h * 0.030)) / 1
    c.rrect((w - pad - lw - int(h * 0.030), pad - 6, w - pad, pad + int(h * 0.048)),
            int(h * 0.022), fill=S.GREEN_D)
    c.text(w - pad - lw - int(h * 0.015), pad, label, int(h * 0.030), S.GREEN)

    # 主标题：按宽度自适应字号，最多两行
    title = ep["title"]
    size = int(h * 0.115)
    while size > int(h * 0.05) and S.text_w(title, size) / 1 > w - pad * 2:
        size -= 2
    c.text(pad, int(h * 0.215), title, size, S.TEXT, True)

    # 副标题
    sub = ep.get("cover_sub", "")
    ssize = int(h * 0.042)
    while ssize > int(h * 0.026) and S.text_w(sub, ssize) / 1 > w - pad * 2:
        ssize -= 1
    c.text(pad, int(h * 0.215) + size + int(h * 0.045), sub, ssize, S.GREEN, True)

    # 三条钩子：从第一段 points 取，没有就用固定句。逐个缩到放得下为止——
    # 封面文字超宽会被平台裁掉，而裁掉的是「它是什么」这种关键信息。
    hooks = []
    seg0 = ep["segments"][0]["scene"]
    for s in seg0.get("points", [])[:3]:
        hooks.append(s)
    if not hooks:
        hooks = ["它是什么 · 和谁比 · 什么时候该用"]
    hy = int(h * 0.60)
    avail = w - pad * 2 - 32
    for i, hk in enumerate(hooks[:3]):
        hs = int(h * 0.032)
        while hs > int(h * 0.018) and S.text_w(hk, hs) / 1 > avail:
            hs -= 1
        y = hy + i * int(h * 0.075)
        c.rrect((pad, y, pad + 8, y + int(h * 0.040)), 4, fill=S.GREEN)
        c.text(pad + 24, y, hk, hs, S.MUTED)

    # 底部色带：本集关键词
    band_top = h - int(h * 0.115)
    c.rect((0, band_top, w, h), (12, 14, 20))
    c.rect((0, band_top, w, band_top + 3), S.GREEN)
    c.text(pad, band_top + int(h * 0.032), "零基础 · 原生开发 · 代码可复现", int(h * 0.030), S.DIM)

    # 右下装饰：三条渐隐竖线（避开文字）
    for i in range(3):
        x = w - pad - 10 - i * 16
        c.rrect((x, int(h * 0.14), x + 6, int(h * 0.14) + int(h * 0.14)),
                3, fill=S.GREEN + (70 - i * 20,))
    return img.convert("RGB")


def check_cover(img, ratio):
    """封面自检：**正文**不许贴边（平台会裁边）。

    阈值取 150 而不是 120：底部满幅色带与绿色分隔线（亮度 ~124）是刻意设计，
    真正怕被裁掉的是白字（~246）和灰字（~157）。只盯这两类，检查才不是噪音。
    """
    import numpy as np
    a = np.asarray(img.convert("L"))
    h, w = a.shape
    lit = a > 150
    if not lit.any():
        return [f"{ratio}: 整张是黑的"]
    ys, xs = np.where(lit)
    margin = int(min(w, h) * 0.02)
    bad = []
    if xs.min() < margin or ys.min() < margin:
        bad.append(f"{ratio}: 文字贴边 x0={xs.min()} y0={ys.min()} (margin {margin})")
    if xs.max() > w - margin or ys.max() > h - margin:
        bad.append(f"{ratio}: 文字贴边 x1={xs.max()}/{w} y1={ys.max()}/{h}")
    return bad


def write_covers(ep, out_dir: pathlib.Path, log=print):
    out_dir.mkdir(parents=True, exist_ok=True)
    made, bad = [], []
    for ratio in RATIOS:
        img = make_cover(ep, ratio)
        bad += [f"ep{ep['id']} {b}" for b in check_cover(img, ratio)]
        p = out_dir / f"ep{ep['id']}-cover-{ratio}.png"
        img.save(p, "PNG", compress_level=9)
        made.append(p)
        log(f"  封面 {p.name}  {img.width}x{img.height}  {p.stat().st_size // 1024} KB")
    return made, bad
