# -*- coding: utf-8 -*-
"""
教学视频生成脚本（可复现）。

- 画布 720x1280 竖屏：顶部标题区 + 中部手机演示区 + 底部字幕区
- 每集 = 场景序列；每场景 = 时长 + 字幕要点列表 + 手机画面绘制函数（按进度 t 驱动）
- 逐帧生成器 → imageio-ffmpeg 内置 ffmpeg 的 rawvideo 管道流式合成 H.264 mp4
  （不落盘 PNG、不缓存帧列表：75s×24fps 全量持有约需 5GB 内存）
- 产物：docs/assets/videos/video-01-*.mp4 等；单集目标 ≤3MB

用法：python tools/gen_videos.py
依赖：pip install imageio-ffmpeg
"""
import functools
import pathlib
import re
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from PIL import Image, ImageDraw, ImageFilter  # noqa: E402
from render import load_font  # noqa: E402

VIDEO_DIR = pathlib.Path(__file__).resolve().parent.parent / "docs" / "assets" / "videos"
VIDEO_DIR.mkdir(parents=True, exist_ok=True)

W, H = 720, 1280
SS = 2
RW, RH = W * SS, H * SS
FPS = 24
SIZE_LIMIT = 3 * 1024 * 1024   # 契约：单集 ≤ 3MB

GREEN = (7, 193, 96)
BG = (18, 20, 26)
GRAY = (150, 156, 168)
WHITE = (245, 245, 245)
ORANGE = (255, 165, 0)
BLUE = (66, 133, 244)
PURPLE = (156, 39, 176)
RED = (255, 100, 100)
CODE_BG = (30, 34, 42)
CODE_KW = (7, 193, 96)
CODE_STR = (255, 165, 0)
CODE_CMT = (100, 108, 120)


def f(size):
    """常规体（视频按 2x 超采样渲染，最终缩到 720x1280）"""
    return load_font(size * SS, "regular")


def fb(size):
    return load_font(size * SS, "bold")


_bg_base = None


def _background():
    """整幅竖向微渐变（只算一次）。纯色背景在 H.264 下容易出色带，也给画面一点纵深。"""
    global _bg_base
    if _bg_base is None:
        ramp = Image.new("RGB", (1, RH))
        top, bottom = BG, (13, 14, 18)
        for y in range(RH):
            t = y / (RH - 1)
            ramp.putpixel((0, y), tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3)))
        _bg_base = ramp.resize((RW, RH), Image.NEAREST)
    return _bg_base.copy()


def canvas(title, series="小程序开发之路 · 教学视频"):
    img = _background()
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, RW, 60 * SS], fill=(12, 13, 17))
    d.text((24 * SS, 14 * SS), series, font=f(20), fill=GRAY)
    # 集数标题做成深绿药丸：右上角唯一的彩色块，缩略图里也能认出当前集
    tw = d.textlength(title, font=f(20))
    pad = 10 * SS
    d.rounded_rectangle([RW - 24 * SS - tw - pad * 2, 11 * SS, RW - 24 * SS, 33 * SS],
                        radius=11 * SS, fill=(23, 74, 47))
    d.text((RW - 24 * SS - tw - pad, 12 * SS), title, font=f(20), fill=GREEN)
    d.rectangle([0, 60 * SS, RW, 62 * SS], fill=(40, 44, 54))
    return img, d


_ATOM_RE = re.compile(r"[A-Za-z0-9+._()$/\[\]*-]+|\s+|.")


@functools.lru_cache(maxsize=512)
def _wrap_lines(text, size=30, max_px=(W - 62 - 40) * SS):
    """字幕折行：按真实像素宽度折行，**绝不把标识符从中间劈开**。

    两代 bug。最早按 22 个字符贪心切，行尾会掉一个孤词——「对比：小程序 vs H5
    网页 vs 原生 / App」第二行只剩「App」。改成按字符数均分之后，「统一身份：
    cloud.getWXContext() 免鉴权拿 openid」被切成「统一身份：cloud.getWXCon /
    text() 免鉴权拿 openid」——屏幕上凭空出现一个不存在的 API 名，比孤词严重。
    于是：
    ① 连续的拉丁字母/数字/`._()[]*+-$/` 算一个不可拆的整体（中文仍可逐字断行）；
    ② 动态规划选断点，代价按 (行数, 最宽行, 宽度平方和) 字典序最小。行数必须排第一：
       只最小化「最宽行」会退化成一行一个字（最宽行 = 最宽的那个 token，已经最小了），
       实测第一版就踩了这个坑；
    ③ 宽度用字体真实量（`max_px` 是 2x 超采样下的物理像素），不再数字符个数。
    字幕字符串每帧重复出现，`lru_cache` 让动态规划每个字符串只算一次。
    """
    lines = []
    fnt = fb(size)
    for raw in text.split("\n"):
        para = raw.strip()
        if not para:
            continue
        toks = _ATOM_RE.findall(para)
        n = len(toks)
        dp = [(n + 1, float("inf"), 0.0, n)] * (n + 1)   # (行数, 最宽行, 平方和, 断点)
        dp[n] = (0, 0.0, 0.0, n)
        for i in range(n - 1, -1, -1):
            best = None
            for j in range(i + 1, n + 1):
                seg = "".join(toks[i:j]).strip()
                if not seg:
                    continue                    # 纯空格不配独占一行
                w = fnt.getlength(seg)
                if w > max_px and j - 1 > i:
                    break                       # 超长标识符独占一行也没办法，不能再撑
                nl, mx, sq, _ = dp[j]
                cost = (nl + 1, max(w, mx), sq + w * w)
                if best is None or cost < best[0]:
                    best = (cost, j)
            if best is None:                    # 剩下全是空格（para 已 strip，正常到不了）
                break
            dp[i] = (best[0][0], best[0][1], best[0][2], best[1])
        i = 0
        while i < n and dp[i][0] <= n:
            j = dp[i][3]
            seg = "".join(toks[i:j]).strip()
            if seg:
                lines.append(seg)
            i = j
    return tuple(lines)


_NOTDEF = None
_GLYPH_CACHE = {}


def _missing_glyphs(text):
    """返回 `text` 里渲染字体**画不出来**的字符（去重保序）。

    判定不靠猜：拿 U+10FFFF（必然未分配 ⇒ 一定走 .notdef）的字模位图当参照，
    某个字符的点阵和它一模一样，就说明这个字符在该字体里没有字形——屏幕上会是
    一个空心方块。`✓ ✗ ✅ ❌ 👆 ▶` 实测都是这样，此前「模拟器：成功 ✓」这类
    文案已经在 GIF 里当了很久豆腐块。字幕是逐帧重复的，按整串缓存。
    """
    global _NOTDEF
    if text in _GLYPH_CACHE:
        return _GLYPH_CACHE[text]
    fnt = load_font(30, "regular")
    if _NOTDEF is None:
        m = fnt.getmask("\U0010FFFF", mode="1")
        _NOTDEF = (m.size, bytes(m))
    missing = []
    for ch in dict.fromkeys(text):
        if ch in " \n":
            continue
        m = fnt.getmask(ch, mode="1")
        if (m.size, bytes(m)) == _NOTDEF:
            missing.append(ch)
    _GLYPH_CACHE[text] = tuple(missing)
    return _GLYPH_CACHE[text]


def caption(img, d, text):
    """底部字幕区：常驻标题 + 当前要点"""
    bad = _missing_glyphs(text)
    if bad:
        # 宁可渲染一启动就停下来，也不要花二十分钟渲染出一堆豆腐再靠人眼发现
        raise SystemExit(f"字幕里有字体画不出的字符 {list(bad)}：{text}\n"
                         f"换成本仓库画得出来的字符（→ ← ↑ ↓ √ × ● ○ ★ ☆ ·），"
                         f"见 tools/test_gen_videos.py 的 PRESENT")
    d.rectangle([0, 1120 * SS, RW, RH], fill=(12, 13, 17))
    d.rectangle([0, 1120 * SS, RW, 1123 * SS], fill=(40, 44, 54))
    lines = _wrap_lines(text, 30)
    shown = lines[:3]
    # 小字常驻在字幕区底部，正文字号 30、最多 3 行；行距按行数自适应，
    # 保证 3 行也不会压到小字（实测 2 行时行距仍是 42，第 3 行缩到 36）
    meta_y = 1248
    top = 1146
    pitch = min(42, (meta_y - 12 - top) // max(1, len(shown))) if shown else 42
    if shown:
        # 绿色引导条：把视线从手机演示引到字幕，也标出这片区域的起点
        d.rounded_rectangle([40 * SS, (top + 2) * SS, 46 * SS, (top + len(shown) * pitch - 14) * SS],
                            radius=3 * SS, fill=GREEN)
    for i, ln in enumerate(shown):
        d.text((62 * SS, (top + i * pitch) * SS), ln, font=fb(30), fill=WHITE)
    # 原先这行行首有个实心三角符号，本仓库用的字体没有它的字形，渲染出来是空心方块；
    d.text((62 * SS, meta_y * SS), "学习路径 · 每集 1-2 分钟 · 代码可复现", font=f(18), fill=GRAY)


def subtitle_bar(img, d, t, points):
    """按进度切换要点字幕"""
    dur = max(1, len(points))
    idx = min(int(t * dur), len(points) - 1)
    caption(img, d, points[idx])


def phone_frame(draw_fn):
    """中部手机演示区：375x667 设计坐标 -> 2x 超采样区域，含拟真手机框"""
    pw, ph = 480 * SS, 854 * SS
    img = Image.new("RGB", (pw, ph), (24, 26, 32))
    dd = ImageDraw.Draw(img)
    draw_fn(dd, 1.28 * SS)
    return img


_shadow_cache = {}


def _phone_shadow(size):
    """手机外框的柔和投影（按尺寸缓存：1080 帧只模糊一次）。

    深色画布上放一块深色手机，没有投影就是"一团黑贴在上面"；
    一层向下偏移的柔化黑影把手机从背景里托出来。
    """
    if size in _shadow_cache:
        return _shadow_cache[size]
    w, h = size[0] + 16 * SS, size[1] + 16 * SS
    m = Image.new("L", (w, h), 0)
    ImageDraw.Draw(m).rounded_rectangle([0, 0, w - 1, h - 1], radius=32 * SS, fill=120)
    _shadow_cache[size] = m.filter(ImageFilter.GaussianBlur(16 * SS))
    return _shadow_cache[size]


def paste_phone(canvas_img, phone_img):
    """将手机画面粘贴到画布，叠加拟真手机框（圆角 + 刘海 + 底部指示条 + 柔和投影）

    位置取两轴居中：水平方向左右等距，垂直方向在标题带（62）与字幕带（1120）
    之间等距。此前写死左上角 (40,110)，实测右边留 184、下边留 141，
    主体明显偏在左上——整条视频最扎眼的结构问题。
    """
    px = (W * SS - phone_img.size[0] - 16 * SS) // 2
    py = 62 * SS + ((1120 - 62) * SS - phone_img.size[1] - 16 * SS) // 2
    pw, ph = phone_img.size
    r = 28 * SS
    canvas_img.paste((0, 0, 0), (px, py + 8 * SS), _phone_shadow((pw, ph)))
    mask = Image.new("L", (pw, ph), 0)
    md = ImageDraw.Draw(mask)
    md.rounded_rectangle([0, 0, pw, ph], radius=r, fill=255)
    frame_layer = Image.new("RGBA", (pw + 16 * SS, ph + 16 * SS), (0, 0, 0, 0))
    fd = ImageDraw.Draw(frame_layer)
    fd.rounded_rectangle([0, 0, pw + 16 * SS - 1, ph + 16 * SS - 1], radius=r + 4 * SS,
                         outline=(60, 64, 74), width=3 * SS)
    canvas_img.paste(phone_img, (px + 8 * SS, py + 8 * SS), mask)
    canvas_img.paste(frame_layer, (px, py), frame_layer)
    notch_w, notch_h = 120 * SS, 24 * SS
    notch_x = px + 8 * SS + (pw - notch_w) // 2
    notch_y = py + 8 * SS
    nd = ImageDraw.Draw(canvas_img)
    nd.rounded_rectangle([notch_x, notch_y, notch_x + notch_w, notch_y + notch_h],
                         radius=notch_h // 2, fill=(12, 13, 17))
    indicator_w = 100 * SS
    indicator_x = px + 8 * SS + (pw - indicator_w) // 2
    indicator_y = py + 8 * SS + ph - 16 * SS
    nd.rounded_rectangle([indicator_x, indicator_y, indicator_x + indicator_w, indicator_y + 4 * SS],
                         radius=2 * SS, fill=(80, 84, 94))


def text_center(d, cx, y, s, font, fill):
    tw = d.textlength(s, font=font)
    d.text((cx * SS - tw / 2, y * SS), s, font=font, fill=fill)


def draw_code_block(d, x, y, lines, font_regular, font_bold):
    """代码语法高亮块：关键字绿色、字符串橙色、注释灰色、标识符白色。"""
    pad = 16 * SS
    line_h = 32 * SS
    max_w = max(d.textlength(ln, font=font_regular) for ln in lines) if lines else 0
    bw, bh = max_w + pad * 2, len(lines) * line_h + pad * 2
    d.rounded_rectangle([x * SS, y * SS, x * SS + bw, y * SS + bh],
                        radius=12 * SS, fill=CODE_BG)
    keywords = {"function", "return", "const", "let", "var", "if", "else", "for", "while",
                "this", "new", "true", "false", "null", "import", "from", "export", "def",
                "Page", "App", "Component", "wx", "cloud"}
    for i, ln in enumerate(lines):
        ly = y * SS + pad + i * line_h
        if ln.strip().startswith("//") or ln.strip().startswith("#"):
            d.text((x * SS + pad, ly), ln, font=font_regular, fill=CODE_CMT)
        else:
            tokens = ln.split()
            cx = x * SS + pad
            for tok in tokens:
                clean = tok.strip("(),{}[];:'\"")
                if clean in keywords:
                    d.text((cx, ly), tok, font=font_regular, fill=CODE_KW)
                elif tok.startswith(("'", '"')) or tok.endswith(("'", '"')):
                    d.text((cx, ly), tok, font=font_regular, fill=CODE_STR)
                else:
                    d.text((cx, ly), tok, font=font_regular, fill=WHITE)
                cx += d.textlength(tok + " ", font=font_regular)


# ============ 第 1 集：学习路径导览 ============
STAGES = [("①", "认知"), ("②", "准备"), ("③", "基础"),
          ("④", "进阶"), ("⑤", "云开发"), ("⑥", "发布"), ("⑦", "实战")]


def episode1():
    title = "第 1 集"
    T = 60.0
    n = int(T * FPS)

    captions = ["从零到上线：一条完整路径",
                "阶段① 认知：小程序是什么、值不值得学",
                "阶段② 准备：注册账号、装好开发者工具",
                "阶段③ 基础：WXML / WXSS / JS 三件套",
                "阶段④ 进阶：组件化、网络、性能、支付",
                "阶段⑤ 云开发：云函数 · 云数据库 · 云存储",
                "阶段⑥ 发布：体验版、审核、上线",
                "阶段⑦ 实战：完整待办项目端到端跑通",
                "每篇独立可读 · 代码可复现 · 事实链接官方",
                "下一集：《认识小程序》"]

    for i in range(n):
        t = i / FPS
        img, d = canvas(title)
        if t < 5:
            # 开场卡
            text_center(d, W / 2, 420, "小程序开发之路", fb(56), WHITE)
            text_center(d, W / 2, 520, "学习路径导览 · 第 1 集", f(30), GREEN)
            text_center(d, W / 2, 620, "5 分钟看懂从零到上线的完整路线", f(22), GRAY)
            caption(img, d, "从零到上线：一条完整路径")
        elif t < 46:
            # 阶梯逐个点亮（7 级）
            k = int((t - 5) / 5.8)  # 每级约 5.8s
            k = min(k, 6)
            p = phone_frame(lambda dd, s: _draw_stairs(dd, s, k))
            paste_phone(img, p)
            subtitle_bar(img, d, (t - 5) / 41, captions[1:8])
        elif t < 55:
            p = phone_frame(lambda dd, s: _draw_method(dd, s, t))
            paste_phone(img, p)
            caption(img, d, captions[8])
        else:
            text_center(d, W / 2, 460, "开始你的第一行代码", fb(44), WHITE)
            text_center(d, W / 2, 560, "下一集：《认识小程序》", f(26), GREEN)
            caption(img, d, captions[9])
        yield img


def _draw_stairs(dd, s, k):
    """阶梯：7 级逐级点亮"""
    base_y = 780
    for idx, (tag, _) in enumerate(STAGES[:k + 1]):
        x = 40 + idx * 52
        y = base_y - idx * 78
        col = GREEN if idx < k else (60, 66, 80)
        dd.rounded_rectangle([x * s, y * s, (x + 44) * s, (y + 72) * s], radius=8, fill=col)
        dd.text(((x + 6) * s, (y + 12) * s), tag, font=f(16), fill=WHITE)


def _draw_method(dd, s, t):
    items = [("每篇独立可读", "按需跳读，不依赖上下文"), ("代码可复现", "复制即跑，逐行可对照"), ("事实链接官方", "版本与 API 以官方为准")]
    for idx, (a, b) in enumerate(items):
        y = 220 + idx * 200
        dd.rounded_rectangle([30 * s, y * s, 345 * s, (y + 150) * s], radius=14, fill=(38, 42, 52))
        dd.text((48 * s, (y + 30) * s), a, font=fb(24), fill=WHITE)
        dd.text((48 * s, (y + 85) * s), b, font=f(20), fill=GRAY)


# ============ 第 2 集：认识小程序 ============
def episode2():
    title = "第 2 集"
    n = int(75 * FPS)
    captions = ["小程序：微信内的轻量应用，用完即走",
                "对比：小程序 vs H5 网页 vs 原生 App",
                "入口：微信内即开即用，免安装下载",
                "性能：原生渲染，比 H5 流畅",
                "生态：微信账号体系 + 支付 + 分享",
                "优势总结：触达成本最低的移动端载体",
                "边界：重内容/重游戏场景并不适合",
                "判断：你的产品适合做小程序吗",
                "下一集：《环境准备》——注册账号装好工具"]

    def scene_compare(dd, s, k):
        headers = ["H5 网页", "小程序", "原生 App"]
        cols = [("入口", "浏览器/链接", "微信内即开", "应用商店下载"),
                ("安装", "免安装", "免安装", "需安装"),
                ("性能", "一般", "原生渲染", "最优"),
                ("生态", "无", "微信账号/支付", "系统能力")]
        # 三列卡
        for ci, hname in enumerate(headers):
            x = 20 + ci * 120
            dd.rounded_rectangle([x * s, 180 * s, (x + 108) * s, 230 * s], radius=10, fill=GREEN if ci == 1 else (48, 52, 62))
            dd.text(((x + 18) * s, 196 * s), hname, font=fb(20), fill=WHITE)
        for ri, (kname, h5, mp, ap) in enumerate(cols):
            if ri >= k:
                break
            y = 270 + ri * 130
            dd.rounded_rectangle([20 * s, y * s, 348 * s, (y + 100) * s], radius=12, fill=(38, 42, 52))
            dd.text((36 * s, (y + 16) * s), kname, font=fb(22), fill=GREEN)
            dd.text((36 * s, (y + 52) * s), f"H5：{h5}   小程序：{mp}   原生：{ap}", font=f(18), fill=WHITE)

    def scene_reasons(dd, s, k):
        reasons = [("用完即走", "低频工具最友好"), ("微信生态", "登录/支付/分享开箱即用"), ("低成本触达", "扫码即用，无需下载")]
        for idx, (a, b) in enumerate(reasons[:k + 1]):
            y = 200 + idx * 200
            dd.rounded_rectangle([30 * s, y * s, 345 * s, (y + 150) * s], radius=14, fill=(38, 42, 52))
            dd.text((48 * s, (y + 28) * s), a, font=fb(26), fill=WHITE)
            dd.text((48 * s, (y + 88) * s), b, font=f(20), fill=GRAY)

    for i in range(n):
        t = i / FPS
        img, d = canvas(title)
        if t < 6:
            text_center(d, W / 2, 430, "认识小程序", fb(54), WHITE)
            text_center(d, W / 2, 540, "入口在微信内 · 无需下载 · 用完即走", f(26), GREEN)
            caption(img, d, captions[0])
        elif t < 30:
            k = int((t - 6) / 5.5)
            p = phone_frame(lambda dd, s: scene_compare(dd, s, min(k, 3)))
            paste_phone(img, p)
            subtitle_bar(img, d, (t - 6) / 24, captions[1:5])
        elif t < 50:
            k = int((t - 30) / 6.0)
            p = phone_frame(lambda dd, s: scene_reasons(dd, s, min(k, 2)))
            paste_phone(img, p)
            caption(img, d, captions[5])
        elif t < 62:
            text_center(d, W / 2, 440, "边界：什么不适合小程序", fb(40), WHITE)
            text_center(d, W / 2, 540, "重内容阅读 · 重游戏 · 高频重型工具", f(24), GRAY)
            text_center(d, W / 2, 620, "先判断产品形态，再选技术栈", f(22), GREEN)
            caption(img, d, captions[6])
        elif t < 68:
            text_center(d, W / 2, 460, "三个问题自检", fb(40), WHITE)
            for qy, q in enumerate(["高频还是低频？", "需要微信关系链吗？", "轻交互还是重内容？"], 1):
                text_center(d, W / 2, 560 + qy * 60, q, f(24), GRAY)
            caption(img, d, captions[7])
        else:
            text_center(d, W / 2, 460, "下一集：《环境准备》", fb(42), GREEN)
            text_center(d, W / 2, 560, "注册账号 · 装好开发者工具", f(24), GRAY)
            caption(img, d, captions[8])
        yield img


# ============ 第 3 集：环境准备 ============
def episode3():
    title = "第 3 集"
    n = int(75 * FPS)
    captions = ["环境准备：三件事——注册、装工具、跑通 Hello World",
                "第 1 步：注册小程序账号，拿到 AppID",
                "个人测试：用「测试号」免注册快速体验",
                "第 2 步：下载微信开发者工具（Stable 版）",
                "第 3 步：新建项目，填入 AppID",
                "Hello World：模拟器编译预览",
                "真机预览的本质：代码包上传到微信服务器",
                "验证：真机扫码，手机上看到 Hello World",
                "下一集：《项目结构》——app.json 与页面四件套"]

    def scene_register(dd, s, k):
        steps = [("注册小程序", "微信公众平台 → 立即注册"), ("开发设置", "拿到 AppID / AppSecret"), ("两种选择", "测试号免注册 · 真实号要审核")]
        for idx, (a, b) in enumerate(steps[:k + 1]):
            y = 160 + idx * 190
            dd.rounded_rectangle([30 * s, y * s, 345 * s, (y + 140) * s], radius=14, fill=(38, 42, 52))
            dd.text((50 * s, (y + 24) * s), f"{idx + 1}. {a}", font=fb(24), fill=WHITE)
            dd.text((50 * s, (y + 84) * s), b, font=f(19), fill=GRAY)

    def scene_project(dd, s, k):
        if k == 0:
            dd.rounded_rectangle([30 * s, 200 * s, 345 * s, 260 * s], radius=12, fill=(38, 42, 52))
            dd.text((50 * s, 220 * s), "下载开发者工具 Stable 版", font=fb(22), fill=WHITE)
        elif k == 1:
            dd.rounded_rectangle([30 * s, 200 * s, 345 * s, 380 * s], radius=12, fill=(38, 42, 52))
            dd.text((50 * s, 220 * s), "新建项目", font=fb(24), fill=WHITE)
            dd.text((50 * s, 280 * s), "项目名称：my-first-miniprogram", font=f(19), fill=GRAY)
            dd.text((50 * s, 320 * s), "AppID：你的真实 AppID 或测试号", font=f(19), fill=GRAY)
        else:
            dd.rounded_rectangle([30 * s, 200 * s, 345 * s, 380 * s], radius=12, fill=(38, 42, 52))
            dd.text((50 * s, 220 * s), "编译预览", font=fb(24), fill=GREEN)
            dd.text((50 * s, 280 * s), "模拟器显示 Hello, 小程序!", font=f(19), fill=WHITE)
            dd.text((50 * s, 320 * s), "JS data + WXML 绑定 = 数据驱动", font=f(19), fill=GRAY)

    for i in range(n):
        t = i / FPS
        img, d = canvas(title)
        if t < 6:
            text_center(d, W / 2, 430, "环境准备", fb(54), WHITE)
            text_center(d, W / 2, 540, "注册账号 · 装工具 · 跑通 Hello World", f(26), GREEN)
            caption(img, d, captions[0])
        elif t < 30:
            k = int((t - 6) / 7.0)
            p = phone_frame(lambda dd, s: scene_register(dd, s, min(k, 2)))
            paste_phone(img, p)
            subtitle_bar(img, d, (t - 6) / 24, captions[1:4])
        elif t < 54:
            k = int((t - 30) / 7.5)
            p = phone_frame(lambda dd, s: scene_project(dd, s, min(k, 2)))
            paste_phone(img, p)
            subtitle_bar(img, d, (t - 30) / 24, captions[4:7])
        elif t < 64:
            text_center(d, W / 2, 440, "真机预览的本质", fb(42), WHITE)
            text_center(d, W / 2, 540, "工具把代码包上传到微信服务器", f(24), GRAY)
            text_center(d, W / 2, 620, "手机扫码下载 → 在微信里运行", f(24), GREEN)
            caption(img, d, captions[7])
        else:
            text_center(d, W / 2, 460, "下一集：《项目结构》", fb(42), GREEN)
            text_center(d, W / 2, 560, "app.json 与页面四件套", f(24), GRAY)
            caption(img, d, captions[8])
        yield img


# ---------- 合成 ----------
def render_mp4(frames, name, fps=FPS):
    """逐帧流式写入 ffmpeg stdin 合成 H.264。

    2x 超采样：帧以 RW×RH 渲染，此处 LANCZOS 缩到 W×H 消除文字锯齿。
    不缓存帧列表：生成器 + rawvideo 管道，峰值内存仅数帧。
    """
    try:
        import imageio_ffmpeg
        exe = imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        raise SystemExit("缺少 imageio-ffmpeg：pip install imageio-ffmpeg")

    out = VIDEO_DIR / f"{name}.mp4"
    cmd = [exe, "-y",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
           "-framerate", str(fps), "-i", "pipe:0",
           "-c:v", "libx264", "-preset", "medium", "-crf", "27",
           "-pix_fmt", "yuv420p", "-threads", "1", "-movflags", "+faststart",
           str(out)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE,
                            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    count = 0
    try:
        for frame in frames:
            small = frame.resize((W, H), Image.LANCZOS)
            proc.stdin.write(small.tobytes())
            count += 1
    except BrokenPipeError:
        pass
    finally:
        try:
            proc.stdin.close()
        except BrokenPipeError:
            pass
        err = proc.stderr.read().decode("utf-8", "replace")
        if proc.wait() != 0:
            raise SystemExit(f"ffmpeg 合成失败（{name}）：\n{err[-2000:]}")

    size = out.stat().st_size
    print(f"{name}.mp4: {size // 1024} KB, {count} 帧, 时长 {count / fps:.1f}s")
    if size > SIZE_LIMIT:
        raise SystemExit(
            f"{name}.mp4 体积 {size // 1024} KB 超过契约上限 {SIZE_LIMIT // 1024} KB，"
            f"请提高 -crf 或缩短时长")


# ============ 第 4 集：WXML 数据绑定 ============
def episode4():
    title = "第 4 集"
    n = int(75 * FPS)
    captions = ["WXML：小程序的视图层模板语言",
                "数据绑定：{{}} 把 JS data 渲染到页面",
                "列表渲染：wx:for 遍历数组生成列表",
                "条件渲染：wx:if 控制组件的显示隐藏",
                "wx:key：列表 diff 的锚点，避免重渲染错乱",
                "事件绑定：bindtap/catchtap 响应用户操作",
                "数据流：用户操作 → 事件回调 → setData → 视图更新",
                "核心原则：视图只认 setData，直接改 data 不生效",
                "下一集：《自定义组件》——封装可复用的 UI 单元"]

    def scene_binding(dd, s, k):
        items = [
            ("{{message}}", "把 JS 的 data.message 渲染到视图"),
            ("{{count + 1}}", "支持简单表达式运算"),
            ("{{flag ? '显示' : '隐藏'}}", "三元表达式"),
        ]
        for idx, (code, desc) in enumerate(items[:k + 1]):
            y = 200 + idx * 180
            dd.rounded_rectangle([30 * s, y * s, 345 * s, (y + 140) * s], radius=12, fill=(38, 42, 52))
            dd.text((50 * s, (y + 20) * s), code, font=fb(22), fill=GREEN)
            dd.text((50 * s, (y + 70) * s), desc, font=f(19), fill=GRAY)

    def scene_list(dd, s, k):
        if k == 0:
            dd.text((50 * s, 200 * s), "wx:for=\"{{items}}\"", font=fb(22), fill=GREEN)
            dd.text((50 * s, 260 * s), "遍历数组，每项生成一个组件", font=f(19), fill=GRAY)
            for idx in range(3):
                dd.rounded_rectangle([50 * s, (320 + idx * 80) * s, 320 * s, (380 + idx * 80) * s],
                                     radius=8, fill=(50, 54, 66))
                dd.text((70 * s, (335 + idx * 80) * s), f"Item {{item_{idx}}}", font=f(18), fill=WHITE)
        elif k == 1:
            dd.text((50 * s, 200 * s), "wx:key=\"id\"", font=fb(22), fill=GREEN)
            dd.text((50 * s, 260 * s), "给每个列表项一个唯一标识", font=f(19), fill=GRAY)
            dd.text((50 * s, 320 * s), "diff 算法靠它识别哪些项变了", font=f(19), fill=WHITE)
            dd.text((50 * s, 380 * s), "不写 wx:key → Console 报警告", font=f(19), fill=(255, 100, 100))
        else:
            dd.text((50 * s, 200 * s), "wx:if vs hidden", font=fb(22), fill=GREEN)
            dd.text((50 * s, 260 * s), "wx:if：销毁/重建组件", font=f(19), fill=WHITE)
            dd.text((50 * s, 320 * s), "hidden：只改 display 样式", font=f(19), fill=WHITE)
            dd.text((50 * s, 400 * s), "频繁切换 → hidden", font=f(19), fill=GREEN)
            dd.text((50 * s, 460 * s), "很少变化 → wx:if", font=f(19), fill=GREEN)

    for i in range(n):
        t = i / FPS
        img, d = canvas(title)
        if t < 6:
            text_center(d, W / 2, 430, "WXML 数据绑定", fb(54), WHITE)
            text_center(d, W / 2, 540, "{{}} · wx:for · wx:if · 事件绑定", f(26), GREEN)
            caption(img, d, captions[0])
        elif t < 28:
            k = int((t - 6) / 7.0)
            p = phone_frame(lambda dd, s: scene_binding(dd, s, min(k, 2)))
            paste_phone(img, p)
            subtitle_bar(img, d, (t - 6) / 22, captions[1:4])
        elif t < 52:
            k = int((t - 28) / 7.5)
            p = phone_frame(lambda dd, s: scene_list(dd, s, min(k, 2)))
            paste_phone(img, p)
            subtitle_bar(img, d, (t - 28) / 24, captions[4:7])
        elif t < 64:
            text_center(d, W / 2, 400, "数据流闭环", fb(42), WHITE)
            text_center(d, W / 2, 500, "用户操作 → 事件 → setData → 视图", f(24), GREEN)
            text_center(d, W / 2, 580, "视图只认 setData", f(24), (255, 100, 100))
            caption(img, d, captions[7])
        else:
            text_center(d, W / 2, 460, "下一集：《自定义组件》", fb(42), GREEN)
            text_center(d, W / 2, 560, "封装可复用的 UI 单元", f(24), GRAY)
            caption(img, d, captions[8])
        yield img


# ============ 第 5 集：自定义组件 ============
def episode5():
    title = "第 5 集"
    n = int(90 * FPS)
    captions = ["为什么要拆组件？复用、解耦、可维护",
                "Component 构造器：properties / data / methods",
                "父传子：properties 声明接收的数据",
                "子传父：triggerEvent 抛出自定义事件",
                "组件通信全景：properties + triggerEvent + selectComponent",
                "样式隔离：默认隔离 / 启用外部样式类",
                "slot 插槽：在组件内放置父级的内容",
                "最佳实践：组件粒度适中、职责单一",
                "下一集：《云开发入门》——Serverless 后端能力"]

    def scene_component(dd, s, k):
        if k == 0:
            dd.text((50 * s, 200 * s), "Component({", font=fb(22), fill=GREEN)
            dd.text((50 * s, 250 * s), "  properties: { title: String },", font=f(18), fill=WHITE)
            dd.text((50 * s, 290 * s), "  data: { count: 0 },", font=f(18), fill=WHITE)
            dd.text((50 * s, 330 * s), "  methods: { onTap() { ... } }", font=f(18), fill=WHITE)
            dd.text((50 * s, 370 * s), "})", font=fb(22), fill=GREEN)
        elif k == 1:
            dd.text((50 * s, 180 * s), "父 → 子", font=fb(24), fill=GREEN)
            dd.rounded_rectangle([50 * s, 230 * s, 320 * s, 310 * s], radius=10, fill=(50, 54, 66))
            dd.text((70 * s, 250 * s), "properties: { item: Object }", font=f(18), fill=WHITE)
            dd.text((50 * s, 350 * s), "子 → 父", font=fb(24), fill=GREEN)
            dd.rounded_rectangle([50 * s, 400 * s, 320 * s, 480 * s], radius=10, fill=(50, 54, 66))
            dd.text((70 * s, 420 * s), "this.triggerEvent('change', {id})", font=f(18), fill=WHITE)
        else:
            dd.text((50 * s, 180 * s), "slot 插槽", font=fb(24), fill=GREEN)
            dd.rounded_rectangle([50 * s, 230 * s, 320 * s, 350 * s], radius=10, fill=(50, 54, 66))
            dd.text((70 * s, 250 * s), "组件模板：", font=f(18), fill=GRAY)
            dd.text((70 * s, 290 * s), "<slot></slot>", font=f(20), fill=WHITE)
            dd.text((50 * s, 390 * s), "父级使用：", font=f(18), fill=GRAY)
            dd.text((70 * s, 430 * s), "<my-card>自定义内容</my-card>", font=f(18), fill=WHITE)

    for i in range(n):
        t = i / FPS
        img, d = canvas(title)
        if t < 6:
            text_center(d, W / 2, 430, "自定义组件", fb(54), WHITE)
            text_center(d, W / 2, 540, "Component · 通信 · 样式隔离 · slot", f(26), GREEN)
            caption(img, d, captions[0])
        elif t < 36:
            k = int((t - 6) / 9.5)
            p = phone_frame(lambda dd, s: scene_component(dd, s, min(k, 2)))
            paste_phone(img, p)
            subtitle_bar(img, d, (t - 6) / 30, captions[1:4])
        elif t < 60:
            text_center(d, W / 2, 380, "组件通信全景", fb(42), WHITE)
            text_center(d, W / 2, 480, "properties ↓  triggerEvent ↑", f(28), GREEN)
            text_center(d, W / 2, 560, "selectComponent → 跨层级", f(22), GRAY)
            caption(img, d, captions[4])
        elif t < 76:
            text_center(d, W / 2, 400, "样式隔离", fb(42), WHITE)
            text_center(d, W / 2, 500, "默认：组件内外互不影响", f(24), GRAY)
            text_center(d, W / 2, 580, "externalClasses 按需开放", f(24), GREEN)
            caption(img, d, captions[6])
        else:
            text_center(d, W / 2, 460, "下一集：《云开发入门》", fb(42), GREEN)
            text_center(d, W / 2, 560, "Serverless 后端能力全景", f(24), GRAY)
            caption(img, d, captions[8])
        yield img


# ============ 第 6 集：云开发入门 ============
def episode6():
    title = "第 6 集"
    n = int(75 * FPS)
    captions = ["云开发 = Serverless 后端，免运维",
                "四大能力：云函数 · 云数据库 · 云存储 · 云托管",
                "统一身份：cloud.getWXContext() 免鉴权拿 openid",
                "云函数：后端逻辑，Node.js 运行环境",
                "云数据库：JSON 文档型，按集合组织",
                "云存储：上传文件，获取临时链接",
                "安全原则：前端不可信，敏感逻辑走云函数",
                "免费额度学习够用，按调用计费",
                "下一集：跟随实战项目完整上线"]

    def scene_cloud(dd, s, k):
        caps = [("云函数", "后端逻辑", GREEN), ("云数据库", "JSON 文档", (255, 165, 0)),
                ("云存储", "文件管理", (66, 133, 244)), ("云托管", "容器服务", (156, 39, 176))]
        for idx, (name, desc, col) in enumerate(caps[:k + 1]):
            x = 40 + (idx % 2) * 155
            y = 220 + (idx // 2) * 180
            dd.rounded_rectangle([x * s, y * s, (x + 140) * s, (y + 130) * s], radius=12, fill=(38, 42, 52))
            dd.rounded_rectangle([x * s, y * s, (x + 140) * s, (y + 40) * s], radius=12, fill=col)
            dd.text(((x + 15) * s, (y + 8) * s), name, font=fb(20), fill=WHITE)
            dd.text(((x + 15) * s, (y + 60) * s), desc, font=f(18), fill=GRAY)

    for i in range(n):
        t = i / FPS
        img, d = canvas(title)
        if t < 6:
            text_center(d, W / 2, 430, "云开发入门", fb(54), WHITE)
            text_center(d, W / 2, 540, "Serverless · 免运维 · 按调用计费", f(26), GREEN)
            caption(img, d, captions[0])
        elif t < 30:
            k = int((t - 6) / 5.5)
            p = phone_frame(lambda dd, s: scene_cloud(dd, s, min(k, 3)))
            paste_phone(img, p)
            subtitle_bar(img, d, (t - 6) / 24, captions[1:5])
        elif t < 50:
            text_center(d, W / 2, 380, "统一身份体系", fb(42), WHITE)
            text_center(d, W / 2, 480, "cloud.getWXContext()", f(28), GREEN)
            text_center(d, W / 2, 560, "免鉴权拿 openid", f(24), GRAY)
            caption(img, d, captions[5])
        elif t < 64:
            text_center(d, W / 2, 400, "安全原则", fb(42), WHITE)
            text_center(d, W / 2, 500, "前端不可信", f(28), (255, 100, 100))
            text_center(d, W / 2, 580, "敏感逻辑一律走云函数", f(24), GREEN)
            caption(img, d, captions[6])
        else:
            text_center(d, W / 2, 460, "跟随实战项目完整上线", fb(42), GREEN)
            text_center(d, W / 2, 560, "从零做一个可上线的待办清单", f(24), GRAY)
            caption(img, d, captions[8])
        yield img


# ============ 第 7 集：性能优化 ============
def episode7():
    title = "第 7 集"
    n = int(75 * FPS)
    captions = ["性能瓶颈：setData 跨线程通信是核心开销",
                "军规一：只传差异，不传全量",
                "军规二：拆分大对象为小组件",
                "军规三：避免高频事件里频繁 setData",
                "军规四：wx:key 帮助列表精确 diff",
                "军规五：长列表按需渲染（可视区域 ± 缓冲）",
                "军规六：setUpdatePerformanceListener 测量",
                "分包加载：主包 ≤2M，总 ≤30M",
                "性能优化不是猜，是测量后精准打击"]

    def scene_perf(dd, s, k):
        rules = [
            ("路径写法", "setData({'list[0].done': true})", GREEN),
            ("拆组件", "Shadow 树规模 ∝ diff 成本", (255, 165, 0)),
            ("防抖", "scroll/touch → debounce 300ms", (66, 133, 244)),
            ("wx:key", "精确 diff，避免全量重渲染", GREEN),
        ]
        for idx, (title_text, desc, col) in enumerate(rules[:k + 1]):
            y = 180 + idx * 140
            dd.rounded_rectangle([30 * s, y * s, 345 * s, (y + 110) * s], radius=10, fill=(38, 42, 52))
            dd.rounded_rectangle([30 * s, y * s, 345 * s, (y + 36) * s], radius=10, fill=col)
            dd.text((45 * s, (y + 6) * s), title_text, font=fb(20), fill=WHITE)
            dd.text((45 * s, (y + 55) * s), desc, font=f(17), fill=GRAY)

    for i in range(n):
        t = i / FPS
        img, d = canvas(title)
        if t < 6:
            text_center(d, W / 2, 430, "性能优化", fb(54), WHITE)
            text_center(d, W / 2, 540, "setData 军规 · 分包 · 测量驱动", f(26), GREEN)
            caption(img, d, captions[0])
        elif t < 36:
            k = int((t - 6) / 7.0)
            p = phone_frame(lambda dd, s: scene_perf(dd, s, min(k, 3)))
            paste_phone(img, p)
            subtitle_bar(img, d, (t - 6) / 30, captions[1:5])
        elif t < 55:
            text_center(d, W / 2, 380, "分包加载", fb(42), WHITE)
            text_center(d, W / 2, 480, "主包 ≤ 2MB", f(28), (255, 100, 100))
            text_center(d, W / 2, 560, "总包 ≤ 30MB", f(28), GREEN)
            caption(img, d, captions[7])
        elif t < 65:
            text_center(d, W / 2, 400, "测量而非猜测", fb(42), WHITE)
            text_center(d, W / 2, 500, "setUpdatePerformanceListener", f(24), GREEN)
            text_center(d, W / 2, 580, "量化每次 setData 的耗时", f(22), GRAY)
            caption(img, d, captions[8])
        else:
            text_center(d, W / 2, 460, "下一集：《微信支付》", fb(42), GREEN)
            text_center(d, W / 2, 560, "云调用接入，安全又简单", f(24), GRAY)
            caption(img, d, captions[8])
        yield img


# ============ 第 8 集：微信支付 ============
def episode8():
    title = "第 8 集"
    n = int(75 * FPS)
    captions = ["微信支付：云开发云调用接入，免自建服务端",
                "前置条件：企业主体 + 商户号 + 关联小程序",
                "云调用：cloud.cloudPay 统一下单",
                "前端：wx.requestPayment 拉起支付",
                "回调处理：幂等校验，防重复发货",
                "退款：cloudPay.refund，原路退回",
                "安全：签名校验在云函数，前端不碰密钥",
                "测试：沙箱环境验证全流程",
                "支付是商业闭环的核心能力"]

    def scene_pay(dd, s, k):
        steps = [
            ("1. 下单", "cloudPay.unifiedOrder()", GREEN),
            ("2. 支付", "wx.requestPayment()", (255, 165, 0)),
            ("3. 回调", "幂等校验 + 发货", (66, 133, 244)),
            ("4. 退款", "cloudPay.refund()", (156, 39, 176)),
        ]
        for idx, (title_text, desc, col) in enumerate(steps[:k + 1]):
            y = 180 + idx * 130
            dd.rounded_rectangle([30 * s, y * s, 345 * s, (y + 100) * s], radius=10, fill=(38, 42, 52))
            dd.rounded_rectangle([30 * s, y * s, 120 * s, (y + 36) * s], radius=10, fill=col)
            dd.text((40 * s, (y + 6) * s), title_text, font=fb(18), fill=WHITE)
            dd.text((45 * s, (y + 55) * s), desc, font=f(17), fill=GRAY)

    for i in range(n):
        t = i / FPS
        img, d = canvas(title)
        if t < 6:
            text_center(d, W / 2, 430, "微信支付", fb(54), WHITE)
            text_center(d, W / 2, 540, "云调用 · requestPayment · 幂等回调", f(26), GREEN)
            caption(img, d, captions[0])
        elif t < 30:
            k = int((t - 6) / 5.5)
            p = phone_frame(lambda dd, s: scene_pay(dd, s, min(k, 3)))
            paste_phone(img, p)
            subtitle_bar(img, d, (t - 6) / 24, captions[1:5])
        elif t < 50:
            text_center(d, W / 2, 380, "安全原则", fb(42), WHITE)
            text_center(d, W / 2, 480, "签名校验在云函数", f(28), (255, 100, 100))
            text_center(d, W / 2, 560, "前端不碰商户密钥", f(24), GREEN)
            caption(img, d, captions[6])
        elif t < 64:
            text_center(d, W / 2, 400, "回调幂等", fb(42), WHITE)
            text_center(d, W / 2, 500, "同一笔支付可能多次通知", f(24), GRAY)
            text_center(d, W / 2, 580, "用订单号去重，防重复发货", f(24), GREEN)
            caption(img, d, captions[7])
        else:
            text_center(d, W / 2, 460, "下一集：《上线发布》", fb(42), GREEN)
            text_center(d, W / 2, 560, "体验版 → 审核 → 发布", f(24), GRAY)
            caption(img, d, captions[8])
        yield img


# ============ 第 9 集：上线发布 ============
def episode9():
    title = "第 9 集"
    n = int(75 * FPS)
    captions = ["上线流程：上传 → 体验版 → 审核 → 发布",
                "上传代码：开发者工具 → 上传（填版本号 + 备注）",
                "体验版：指定体验成员扫码测试",
                "提交审核：选类目 + 填审核材料",
                "审核周期：通常 1-7 个工作日",
                "发布：全量发布 or 灰度发布",
                "版本回退：发现严重 bug 可即时回退上一版",
                "更新机制：getUpdateManager 提示用户更新",
                "上线不是终点，持续运营才是开始"]

    def scene_release(dd, s, k):
        stages = [
            ("上传", "填版本号+备注", GREEN),
            ("体验版", "成员扫码测试", (255, 165, 0)),
            ("审核", "1-7 工作日", (66, 133, 244)),
            ("发布", "全量 or 灰度", (156, 39, 176)),
        ]
        for idx, (name, desc, col) in enumerate(stages[:k + 1]):
            x = 60 + idx * 75
            y_base = 350
            dd.rounded_rectangle([x * s, y_base * s, (x + 60) * s, (y_base + 60) * s], radius=30, fill=col)
            text_center(dd, (x + 30) * s, (y_base + 15) * s, name, fb(18), WHITE)
            dd.text(((x - 5) * s, (y_base + 80) * s), desc, font=f(14), fill=GRAY)
            if idx < k:
                dd.text(((x + 60) * s, (y_base + 20) * s), "→", font=fb(24), fill=GRAY)

    for i in range(n):
        t = i / FPS
        img, d = canvas(title)
        if t < 6:
            text_center(d, W / 2, 430, "上线发布", fb(54), WHITE)
            text_center(d, W / 2, 540, "上传 · 体验版 · 审核 · 发布 · 回退", f(26), GREEN)
            caption(img, d, captions[0])
        elif t < 36:
            k = int((t - 6) / 7.0)
            p = phone_frame(lambda dd, s: scene_release(dd, s, min(k, 3)))
            paste_phone(img, p)
            subtitle_bar(img, d, (t - 6) / 30, captions[1:5])
        elif t < 55:
            text_center(d, W / 2, 380, "版本回退", fb(42), WHITE)
            text_center(d, W / 2, 480, "MP 后台 → 版本管理", f(26), GREEN)
            text_center(d, W / 2, 560, "即时回退，无需审核", f(24), GRAY)
            caption(img, d, captions[6])
        elif t < 65:
            text_center(d, W / 2, 400, "更新机制", fb(42), WHITE)
            text_center(d, W / 2, 500, "getUpdateManager()", f(26), GREEN)
            text_center(d, W / 2, 580, "检测到新版本 → 提示用户更新", f(22), GRAY)
            caption(img, d, captions[7])
        else:
            text_center(d, W / 2, 460, "下一集：《实战项目导览》", fb(42), GREEN)
            text_center(d, W / 2, 560, "三个完整项目串联全部知识", f(24), GRAY)
            caption(img, d, captions[8])
        yield img


# ============ 第 10 集：实战项目导览 ============
def episode10():
    title = "第 10 集"
    n = int(90 * FPS)
    captions = ["三个实战项目，串联本库全部核心知识",
                "待办清单：云开发全栈（云函数 + 云数据库 + 权限隔离）",
                "多页面导航：tabBar + 四种跳转 API + 生命周期",
                "商品列表：wx:for/wx:key + scroll-view + 搜索",
                "每个项目都有完整代码 + 架构决策复盘",
                "踩坑回顾：真实开发中遇到的问题与解决",
                "导入开发者工具即可运行",
                "代码与教程逐行一致，CI 自动校验",
                "从零做一个可上线的小程序，你准备好了吗"]

    def scene_projects(dd, s, k):
        projects = [
            ("待办清单", "云开发全栈", "★★★★☆", GREEN),
            ("多页面导航", "TabBar + 跳转", "★★☆☆☆", (255, 165, 0)),
            ("商品列表", "列表 + 搜索", "★★★☆☆", (66, 133, 244)),
        ]
        for idx, (name, desc, stars, col) in enumerate(projects[:k + 1]):
            y = 190 + idx * 160
            dd.rounded_rectangle([30 * s, y * s, 345 * s, (y + 130) * s], radius=12, fill=(38, 42, 52))
            dd.rounded_rectangle([30 * s, y * s, 345 * s, (y + 42) * s], radius=12, fill=col)
            dd.text((45 * s, (y + 8) * s), name, font=fb(22), fill=WHITE)
            dd.text((45 * s, (y + 60) * s), desc, font=f(19), fill=GRAY)
            dd.text((45 * s, (y + 95) * s), stars, font=f(18), fill=(255, 200, 0))

    for i in range(n):
        t = i / FPS
        img, d = canvas(title)
        if t < 6:
            text_center(d, W / 2, 430, "实战项目导览", fb(54), WHITE)
            text_center(d, W / 2, 540, "三个完整项目 · 串联全部知识", f(26), GREEN)
            caption(img, d, captions[0])
        elif t < 36:
            k = int((t - 6) / 9.5)
            p = phone_frame(lambda dd, s: scene_projects(dd, s, min(k, 2)))
            paste_phone(img, p)
            subtitle_bar(img, d, (t - 6) / 30, captions[1:4])
        elif t < 58:
            text_center(d, W / 2, 380, "代码与教程一致", fb(42), WHITE)
            text_center(d, W / 2, 480, "逐行比对 · CI 自动校验", f(26), GREEN)
            text_center(d, W / 2, 560, "架构决策复盘 + 踩坑回顾", f(24), GRAY)
            caption(img, d, captions[4])
        elif t < 74:
            text_center(d, W / 2, 400, "导入即运行", fb(42), WHITE)
            text_center(d, W / 2, 500, "examples/ 目录下三个工程", f(24), GREEN)
            text_center(d, W / 2, 580, "开发者工具 → 导入项目", f(24), GRAY)
            caption(img, d, captions[6])
        else:
            text_center(d, W / 2, 420, "你准备好了吗？", fb(48), GREEN)
            text_center(d, W / 2, 540, "从零做一个可上线的小程序", f(26), WHITE)
            caption(img, d, captions[8])
        yield img


def episode11():
    title = "第 11 集"
    n = int(75 * FPS)
    captions = ["云函数：在云端运行 Node.js 代码",
                "无需自建服务器，微信托管按量付费",
                "小程序端 wx.cloud.callFunction 调用",
                "云函数内 cloud.database() 操作数据库",
                "权限隔离：云函数可绕过前端权限限制",
                "冷启动优化：初始化逻辑放函数外层",
                "本地调试：右键云函数目录 → 本地调试"]

    def scene_cloud_func(dd, s):
        dd.rounded_rectangle([20 * s, 180 * s, 355 * s, 340 * s], radius=12, fill=(38, 42, 52))
        dd.text((35 * s, 195 * s), "cloudfunctions/", font=fb(18), fill=GREEN)
        dd.text((35 * s, 230 * s), "  todo/", font=f(16), fill=WHITE)
        dd.text((50 * s, 260 * s), "index.js", font=f(15), fill=GRAY)
        dd.text((50 * s, 290 * s), "package.json", font=f(15), fill=GRAY)
        dd.rounded_rectangle([20 * s, 360 * s, 355 * s, 480 * s], radius=12, fill=(38, 42, 52))
        dd.text((35 * s, 375 * s), "调用链路", font=fb(16), fill=GREEN)
        for i, step in enumerate(["小程序 → callFunction", "云函数 → database()", "返回结果 → setData"]):
            dd.text((50 * s, (405 + i * 28) * s), step, font=f(14), fill=GRAY)

    for i in range(n):
        t = i / FPS
        img, d = canvas(title)
        if t < 6:
            text_center(d, W / 2, 430, "云函数", fb(54), WHITE)
            text_center(d, W / 2, 540, "云端运行 · 无需服务器", f(26), GREEN)
            caption(img, d, captions[0])
        elif t < 30:
            p = phone_frame(lambda dd, s: scene_cloud_func(dd, s))
            paste_phone(img, p)
            subtitle_bar(img, d, (t - 6) / 24, captions[1:4])
        elif t < 52:
            text_center(d, W / 2, 380, "权限隔离", fb(42), WHITE)
            text_center(d, W / 2, 480, "云函数可绕过前端权限", f(26), GREEN)
            text_center(d, W / 2, 560, "数据库权限设为「仅云函数可读写」", f(22), GRAY)
            caption(img, d, captions[4])
        else:
            text_center(d, W / 2, 400, "调试与优化", fb(42), WHITE)
            text_center(d, W / 2, 500, "右键 → 本地调试", f(26), GREEN)
            text_center(d, W / 2, 580, "初始化放外层减少冷启动", f(24), GRAY)
            caption(img, d, captions[6])
        yield img


def episode12():
    title = "第 12 集"
    n = int(75 * FPS)
    captions = ["授权与隐私：小程序的数据安全模型",
                "scope 机制：每个能力对应一个授权开关",
                "wx.authorize 首次弹窗 → wx.getSetting 查询",
                "用户拒绝后需引导去设置页手动开启",
                "隐私指引：收集用户信息前必须声明用途",
                "MP 后台 → 设置 → 服务内容声明",
                "合规是上线的前提，不可忽视"]

    def scene_auth(dd, s):
        dd.rounded_rectangle([20 * s, 180 * s, 355 * s, 500 * s], radius=12, fill=(38, 42, 52))
        dd.text((35 * s, 195 * s), "scope 授权模型", font=fb(18), fill=GREEN)
        scopes = [
            ("scope.userInfo", "用户信息"),
            ("scope.location", "精确位置"),
            ("scope.camera", "摄像头"),
            ("scope.record", "录音"),
            ("scope.writePhotosAlbum", "保存到相册"),
        ]
        for i, (scope, desc) in enumerate(scopes):
            y = 235 + i * 48
            dd.text((40 * s, y * s), scope, font=f(13), fill=WHITE)
            dd.text((250 * s, y * s), desc, font=f(13), fill=GRAY)
            col = GREEN if i < 2 else (100, 100, 110)
            dd.ellipse([320 * s, (y + 2) * s, 340 * s, (y + 18) * s], fill=col)

    for i in range(n):
        t = i / FPS
        img, d = canvas(title)
        if t < 6:
            text_center(d, W / 2, 430, "授权与隐私", fb(54), WHITE)
            text_center(d, W / 2, 540, "scope 模型 · 隐私指引", f(26), GREEN)
            caption(img, d, captions[0])
        elif t < 30:
            p = phone_frame(lambda dd, s: scene_auth(dd, s))
            paste_phone(img, p)
            subtitle_bar(img, d, (t - 6) / 24, captions[1:4])
        elif t < 52:
            text_center(d, W / 2, 380, "隐私指引", fb(42), WHITE)
            text_center(d, W / 2, 480, "收集信息前声明用途", f(26), GREEN)
            text_center(d, W / 2, 560, "MP 后台 → 服务内容声明", f(22), GRAY)
            caption(img, d, captions[4])
        else:
            text_center(d, W / 2, 420, "合规是上线前提", fb(42), GREEN)
            text_center(d, W / 2, 540, "审核会检查隐私合规", f(26), WHITE)
            caption(img, d, captions[6])
        yield img


def episode13():
    title = "第 13 集"
    n = int(75 * FPS)
    captions = ["调试与排错：定位问题的系统方法",
                "开发者工具：Console / Network / AppData",
                "真机调试：实时看日志，要求同 WiFi",
                "vConsole：真机上的调试面板",
                "常见坑：模拟器正常但真机异常",
                "线上监控：MP 后台 → 运维中心",
                "排错是进阶必备技能，越早练越好"]

    def scene_debug(dd, s):
        dd.rounded_rectangle([20 * s, 180 * s, 355 * s, 520 * s], radius=12, fill=(38, 42, 52))
        dd.text((35 * s, 195 * s), "调试面板", font=fb(18), fill=GREEN)
        panels = [
            ("Console", "日志 · 错误 · warn", GREEN),
            ("Network", "请求 · 响应 · 耗时", (66, 133, 244)),
            ("AppData", "data 实时查看 · 编辑", (255, 165, 0)),
            ("Audits", "性能分析 · 评分", (150, 100, 200)),
        ]
        for i, (name, desc, col) in enumerate(panels):
            y = 240 + i * 65
            dd.rounded_rectangle([35 * s, y * s, 340 * s, (y + 50) * s], radius=8, fill=(50, 54, 64))
            dd.text((50 * s, (y + 8) * s), name, font=fb(16), fill=col)
            dd.text((50 * s, (y + 30) * s), desc, font=f(13), fill=GRAY)

    for i in range(n):
        t = i / FPS
        img, d = canvas(title)
        if t < 6:
            text_center(d, W / 2, 430, "调试与排错", fb(54), WHITE)
            text_center(d, W / 2, 540, "定位问题的系统方法", f(26), GREEN)
            caption(img, d, captions[0])
        elif t < 30:
            p = phone_frame(lambda dd, s: scene_debug(dd, s))
            paste_phone(img, p)
            subtitle_bar(img, d, (t - 6) / 24, captions[1:4])
        elif t < 52:
            text_center(d, W / 2, 380, "真机 ≠ 模拟器", fb(42), WHITE)
            text_center(d, W / 2, 480, "渲染环境不同", f(26), GREEN)
            text_center(d, W / 2, 560, "fixed 定位 · canvas · 音频差异", f(22), GRAY)
            caption(img, d, captions[4])
        else:
            text_center(d, W / 2, 400, "线上监控", fb(42), WHITE)
            text_center(d, W / 2, 500, "MP 后台 → 运维中心", f(26), GREEN)
            text_center(d, W / 2, 580, "错误日志 · 性能数据 · 用户反馈", f(22), GRAY)
            caption(img, d, captions[6])
        yield img


EPISODES = [("video-01-roadmap", episode1),
            ("video-02-intro", episode2),
            ("video-03-env", episode3),
            ("video-04-wxml", episode4),
            ("video-05-component", episode5),
            ("video-06-cloud", episode6),
            ("video-07-perf", episode7),
            ("video-08-payment", episode8),
            ("video-09-release", episode9),
            ("video-10-practice", episode10),
            ("video-11-cloudfunc", episode11),
            ("video-12-auth", episode12),
            ("video-13-debug", episode13)]


if __name__ == "__main__":
    for ep_name, ep_fn in EPISODES:
        print(f"渲染 {ep_name} …")
        render_mp4(ep_fn(), ep_name)
    print("全部视频生成完成")
