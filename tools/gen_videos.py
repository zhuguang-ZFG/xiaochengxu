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
import pathlib
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from PIL import Image, ImageDraw  # noqa: E402
from render import load_font  # noqa: E402

VIDEO_DIR = pathlib.Path(__file__).resolve().parent.parent / "docs" / "assets" / "videos"
VIDEO_DIR.mkdir(parents=True, exist_ok=True)

W, H = 720, 1280
FPS = 24
SIZE_LIMIT = 3 * 1024 * 1024   # 契约：单集 ≤ 3MB

GREEN = (7, 193, 96)
BG = (18, 20, 26)
GRAY = (150, 156, 168)
WHITE = (245, 245, 245)


def f(size):
    """常规体（视频按 1x 物理像素绘制，不走 render 的 2x 超采样）"""
    return load_font(size, "regular")


def fb(size):
    return load_font(size, "bold")


def canvas(title, series="小程序开发之路 · 教学视频"):
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, 60], fill=(12, 13, 17))
    d.text((24, 14), series, font=f(20), fill=GRAY)
    d.text((W - 24 - d.textlength(title, font=f(20)), 14), title, font=f(20), fill=GREEN)
    d.rectangle([0, 60, W, 62], fill=(40, 44, 54))
    return img, d


def caption(img, d, text):
    """底部字幕区：常驻标题 + 当前要点"""
    d.rectangle([0, 1120, W, H], fill=(12, 13, 17))
    d.rectangle([0, 1120, W, 1122], fill=(40, 44, 54))
    # 要点文字自动换行（每行最多 24 字）
    lines = []
    for para in text.split("\n"):
        cur = ""
        for ch in para:
            if len(cur) >= 22:
                lines.append(cur)
                cur = ""
            cur += ch
        if cur:
            lines.append(cur)
    y0 = 1150
    for i, ln in enumerate(lines[:3]):
        d.text((40, y0 + i * 42), ln, font=fb(30), fill=WHITE)
    d.text((40, 1226), "▶ 学习路径 · 每集 1-2 分钟 · 代码可复现", font=f(18), fill=GRAY)


def subtitle_bar(img, d, t, points):
    """按进度切换要点字幕"""
    dur = max(1, len(points))
    idx = min(int(t * dur), len(points) - 1)
    caption(img, d, points[idx])


def phone_frame(draw_fn):
    """中部手机演示区：375x667 设计坐标 -> 480x854 区域（x 40-520, y 110-964）"""
    img = Image.new("RGB", (480, 854), (24, 26, 32))
    dd = ImageDraw.Draw(img)
    draw_fn(dd, 1.28)  # 375*1.28=480
    return img


def paste_phone(canvas_img, phone_img):
    canvas_img.paste(phone_img, (40, 110))


def text_center(d, cx, y, s, font, fill):
    tw = d.textlength(s, font=font)
    d.text((cx - tw / 2, y), s, font=font, fill=fill)


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

    不缓存帧列表：720x1280 RGB 单帧 2.7MB，75s×24fps 一次性持有会占用约 5GB 内存。
    改为生成器 + rawvideo 管道后峰值内存仅数帧，且省去上千个 PNG 临时文件。
    """
    try:
        import imageio_ffmpeg
        exe = imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        raise SystemExit("缺少 imageio-ffmpeg：pip install imageio-ffmpeg")

    out = VIDEO_DIR / f"{name}.mp4"
    # -threads 1 不是为了速度，而是为了**可复现**：libx264 的帧级多线程会让
    # 同一份输入在不同核数的机器上编出不同字节（实测 1/2/4/8 线程四个哈希全不同），
    # 那样 CI 上「重新生成并与已提交文件比对」的检查会永远失败。代价约 +7 秒/集。
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
            proc.stdin.write(frame.tobytes())
            count += 1
    except BrokenPipeError:
        pass   # ffmpeg 已退出，错误详情从 stderr 读取
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


EPISODES = [("video-01-roadmap", episode1),
            ("video-02-intro", episode2),
            ("video-03-env", episode3)]


if __name__ == "__main__":
    for ep_name, ep_fn in EPISODES:
        print(f"渲染 {ep_name} …")
        render_mp4(ep_fn(), ep_name)
    print("全部视频生成完成")
