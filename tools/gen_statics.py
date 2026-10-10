# -*- coding: utf-8 -*-
"""静态图生成：hero 横幅、实物风格界面图、概念示意图。
与 gen_animations.py 共用 tools/render.py 的超采样管线，保证视觉一致。"""
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from PIL import Image, ImageDraw  # noqa: E402
from render import (  # noqa: E402
    ASSETS, phone_frame, ease,
    GREEN, GREEN_DARK, BG, WHITE, DARK, GRAY, GRAY_L, RED, BLUE, ORANGE, PURPLE, NAV_BG, S,
    font, font_b, new_screen, status_bar, nav_bar, card, rrect, txt, text_w, text_c, shadow,
)


def hi_canvas(w, h, bg=(243, 244, 246)):
    """高分辨率画布：逻辑尺寸 w×h，内部 2x 渲染"""
    img = Image.new("RGB", (w * S, h * S), bg)
    return img, ImageDraw.Draw(img)


def save_hi(img, w, h, name):
    out = ASSETS / name
    img.resize((w, h), Image.LANCZOS).save(out, optimize=True)
    print(f"{name}: {out.stat().st_size} bytes")


# ============ hero-knowledge.png ============
def gen_hero():
    W, H = 1000, 420
    img, d = hi_canvas(W, H, (236, 250, 242))
    def rr(box, r, fill=None, outline=None, w=1):
        d.rounded_rectangle([v * S for v in box], radius=r * S, fill=fill, outline=outline, width=w * S)
    def t(xy, s, f, fill):
        d.text((xy[0] * S, xy[1] * S), s, font=f, fill=fill)

    t((56, 56), "小程序开发之路", font_b(40), DARK)
    t((58, 122), "仿「通往 AGI 之路」知识库模式 · 开源共建", font(18), GRAY)
    t((58, 158), "从认识小程序到上线发布，一条人人都能走的路", font(18), GRAY)
    stages = [("① 认知", BLUE), ("② 准备", GREEN), ("③ 基础", ORANGE), ("④ 进阶", PURPLE), ("⑤ 实战与发布", RED)]
    x = 58
    for name, col in stages:
        w = text_w(d, name, font(14)) + 26
        rr((x, 238, x + w, 284), 23, fill=col)
        d.text(((x + 13) * S, 250 * S), name, font=font(14), fill=WHITE)
        x += w + 12
    # 左下角原本空到画布底（chips 结束于 284，画布高 420）——用一行真实统计补上。
    # 数字从仓库里数出来，别拍脑袋：29 篇教学文章、121 道随堂测验、13 集视频、3 个示例工程。
    stats = [("29", "篇教程"), ("121", "道随堂测验"), ("13", "集视频"), ("3", "个示例工程")]
    sx = 58
    for num, label in stats:
        t((sx, 322), num, font_b(24), GREEN_DARK)
        sx += int(text_w(d, num, font_b(24))) + 6
        t((sx, 330), label, font(13), GRAY)
        sx += int(text_w(d, label, font(13))) + 26
    # 右侧手机（复用动画管线的高保真手机框）
    sw, sh = new_screen()
    sd = ImageDraw.Draw(sw)
    status_bar(sd)
    nav_bar(sd, "待办清单")
    rrect(sd, (24, 108, 240, 160), 12, outline=(225, 225, 228), width=2)
    txt(sd, (40, 122), "输入待办事项…", font(13), GRAY)
    rrect(sd, (256, 108, 351, 160), 12, fill=GREEN)
    text_c(sd, 303, 122, "添加", font(13), WHITE)
    for i, (tx, done) in enumerate([("学习 WXML", True), ("学习 WXSS", False), ("完成实战项目", False)]):
        y = 200 + i * 80
        card(sd, (24, y, 351, y + 66), 12)
        if done:
            sd.ellipse([42 * S, (y + 22) * S, 62 * S, (y + 42) * S], fill=GREEN)
        else:
            sd.ellipse([42 * S, (y + 22) * S, 62 * S, (y + 42) * S], outline=GREEN, width=S)
        txt(sd, (78, y + 22), tx, font(14), GRAY if done else DARK)
    ph = phone_frame(sw)                    # 已是 1x（降采样后）
    ph = ph.resize((ph.width * S, ph.height * S), Image.LANCZOS)  # 放回 2x 与画布同尺度
    px = W - ph.width // S - 6
    img.paste(ph, (px * S, ((H - ph.height // S) // 2) * S))
    save_hi(img, W, H, "hero-knowledge.png")


# ============ screen-hello.png / screen-todo.png ============
def gen_screens():
    # hello
    sw, sd = new_screen()
    status_bar(sd)
    nav_bar(sd, "我的小程序")
    text_c(sd, 187, 280, "Hello, 小程序!", font_b(26), GREEN)
    text_c(sd, 187, 340, "data.message → {{message}}", font(13), GRAY)
    rrect(sd, (110, 430, 265, 486), 12, fill=GREEN)
    text_c(sd, 187, 444, "编译", font_b(15), WHITE)
    save_hi(phone_frame(sw).resize((phone_frame(sw).width * S, phone_frame(sw).height * S), Image.LANCZOS),
            427, 729, "screen-hello.png")

    # todo
    sw, sd = new_screen()
    status_bar(sd)
    nav_bar(sd, "待办清单")
    rrect(sd, (24, 108, 240, 160), 12, outline=(225, 225, 228), width=2)
    txt(sd, (40, 122), "输入待办事项…", font(13), GRAY)
    rrect(sd, (256, 108, 351, 160), 12, fill=GREEN)
    text_c(sd, 303, 122, "添加", font(13), WHITE)
    for i, (name, active) in enumerate([("全部", True), ("未完成", False), ("已完成", False)]):
        txt(sd, (28 + i * 76, 180), name, font(13), GREEN if active else GRAY)
    y = 224
    for tx, done in [("学习 WXML 数据绑定", True), ("学习 WXSS 与 rpx", False), ("完成待办实战项目", False)]:
        card(sd, (24, y, 351, y + 66), 12)
        if done:
            sd.ellipse([42 * S, (y + 22) * S, 62 * S, (y + 42) * S], fill=GREEN)
            sd.line([47 * S, (y + 32) * S, 51 * S, (y + 37) * S], fill=WHITE, width=2 * S)
            sd.line([51 * S, (y + 37) * S, 58 * S, (y + 27) * S], fill=WHITE, width=2 * S)
        else:
            sd.ellipse([42 * S, (y + 22) * S, 62 * S, (y + 42) * S], outline=GREEN, width=S)
        txt(sd, (78, y + 22), tx, font(14), GRAY if done else DARK)
        txt(sd, (298, y + 22), "删除", font(12), RED)
        y += 80
    pf = phone_frame(sw)
    save_hi(pf.resize((pf.width * S, pf.height * S), Image.LANCZOS), 427, 729, "screen-todo.png")


if __name__ == "__main__":
    gen_hero()
    gen_screens()
    print("静态图生成完成（diagram-* 见 gen_diagrams.py）")
