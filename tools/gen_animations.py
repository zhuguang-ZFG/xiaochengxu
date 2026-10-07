# -*- coding: utf-8 -*-
"""动画生成：每个动画由关键帧+补间帧构成，含转场/滚动/波纹过渡。"""
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from render import (  # noqa: E402
    new_screen, rrect, txt, text_w, text_c, status_bar, nav_bar, card, ripple,
    emit, ease, ease_out, lerp, font, font_b, shadow,
    GREEN, GREEN_DARK, BG, WHITE, DARK, GRAY, GRAY_L, RED, BLUE, ORANGE, PURPLE, NAV_BG, S,
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
        arrows = {0: ("↓ properties 传参", BLUE), 1: ("👆 点击组件", GREEN),
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
            txt(d, (46, 244), "模拟器：成功 ✓", font(14), GREEN)
            txt(d, (46, 268), "「不校验合法域名」已勾选", font(12), GRAY)
        elif phase == 1:
            rrect(d, (28, 230, 347, 296), 12, fill=(255, 240, 240))
            txt(d, (46, 244), "真机：失败 ✗", font(14), RED)
            txt(d, (46, 268), "url not in domain list", font(12), RED)
        else:
            rrect(d, (28, 230, 347, 296), 12, fill=(235, 255, 240))
            txt(d, (46, 244), "配置域名后：真机成功 ✓", font(14), GREEN)
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
            doc(220, "文档 1：学习云数据库", "done: true ✓")(d)
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
            txt(d, (40, 180), "❌ 未 setData：值丢失/光标乱跳", font(12), RED)
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
    frames.append(frame([("item: A", "1"), ("item: B", "2")], "❌ 无 wx:key：复用旧节点", False)); durs.append(1200)
    frames.append(frame([("item: B", "1"), ("item: A", "2")], "❌ 重排后内容与 key 错位", False)); durs.append(1300)
    frames.append(frame([("item: A", "1"), ("item: B", "2")], "✅ 有 wx:key：按 key 复用", True)); durs.append(1200)
    frames.append(frame([("item: B", "2"), ("item: A", "1")], "✅ 重排后节点跟随 key，正确", True)); durs.append(1500)
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
    print("全部动画生成完成")
