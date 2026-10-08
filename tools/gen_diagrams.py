# -*- coding: utf-8 -*-
"""概念示意图生成（2x 超采样，与动画管线视觉一致）。"""
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from PIL import Image, ImageDraw  # noqa: E402
from render import (  # noqa: E402
    ASSETS, font, font_b, S,
    GREEN, BG, WHITE, DARK, GRAY, GRAY_L, RED, BLUE, ORANGE, PURPLE,
)


class C:
    """逻辑坐标 2x 画布"""
    def __init__(self, w, h, bg=(243, 244, 246)):
        self.w, self.h = w, h
        self.img = Image.new("RGB", (w * S, h * S), bg)
        self.d = ImageDraw.Draw(self.img)

    def t(self, x, y, s, f, fill):
        self.d.text((x * S, y * S), s, font=f, fill=fill)

    def tc(self, cx, y, s, f, fill):
        w = self.d.textlength(s, font=f) / S
        self.d.text(((cx - w / 2) * S, y * S), s, font=f, fill=fill)

    def rr(self, box, r, fill=None, outline=None, w=1):
        self.d.rounded_rectangle([v * S for v in box], radius=r * S, fill=fill, outline=outline, width=w * S)

    def card(self, box, r=14, border=None, fill=WHITE):
        for i in range(2, 0, -1):
            layer = Image.new("RGBA", self.img.size, (0, 0, 0, 0))
            ld = ImageDraw.Draw(layer)
            ld.rounded_rectangle([(box[0]-i*2)*S, (box[1]-i*2)*S, (box[2]+i*2)*S, (box[3]+i*2)*S],
                                 radius=r*S+i*2, fill=(0, 0, 0, 20))
            self.img.paste(layer, (0, 0), layer)
        self.rr(box, r, fill=fill, outline=border, w=2 if border else 1)

    def tw(self, s, f):
        return self.d.textlength(s, font=f) / S

    def save(self, name):
        out = ASSETS / name
        self.img.resize((self.w, self.h), Image.LANCZOS).save(out, optimize=True)
        print(f"{name}: {out.stat().st_size} bytes")


def title(c, s):
    c.tc(c.w / 2, 22, s, font_b(26), DARK)


# ============ diagram-compare ============
def gen_compare():
    c = C(800, 520); title(c, "三种应用形态对比")
    cols = [("H5 网页", BLUE, ["入口：浏览器/链接", "无需安装", "能力：浏览器 API", "无微信生态能力"]),
            ("微信小程序", GREEN, ["入口：微信内扫码/搜索", "即点即用", "登录/支付/地图原生能力", "需微信审核上线"]),
            ("原生 App", ORANGE, ["入口：应用商店下载", "安装到桌面", "系统级能力全开放", "双端开发成本高"])]
    x = 36
    for name, col, items in cols:
        c.card((x, 96, x + 226, 420), border=col)
        c.t(x + 20, 116, name, font_b(18), col)
        y = 168
        for it in items:
            c.d.ellipse([(x + 20) * S, (y + 6) * S, (x + 32) * S, (y + 18) * S], fill=col)
            c.t(x + 44, y, it, font(14), DARK)
            y += 56
        x += 250
    c.t(36, 448, "选择依据：入口在微信内、需要微信身份/支付 → 小程序；需要 SEO → H5；需要系统级能力 → 原生", font(14), GRAY)
    c.save("diagram-compare.png")


# ============ diagram-cloud ============
def gen_cloud():
    c = C(800, 520); title(c, "云开发能力全景")
    c.card((300, 120, 500, 196), border=BLUE)
    c.tc(400, 138, "小程序端", font_b(18), BLUE)
    c.tc(400, 170, "wx.cloud.* API", font(13), GRAY)
    caps = [(80, 280, "云函数", "后端逻辑/聚合", GREEN), (260, 280, "云数据库", "结构化数据", ORANGE),
            (440, 280, "云存储", "图片/音视频", BLUE), (620, 280, "云托管", "容器化服务", PURPLE)]
    for x, y, name, sub, col in caps:
        c.card((x, y, x + 170, y + 118), border=col)
        c.t(x + 24, y + 24, name, font_b(18), col)
        c.t(x + 24, y + 64, sub, font(14), DARK)
        c.d.line([400 * S, 196 * S, (x + 85) * S, y * S], fill=GRAY_L, width=2 * S)
    c.t(36, 440, "统一身份：cloud.getWXContext() 免鉴权拿 openid · 免运维 · 按调用计费", font(14), GRAY)
    c.t(36, 468, "免费额度学习够用；敏感逻辑一律走云函数（前端权限不可信）", font(14), RED)
    c.save("diagram-cloud.png")


# ============ diagram-resources ============
def gen_resources():
    c = C(800, 520); title(c, "学习资源导航")
    layers = [("官方文档（第一优先级）", BLUE, ["小程序开发指南", "组件文档 · API 文档", "云开发文档", "运营规范"]),
              ("社区提问", GREEN, ["微信开放社区（官方答疑）", "掘金 / CSDN（报错解法）", "GitHub 开源项目"]),
              ("工具链", ORANGE, ["微信开发者工具", "miniprogram-ci（CI/CD）", "云开发控制台"])]
    y = 110
    for name, col, items in layers:
        c.card((60, y, 740, y + 108), border=col)
        c.t(84, y + 18, name, font_b(18), col)
        xs = 84
        for it in items:
            w = max(150, c.tw(it, font(13)) + 20)
            c.rr((xs, y + 56, xs + w, y + 94), 8, fill=(250, 250, 252), outline=GRAY_L)
            c.t(xs + 10, y + 66, it, font(13), DARK)
            xs += w + 14
        y += 132
    c.t(60, 478, "提问四要素：报错信息 + 基础库版本 + 机型 + 复现步骤", font(14), RED)
    c.save("diagram-resources.png")


# ============ diagram-path ============
def gen_path():
    c = C(800, 520); title(c, "五阶段学习路径")
    stages = [("① 认知", "小程序是什么", BLUE), ("② 准备", "环境与项目结构", GREEN),
              ("③ 基础", "WXML/WXSS/JS/生命周期", ORANGE), ("④ 进阶", "组件/网络/数据/性能", PURPLE),
              ("⑤ 实战与发布", "云开发 → 上线", RED)]
    y = 118
    for i, (name, sub, col) in enumerate(stages):
        bw = 340 + i * 56
        bx = (c.w - bw) / 2
        c.card((bx, y, bx + bw, y + 66), border=col)
        c.d.ellipse([(bx + 16) * S, (y + 21) * S, (bx + 44) * S, (y + 49) * S], fill=col)
        c.tc(bx + 30, y + 27, str(i + 1), font_b(14), WHITE)
        c.t(bx + 60, y + 14, name, font_b(18), col)
        c.t(bx + 60, y + 44, sub, font(14), GRAY)
        y += 78
    c.save("diagram-path.png")


# ============ diagram-components ============
def gen_components():
    c = C(800, 520); title(c, "高频内置组件速查")
    comps = [("view", "布局容器", BLUE), ("text", "文本/可复制", GREEN), ("button", "按钮/open-type", ORANGE),
             ("input", "输入框", GREEN), ("image", "图片/懒加载", BLUE), ("swiper", "轮播", PURPLE),
             ("scroll-view", "滚动/加载更多", RED), ("navigator", "页面跳转", BLUE), ("rich-text", "富文本", ORANGE),
             ("web-view", "嵌 H5", PURPLE)]
    for i, (name, desc, col) in enumerate(comps):
        cx = 40 + (i % 3) * 244
        cy = 96 + (i // 3) * 100
        c.card((cx, cy, cx + 228, cy + 88), border=col)
        c.t(cx + 16, cy + 14, name, font_b(17), col)
        c.t(cx + 16, cy + 50, desc, font(13), DARK)
    c.t(40, 476, "通用规则：id/class/style + data-* 传参 + bind*/catch* 事件 + 布尔值用 {{}} 包裹", font(14), GRAY)
    c.save("diagram-components.png")


# ============ diagram-languages ============
def gen_languages():
    c = C(800, 520); title(c, "小程序技术栈：四种语言")
    c.t(36, 74, "双线程架构", font_b(17), DARK)
    c.card((36, 104, 386, 190), border=BLUE)
    c.t(54, 118, "逻辑层 AppService", font(14), BLUE)
    c.t(54, 148, "JavaScript（Page/App/setData）", font(14), DARK)
    c.card((414, 104, 764, 190), border=GREEN)
    c.t(432, 118, "渲染层 WebView / Skyline", font(14), GREEN)
    c.t(432, 148, "WXML + WXSS 声明式模板", font(14), DARK)
    c.d.line([386 * S, 147 * S, 414 * S, 147 * S], fill=GRAY, width=2 * S)
    c.tc(400, 100, "setData ⇄ 事件", font(12), GRAY)
    langs = [("JavaScript", ["逻辑层主力", "ES6+ · 数据驱动"], BLUE), ("WXML", ["视图模板", "类 HTML + {{}}"], GREEN),
             ("WXSS", ["样式语言", "CSS + rpx"], PURPLE), ("JSON", ["配置语言", "app.json 等"], PURPLE)]
    x = 36
    for name, sub, col in langs:
        c.card((x, 228, x + 173, 400), border=col)
        c.t(x + 20, 246, name, font_b(17), col)
        for i, ln in enumerate(sub):
            c.t(x + 20, 300 + i * 34, ln, font(13), DARK)
        x += 187
    c.t(36, 428, "协作：JS 定义 data → setData 推给 WXML → WXSS 上样式 → JSON 声明页面", font(14), GRAY)
    c.t(36, 458, "进阶可选：TypeScript（类型）、WXS（视图层脚本）、云函数 Node.js", font(14), GRAY)
    c.save("diagram-languages.png")


if __name__ == "__main__":
    gen_compare(); gen_cloud(); gen_resources(); gen_path(); gen_components(); gen_languages()
    print("概念图生成完成")
