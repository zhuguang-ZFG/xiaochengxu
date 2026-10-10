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
        for i in range(3, 0, -1):
            layer = Image.new("RGBA", self.img.size, (0, 0, 0, 0))
            ld = ImageDraw.Draw(layer)
            ld.rounded_rectangle([(box[0]-i*2)*S, (box[1]-i*2)*S, (box[2]+i*2)*S, (box[3]+i*2)*S],
                                 radius=r*S+i*2, fill=(0, 0, 0, 35))
            self.img.paste(layer, (0, 0), layer)
        self.rr(box, r, fill=fill, outline=border, w=2 if border else 1)

    def card_title(self, box, r=14, color=GREEN, title_text="", body_text=""):
        self.card(box, r, border=color)
        self.rr((box[0], box[1], box[2], box[1] + 36), r, fill=color)
        self.d.rounded_rectangle([(box[0])*S, (box[1]+20)*S, (box[2])*S, (box[1]+36)*S], fill=color)
        self.t(box[0] + 14, box[1] + 8, title_text, font_b(14), WHITE)
        if body_text:
            self.t(box[0] + 14, box[1] + 46, body_text, font(12), DARK)

    def icon_cloud(self, cx, cy, size, color):
        s = S
        self.d.ellipse([(cx-size)*s, (cy-size*0.4)*s, (cx+size*0.6)*s, (cy+size*0.4)*s], fill=color)
        self.d.ellipse([(cx-size*0.3)*s, (cy-size*0.7)*s, (cx+size)*s, (cy+size*0.3)*s], fill=color)
        self.d.rectangle([(cx-size*0.6)*s, (cy)*s, (cx+size*0.6)*s, (cy+size*0.4)*s], fill=color)

    def icon_database(self, cx, cy, size, color):
        s = S
        self.d.ellipse([(cx-size)*s, (cy-size*0.6)*s, (cx+size)*s, (cy+size*0.2)*s], fill=color)
        self.d.rectangle([(cx-size)*s, (cy-size*0.2)*s, (cx+size)*s, (cy+size*0.4)*s], fill=color)
        self.d.ellipse([(cx-size)*s, (cy+size*0.1)*s, (cx+size)*s, (cy+size*0.6)*s], fill=color)

    def icon_code(self, cx, cy, size, color):
        s = S
        self.d.line([(cx-size*0.6)*s, (cy)*s, (cx-size*0.2)*s, (cy-size*0.5)*s], fill=color, width=3*s)
        self.d.line([(cx-size*0.6)*s, (cy)*s, (cx-size*0.2)*s, (cy+size*0.5)*s], fill=color, width=3*s)
        self.d.line([(cx+size*0.6)*s, (cy)*s, (cx+size*0.2)*s, (cy-size*0.5)*s], fill=color, width=3*s)
        self.d.line([(cx+size*0.6)*s, (cy)*s, (cx+size*0.2)*s, (cy+size*0.5)*s], fill=color, width=3*s)

    def arrow(self, start, end, color, width=2):
        s = S
        self.d.line([start[0]*s, start[1]*s, end[0]*s, end[1]*s], fill=color, width=width*s)
        import math
        angle = math.atan2(end[1]-start[1], end[0]-start[0])
        sz = 10
        p1 = (end[0] - sz*math.cos(angle - 0.4), end[1] - sz*math.sin(angle - 0.4))
        p2 = (end[0] - sz*math.cos(angle + 0.4), end[1] - sz*math.sin(angle + 0.4))
        self.d.polygon([tuple(v*s for v in end), tuple(v*s for v in p1), tuple(v*s for v in p2)], fill=color)

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
    cols, cw, ch, gap_x = 3, 228, 84, 16
    pitch_x, pitch_y = cw + gap_x, ch + 12
    for i, (name, desc, col) in enumerate(comps):
        row, idx = divmod(i, cols)
        n_in_row = min(cols, len(comps) - row * cols)      # 末行可能不满 3 个
        # 不满的行整体居中：末行只有 1 个卡片时贴左，右边空一大块很难看
        cx = 40 + (cols - n_in_row) * pitch_x // 2 + idx * pitch_x
        cy = 96 + row * pitch_y
        c.card((cx, cy, cx + cw, cy + ch), border=col)
        c.t(cx + 16, cy + 12, name, font_b(17), col)
        c.t(cx + 16, cy + 48, desc, font(13), DARK)
    # 末行卡片底 468，脚注留 18px 呼吸——此前脚注写在 476，与卡片只差 8px，
    # 灰字压在白色卡片的边框上
    c.t(40, 492, "通用规则：id/class/style + data-* 传参 + bind*/catch* 事件 + 布尔值用 {{}} 包裹", font(14), GRAY)
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
             ("WXSS", ["样式语言", "CSS + rpx"], ORANGE), ("JSON", ["配置语言", "app.json 等"], PURPLE)]
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


# ============ diagram-knowledge-graph ============
def gen_knowledge_graph():
    """全局概念关系图：29 篇教学文章为节点，5 个阶段分组着色，前置关系为有向边。

    篇数由节点数推导（`sum(len(x) for …)`），不写死：此前标题手打「29 篇」而图里
    只有 27 个节点——v2.0.0 新增的多页面导航实战、商品列表实战从未进图，
    篇数与图形自此脱钩，也没人发现。
    """
    CARD_W_MIN, CARD_H = 100, 32

    layout = [
        ("① 认知", BLUE, [(40, ["认识小程序", "编程语言与技术栈"], 120, 60)]),
        ("② 准备", GREEN, [(180, ["环境准备", "项目结构"], 120, 60)]),
        ("③ 基础", ORANGE, [(320, ["WXML 数据绑定", "WXSS 与 rpx", "JS 逻辑层", "页面生命周期"], 90, 60)]),
        ("④ 进阶", PURPLE, [
            (460, ["内置组件", "自定义组件", "网络请求与数据", "性能优化", "媒体能力", "地图与定位"], 70, 48),
            (600, ["授权与隐私", "分享与订阅", "Skyline 适配", "第三方组件库", "调试与排错", "微信支付"], 70, 48),
        ]),
        ("⑤ 云开发 · 实战 · 发布", RED, [
            (740, ["云开发入门", "云函数", "云数据库", "云存储", "待办清单实战"], 70, 60),
            (880, ["多页面导航实战", "商品列表实战", "上线发布", "资源与工具"], 70, 60),
        ]),
    ]

    total = sum(len(labels) for _, _, cols in layout for _, labels, _, _ in cols)
    c = C(1010, 520)
    title(c, f"知识图谱：{total} 篇文章的概念关系")

    edges = [
        ("认识小程序", "编程语言与技术栈"), ("认识小程序", "环境准备"),
        ("编程语言与技术栈", "环境准备"), ("认识小程序", "项目结构"),
        ("环境准备", "项目结构"),
        ("项目结构", "WXML 数据绑定"), ("项目结构", "WXSS 与 rpx"), ("项目结构", "JS 逻辑层"),
        ("WXML 数据绑定", "页面生命周期"), ("WXSS 与 rpx", "页面生命周期"),
        ("JS 逻辑层", "页面生命周期"),
        ("页面生命周期", "内置组件"), ("页面生命周期", "自定义组件"),
        ("页面生命周期", "网络请求与数据"),
        ("内置组件", "性能优化"), ("自定义组件", "性能优化"), ("网络请求与数据", "性能优化"),
        ("页面生命周期", "媒体能力"), ("页面生命周期", "地图与定位"), ("页面生命周期", "授权与隐私"),
        ("授权与隐私", "分享与订阅"), ("授权与隐私", "Skyline 适配"),
        ("内置组件", "第三方组件库"), ("自定义组件", "第三方组件库"),
        ("性能优化", "调试与排错"), ("网络请求与数据", "调试与排错"),
        ("媒体能力", "微信支付"), ("网络请求与数据", "微信支付"),
        ("JS 逻辑层", "云开发入门"), ("网络请求与数据", "云开发入门"),
        ("云开发入门", "云函数"), ("云开发入门", "云数据库"), ("云开发入门", "云存储"),
        ("云函数", "待办清单实战"), ("云数据库", "待办清单实战"), ("云存储", "待办清单实战"),
        ("页面生命周期", "多页面导航实战"), ("项目结构", "多页面导航实战"),
        ("WXML 数据绑定", "商品列表实战"), ("自定义组件", "商品列表实战"),
        ("待办清单实战", "多页面导航实战"), ("待办清单实战", "商品列表实战"),
        ("多页面导航实战", "上线发布"), ("商品列表实战", "上线发布"),
        ("上线发布", "资源与工具"),
    ]

    # 先算节点位置：边要在卡片之前画，才不会被卡片盖住一段
    pos = {}
    for stage_name, col, columns in layout:
        for x, labels, y0, pitch in columns:
            for i, name in enumerate(labels):
                w = max(CARD_W_MIN, c.tw(name, font(12)) + 20)
                pos[name] = (x, y0 + i * pitch, w, CARD_H, col)

    # 边：深一档的灰 + 真箭头，两端各让出卡片宽度，起笔/收笔都不钻进卡片里
    for src, dst in edges:
        if src not in pos or dst not in pos:
            continue
        sx, sy, sw, sh, _ = pos[src]
        dx_, dy_, dw, dh, _ = pos[dst]
        x1, y1 = sx + sw / 2, sy + sh / 2
        x2, y2 = dx_ + dw / 2, dy_ + dh / 2
        dist = ((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5 or 1
        ux, uy = (x2 - x1) / dist, (y2 - y1) / dist
        c.arrow((x1 + ux * 26, y1 + uy * 26), (x2 - ux * 30, y2 - uy * 30),
                (160, 166, 180), width=2)

    # 节点：最后画，白卡片压在边上面
    for stage_name, col, columns in layout:
        for x, labels, y0, pitch in columns:
            for i, name in enumerate(labels):
                nx, ny, w, h, _ = pos[name]
                c.card((nx, ny, nx + w, ny + h), r=8, border=col)
                c.t(nx + 10, ny + 8, name, font(12), DARK)

    c.t(40, 400, "阶段分组：", font_b(14), DARK)
    legend = [("① 认知", BLUE), ("② 准备", GREEN), ("③ 基础", ORANGE), ("④ 进阶", PURPLE),
              ("⑤ 云开发、实战与发布", RED)]
    lx = 170
    for name, col in legend:
        c.d.ellipse([lx * S, 404 * S, (lx + 14) * S, 418 * S], fill=col)
        c.t(lx + 20, 400, name, font(13), DARK)
        lx += c.tw(name, font(13)) + 40
    c.t(40, 442, "箭头表示前置关系：左边/上边的文章是右边/下边文章的前置知识。按从左上到右下的顺序学习。",
        font(13), GRAY)
    c.t(40, 472, "配套：[PROGRESS.md] 跟踪学习进度 · [FAQ] 高频问答 · 每篇随堂测验自测", font(13), GRAY)
    c.save("diagram-knowledge-graph.png")


# ============ diagram-setdata-mechanism ============
def gen_setdata_mechanism():
    """setData 跨线程通信流程：逻辑层 → 序列化 → 渲染层 → diff → 更新视图。"""
    c = C(800, 520); title(c, "setData 跨线程通信机制")

    boxes = [
        (40, 100, 200, 200, "逻辑层 (JS)", BLUE, "Page.data"),
        (280, 100, 440, 200, "序列化", ORANGE, "JSON diff"),
        (520, 100, 760, 200, "渲染层 (WebView)", GREEN, "WXML 模板"),
    ]
    for x1, y1, x2, y2, name, col, sub in boxes:
        c.card((x1, y1, x2, y2), border=col)
        c.tc((x1 + x2) / 2, y1 + 20, name, font_b(16), col)
        c.tc((x1 + x2) / 2, y1 + 58, sub, font(13), DARK)

    c.d.line([200 * S, 150 * S, 280 * S, 150 * S], fill=GRAY, width=2 * S)
    c.d.polygon([(280 * S, 145 * S), (280 * S, 155 * S), (290 * S, 150 * S)], fill=GRAY)
    c.tc(240, 120, "① setData", font(12), BLUE)

    c.d.line([440 * S, 150 * S, 520 * S, 150 * S], fill=GRAY, width=2 * S)
    c.d.polygon([(520 * S, 145 * S), (520 * S, 155 * S), (530 * S, 150 * S)], fill=GRAY)
    c.tc(480, 120, "② diff 数据", font(12), ORANGE)

    c.d.line([640 * S, 200 * S, 640 * S, 260 * S], fill=GRAY, width=2 * S)
    c.d.polygon([(635 * S, 260 * S), (645 * S, 260 * S), (640 * S, 270 * S)], fill=GRAY)

    c.card((440, 270, 760, 360), border=PURPLE)
    c.tc(600, 285, "③ Virtual DOM diff", font_b(14), PURPLE)
    c.tc(600, 320, "Shadow Tree 对比变化", font(13), DARK)
    c.tc(600, 345, "最小化 DOM 操作", font(13), GRAY)

    c.card((40, 270, 360, 360), border=RED)
    c.tc(200, 285, "事件回调", font_b(14), RED)
    c.tc(200, 320, "用户交互 → bindtap 等", font(13), DARK)
    c.tc(200, 345, "事件冒泡回逻辑层", font(13), GRAY)

    c.d.line([200 * S, 270 * S, 120 * S, 200 * S], fill=GRAY, width=2 * S)
    c.d.polygon([(115 * S, 200 * S), (125 * S, 200 * S), (120 * S, 190 * S)], fill=GRAY)
    c.tc(130, 230, "④ 事件", font(12), RED)

    c.t(40, 390, "关键约束：", font_b(14), DARK)
    c.t(40, 418, "· setData 传输的是 JSON 序列化后的 diff，不是全量数据 → 数据越大越慢", font(13), DARK)
    c.t(40, 444, "· 逻辑层与渲染层运行在不同线程，通过 Native 桥接通信 → 有延迟", font(13), DARK)
    c.t(40, 470, "· 优化方向：减小 setData 数据量、合并调用、用 WXS 处理高频变化", font(13), RED)
    c.save("diagram-setdata-mechanism.png")


# ============ diagram-component-comm ============
def gen_component_comm():
    """自定义组件通信流：properties 下行、triggerEvent 上行、selectComponent 跨级。"""
    c = C(800, 520); title(c, "自定义组件通信机制")

    c.card((250, 90, 550, 180), border=BLUE)
    c.tc(400, 105, "父组件", font_b(18), BLUE)
    c.tc(400, 140, "data: { message: 'Hello' }", font(13), DARK)
    c.tc(400, 165, '<child msg="{{message}}" />', font(12), GRAY)

    c.card((250, 300, 550, 390), border=GREEN)
    c.tc(400, 315, "子组件", font_b(18), GREEN)
    c.tc(400, 350, "properties: { msg: String }", font(13), DARK)
    c.tc(400, 375, 'this.triggerEvent("change", val)', font(12), GRAY)

    c.d.line([400 * S, 180 * S, 400 * S, 300 * S], fill=BLUE, width=2 * S)
    c.d.polygon([(395 * S, 300 * S), (405 * S, 300 * S), (400 * S, 310 * S)], fill=BLUE)
    c.t(410, 220, "properties 下行", font_b(13), BLUE)
    c.t(410, 244, "父 → 子：数据传递", font(12), DARK)

    c.d.line([340 * S, 300 * S, 340 * S, 180 * S], fill=ORANGE, width=2 * S)
    c.d.polygon([(335 * S, 180 * S), (345 * S, 180 * S), (340 * S, 170 * S)], fill=ORANGE)
    c.t(200, 220, "triggerEvent 上行", font_b(13), ORANGE)
    c.t(200, 244, "子 → 父：事件通知", font(12), DARK)

    c.card((40, 420, 360, 490), border=PURPLE)
    c.t(60, 435, "跨级通信", font_b(14), PURPLE)
    c.t(60, 462, "selectComponent / EventChannel", font(12), DARK)

    c.card((440, 420, 760, 490), border=RED)
    c.t(460, 435, "避免", font_b(14), RED)
    c.t(460, 462, "子组件直接修改 properties 的值", font(12), DARK)
    c.save("diagram-component-comm.png")


# ============ diagram-request-lifecycle ============
def gen_request_lifecycle():
    """网络请求生命周期：发起 → 等待 → 响应 → 本地缓存 → 视图更新。"""
    c = C(800, 520); title(c, "网络请求生命周期")

    steps = [
        (30, 110, "发起请求", "wx.request({url})", BLUE),
        (180, 110, "网络层", "DNS → TCP → TLS", ORANGE),
        (350, 110, "服务器处理", "业务逻辑 + 响应", GREEN),
        (520, 110, "响应返回", "JSON 数据", BLUE),
        (670, 110, "setData", "更新视图", PURPLE),
    ]
    for x, y, name, sub, col in steps:
        c.card((x, y, x + 120, y + 80), border=col)
        c.tc(x + 60, y + 14, name, font_b(13), col)
        c.tc(x + 60, y + 46, sub, font(11), DARK)

    for i in range(len(steps) - 1):
        x1 = steps[i][0] + 120
        x2 = steps[i + 1][0]
        c.d.line([x1 * S, 150 * S, x2 * S, 150 * S], fill=GRAY, width=2 * S)
        c.d.polygon([(x2 * S, 145 * S), (x2 * S, 155 * S), ((x2 + 8) * S, 150 * S)], fill=GRAY)

    c.card((30, 240, 380, 370), border=ORANGE)
    c.t(50, 255, "本地缓存策略", font_b(16), ORANGE)
    c.t(50, 288, "wx.setStorageSync(key, data)", font(13), DARK)
    c.t(50, 314, "· 容量上限 10MB", font(12), GRAY)
    c.t(50, 338, "· 适合缓存用户信息、列表数据", font(12), GRAY)
    c.t(50, 358, "· 过期策略需自行实现", font(12), RED)

    c.card((420, 240, 770, 370), border=GREEN)
    c.t(440, 255, "请求优化模式", font_b(16), GREEN)
    c.t(440, 288, "先展示缓存 → 再请求刷新", font(13), DARK)
    c.t(440, 314, "· 首屏秒开（缓存兜底）", font(12), GRAY)
    c.t(440, 338, "· 下拉刷新触发新请求", font(12), GRAY)
    c.t(440, 358, "· 请求失败不阻塞体验", font(12), GRAY)

    c.t(30, 400, "错误处理：", font_b(14), RED)
    c.t(30, 428, "· fail 回调处理网络异常 · statusCode !== 200 处理业务异常 · 超时设置 timeout", font(13), DARK)
    c.t(30, 456, "· 并发请求用 Promise.all · 串行依赖用 async/await", font(13), DARK)
    c.save("diagram-request-lifecycle.png")


# ============ diagram-cloud-callchain ============
def gen_cloud_callchain():
    """云调用链路：客户端 → 云函数 → 云数据库/存储 → 响应。"""
    c = C(800, 520); title(c, "云开发调用链路")

    c.card((30, 100, 200, 200), border=BLUE)
    c.tc(115, 115, "小程序端", font_b(16), BLUE)
    c.tc(115, 150, "wx.cloud", font(13), DARK)
    c.tc(115, 175, ".callFunction()", font(12), GRAY)

    c.card((280, 100, 450, 200), border=GREEN)
    c.tc(365, 115, "云函数", font_b(16), GREEN)
    c.tc(365, 150, "Node.js 运行环境", font(13), DARK)
    c.tc(365, 175, "免鉴权 · 自动日志", font(12), GRAY)

    c.card((530, 80, 770, 160), border=ORANGE)
    c.tc(650, 95, "云数据库", font_b(14), ORANGE)
    c.tc(650, 128, "JSON 文档型 · 权限控制", font(12), DARK)

    c.card((530, 180, 770, 260), border=PURPLE)
    c.tc(650, 195, "云存储", font_b(14), PURPLE)
    c.tc(650, 228, "图片/文件 · CDN 加速", font(12), DARK)

    c.d.line([200 * S, 150 * S, 280 * S, 150 * S], fill=GRAY, width=2 * S)
    c.d.polygon([(280 * S, 145 * S), (280 * S, 155 * S), (290 * S, 150 * S)], fill=GRAY)

    c.d.line([450 * S, 130 * S, 530 * S, 120 * S], fill=GRAY, width=2 * S)
    c.d.line([450 * S, 170 * S, 530 * S, 220 * S], fill=GRAY, width=2 * S)

    c.d.line([280 * S, 160 * S, 200 * S, 160 * S], fill=GREEN, width=2 * S)
    c.d.polygon([(200 * S, 155 * S), (200 * S, 165 * S), (190 * S, 160 * S)], fill=GREEN)
    c.tc(240, 175, "返回结果", font(12), GREEN)

    c.card((30, 290, 770, 400), border=RED)
    c.t(50, 305, "安全模型", font_b(16), RED)
    c.t(50, 338, "· 客户端不能直接操作数据库（除非权限设为「所有用户可读写」）", font(13), DARK)
    c.t(50, 362, "· 云函数内 cloud.getWXContext() 拿到的 openid 是微信服务端签发的，不可伪造", font(13), DARK)
    c.t(50, 386, "· 敏感逻辑（支付/权限判断/数据聚合）一律放云函数", font(13), RED)

    c.t(30, 425, "调用计费：云函数按调用次数 + 执行时间计费；数据库按读/写次数 + 存储计费", font(13), GRAY)
    c.t(30, 452, "免费额度：每月 50 万次云函数调用 + 2GB 数据库存储 · 学习阶段足够", font(13), GRAY)
    c.save("diagram-cloud-callchain.png")


# ============ diagram-shadow-tree ============
def gen_shadow_tree():
    """Shadow Tree diff 机制：组件隔离 + 最小化 DOM 更新。"""
    c = C(800, 520); title(c, "Shadow Tree 与 diff 机制")

    c.card((30, 90, 370, 250), border=BLUE)
    c.t(50, 105, "渲染层 Shadow Tree", font_b(16), BLUE)
    c.t(50, 140, "page", font_b(13), DARK)
    c.t(70, 168, "custom-header", font(13), GREEN)
    c.t(90, 196, "#shadow-root", font(12), GRAY)
    c.t(110, 220, "<view>标题</view>", font(12), DARK)
    c.t(70, 240, "custom-list", font(13), GREEN)

    c.card((430, 90, 770, 250), border=ORANGE)
    c.t(450, 105, "diff 过程", font_b(16), ORANGE)
    c.t(450, 140, "① setData 产生新 VTree", font(13), DARK)
    c.t(450, 168, "② 与旧 VTree 逐节点对比", font(13), DARK)
    c.t(450, 196, "③ 找出最小变更集", font(13), DARK)
    c.t(450, 224, "④ 只更新变化的 DOM 节点", font(13), RED)

    c.card((30, 280, 770, 400), border=PURPLE)
    c.t(50, 295, "组件隔离的意义", font_b(16), PURPLE)
    c.t(50, 328, "· 每个自定义组件有独立的 Shadow Tree → 样式不泄漏、不冲突", font(13), DARK)
    c.t(50, 352, "· diff 范围限定在变更的组件子树内 → 避免全页重算", font(13), DARK)
    c.t(50, 376, "· 组件化越彻底，diff 粒度越细，性能越好", font(13), DARK)

    c.t(30, 425, "性能优化要点：", font_b(14), RED)
    c.t(30, 452, "· 减少 setData 频率与数据量 · 长列表用 recycle-view 或分页", font(13), DARK)
    c.t(30, 476, "· 图片懒加载 lazy-load · 避免频繁操作 DOM（用数据驱动代替）", font(13), DARK)
    c.save("diagram-shadow-tree.png")


def gen_api_capability_map():
    c = C(800, 520)
    c.t(30, 20, "wx.API 能力全景图", font_b(22), DARK)
    c.t(30, 52, "按能力域分类 · 每域标注核心 API 数量 · 详见 API 速查索引", font(13), GRAY)

    domains = [
        ("登录与身份", 4, GREEN, "login / checkSession / getUserProfile"),
        ("网络请求", 3, BLUE, "request / uploadFile / downloadFile"),
        ("数据缓存", 3, ORANGE, "setStorage / getStorage / clearStorage"),
        ("媒体能力", 5, PURPLE, "chooseImage / chooseMedia / createCameraContext"),
        ("位置与地图", 3, GREEN, "getLocation / openLocation / createMapContext"),
        ("设备能力", 4, BLUE, "getSystemInfo / scanCode / vibrateShort"),
        ("授权与隐私", 3, ORANGE, "authorize / getSetting / openSetting"),
        ("分享与订阅", 3, PURPLE, "shareAppMessage / requestSubscribeMessage"),
        ("支付", 2, GREEN, "requestPayment / 云调用统一订单"),
        ("云开发", 6, BLUE, "cloud.init / callFunction / database / uploadFile"),
    ]

    cols = 2
    card_w, card_h = 360, 72
    x_start = [30, 410]
    y_start = 85

    for i, (name, count, color, apis) in enumerate(domains):
        col = i % cols
        row = i // cols
        x = x_start[col]
        y = y_start + row * (card_h + 12)
        c.card((x, y, x + card_w, y + card_h), border=color)
        c.rr((x + 12, y + 12, x + 52, y + 42), 8, fill=color)
        c.tc(x + 32, y + 18, str(count), font_b(16), WHITE)
        c.t(x + 62, y + 14, name, font_b(14), DARK)
        c.t(x + 62, y + 40, apis, font(11), GRAY)

    c.t(30, 480, "共 10 大能力域 · 36+ 核心 API · 以基础库版本为准", font(13), GRAY)
    c.save("diagram-api-capability-map.png")


# ============ diagram-component-mechanism ============
def gen_component_mechanism():
    """组件行为设计原理：input 受控、swiper 绝对定位、scroll-view 固定高度、image 默认尺寸。"""
    c = C(800, 600); title(c, "组件行为的设计原理")

    c.card((30, 90, 380, 250), border=BLUE)
    c.t(50, 105, "input 为什么是受控组件", font_b(15), BLUE)
    c.t(50, 138, "渲染层拥有 DOM，逻辑层拥有 data", font(13), DARK)
    c.t(50, 164, "value 是从逻辑层推到渲染层的「建议值」", font(13), DARK)
    c.t(50, 190, "bindinput 里不 setData → 两层状态分叉", font(13), RED)
    c.t(50, 216, "→ 光标位置错乱、输入丢失", font(13), RED)

    c.card((420, 90, 770, 250), border=GREEN)
    c.t(440, 105, "swiper 为什么不能 auto-height", font_b(15), GREEN)
    c.t(440, 138, "swiper-item 用 position: absolute", font(13), DARK)
    c.t(440, 164, "脱离文档流 → 父容器没有内在高度", font(13), DARK)
    c.t(440, 190, "增量渲染模型：不等所有 slide 测量完", font(13), DARK)
    c.t(440, 216, "→ 必须给 swiper 设置固定高度", font(13), RED)

    c.card((30, 280, 380, 440), border=ORANGE)
    c.t(50, 295, "scroll-view 为什么必须固定高度", font_b(15), ORANGE)
    c.t(50, 328, "滚动范围 = scrollHeight - clientHeight", font(13), DARK)
    c.t(50, 354, "没有显式高度时：", font(13), DARK)
    c.t(50, 380, "clientHeight = scrollHeight → 无法滚动", font(13), RED)
    c.t(50, 406, "→ 必须给 scroll-view 设置固定高度", font(13), RED)

    c.card((420, 280, 770, 440), border=PURPLE)
    c.t(440, 295, "image 默认 320×240 的原因", font_b(15), PURPLE)
    c.t(440, 328, "向后兼容早期版本", font(13), DARK)
    c.t(440, 354, "图片加载前占位 → 防止布局偏移(CLS)", font(13), DARK)
    c.t(440, 380, "→ 实际开发中用 mode 属性控制尺寸", font(13), DARK)
    c.t(440, 406, "→ 推荐 mode=\"widthFix\" 或 mode=\"aspectFill\"", font(13), GREEN)

    c.card((30, 470, 770, 570), border=RED)
    c.t(50, 485, "设计原则", font_b(16), RED)
    c.t(50, 518, "· 组件行为由底层渲染模型决定，不是随意设计", font(13), DARK)
    c.t(50, 544, "· 理解「为什么」比记住「怎么用」更重要 → 遇到类似问题能自己推理", font(13), DARK)
    c.save("diagram-component-mechanism.png")


# ============ diagram-serverless-mechanism ============
def gen_serverless_mechanism():
    """Serverless 架构原理：身份注入、环境隔离、冷启动、量化额度。"""
    c = C(800, 620); title(c, "Serverless 架构原理")

    c.card((30, 90, 770, 230), border=BLUE)
    c.t(50, 105, "身份注入：为什么云函数天然拿到用户身份", font_b(15), BLUE)
    c.t(50, 138, "① 小程序调用 wx.cloud.callFunction()", font(13), DARK)
    c.t(50, 162, "② 微信客户端附加 access token", font(13), DARK)
    c.t(50, 186, "③ CloudBase 向微信认证服务验证 token → 注入 openid/unionid 到 context.WX_CONTEXT", font(13), DARK)
    c.t(50, 210, "→ cloud.getWXContext() 不需要换码，身份由微信客户端 SDK 担保", font(13), GREEN)

    c.card((30, 250, 380, 390), border=GREEN)
    c.t(50, 265, "环境隔离", font_b(15), GREEN)
    c.t(50, 298, "每个环境 = 独立 CloudBase 项目", font(13), DARK)
    c.t(50, 322, "· 数据库集合按环境隔离", font(13), DARK)
    c.t(50, 346, "· 云函数部署按环境隔离", font(13), DARK)
    c.t(50, 370, "· 存储桶按环境隔离", font(13), DARK)

    c.card((420, 250, 770, 390), border=ORANGE)
    c.t(440, 265, "冷启动机制", font_b(15), ORANGE)
    c.t(440, 298, "运行在临时容器中", font(13), DARK)
    c.t(440, 322, "无请求 → 容器回收", font(13), DARK)
    c.t(440, 346, "下次请求 → 容器创建 + 依赖加载", font(13), DARK)
    c.t(440, 370, "exports.main 外的代码只在冷启动执行", font(13), RED)

    c.card((30, 410, 770, 530), border=PURPLE)
    c.t(50, 425, "量化：免费额度", font_b(15), PURPLE)
    c.t(50, 458, "· 云函数：50 万次调用/月 · 数据库：2GB 存储 + 2GB/月流量", font(13), DARK)
    c.t(50, 482, "· 云存储：5GB 存储 + 5GB/月流量", font(13), DARK)
    c.t(50, 506, "→ 学习阶段完全够用；生产环境按量计费，成本可控", font(13), GREEN)

    c.t(30, 555, "安全边界：前端权限不可信，敏感逻辑一律走云函数", font_b(14), RED)
    c.t(30, 585, "冷启动优化：复用容器内变量、减少依赖包体积、预置并发", font(13), GRAY)
    c.save("diagram-serverless-mechanism.png")


# ============ diagram-wxkey-diff ============
def gen_wxkey_diff():
    """wx:key 的 diff 锚点原理：有 key vs 无 key vs *this 的对比。"""
    c = C(800, 580); title(c, "wx:key 的 diff 锚点原理")

    c.card((30, 90, 380, 310), border=GREEN)
    c.t(50, 105, "有 wx:key（正确）", font_b(15), GREEN)
    c.t(50, 138, "旧数组：[A:id1, B:id2, C:id3]", font(13), DARK)
    c.t(50, 162, "新数组：[A:id1, X:id4, B:id2, C:id3]", font(13), DARK)
    c.t(50, 192, "框架用 key 值做身份标识：", font_b(13), BLUE)
    c.t(50, 218, "· id1 → 复用（未变）", font(13), DARK)
    c.t(50, 242, "· id4 → 新增（插入）", font(13), GREEN)
    c.t(50, 266, "· id2, id3 → 复用（未变）", font(13), DARK)
    c.t(50, 290, "→ 只渲染 1 个新项，最小化 DOM 操作", font(13), GREEN)

    c.card((420, 90, 770, 310), border=RED)
    c.t(440, 105, "无 wx:key（错误）", font_b(15), RED)
    c.t(440, 138, "旧数组：[A, B, C]", font(13), DARK)
    c.t(440, 162, "新数组：[A, X, B, C]", font(13), DARK)
    c.t(440, 192, "退化为 index 对比：", font_b(13), BLUE)
    c.t(440, 218, "· index 0 → 复用（A=A）", font(13), DARK)
    c.t(440, 242, "· index 1 → 更新（B→X）", font(13), RED)
    c.t(440, 266, "· index 2 → 更新（C→B）", font(13), RED)
    c.t(440, 290, "→ 3 项全部重渲染，性能浪费", font(13), RED)

    c.card((30, 340, 770, 480), border=ORANGE)
    c.t(50, 355, "wx:key=\"*this\" 的适用场景", font_b(15), ORANGE)
    c.t(50, 388, "· *this 用值本身做 key", font(13), DARK)
    c.t(50, 412, "· 基本类型（字符串/数字）→ 可用，值相等即复用", font(13), DARK)
    c.t(50, 436, "· 对象类型 → 按引用比较，通常失败 → 不推荐", font(13), RED)
    c.t(50, 460, "→ 推荐用唯一标识字段（如 id）作为 wx:key", font(13), GREEN)

    c.card((30, 500, 770, 555), border=PURPLE)
    c.t(50, 515, "本质", font_b(14), PURPLE)
    c.t(200, 515, "wx:key 不是「最佳实践」而是「性能必需」—— 没有它，列表更新退化为全量重渲染", font(13), DARK)
    c.save("diagram-wxkey-diff.png")


if __name__ == "__main__":
    gen_compare(); gen_cloud(); gen_resources(); gen_path(); gen_components(); gen_languages()
    gen_knowledge_graph()
    gen_setdata_mechanism(); gen_component_comm(); gen_request_lifecycle()
    gen_cloud_callchain(); gen_shadow_tree()
    gen_api_capability_map()
    gen_component_mechanism(); gen_serverless_mechanism(); gen_wxkey_diff()
    print("概念图生成完成")
