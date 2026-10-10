# -*- coding: utf-8 -*-
"""动画生成：每个动画由关键帧+补间帧构成，含转场/滚动/波纹过渡。"""
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from PIL import Image, ImageDraw, ImageEnhance  # noqa: E402
from render import (  # noqa: E402
    new_screen, rrect, txt, text_w, text_c, status_bar, nav_bar, card, ripple,
    emit, build, retween_gif, ease, ease_out, ease_spring, lerp, font, font_b, font_mono, shadow,
    GREEN, GREEN_DARK, BG, WHITE, DARK, GRAY, GRAY_L, RED, BLUE, ORANGE, PURPLE, NAV_BG, S, SW, SH,
)


# ============ demo-setdata：setData 数据流 ============
def anim_setdata():
    def frame(roll, count, pressed, rip, label):
        img, d = new_screen(); status_bar(d); nav_bar(d, "数据绑定演示")
        f = font_b(52)
        d.text(((375 - text_w(d, str(count), f)) / 2 * S, (300 + (1 - roll) * 18) * S),
               str(count), font=f, fill=GREEN)
        if label:
            for i, (s, c) in enumerate([(f"this.setData({{ count: {count} }})", GRAY),
                                        ("→ 视图层 diff 更新", GREEN)]):
                text_c(d, 375 / 2, 390 + i * 22, s, font(13), c)
        rrect(d, (120, 460, 255, 510), 12, fill=GREEN if not pressed else GREEN_DARK)
        f2 = font_b(15)
        text_c(d, 187.5, 474, "count + 1", f2, WHITE)
        if rip >= 0:
            ripple(img, 187.5, 485, rip)
        return img

    frames, durs = [], []
    def press(n):
        for i in range(5):
            frames.append(frame(1, n, i < 2, i / 4, True)); durs.append(45)
    def roll(a, b):
        for i in range(7):
            t = i / 6
            frames.append(frame(t, a if i < 3 else b, False, -1, True)); durs.append(60)

    frames.append(frame(1, 0, False, -1, False)); durs.append(600)
    press(0); roll(0, 1)
    frames.append(frame(1, 1, False, -1, True)); durs.append(650)
    press(1); roll(1, 2)
    frames.append(frame(1, 2, False, -1, True)); durs.append(650)
    press(2); roll(2, 3)
    frames.append(frame(1, 3, False, -1, True)); durs.append(1000)
    emit(frames, durs, "demo-setdata.gif")


# ============ demo-lifecycle：页面转场 ============
def anim_lifecycle():
    def page(letter, title, slide=0.0, yes=None):
        img, d = new_screen(); status_bar(d); nav_bar(d, title, back=(letter == "B"))
        col = GREEN if letter == "A" else ORANGE
        off = slide * 375 * S
        f = font_b(36)
        d.text(((375 - text_w(d, f"页面 {letter}", f)) / 2 * S + off, 320 * S),
               f"页面 {letter}", font=f, fill=col)
        if yes:
            y = 470
            for label, active in yes:
                card(d, (24, y, 351, y + 44), 10, fill=WHITE if active else (250, 250, 250))
                if active:
                    d.ellipse([36 * S, (y + 14) * S, 52 * S, (y + 30) * S], fill=GREEN)
                else:
                    d.ellipse([36 * S, (y + 14) * S, 52 * S, (y + 30) * S], outline=GRAY, width=S)
                txt(d, (64, y + 12), label, font(13), DARK if active else GRAY)
                y += 54
        return img

    frames, durs = [], []
    base = [("onLoad(query)", 0), ("onShow", 0), ("onReady", 0)]
    for i in range(12):
        n = min(3, i // 4 + 1)
        frames.append(page("A", "首页 A", 0, [(l, j < n) for j, (l, _) in enumerate(base)]))
        durs.append(120)
    for i in range(8):  # A 出、B 入
        t = ease(i / 7)
        a = page("A", "首页 A", t)
        a.paste(page("B", "详情页 B", 1 - t), (0, 0))
        frames.append(a); durs.append(60)
    for i in range(9):  # B 生命周期
        n = min(3, i // 3 + 1)
        frames.append(page("B", "详情页 B", 0, [("onHide ← A", n >= 1), ("onLoad(query)", n >= 2), ("onShow", n >= 3)]))
        durs.append(110)
    for i in range(8):  # B 出、A 入
        t = ease(i / 7)
        b = page("B", "详情页 B", t)
        b.paste(page("A", "首页 A", 1 - t), (0, 0))
        frames.append(b); durs.append(60)
    for i in range(8):  # A 返回 + 卸载
        n = min(2, i // 4 + 1)
        frames.append(page("A", "首页 A", 0, [("onShow（返回）", n >= 1), ("onUnload", n >= 2)]))
        durs.append(130)
    frames.append(frames[-1]); durs.append(800)
    emit(frames, durs, "demo-lifecycle.gif")


# ============ demo-wxfor：逐条插入 ============
def anim_wxfor():
    ITEMS = ["学习 WXML 数据绑定", "学习 WXSS 与 rpx", "写一个待办 demo"]
    def frame(n, offsets, header="data: todos 数组（JS）"):
        img, d = new_screen(); status_bar(d); nav_bar(d, "wx:for 列表渲染")
        txt(d, (24, 108), header, font(13), GRAY)
        for i in range(n):
            y = 170 + i * 80 + offsets.get(i, 0)
            card(d, (24, y, 351, y + 62), 12)
            d.ellipse([40 * S, (y + 18) * S, 62 * S, (y + 40) * S], fill=GREEN)
            f = font_b(15)
            text_c(d, 51, y + 22, str(i + 1), f, WHITE)
            txt(d, (78, y + 20), ITEMS[i], font(15), DARK)
        return img

    frames, durs = [], []
    for n in range(1, 4):
        for i in range(7):
            t = ease_out(i / 6)
            offs = {n - 1: 40 * (1 - t)}
            for k in range(n - 1):
                offs[k] = -4 * (1 - t)
            frames.append(frame(n, offs)); durs.append(55)
        frames.append(frame(n, {})); durs.append(430)
    frames.append(frame(3, {}, "数组变化 → 视图自动更新（按 wx:key 复用节点）")); durs.append(900)
    emit(frames, durs, "demo-wxfor.gif", colors=64)


# ============ demo-ifhidden：条件渲染对比 ============
def anim_ifhidden():
    def frame(show, if_on, hid_on):
        img, d = new_screen(); status_bar(d); nav_bar(d, "wx:if 与 hidden")
        # 左栏 wx:if
        card(d, (24, 110, 179, 400), 12)
        txt(d, (36, 122), 'wx:if="{{show}}"', font(13), BLUE)
        if if_on:
            rrect(d, (36, 160, 167, 240), 10, fill=(230, 240, 255))
            txt(d, (46, 176), "节点渲染", font(14), BLUE)
            txt(d, (46, 200), f"show={str(show).lower()}", font(13), DARK)
        else:
            txt(d, (40, 290), "节点销毁", font(13), RED)
            txt(d, (40, 312), "不在 DOM 中", font(13), RED)
        # 右栏 hidden
        card(d, (196, 110, 351, 400), 12)
        txt(d, (208, 122), 'hidden="{{!show}}"', font(13), GREEN)
        if hid_on:
            rrect(d, (208, 160, 339, 240), 10, fill=(235, 255, 240))
            txt(d, (218, 176), "节点渲染", font(14), GREEN)
            txt(d, (218, 200), f"show={str(show).lower()}", font(13), DARK)
        else:
            rrect(d, (208, 160, 339, 240), 10, outline=GRAY, width=2)
            txt(d, (218, 176), "节点仍在 DOM", font(14), GRAY)
            txt(d, (218, 200), "display: none", font(13), GRAY)
        return img

    frames, durs = [], []
    frames.append(frame(True, True, True)); durs.append(1300)
    frames.append(frame(False, False, True)); durs.append(1100)
    frames.append(frame(False, False, False)); durs.append(1100)
    img, d = new_screen(); status_bar(d); nav_bar(d, "wx:if 与 hidden")
    txt(d, (36, 130), "切换不频繁 → wx:if（销毁重建）", font(15), BLUE)
    txt(d, (36, 180), "频繁切换 → hidden（仅隐藏）", font(15), GREEN)
    txt(d, (36, 240), "hidden 内放重组件仍会初始化", font(14), RED)
    frames.append(img); durs.append(1600)
    emit(frames, durs, "demo-ifhidden.gif")


# ============ demo-event：事件冒泡 ============
def anim_event():
    def frame(lit, note, catch=False):
        img, d = new_screen(); status_bar(d); nav_bar(d, "事件冒泡")
        card(d, (40, 120, 335, 400), 14, border=GREEN if lit == 0 else None)
        txt(d, (56, 134), '外层 bindtap="onOuter"', font(13), DARK)
        card(d, (80, 180, 295, 350), 12, fill=(240, 240, 245), border=GREEN if lit == 1 else None)
        txt(d, (96, 194), "中层 view", font(13), DARK)
        rrect(d, (130, 240, 245, 310), 10, fill=(230, 240, 255),
              outline=GREEN if lit == 2 else None, width=2)
        txt(d, (146, 254), "内层 view", font(13), BLUE)
        txt(d, (40, 424), note, font(14), GREEN if not catch else RED)
        card(d, (40, 480, 335, 545), 12)
        txt(d, (56, 494), "catchtap 阻止冒泡", font(13), RED)
        txt(d, (56, 518), "点内层 → 不外传", font(13), DARK)
        return img

    frames, durs = [], []
    for lit, note in [(None, "点击内层（bindtap）"), (2, "内层处理 target"),
                      (1, "冒泡 ↑ 到中层"), (0, "冒泡 ↑ 到外层 onOuter")]:
        frames.append(frame(lit, note)); durs.append(1000)
    frames.append(frame(2, "catchtap：外层不触发", catch=True)); durs.append(1400)
    emit(frames, durs, "demo-event.gif")


# ============ demo-component：组件通信 ============
def anim_component():
    def frame(phase):
        img, d = new_screen(); status_bar(d); nav_bar(d, "自定义组件通信")
        txt(d, (28, 106), "页面（父）", font(13), GRAY)
        card(d, (28, 140, 347, 214), 14, border=BLUE if phase in (0, 3) else None)
        txt(d, (46, 154), "<todo-item>", font(14), BLUE)
        txt(d, (46, 180), "text / done（properties）", font(13), DARK)
        card(d, (56, 250, 319, 322), 14, border=GREEN if phase in (1, 2) else None)
        txt(d, (74, 262), "组件（子）", font(13), GRAY)
        d.ellipse([74 * S, 292 * S, 92 * S, 310 * S], outline=GREEN, width=S)
        txt(d, (106, 288), "学习云数据库", font(14), DARK)
        arrows = {0: ("↓ properties 传参", BLUE), 1: ("● 点击组件", GREEN),
                  2: ("↑ triggerEvent('toggle')", GREEN), 3: ("↓ e.detail 回调页面", BLUE)}
        s, c = arrows[phase]
        text_c(d, 187, 228 if phase == 0 else 340, s, font(13), c)
        if phase == 3:
            card(d, (28, 400, 347, 456), 12)
            txt(d, (46, 414), "页面 onToggle(e) → setData 更新", font(13), BLUE)
        return img

    frames, durs = [], []
    for ph in range(4):
        frames.append(frame(ph)); durs.append(1200 if ph == 0 else 950)
    emit(frames, durs, "demo-component.gif")


# ============ demo-rpx：响应式 ============
def anim_rpx():
    def frame(phase):
        img, d = new_screen(); status_bar(d); nav_bar(d, "rpx 响应式单位")
        if phase in (0, 1):
            w = 375 if phase == 0 else 390
            txt(d, (28, 120), f"机型逻辑宽 {w}px", font(14), DARK)
            rrect(d, (28, 160, 347, 200), 8, fill=GREEN)
            txt(d, (60, 168), f"width: 750rpx = {w}px", font(13), WHITE)
            txt(d, (28, 220), f"1px ≈ {750/w:.2f}rpx", font(13), GRAY)
            txt(d, (28, 250), "元素始终铺满整屏宽", font(14), DARK)
        else:
            txt(d, (28, 120), "同一套代码，两种机型", font(14), DARK)
            for i, (x, w) in enumerate([(28, 150), (205, 152)]):
                rrect(d, (x, 160, x + w, 195), 6, fill=GREEN)
                f = font(12)
                text_c(d, x + w / 2, 166, f"{375+i*15}px 屏", f, WHITE)
            txt(d, (28, 220), "750rpx 两屏都铺满", font(14), GREEN)
            txt(d, (28, 250), "→ 无需媒体查询，自动等比", font(14), DARK)
        return img

    frames, durs = [], []
    for ph in range(3):
        frames.append(frame(ph)); durs.append(1300)
    durs[-1] = 1800
    emit(frames, durs, "demo-rpx.gif")


# ============ demo-domain：域名白名单 ============
def anim_domain():
    def frame(phase):
        img, d = new_screen(); status_bar(d); nav_bar(d, "请求域名白名单")
        card(d, (28, 120, 347, 194), 12)
        txt(d, (46, 136), "GET https://api.example.com/list", font(13), DARK)
        txt(d, (46, 164), "header: application/json", font(12), GRAY)
        if phase == 0:
            rrect(d, (28, 230, 347, 296), 12, fill=(235, 255, 240))
            txt(d, (46, 244), "模拟器：成功 √", font(14), GREEN)
            txt(d, (46, 268), "「不校验合法域名」已勾选", font(12), GRAY)
        elif phase == 1:
            rrect(d, (28, 230, 347, 296), 12, fill=(255, 240, 240))
            txt(d, (46, 244), "真机：失败 ×", font(14), RED)
            txt(d, (46, 268), "url not in domain list", font(12), RED)
        else:
            rrect(d, (28, 230, 347, 296), 12, fill=(235, 255, 240))
            txt(d, (46, 244), "配置域名后：真机成功 √", font(14), GREEN)
            txt(d, (46, 268), "HTTPS + 备案 + 归属校验", font(12), GRAY)
        tips = ["后台：开发设置 → 服务器域名", "不校验仅限开发，上线必须配好", "配置生效有延迟（约数分钟）"]
        card(d, (28, 336, 347, 400), 12)
        txt(d, (46, 358), tips[phase], font(13), ORANGE)
        return img

    frames, durs = [], []
    for ph in range(3):
        frames.append(frame(ph)); durs.append(1400)
    emit(frames, durs, "demo-domain.gif")


# ============ demo-callfunction：调用链路 ============
def anim_callfunction():
    def frame(step):
        img, d = new_screen(); status_bar(d); nav_bar(d, "云函数调用链路")
        nodes = [("小程序端", "wx.cloud.callFunction", BLUE, 120),
                 ("云函数", "event → 业务逻辑", GREEN, 290),
                 ("云数据库", "增删改查 / 聚合", ORANGE, 460)]
        for name, sub, col, y in nodes:
            card(d, (40, y, 335, y + 96), 14, border=col)
            text_c(d, 187, y + 20, name, font_b(16), col)
            text_c(d, 187, y + 56, sub, font(12), GRAY)
        # 箭头按步骤点亮
        def arrow(y0, y1, label, on):
            c = GREEN if on else GRAY_L
            d.line([187 * S, y0 * S, 187 * S, y1 * S], fill=c, width=2 * S)
            d.polygon([(187 * S, y1 * S), ((187 - 6) * S, (y1 - 10) * S), ((187 + 6) * S, (y1 - 10) * S)], fill=c)
            txt(d, (200, (y0 + y1) / 2 - 8), label, font(12), c)
        arrow(216, 290, "① data 参数", step >= 1)
        arrow(386, 460, "② 数据操作", step >= 2)
        if step >= 3:
            card(d, (40, 580, 335, 624), 10)
            text_c(d, 187, 592, "res.result → 小程序端", font(13), BLUE)
        return img

    frames, durs = [], []
    for s in range(4):
        frames.append(frame(s)); durs.append(1000)
    durs[-1] = 1600
    emit(frames, durs, "demo-callfunction.gif")


# ============ demo-database：CRUD ============
def anim_database():
    def doc(y, title, sub, hi=False):
        def inner(d):
            card(d, (28, y, 347, y + 60), 10, border=GREEN if hi else None)
            txt(d, (46, y + 12), title, font(12), DARK)
            txt(d, (46, y + 36), sub, font(11), GRAY)
        return inner

    def frame(phase):
        img, d = new_screen(); status_bar(d); nav_bar(d, "云数据库 CRUD")
        txt(d, (30, 106), "集合：todos（权限：仅创建者可读写）", font(12), GRAY)
        if phase == 0:
            doc(150, 'add({ title: "学习云数据库" })', "_id + openid 自动写入", True)(d)
            txt(d, (46, 236), "→ 新增文档", font(13), GREEN)
        elif phase == 1:
            doc(150, "where({ done: false }).get()", "仅返回未完成 + 自己的数据")(d)
            doc(220, "文档 1：学习云数据库", "done: false")(d)
            doc(290, "文档 2：写云函数", "done: false")(d)
            txt(d, (46, 380), "→ 查询结果（≤20 条/次）", font(13), GREEN)
        elif phase == 2:
            doc(150, "doc(id).update({ done: true })", "部分更新，只改传的字段", True)(d)
            doc(220, "文档 1：学习云数据库", "done: true √")(d)
            txt(d, (46, 310), "→ 更新成功", font(13), GREEN)
        else:
            doc(150, "doc(id).remove()", "不可撤销，生产用软删除")(d)
            txt(d, (46, 240), "→ 文档已删除", font(13), GREEN)
        return img

    frames, durs = [], []
    for ph in range(4):
        frames.append(frame(ph)); durs.append(1400)
    emit(frames, durs, "demo-database.gif")


# ============ demo-release：发布流程 ============
def anim_release():
    def frame(idx):
        img, d = new_screen(); status_bar(d); nav_bar(d, "上线发布流程")
        steps = [("① 代码上传", ["开发者工具「上传」", "版本号 1.0.0 + 备注"], BLUE),
                 ("② 体验版", ["版本管理 → 选为体验版", "体验成员扫码测试"], GREEN),
                 ("③ 提交审核", ["类目：工具 > 效率", "功能可完整体验"], ORANGE),
                 ("④ 审核通过", ["结果通知 → 点击「发布」", "全量 / 分批灰度"], GREEN),
                 ("⑤ 运营期", ["版本更新检查", "异常可一键回退"], RED)]
        title, lines, col = steps[idx]
        card(d, (24, 110, 351, 250), 14, border=col)
        txt(d, (42, 128), title, font_b(16), col)
        for i, ln in enumerate(lines):
            txt(d, (42, 174 + i * 30), ln, font(13), DARK)
        # 进度
        names = ["上传", "体验版", "审核", "发布"]
        x = 30
        for i, n in enumerate(names):
            done = i <= idx
            c = GREEN if done else GRAY_L
            d.ellipse([x * S, 310 * S, (x + 22) * S, 332 * S], outline=c, width=2 * S if done else S)
            if done:
                d.line([(x + 5) * S, 321 * S, (x + 9) * S, 327 * S], fill=c, width=2 * S)
                d.line([(x + 9) * S, 327 * S, (x + 17) * S, 315 * S], fill=c, width=2 * S)
            txt(d, (x + 26, 315), n, font(12), c if done else GRAY)
            x += 86
        notes = ["上传的是开发版，仅开发者可见", "体验版与线上版互不影响", "审核 1~7 个工作日，可加急",
                 "发布后盯一周崩溃率与反馈", "回退：版本管理 → 一键回退"]
        text_c(d, 187, 380, notes[idx], font(13), RED if idx == 4 else GRAY)
        return img

    frames, durs = [], []
    for i in range(5):
        frames.append(frame(i)); durs.append(1100)
    durs[-1] = 1700
    emit(frames, durs, "demo-release.gif")


# ============ demo-loading：页面加载链路 ============
def anim_loading():
    def frame(phase):
        img, d = new_screen(); status_bar(d); nav_bar(d, "页面加载链路")
        card(d, (24, 106, 351, 162), 12, border=BLUE)
        txt(d, (42, 118), "app.json → pages[0]", font(13), BLUE)
        txt(d, (42, 140), "定位页面路径 pages/index", font(12), DARK)
        files = [("index.json", "页面配置", ORANGE), ("index.wxml", "页面结构", GREEN),
                 ("index.wxss", "页面样式", BLUE), ("index.js", "页面逻辑", RED)]
        y = 186
        for i, (fn, desc, col) in enumerate(files):
            loaded = phase > i
            card(d, (24, y, 351, y + 52), 10, border=col if loaded else None)
            txt(d, (42, y + 10), f"{i+1}. {fn}", font(13), col if loaded else GRAY)
            txt(d, (42, y + 32), desc, font(12), DARK if loaded else GRAY)
            y += 62
        if phase >= 4:
            rrect(d, (24, 450, 351, 512), 12, fill=(235, 255, 240))
            txt(d, (42, 464), "Page() 注册 + data 绑定 {{}}", font(13), GREEN)
            txt(d, (42, 488), "→ 页面渲染完成", font(13), GREEN)
        else:
            text_c(d, 187, 470, "按序加载中…", font(13), GRAY)
        return img

    frames, durs = [], []
    for ph in range(5):
        frames.append(frame(ph)); durs.append(850)
    durs[-1] = 1600
    emit(frames, durs, "demo-loading.gif")


# ============ demo-stack：页面栈 ============
def anim_stack():
    def frame(items, note, hi=None):
        img, d = new_screen(); status_bar(d); nav_bar(d, "页面栈")
        card(d, (60, 120, 315, 380), 12)
        txt(d, (76, 132), "页面栈（最多 10 层）", font(12), GRAY)
        y = 176
        for i, (pg, is_a) in enumerate(items):
            col = BLUE if is_a else GREEN
            rrect(d, (84, y, 291, y + 50), 10, fill=(230, 240, 255) if is_a else (235, 255, 240),
                  outline=col if hi == i else None, width=2)
            txt(d, (100, y + 14), pg, font(13), col)
            y += 62
        txt(d, (40, 430), note, font(13), GREEN)
        return img

    frames, durs = [], []
    A = ("首页 A", True); B = ("详情页 B", False)
    seq = [([A], "初始：栈中只有首页", None),
           ([A, B], "navigateTo 压栈 → 进 B", 1),
           ([A], "navigateBack 弹栈 → 回 A", None),
           ([A], "switchTab 清栈（仅 tab 页）", 0),
           ([B], "reLaunch 重置栈 → 新页面", 0)]
    for items, note, hi in seq:
        frames.append(frame(items, note, hi)); durs.append(1100)
    emit(frames, durs, "demo-stack.gif")


# ============ demo-input：受控更新 ============
def anim_input():
    def frame(typed, controlled, note):
        img, d = new_screen(); status_bar(d); nav_bar(d, "input 受控更新")
        rrect(d, (24, 120, 351, 172), 12, outline=GREEN if controlled else RED, width=2)
        txt(d, (40, 138), typed if typed else "搜索", font(14), DARK if typed else GRAY)
        if controlled:
            txt(d, (40, 180), "value ← data.keyword（回填）", font(12), GREEN)
        else:
            txt(d, (40, 180), "× 未 setData：值丢失/光标乱跳", font(12), RED)
        card(d, (24, 220, 351, 400), 12)
        code = ['bindinput="onInput"', "onInput(e) {", "  this.setData({",
                "    keyword: e.detail.value", "  })", "}"]
        for i, ln in enumerate(code):
            txt(d, (42, 240 + i * 26), ln, font(12), DARK)
        txt(d, (40, 430), note, font(13), GREEN)
        return img

    frames, durs = [], []
    frames.append(frame("", True, "初始：value 绑定 data.keyword")); durs.append(1000)
    frames.append(frame("搜", False, "输入后未 setData → 视图不同步")); durs.append(1300)
    frames.append(frame("搜", True, "setData 回填 → 正常受控")); durs.append(1500)
    emit(frames, durs, "demo-input.gif")


# ============ demo-scroll：触底加载 ============
def anim_scroll():
    def frame(visible, note):
        img, d = new_screen(); status_bar(d); nav_bar(d, "scroll-view 触底加载")
        card(d, (24, 110, 351, 500), 12)
        txt(d, (42, 122), "scroll-y 滚动区域（需限高）", font(12), GRAY)
        y = 160
        for i in range(visible):
            rrect(d, (42, y, 333, y + 42), 8, fill=(245, 245, 248))
            txt(d, (56, y + 10), f"第 {i+1} 条数据", font(13), DARK)
            y += 56
        txt(d, (60, 520), note, font(13), GREEN if visible < 6 else GRAY)
        return img

    frames, durs = [], []
    for v, note in [(3, "↓ 滚动触底 → bindscrolltolower"),
                    (5, "第 2 页数据追加"),
                    (8, "第 3 页追加（分页加载）"),
                    (10, "没有更多了")]:
        frames.append(frame(v, note)); durs.append(900)
    durs[-1] = 1300
    emit(frames, durs, "demo-scroll.gif")


# ============ demo-wxkey：wx:key 重要性 ============
def anim_wxkey():
    def frame(items, note, ok):
        img, d = new_screen(); status_bar(d); nav_bar(d, "wx:key 的重要性")
        txt(d, (24, 108), note, font(13), GREEN if ok else RED)
        for i, (label, tag) in enumerate(items):
            y = 160 + i * 76
            card(d, (40, y, 335, y + 62), 10)
            txt(d, (56, y + 14), label, font(13), DARK)
            txt(d, (56, y + 38), f"wx:key = {tag}", font(11), GREEN if ok else GRAY)
        return img

    frames, durs = [], []
    frames.append(frame([("item: A", "1"), ("item: B", "2")], "× 无 wx:key：复用旧节点", False)); durs.append(1200)
    frames.append(frame([("item: B", "1"), ("item: A", "2")], "× 重排后内容与 key 错位", False)); durs.append(1300)
    frames.append(frame([("item: A", "1"), ("item: B", "2")], "√ 有 wx:key：按 key 复用", True)); durs.append(1200)
    frames.append(frame([("item: B", "2"), ("item: A", "1")], "√ 重排后节点跟随 key，正确", True)); durs.append(1500)
    emit(frames, durs, "demo-wxkey.gif")


# ============ demo-todo-flow：待办完整操作流 ============
def anim_todo_flow():
    def frame(items, input_text="", focus=False, note=""):
        img, d = new_screen(); status_bar(d); nav_bar(d, "待办清单")
        # 输入栏
        rrect(d, (24, 108, 240, 160), 12, outline=GREEN if focus else (225, 225, 228), width=2)
        txt(d, (40, 122), input_text if input_text else "输入待办事项…",
            font(13), DARK if input_text else GRAY)
        rrect(d, (256, 108, 351, 160), 12, fill=GREEN)
        text_c(d, 303, 122, "添加", font(13), WHITE)
        # 筛选
        for i, (name, active) in enumerate([("全部", True), ("未完成", False), ("已完成", False)]):
            txt(d, (28 + i * 76, 180), name, font(13), GREEN if active else GRAY)
            if active:
                d.rectangle([28 * S, 200 * S, (28 + text_w(d, "全部", font(13))) * S, 202 * S], fill=GREEN)
        # 列表
        y = 224
        for text, done in items:
            card(d, (24, y, 351, y + 66), 12)
            if done:
                d.ellipse([42 * S, (y + 22) * S, 62 * S, (y + 42) * S], fill=GREEN)
                d.line([47 * S, (y + 32) * S, 51 * S, (y + 37) * S], fill=WHITE, width=2 * S)
                d.line([51 * S, (y + 37) * S, 58 * S, (y + 27) * S], fill=WHITE, width=2 * S)
            else:
                d.ellipse([42 * S, (y + 22) * S, 62 * S, (y + 42) * S], outline=GREEN, width=S)
            txt(d, (78, y + 22), text, font(14), GRAY if done else DARK)
            txt(d, (300, y + 22), "删除", font(12), RED)
            y += 80
        if not items:
            text_c(d, 187, 300, "暂无待办", font(13), GRAY)
        if note:
            txt(d, (28, 560), note, font(13), GREEN)
        return img

    frames, durs = [], []
    # 1. 空列表 + 输入框聚焦
    frames.append(frame([], "", True, "① 输入框聚焦（bindinput）")); durs.append(900)
    # 2. 逐字输入
    for i in range(1, 6):
        frames.append(frame([], "学习云数据库"[:i], True, "")); durs.append(90)
    frames.append(frame([], "学习云数据库", True, "② 输入完成")); durs.append(700)
    # 3. 点击添加 → 新项插入
    for i in range(3):
        frames.append(frame([("学习云数据库", False)], "学习云数据库", False, "③ 点击添加 → callFunction")); durs.append(180)
    frames.append(frame([("学习云数据库", False)], "", False, "④ 云函数写入数据库")); durs.append(700)
    # 4. 再加一条
    frames.append(frame([("学习云数据库", False), ("写云函数", False)], "", False, "⑤ 列表已更新")); durs.append(800)
    # 5. 勾选完成
    frames.append(frame([("学习云数据库", True), ("写云函数", False)], "", False, "⑥ 点击勾选 → toggle")); durs.append(900)
    # 6. 删除
    frames.append(frame([("学习云数据库", True)], "", False, "⑦ 删除 → remove")); durs.append(1000)
    emit(frames, durs, "demo-todo-flow.gif")


# ============ demo-perf-setdata：拆组件优化对比 ============
def anim_perf_setdata():
    def grid(d, x0, y0, cols, rows, lit, cell=13, gap=3, col=GRAY_L, lit_col=GREEN):
        """节点网格，前 lit 个高亮"""
        for i in range(cols * rows):
            cx = x0 + (i % cols) * (cell + gap)
            cy = y0 + (i // cols) * (cell + gap)
            c = lit_col if i < lit else col
            rrect(d, (cx, cy, cx + cell, cy + cell), 3, fill=c)

    def bar(d, x0, y0, w, h, t, col):
        rrect(d, (x0, y0, x0 + w, y0 + h), h // 2, fill=(235, 235, 238))
        if t > 0:
            rrect(d, (x0, y0, x0 + w * t, y0 + h), h // 2, fill=col)

    def frame(t_left, t_right, note):
        img, d = new_screen(); status_bar(d); nav_bar(d, "setData 优化对比")
        # 左：页面级更新（大树，慢）
        card(d, (20, 104, 183, 400), 12)
        text_c(d, 101, 116, "页面级 setData", font_b(14), RED)
        txt(d, (34, 144), "Shadow 树 20 节点", font(11), GRAY)
        grid(d, 34, 168, 5, 4, int(20 * t_left), cell=17, gap=5, lit_col=RED)
        bar(d, 34, 300, 130, 10, t_left, RED)
        txt(d, (34, 322), f"updateCost: {int(48*t_left)}ms", font(12), RED)
        txt(d, (34, 350), "全树遍历", font(10), GRAY)
        # 右：组件内更新（小树，快）
        card(d, (192, 104, 355, 400), 12)
        text_c(d, 273, 116, "组件内 setData", font_b(14), GREEN)
        txt(d, (206, 144), "Shadow 树 4 节点", font(11), GRAY)
        grid(d, 206, 168, 2, 2, int(4 * t_right), cell=17, gap=5, lit_col=GREEN)
        bar(d, 206, 300, 130, 10, t_right, GREEN)
        txt(d, (206, 322), f"updateCost: {int(3*t_right)}ms", font(11), GREEN)
        txt(d, (206, 350), "仅组件子树", font(10), GRAY)
        if note:
            text_c(d, 187, 430, note, font(13), DARK)
        return img

    kfs = [frame(0, 0, "同一字段更新，两种代价"),
           frame(0.35, 1.0, "组件范围小 → 遍历节点少 → 更快"),
           frame(1.0, 1.0, "结论：拆组件 > 减数据（节点量影响更大）")]
    build(kfs, hold=1300, tween=6, tdur=70, colors=96, name="demo-perf-setdata.gif")


# ============ demo-perf-shadow：更新算法对比 ============
def anim_perf_shadow():
    N_COLS, N_ROWS = 5, 4
    TARGET = 12  # 目标绑定所在节点索引

    def grid(d, x0, y0, lit_set, target_lit=False):
        for i in range(N_COLS * N_ROWS):
            cx = x0 + (i % N_COLS) * 20
            cy = y0 + (i // N_COLS) * 20
            if i == TARGET and target_lit:
                fill = GREEN
            elif i in lit_set:
                fill = ORANGE
            else:
                fill = GRAY_L
            rrect(d, (cx, cy, cx + 15, cy + 15), 3, fill=fill)

    def frame(visited, note):
        img, d = new_screen(); status_bar(d); nav_bar(d, "数据更新算法")
        # 左：虚拟树更新（DFS 逐个访问）
        card(d, (20, 104, 183, 360), 12)
        text_c(d, 101, 116, "虚拟树更新", font_b(14), ORANGE)
        txt(d, (34, 142), "遍历 Shadow 树找绑定", font(10), GRAY)
        lit = set(range(visited))
        grid(d, 36, 168, lit, target_lit=(visited > TARGET))
        txt(d, (34, 280), f"已访问 {min(visited, N_COLS*N_ROWS)}/{N_COLS*N_ROWS} 节点", font(11), ORANGE)
        txt(d, (34, 306), "成本 ∝ 节点量", font(10), GRAY)
        # 右：绑定映射表（直接定位）
        card(d, (192, 104, 355, 360), 12)
        text_c(d, 273, 116, "绑定映射表", font_b(14), GREEN)
        txt(d, (206, 142), "编译期信息直接定位", font(10), GRAY)
        hit = {TARGET} if visited > TARGET else set()
        grid(d, 208, 168, hit, target_lit=(visited > TARGET))
        txt(d, (206, 280), "直接命中目标绑定" if visited > TARGET else "等待…", font(11), GREEN)
        txt(d, (206, 306), "免遍历，成本低", font(10), GRAY)
        text_c(d, 187, 392, note, font(13), DARK)
        return img

    kfs = [frame(0, "更新 1 个字段（未用于 wx:if/wx:for）"),
           frame(4, "虚拟树：逐节点深度优先遍历"),
           frame(TARGET + 1, "绑定映射表：跳过遍历，直接命中"),
           frame(N_COLS * N_ROWS, "小更新走映射表，否则回退虚拟树")]
    build(kfs, hold=1200, tween=4, tdur=70, colors=96, name="demo-perf-shadow.gif")


# ============ demo-compare：三种形态上手步骤对比 ============
def lcard(d, box, r=12, border=None, fill=WHITE):
    """无阴影卡片：内容密集的动画用它，可显著降低 GIF 体积（阴影渐变是主因）"""
    rrect(d, box, r, fill=fill, outline=border, width=2 if border else 1)


def anim_compare():
    def frame(step, note):
        img, d = new_screen(); status_bar(d); nav_bar(d, "上手步骤对比")
        rows = [("H5 网页", ["打开浏览器", "输入网址"], BLUE),
                ("微信小程序", ["扫码即用"], GREEN),
                ("原生 App", ["商店下载", "安装", "打开"], ORANGE)]
        y = 130
        for name, steps, col in rows:
            lcard(d, (20, y, 355, y + 118), 14, border=col if step > 0 else None)
            txt(d, (36, y + 14), name, font_b(16), col)
            sx = 36
            for i, s in enumerate(steps):
                on = step > i
                rrect(d, (sx, y + 54, sx + 92, y + 96), 10,
                      fill=(col if on else (242, 242, 245)) if False else ((235, 250, 241) if on else (242, 242, 245)),
                      outline=col if on else None, width=2)
                txt(d, (sx + 8, y + 66), s, font(11), DARK if on else GRAY)
                sx += 100
            txt(d, (36, y + 100), f"{len(steps)} 步", font(11), col)
            y += 136
        text_c(d, 187, 540, note, font(13), DARK)
        return img

    kfs = [frame(0, "从「看到」到「用上」的步骤数"),
           frame(1, "小程序：扫码即用（1 步）"),
           frame(2, "H5：需打开浏览器输入网址（2 步）"),
           frame(3, "App：需下载 + 安装（3 步，最重）")]
    build(kfs, hold=1100, tween=5, tdur=70, colors=128, name="demo-compare.gif")


# ============ demo-env：环境准备四步 ============
def anim_env():
    steps = [("① 注册小程序账号", "mp.weixin.qq.com → 拿 AppID", BLUE),
             ("② 安装开发者工具", "下载稳定版 → 微信扫码登录", GREEN),
             ("③ 新建项目", "填 AppID → 选空白模板", ORANGE),
             ("④ 跑通 Hello World", "改 WXML/JS → 编译 → 真机预览", RED)]

    def frame(n, note):
        img, d = new_screen(); status_bar(d); nav_bar(d, "环境准备四步")
        y = 120
        for i, (title, sub, col) in enumerate(steps):
            done = i < n
            lcard(d, (20, y, 355, y + 96), 14, border=col if done else None)
            d.ellipse([36 * S, (y + 30) * S, 60 * S, (y + 54) * S],
                      fill=col if done else WHITE, outline=col if done else GRAY_L, width=S)
            txt(d, (42, y + 36), str(i + 1), font_b(12), WHITE if done else GRAY)
            txt(d, (72, y + 22), title, font_b(14), col if done else GRAY)
            txt(d, (72, y + 52), sub, font(11), DARK if done else GRAY)
            y += 112
        text_c(d, 187, 580, note, font(13), GREEN)
        return img

    kfs = [frame(0, "四步跑通开发环境"),
           frame(1, "① 注册账号获取 AppID"),
           frame(2, "② 安装工具并扫码登录"),
           frame(3, "③ 新建项目"),
           frame(4, "④ 编译运行 + 真机预览")]
    build(kfs, hold=1000, tween=5, tdur=70, colors=128, name="demo-env.gif")


# ============ demo-langflow：四种语言协作数据流 ============
def anim_langflow():
    nodes = [("JavaScript", "定义 data / 处理事件", BLUE),
             ("setData", "数据推送到渲染层", GRAY),
             ("WXML", "{{}} 渲染结构", GREEN),
             ("WXSS", "rpx / flex 上样式", ORANGE),
             ("事件回调", "点击 → 回到 JS", RED)]

    def frame(active, note):
        img, d = new_screen(); status_bar(d); nav_bar(d, "四种语言如何协作")
        y = 108
        for i, (name, sub, col) in enumerate(nodes):
            on = i == active
            lcard(d, (24, y, 351, y + 78), 12, border=col if on else None)
            txt(d, (42, y + 14), name, font_b(15), col if on else GRAY)
            txt(d, (42, y + 44), sub, font(11), DARK if on else GRAY)
            if i < len(nodes) - 1:
                c = col if on else GRAY_L
                d.line([187 * S, (y + 78) * S, 187 * S, (y + 96) * S], fill=c, width=2 * S)
                d.polygon([(187 * S, (y + 96) * S), (181 * S, (y + 88) * S), (193 * S, (y + 88) * S)], fill=c)
            y += 96
        text_c(d, 187, 600, note, font(13), DARK)
        return img

    kfs = [frame(0, "① JS 定义 data"),
           frame(1, "② setData 把数据推给渲染层"),
           frame(2, "③ WXML 用 {{}} 渲染结构"),
           frame(3, "④ WXSS 给结构上样式"),
           frame(4, "⑤ 用户点击 → 事件回调 JS（闭环）")]
    build(kfs, hold=1000, tween=5, tdur=70, colors=128, name="demo-langflow.gif")


# ============ demo-cloudinit：云开发开通流程 ============
def anim_cloudinit():
    steps = [("开通云开发", "工具栏「云开发」→ 按量付费", GREEN),
             ("创建环境", "dev / prod，记下环境 ID", BLUE),
             ("wx.cloud.init", "app.js onLaunch 里初始化", ORANGE),
             ("写 test 云函数", "exports.main → 返回数据", PURPLE),
             ("调用验证", "callFunction → 拿到 res.result", RED)]

    def frame(n, note):
        img, d = new_screen(); status_bar(d); nav_bar(d, "云开发开通流程")
        y = 116
        for i, (title, sub, col) in enumerate(steps):
            done = i < n
            lcard(d, (24, y, 351, y + 86), 12, border=col if done else None)
            d.ellipse([40 * S, (y + 26) * S, 60 * S, (y + 46) * S],
                      fill=col if done else WHITE, outline=col if done else GRAY_L, width=S)
            txt(d, (44, y + 31), str(i + 1), font_b(11), WHITE if done else GRAY)
            txt(d, (72, y + 18), title, font_b(14), col if done else GRAY)
            txt(d, (72, y + 48), sub, font(11), DARK if done else GRAY)
            y += 100
        text_c(d, 187, 615, note, font(13), GREEN if n > 0 else GRAY)
        return img

    kfs = [frame(0, "从开通到跑通云能力"),
           frame(2, "开通 + 创建环境"),
           frame(3, "初始化 wx.cloud.init"),
           frame(4, "写并部署云函数"),
           frame(5, "调用成功 → 链路打通")]
    build(kfs, hold=1000, tween=5, tdur=70, colors=128, name="demo-cloudinit.gif")


# ============ demo-path：学习路线推进 ============
def anim_path():
    stages = [("① 认知", "认识小程序 · 编程语言与技术栈", BLUE),
              ("② 准备", "环境准备 · 项目结构", GREEN),
              ("③ 基础", "WXML · WXSS · JS · 生命周期", ORANGE),
              ("④ 进阶", "组件 · 网络 · 性能优化", PURPLE),
              ("⑤ 实战与发布", "云开发 · 实战项目 · 上线", RED)]

    def frame(active):
        img, d = new_screen(); status_bar(d); nav_bar(d, "学习路径推进")
        y = 116
        for i, (name, sub, col) in enumerate(stages):
            done = i <= active
            lcard(d, (20, y, 355, y + 88), 12, border=col if done else None)
            d.ellipse([36 * S, (y + 28) * S, 60 * S, (y + 52) * S],
                      fill=col if done else WHITE, outline=col if done else GRAY_L, width=S)
            txt(d, (43, y + 33), str(i + 1), font_b(12), WHITE if done else GRAY)
            txt(d, (72, y + 18), name, font_b(15), col if done else GRAY)
            if done:
                txt(d, (72, y + 48), sub, font(11), DARK)
            else:
                txt(d, (72, y + 48), "待学习", font(11), GRAY)
            if i == active:
                rrect(d, (20, y, 26, y + 88), 3, fill=col)
            y += 102
        # 进度条
        rrect(d, (20, 630, 355, 638), 4, fill=(235, 235, 238))
        rrect(d, (20, 630, 20 + 335 * (active + 1) / 5, 638), 4, fill=GREEN)
        return img

    kfs = [frame(i) for i in range(5)]
    build(kfs, hold=1100, tween=5, tdur=70, colors=128, name="demo-path.gif")


# ============ demo-resources：资源获取流程 ============
def anim_resources():
    steps = [("① 遇到报错", "先把报错信息完整读一遍", RED),
             ("② 查官方文档", "第一优先级，版本以文档为准", BLUE),
             ("③ 搜社区", "微信开放社区 / 掘金 / CSDN", GREEN),
             ("④ 提问四要素", "报错 + 基础库版本 + 机型 + 复现步骤", ORANGE),
             ("⑤ 定位解决", "对照文档与社区答案修复", PURPLE)]

    def frame(n):
        img, d = new_screen(); status_bar(d); nav_bar(d, "遇到问题怎么办")
        y = 116
        for i, (title, sub, col) in enumerate(steps):
            done = i < n
            lcard(d, (20, y, 355, y + 88), 12, border=col if done else None)
            d.ellipse([36 * S, (y + 28) * S, 60 * S, (y + 52) * S],
                      fill=col if done else WHITE, outline=col if done else GRAY_L, width=S)
            txt(d, (43, y + 33), str(i + 1), font_b(12), WHITE if done else GRAY)
            txt(d, (72, y + 18), title, font_b(15), col if done else GRAY)
            txt(d, (72, y + 48), sub, font(11), DARK if done else GRAY)
            if i < 4:
                c = col if done else GRAY_L
                d.line([187 * S, (y + 88) * S, 187 * S, (y + 102) * S], fill=c, width=2 * S)
            y += 102
        return img

    kfs = [frame(1), frame(2), frame(3), frame(4), frame(5)]
    build(kfs, hold=1100, tween=5, tdur=70, colors=128, name="demo-resources.gif")


# ============ demo-media：选图 → 预览 → 上传 ============
def anim_media():
    from PIL import ImageEnhance

    def base(img_card, uploaded):
        img, d = new_screen(); status_bar(d); nav_bar(d, "选择图片")
        rrect(d, (24, 116, 351, 320), 12, fill=WHITE, outline=GRAY_L, width=2)
        if img_card:
            rrect(d, (40, 132, 335, 304), 8, fill=(216, 228, 242))
            d.polygon([(40 * S, 304 * S), (150 * S, 190 * S), (210 * S, 255 * S),
                       (260 * S, 170 * S), (335 * S, 304 * S)], fill=(126, 178, 126))
            d.polygon([(40 * S, 304 * S), (335 * S, 304 * S), (335 * S, 260 * S),
                       (250 * S, 205 * S), (180 * S, 245 * S)], fill=(160, 198, 160))
            txt(d, (48, 268), "本地临时文件 wxfile://…", font(11), GRAY)
        else:
            text_c(d, 187, 205, "点击「选择图片」", font(13), GRAY)
        rrect(d, (24, 340, 351, 388), 12, fill=GREEN if img_card else GRAY_L)
        text_c(d, 187, 358, "上传到云存储", font_b(15), WHITE if img_card else GRAY)
        if uploaded:
            lcard(d, (24, 406, 351, 466), 10, border=GREEN, fill=(238, 250, 243))
            txt(d, (40, 420), "上传成功 fileID", font_b(14), GREEN)
            txt(d, (40, 444), "cloud://env-xxx/avatar/…", font(11), DARK)
        return img, d

    def sheet(img, d, slide):
        img = ImageEnhance.Brightness(img).enhance(0.55)
        d = ImageDraw.Draw(img)
        y = 398 + slide
        rrect(d, (24, y, 351, y + 186), 14, fill=WHITE)
        text_c(d, 187, y + 18, "选择图片来源", font_b(15), DARK)
        rrect(d, (24, y + 48, 351, y + 94), 10, fill=(245, 245, 245))
        text_c(d, 187, y + 65, "拍照", font(14), DARK)
        rrect(d, (24, y + 102, 351, y + 148), 10, fill=(245, 245, 245))
        text_c(d, 187, y + 119, "从相册选择", font(14), DARK)
        rrect(d, (24, y + 156, 351, y + 186), 10, fill=(250, 250, 250))
        text_c(d, 187, y + 168, "取消", font(14), GRAY)
        return img

    frames, durs = [], []
    img0, _ = base(False, False)
    frames.append(img0); durs.append(900)
    for i in range(6):                      # 弹窗滑入
        img, d = base(False, False)
        frames.append(sheet(img, d, (1 - ease(i / 5)) * 240)); durs.append(60)
    img1, _ = base(False, False)
    frames.append(sheet(img1, ImageDraw.Draw(img1), 0)); durs.append(800)
    img2, _ = base(True, False)
    frames.append(img2); durs.append(1100)
    img3, _ = base(True, True)
    frames.append(img3); durs.append(1400)
    emit(frames, durs, "demo-media.gif", colors=96)


# ============ demo-map：定位 → 门店标记 ============
def anim_map():
    def frame(show_dot, show_marker, ripple_t):
        img, d = new_screen(); status_bar(d); nav_bar(d, "附近门店")
        # 简化地图：底色 + 街道 + 建筑块
        rrect(d, (16, 104, 359, 560), 12, fill=(233, 240, 233))
        for y in (170, 260, 350, 440, 520):
            d.line([16 * S, y * S, 359 * S, y * S], fill=WHITE, width=3 * S)
        for x in (90, 200, 300):
            d.line([x * S, 104 * S, x * S, 560 * S], fill=WHITE, width=3 * S)
        for bx, by in [(60, 200), (120, 300), (240, 190), (320, 420), (70, 480), (260, 300)]:
            rrect(d, (bx, by, bx + 46, by + 34), 4, fill=(205, 218, 205))
        if show_dot:
            cx, cy = 187, 320
            if ripple_t is not None:
                layer = Image.new("RGBA", (SW, SH), (0, 0, 0, 0))
                ld = ImageDraw.Draw(layer)
                for r in (18, 30, 42):
                    a = int(90 * (1 - ripple_t))
                    ld.ellipse([(cx - r) * S, (cy - r) * S, (cx + r) * S, (cy + r) * S],
                               outline=(22, 93, 255, a), width=int(2.5 * S))
                img.paste(layer, (0, 0), layer)
            d.ellipse([(cx - 9) * S, (cy - 9) * S, (cx + 9) * S, (cy + 9) * S], fill=BLUE, outline=WHITE, width=2 * S)
        if show_marker:
            lcard(d, (120, 208, 262, 276), 10, border=GREEN, fill=WHITE)
            d.ellipse([156 * S, 222 * S, 178 * S, 244 * S], fill=GREEN)
            txt(d, (168, 234), "店", font_b(12), WHITE)
            txt(d, (188, 220), "门店 A · 距你 300m", font(12), DARK)
            d.line([187 * S, 276 * S, 187 * S, 292 * S], fill=GREEN, width=3 * S)
            d.polygon([(180 * S, 292 * S), (194 * S, 292 * S), (187 * S, 302 * S)], fill=GREEN)
        # 底部按钮
        rrect(d, (24, 590, 351, 636), 12, fill=GREEN)
        text_c(d, 187, 608, "重新定位", font_b(15), WHITE)
        return img

    frames, durs = [], []
    frames.append(frame(False, False, None)); durs.append(900)
    for i in range(5):                       # 蓝点出现 + 波纹
        frames.append(frame(True, False, i / 4)); durs.append(110)
    frames.append(frame(True, False, None)); durs.append(500)
    for i in range(6):                       # marker 弹出
        t = ease(i / 5)
        img, d = new_screen(); status_bar(d); nav_bar(d, "附近门店")
        frames.append(frame(True, True, None)); durs.append(90)
    frames.append(frame(True, True, None)); durs.append(1300)
    emit(frames, durs, "demo-map.gif", colors=96)


# ============ demo-auth：授权弹窗 → 允许 → 已授权 ============
def anim_auth():
    from PIL import ImageEnhance

    def base(authorized):
        img, d = new_screen(); status_bar(d); nav_bar(d, "定位权限")
        if authorized:
            lcard(d, (24, 140, 351, 240), 12, border=GREEN, fill=(238, 250, 243))
            txt(d, (40, 158), "已授权 · scope.userLocation", font_b(14), GREEN)
            txt(d, (40, 190), "lat 39.9042 · lng 116.4074", font(12), DARK)
        else:
            lcard(d, (24, 140, 351, 240), 12, fill=WHITE, border=GRAY_L)
            txt(d, (40, 158), "未授权 · scope.userLocation", font_b(14), DARK)
            txt(d, (40, 190), "调用 getLocation 前需要用户授权", font(12), GRAY)
        rrect(d, (24, 270, 351, 318), 12, fill=GREEN if not authorized else GRAY_L)
        text_c(d, 187, 288, "获取我的位置", font_b(15), WHITE if not authorized else GRAY)
        return img, d

    def popup(img, d, slide):
        img = ImageEnhance.Brightness(img).enhance(0.55)
        d = ImageDraw.Draw(img)
        y = 200 + slide
        rrect(d, (54, y, 321, y + 300), 14, fill=WHITE)
        d.ellipse([(151) * S, (y + 24) * S, (189) * S, (y + 62) * S], fill=(220, 230, 240))
        d.ellipse([(165) * S, (y + 38) * S, (175) * S, (y + 48) * S], fill=DARK)
        d.arc([(158) * S, (y + 42) * S, (182) * S, (y + 58) * S], 200, 340, fill=DARK, width=2 * S)
        text_c(d, 187, y + 76, "申请获取你的位置信息", font_b(15), DARK)
        text_c(d, 187, y + 106, "用于展示附近的合作门店", font(12), GRAY)
        rrect(d, (70, y + 138, 153, y + 182), 10, fill=(250, 250, 250))
        text_c(d, 111, y + 156, "拒绝", font(14), GRAY)
        rrect(d, (163, y + 138, 305, y + 182), 10, fill=GREEN)
        text_c(d, 234, y + 156, "允许", font(14), WHITE)
        text_c(d, 187, y + 216, "由微信系统弹出的授权框", font(11), GRAY)
        text_c(d, 187, y + 236, "开发者无法自定义文案", font(11), GRAY)
        return img

    frames, durs = [], []
    img0, _ = base(False)
    frames.append(img0); durs.append(900)
    for i in range(6):                       # 授权弹窗滑入
        img, d = base(False)
        frames.append(popup(img, d, (1 - ease(i / 5)) * 300)); durs.append(60)
    img1, _ = base(False)
    frames.append(popup(img1, ImageDraw.Draw(img1), 0)); durs.append(1100)
    img2, _ = base(True)
    frames.append(img2); durs.append(1500)
    emit(frames, durs, "demo-auth.gif", colors=96)


# ============ demo-share：分享面板 → 订阅弹窗 ============
def anim_share():
    from PIL import ImageEnhance

    def base():
        img, d = new_screen(); status_bar(d); nav_bar(d, "分享与订阅")
        lcard(d, (24, 140, 351, 340), 12, fill=WHITE, border=GRAY_L)
        txt(d, (40, 160), "待办清单", font_b(17), DARK)
        txt(d, (40, 196), "今天 3 项待办 · 点击查看", font(12), GRAY)
        rrect(d, (250, 150, 335, 320), 10, fill=(222, 232, 244))
        d.polygon([(250 * S, 320 * S), (300 * S, 220 * S), (335 * S, 320 * S)], fill=(140, 170, 220))
        rrect(d, (24, 380, 351, 428), 12, fill=GREEN)
        text_c(d, 187, 398, "分享给好友", font_b(15), WHITE)
        rrect(d, (24, 446, 351, 494), 12, fill=ORANGE)
        text_c(d, 187, 464, "订阅：完成提醒", font_b(15), WHITE)
        return img, d

    def share_panel(img, d, slide):
        img = ImageEnhance.Brightness(img).enhance(0.55)
        d = ImageDraw.Draw(img)
        y = 452 + slide
        rrect(d, (16, y, 359, y + 168), 14, fill=WHITE)
        text_c(d, 187, y + 16, "转发给好友", font_b(14), DARK)
        for i, (label, col) in enumerate([("微信好友", GREEN), ("朋友圈", ORANGE)]):
            x0 = 60 + i * 140
            d.ellipse([(x0) * S, (y + 50) * S, (x0 + 56) * S, (y + 106) * S], fill=col)
            text_c(d, x0 + 28, y + 62, "发", font_b(18), WHITE)
            text_c(d, x0 + 28, y + 122, label, font(12), DARK)
        return img

    def subscribe(img, d, slide):
        img = ImageEnhance.Brightness(img).enhance(0.55)
        d = ImageDraw.Draw(img)
        y = 180 + slide
        rrect(d, (44, y, 331, y + 290), 14, fill=WHITE)
        text_c(d, 187, y + 20, "订阅通知", font_b(15), DARK)
        text_c(d, 187, y + 50, "勾选后每次最多展示 3 个模板", font(11), GRAY)
        rrect(d, (60, y + 76, 315, y + 126), 10, fill=(245, 245, 245))
        txt(d, (76, y + 92), "完成提醒：待办处理通知", font(13), DARK)
        d.ellipse([(286) * S, (y + 88) * S, (302) * S, (y + 104) * S], fill=GREEN, outline=GREEN)
        d.line([(290) * S, (y + 97) * S, (294) * S, (y + 101) * S], fill=WHITE, width=2 * S)
        d.line([(294) * S, (y + 101) * S, (300) * S, (y + 91) * S], fill=WHITE, width=2 * S)
        rrect(d, (60, y + 150, 315, y + 194), 10, fill=GREEN)
        text_c(d, 187, y + 168, "允许", font(14), WHITE)
        rrect(d, (60, y + 204, 315, y + 248), 10, fill=(250, 250, 250))
        text_c(d, 187, y + 222, "取消", font(14), GRAY)
        text_c(d, 187, y + 266, "一次授权 = 一条消息额度", font(11), GRAY)
        return img

    frames, durs = [], []
    img0, _ = base()
    frames.append(img0); durs.append(900)
    for i in range(6):                       # 分享面板滑出
        img, d = base()
        frames.append(share_panel(img, d, (1 - ease(i / 5)) * 220)); durs.append(60)
    img1, _ = base()
    frames.append(share_panel(img1, ImageDraw.Draw(img1), 0)); durs.append(1000)
    for i in range(6):                       # 订阅弹窗滑入
        img, d = base()
        frames.append(subscribe(img, d, (1 - ease(i / 5)) * 260)); durs.append(60)
    img2, _ = base()
    frames.append(subscribe(img2, ImageDraw.Draw(img2), 0)); durs.append(1300)
    emit(frames, durs, "demo-share.gif", colors=96)


# ============ demo-skyline：WebView vs Skyline 动画对比 ============
def anim_skyline():
    def frame(t, web_steps):
        img, d = new_screen(); status_bar(d); nav_bar(d, "动画对比")
        for y0, title, col in [(140, "WebView · setData 驱动", ORANGE), (400, "Skyline · worklet 驱动", GREEN)]:
            lcard(d, (24, y0, 351, y0 + 220), 12, fill=WHITE, border=GRAY_L)
            txt(d, (40, y0 + 16), title, font_b(14), col)
            # 轨道
            d.line([48 * S, (y0 + 150) * S, 327 * S, (y0 + 150) * S], fill=GRAY_L, width=4 * S)
            x = 40 + t * 272
            if "WebView" in title:
                x = 40 + (t // 0.2) / 5 * 272   # 阶梯：0.2 步进
            d.ellipse([(x - 14) * S, (y0 + 136) * S, (x + 14) * S, (y0 + 164) * S],
                      fill=col, outline=WHITE, width=2 * S)
            if "WebView" in title:
                text_c(d, 187, y0 + 188, f"每帧跨线程通信 ×{int(t * 60)}/s", font(11), GRAY)
            else:
                text_c(d, 187, y0 + 188, "渲染线程本地计算 · 0 次通信", font(11), GREEN)
        rrect(d, (24, 590, 351, 636), 12, fill=(245, 245, 245))
        text_c(d, 187, 608, "同一动画：左阶梯卡顿，右顺滑", font(13), DARK)
        return img

    frames, durs = [], []
    for i in range(25):
        t = i / 24
        frames.append(frame(t, None)); durs.append(70)
    frames.append(frame(1.0, None)); durs.append(900)
    emit(frames, durs, "demo-skyline.gif", colors=128)


# ============ demo-storage：上传进度 → 完成 ============
def anim_storage():
    def frame(progress):
        img, d = new_screen(); status_bar(d); nav_bar(d, "云存储上传")
        # 左侧缩略图
        rrect(d, (24, 130, 150, 300), 10, fill=(216, 228, 242))
        d.polygon([(24 * S, 300 * S), (90 * S, 210 * S), (130 * S, 260 * S), (150 * S, 300 * S)],
                  fill=(126, 178, 126))
        txt(d, (30, 310), "本地文件", font(11), GRAY)
        # 右侧进度区
        lcard(d, (168, 130, 351, 300), 12, fill=WHITE, border=GRAY_L)
        txt(d, (184, 150), "uploadFile", font_b(14), DARK)
        txt(d, (184, 180), "cloudPath: avatar/20261008-…", font(11), GRAY)
        rrect(d, (184, 230, 335, 246), 8, fill=GRAY_L)
        rrect(d, (184, 230, 184 + 151 * progress, 246), 8, fill=GREEN)
        if progress >= 1:
            txt(d, (184, 258), "上传完成 · fileID: cloud://…", font(12), GREEN)
        else:
            txt(d, (184, 258), f"上传中 {int(progress * 100)}%", font(12), GRAY)
        # 底部链路提示
        lcard(d, (24, 360, 351, 470), 12, fill=(248, 248, 250), border=GRAY_L)
        txt(d, (40, 378), "本地临时文件", font_b(13), DARK)
        txt(d, (40, 404), "→ 云存储 fileID（小程序可读）", font(12), GRAY)
        txt(d, (40, 430), "→ getTempFileURL 换临时链接（外部可读）", font(12), GRAY)
        return img

    kfs = [frame(0.0), frame(0.35), frame(0.7), frame(1.0)]
    build(kfs, hold=1000, tween=5, tdur=70, colors=96, name="demo-storage.gif")


# ============ demo-lib：组件库组件逐层出现 ============
def anim_lib():
    def frame(n):
        img, d = new_screen(); status_bar(d); nav_bar(d, "组件库表单")
        if n < 1:
            txt(d, (24, 118), "原生 view/text 手写表单", font_b(14), GRAY)
            text_c(d, 187, 260, "每个控件都要自己写样式", font(13), GRAY)
        if n >= 1:
            txt(d, (24, 118), "van-field 输入框", font_b(14), GREEN)
            lcard(d, (24, 148, 351, 218), 12, fill=WHITE, border=GRAY_L)
            txt(d, (40, 166), "待办内容", font(12), GRAY)
            txt(d, (40, 190), "输入待办事项…", font(13), DARK)
            d.line([40 * S, 212 * S, 335 * S, 212 * S], fill=GRAY_L, width=1)
        if n >= 2:
            txt(d, (24, 248), "van-button 按钮", font_b(14), GREEN)
            rrect(d, (24, 276, 351, 324), 12, fill=GREEN)
            text_c(d, 187, 294, "保存", font_b(15), WHITE)
            rrect(d, (24, 336, 351, 384), 12, fill=(245, 245, 245))
            text_c(d, 187, 354, "取消", font_b(15), DARK)
        if n >= 3:
            img = ImageEnhance.Brightness(img).enhance(0.55)
            d = ImageDraw.Draw(img)
            rrect(d, (54, 210, 321, 400), 14, fill=WHITE)
            text_c(d, 187, 246, "van-dialog 弹窗", font_b(15), DARK)
            text_c(d, 187, 290, "保存成功", font(13), GRAY)
            d.line([54 * S, 330 * S, 321 * S, 330 * S], fill=GRAY_L, width=1)
            text_c(d, 187, 356, "确定", font_b(14), GREEN)
        return img

    kfs = [frame(0), frame(1), frame(2), frame(3)]
    build(kfs, hold=1100, tween=5, tdur=70, colors=96, name="demo-lib.gif")


# ============ demo-debug：真机调试 → vConsole 日志 ============
def anim_debug():
    def base(pressed=False):
        img, d = new_screen(); status_bar(d); nav_bar(d, "调试演示")
        txt(d, (24, 118), "页面运行中…", font_b(14), DARK)
        rrect(d, (24, 560, 351, 608), 12, fill=GREEN if not pressed else GREEN_DARK)
        text_c(d, 187, 578, "打开 vConsole", font_b(15), WHITE)
        return img, d

    def console(h, rows, err_hl):
        img, d = base()
        h = int(h)
        rrect(d, (16, 600 - h, 359, 600), 12, fill=(40, 44, 52))
        y = 600 - h + 18
        for i, (s, c) in enumerate(rows):
            if h < (i + 1) * 34:
                break
            if err_hl and s.startswith("ERR"):
                rrect(d, (24, y - 8, 351, y + 16), 8, fill=(120, 40, 40))
                txt(d, (34, y - 2), s, font(12), (255, 150, 150))
            else:
                txt(d, (34, y - 2), s, font(12), c)
            y += 34
        return img

    rows = [("LOG 页面加载 page=index", (200, 210, 220)),
            ("LOG setData ok", (200, 210, 220)),
            ("WARN 请求耗时 860ms", (240, 200, 90)),
            ("ERR TypeError: xxx is not a function", (255, 120, 120))]
    kfs = []
    img, d = base(); kfs.append(img)
    img, d = base(True); kfs.append(img)
    kfs.append(console(170, rows[:2], False))   # 半展开，2 条
    kfs.append(console(340, rows[:4], False))   # 全展开，4 条
    kfs.append(console(340, rows[:4], True))    # 错误条目高亮
    kfs.append(console(0, rows, False))          # 收起
    build(kfs, hold=1000, tween=5, tdur=70, colors=96, name="demo-debug.gif")


# ============ demo-pay：确认支付 → 支付成功 ============
def anim_pay():
    def base(pressed=False, paid=False):
        img, d = new_screen(); status_bar(d); nav_bar(d, "商品详情")
        lcard(d, (24, 118, 351, 300), 12, fill=WHITE, border=GRAY_L)
        rrect(d, (40, 134, 335, 250), 8, fill=(235, 240, 235))
        text_c(d, 187, 178, "示例商品", font_b(16), DARK)
        text_c(d, 187, 214, "¥ 6.00", font_b(18), RED)
        if paid:
            txt(d, (40, 266), "已支付 · 订单 #1024", font(12), GREEN)
        else:
            txt(d, (40, 266), "微信支付 · 担保交易", font(12), GRAY)
        rrect(d, (24, 330, 351, 378), 12, fill=GREEN if not pressed else GREEN_DARK)
        text_c(d, 187, 348, "立即支付", font_b(15), WHITE)
        return img, d

    def sheet(img, d):
        dim = Image.new("RGBA", (SW, SH), (0, 0, 0, 90))
        img.paste(dim, (0, 0), dim)
        d = ImageDraw.Draw(img)
        rrect(d, (24, 380, 351, 620), 14, fill=WHITE)
        text_c(d, 187, 410, "确认支付", font_b(16), DARK)
        txt(d, (40, 452), "商户：示例商店", font(13), GRAY)
        txt(d, (40, 484), "商品：示例商品 × 1", font(13), GRAY)
        txt(d, (40, 516), "金额：¥ 6.00", font_b(14), DARK)
        rrect(d, (40, 556, 335, 604), 12, fill=GREEN)
        text_c(d, 187, 574, "确认支付 ¥6.00", font_b(15), WHITE)
        return img

    def success(img, d):
        rrect(d, (120, 300, 255, 430), 14, fill=WHITE)
        d.ellipse([150 * S, 330 * S, 190 * S, 370 * S], fill=GREEN)
        d.line([161 * S, 352 * S, 172 * S, 363 * S], fill=WHITE, width=4 * S)
        d.line([172 * S, 363 * S, 187 * S, 338 * S], fill=WHITE, width=4 * S)
        text_c(d, 187, 396, "支付成功", font_b(15), DARK)
        return img

    kfs = []
    img, d = base(); kfs.append(img)
    img, d = base(True); kfs.append(img)
    img, d = base(); kfs.append(sheet(img, d))
    img, d = base(True); kfs.append(sheet(img, d))
    img, d = base(); kfs.append(success(img, d))
    img, d = base(paid=True); kfs.append(img)
    build(kfs, hold=900, tween=4, tdur=60, colors=64, name="demo-pay.gif")


# ============ demo-navigation-flow：多页面导航流 ============
def anim_navigation_flow():
    def home_page(highlight_tab=0, note=""):
        img, d = new_screen(); status_bar(d); nav_bar(d, "首页")
        f = font_b(20)
        text_c(d, 187, 200, "首页", f, GREEN)
        for i, label in enumerate(["分类", "购物车", "我的"]):
            rrect(d, (40 + i * 110, 280, 130 + i * 110, 340), 12, fill=GREEN if i == highlight_tab else (240, 240, 240))
            text_c(d, 85 + i * 110, 298, label, font(13), WHITE if i == highlight_tab else DARK)
        # tabBar
        d.rectangle([0, 600 * S, 375 * S, 667 * S], fill=NAV_BG)
        tabs = ["首页", "分类", "我的"]
        for i, t in enumerate(tabs):
            col = GREEN if i == highlight_tab else GRAY
            text_c(d, 62 + i * 125, 620, t, font(11), col)
            d.rectangle([(62 + i * 125 - 8) * S, 640 * S, (62 + i * 125 + 8) * S, 642 * S], fill=col)
        if note:
            txt(d, (28, 560), note, font(13), GREEN)
        return img

    def detail_page(title, note=""):
        img, d = new_screen(); status_bar(d); nav_bar(d, title, back=True)
        f = font_b(18)
        text_c(d, 187, 220, f"商品详情", f, DARK)
        card(d, (24, 280, 351, 420), 12)
        txt(d, (40, 296), f"名称：{title}", font(13), DARK)
        txt(d, (40, 326), "价格：¥99.00", font(13), RED)
        txt(d, (40, 356), "库存：128 件", font(13), GRAY)
        rrect(d, (40, 380, 335, 410), 8, fill=GREEN)
        text_c(d, 187, 384, "加入购物车", font(13), WHITE)
        if note:
            txt(d, (28, 560), note, font(13), GREEN)
        return img

    frames, durs = [], []
    frames.append(home_page(0, "① tabBar 切换：首页")); durs.append(900)
    frames.append(home_page(1, "② tabBar 切换：分类页")); durs.append(900)
    frames.append(home_page(0, "③ 点击商品 → wx.navigateTo")); durs.append(800)
    frames.append(detail_page("小程序开发指南", "④ 详情页入栈（pages/detail/detail）")); durs.append(1000)
    frames.append(detail_page("小程序开发指南", "⑤ 点击返回 → wx.navigateBack")); durs.append(800)
    frames.append(home_page(0, "⑥ 回到首页，页面栈弹出详情页")); durs.append(1000)
    emit(frames, durs, "demo-navigation-flow.gif")


# ============ demo-product-list：商品列表搜索筛选 ============
def anim_product_list():
    products = [
        ("蓝牙耳机", "¥129", "数码"),
        ("手机壳", "¥29", "配件"),
        ("充电宝", "¥89", "数码"),
        ("数据线", "¥19", "配件"),
    ]

    def frame(search="", filtered=None, note=""):
        img, d = new_screen(); status_bar(d); nav_bar(d, "商品列表")
        rrect(d, (24, 108, 351, 152), 12, outline=GREEN if search else (225, 225, 228), width=2)
        txt(d, (40, 118), search if search else "搜索商品…", font(13), DARK if search else GRAY)
        items = filtered if filtered is not None else products
        y = 172
        for name, price, cat in items:
            card(d, (24, y, 351, y + 72), 12)
            rrect(d, (36, y + 10, 96, y + 62), 8, fill=(240, 240, 240))
            text_c(d, 66, y + 28, cat[:2], font(10), GRAY)
            txt(d, (108, y + 12), name, font(14), DARK)
            txt(d, (108, y + 38), price, font(13), RED)
            txt(d, (280, y + 38), cat, font(11), GRAY)
            y += 84
        if not items:
            text_c(d, 187, 300, "无匹配商品", font(13), GRAY)
        if note:
            txt(d, (28, 560), note, font(13), GREEN)
        return img

    frames, durs = [], []
    frames.append(frame("", products, "① 初始列表：4 件商品")); durs.append(900)
    for i in range(1, 5):
        frames.append(frame("充电"[:i], products, "")); durs.append(100)
    filtered = [p for p in products if "充电" in p[0]]
    frames.append(frame("充电", filtered, "② 搜索「充电」→ filter 过滤")); durs.append(900)
    frames.append(frame("充电", filtered, "③ wx:key=\"id\" 精确 diff")); durs.append(800)
    frames.append(frame("", products, "④ 清空搜索 → 恢复全部")); durs.append(1000)
    emit(frames, durs, "demo-product-list.gif")


# ============ demo-component-behavior：input 受控 vs 非受控对比 ============
def anim_component_behavior():
    def frame_controlled(typed, note):
        img, d = new_screen(); status_bar(d); nav_bar(d, "input 受控组件")
        txt(d, (24, 108), "受控模式（正确）", font_b(14), GREEN)
        rrect(d, (24, 140, 351, 192), 12, outline=GREEN, width=2)
        txt(d, (40, 156), typed if typed else "输入关键词…", font(14), DARK if typed else GRAY)
        txt(d, (40, 200), "value ← data.keyword（逻辑层回填）", font(12), GREEN)
        card(d, (24, 240, 351, 370), 12)
        code = ['bindinput="onInput"', "onInput(e) {", "  this.setData({",
                "    keyword: e.detail.value", "  })", "}"]
        for i, ln in enumerate(code):
            txt(d, (42, 258 + i * 20), ln, font_mono(11), DARK if "this" not in ln else GREEN)
        txt(d, (28, 390), note, font(13), GREEN)
        return img

    def frame_uncontrolled(typed, note):
        img, d = new_screen(); status_bar(d); nav_bar(d, "input 非受控对比")
        txt(d, (24, 108), "非受控模式（错误）", font_b(14), RED)
        rrect(d, (24, 140, 351, 192), 12, outline=RED, width=2)
        txt(d, (40, 156), typed if typed else "输入关键词…", font(14), DARK if typed else GRAY)
        txt(d, (40, 200), "未 setData → 渲染层/逻辑层分叉", font(12), RED)
        card(d, (24, 240, 351, 370), 12)
        code = ['bindinput="onInput"', "onInput(e) {", "  // 忘记 setData", "  console.log(e.detail.value)", "}"]
        for i, ln in enumerate(code):
            txt(d, (42, 258 + i * 20), ln, font_mono(11), RED if "忘记" in ln else DARK)
        txt(d, (28, 390), note, font(13), RED)
        return img

    frames, durs = [], []
    frames.append(frame_controlled("", "初始：value 绑定 data.keyword")); durs.append(1000)
    for i in range(1, 4):
        frames.append(frame_controlled("搜索"[:i], "")); durs.append(120)
    frames.append(frame_controlled("搜索", "每次输入都 setData → 受控正常")); durs.append(1200)
    frames.append(frame_uncontrolled("", "非受控：初始状态相同")); durs.append(1000)
    for i in range(1, 4):
        frames.append(frame_uncontrolled("搜索"[:i], "")); durs.append(120)
    frames.append(frame_uncontrolled("搜索", "DOM 状态与 data 分叉 → 光标乱跳")); durs.append(1400)
    emit(frames, durs, "demo-component-behavior.gif")


# ============ demo-serverless-flow：身份注入流程 ============
def anim_serverless_flow():
    def frame(step):
        img, d = new_screen(); status_bar(d); nav_bar(d, "Serverless 身份注入")
        nodes = [
            (24, 110, 160, "小程序端", "wx.cloud.callFunction", BLUE),
            (191, 110, 160, "微信客户端", "附加 access token", GREEN),
            (24, 280, 160, "CloudBase", "验证 token 注入 openid", ORANGE),
            (191, 280, 160, "云函数", "getWXContext()", PURPLE),
        ]
        for x, y, w, name, sub, col in nodes:
            card(d, (x, y, x + w, y + 80), 12, border=col)
            text_c(d, x + w / 2, y + 14, name, font_b(13), col)
            text_c(d, x + w / 2, y + 44, sub, font(11), GRAY)

        def flow_arrow(x0, y0, x1, y1, label, on):
            c = GREEN if on else GRAY_L
            d.line([x0 * S, y0 * S, x1 * S, y1 * S], fill=c, width=2 * S)
            import math
            angle = math.atan2(y1 - y0, x1 - x0)
            sz = 8
            p1 = (x1 - sz * math.cos(angle - 0.4), y1 - sz * math.sin(angle - 0.4))
            p2 = (x1 - sz * math.cos(angle + 0.4), y1 - sz * math.sin(angle + 0.4))
            d.polygon([(x1 * S, y1 * S), (p1[0] * S, p1[1] * S), (p2[0] * S, p2[1] * S)], fill=c)
            mx, my = (x0 + x1) / 2, (y0 + y1) / 2
            txt(d, (mx + 6, my - 10), label, font(10), c)

        flow_arrow(160, 150, 191, 150, "callFunction", step >= 1)
        flow_arrow(271, 190, 104, 280, "token", step >= 2)
        flow_arrow(160, 320, 191, 320, "openid", step >= 3)

        if step >= 4:
            card(d, (24, 400, 351, 490), 12, border=GREEN, fill=(238, 250, 243))
            txt(d, (40, 416), "身份注入完成", font_b(14), GREEN)
            txt(d, (40, 446), "openid 由微信服务端签发", font(12), DARK)
            txt(d, (40, 468), "不可伪造 / 免换码 / 安全可信", font(12), GREEN)
        else:
            card(d, (24, 400, 351, 460), 12)
            text_c(d, 187, 420, "等待身份注入…", font(13), GRAY)

        notes = ["小程序端发起云函数调用", "微信客户端附加 access token",
                 "CloudBase 验证 token 注入身份", "云函数拿到 openid/unionid",
                 "安全边界：前端权限不可信"]
        idx = min(step, 4)
        txt(d, (28, 520), f"步骤 {idx + 1}/5：{notes[idx]}", font(13), GREEN if step < 4 else RED)
        return img

    frames, durs = [], []
    for s in range(5):
        frames.append(frame(s)); durs.append(1100)
    durs[-1] = 1600
    emit(frames, durs, "demo-serverless-flow.gif")


if __name__ == "__main__":
    anim_setdata()
    anim_lifecycle()
    anim_wxfor()
    anim_ifhidden()
    anim_event()
    anim_component()
    anim_rpx()
    anim_domain()
    anim_callfunction()
    anim_database()
    anim_release()
    anim_loading()
    anim_stack()
    anim_input()
    anim_scroll()
    anim_wxkey()
    anim_todo_flow()
    anim_perf_setdata()
    anim_perf_shadow()
    anim_compare()
    anim_env()
    anim_langflow()
    anim_cloudinit()
    anim_path()
    anim_resources()
    anim_media()
    anim_map()
    anim_auth()
    anim_share()
    anim_skyline()
    anim_storage()
    anim_lib()
    anim_debug()
    anim_pay()
    anim_navigation_flow()
    anim_product_list()
    anim_component_behavior()
    anim_serverless_flow()
    print("全部动画生成完成")

    # 补间后处理：把静态帧切换的动画升级为含过渡的真动画
    print("--- 补间后处理 ---")
    from render import retween_gif
    for name in ["demo-ifhidden.gif", "demo-event.gif", "demo-component.gif", "demo-rpx.gif",
                 "demo-domain.gif", "demo-callfunction.gif", "demo-database.gif", "demo-release.gif",
                 "demo-loading.gif", "demo-stack.gif", "demo-input.gif", "demo-scroll.gif", "demo-wxkey.gif"]:
        retween_gif(name, tween=5, hold=1000, tdur=75, colors=96)
    print("补间完成")
