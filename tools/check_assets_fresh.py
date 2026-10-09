# -*- coding: utf-8 -*-
"""视觉资产新鲜度校验：重跑生成脚本，确认**已提交的**资产就是脚本当前的输出。

为什么需要它：契约声称「资产全部程序化生成，改脚本重跑即可」，但在此之前
没有任何机制校验这句话——CI 只检查已提交文件的体积与命名，从不重新生成，
因此「改了脚本忘了重跑」或「手工改了 GIF」这类漂移完全无人发现。

做法：
1. 先确认 docs/assets 相对 HEAD 是干净的——否则基准不成立
2. **清空 docs/assets**，再依次重跑四个生成脚本
3. `git status` 必须仍然干净；有任何改动就是漂移

第 1 步不能省：若拿「重跑前的工作区」当基准，那么「本地已跑过脚本但忘了提交」
这种情况两次快照相同，脚本会报通过——而仓库里提交的恰恰是旧资产。

第 2 步也不能省：若不清空，脚本已不再产出的旧资产会原样躺在那里，
git 看不出任何差别，「生成器删掉某个资产」这个漂移方向就永远测不到。
清空是可恢复的——第 1 步已保证所有资产都在 HEAD 里（`git checkout -- docs/assets`
即可还原），所以本脚本不会弄丢任何未提交的内容。

三种漂移方向都能报出：
- 内容变化（` M`）：仓库里提交的是旧版本
- 新增未提交（`??`）：脚本新产出的文件没进仓库
- 消失（` D`）：仓库里提交了，但脚本已不再产出

前提：本机渲染必须与资产生成时一致。中文字体是最容易踩的坑——
Windows 走微软雅黑、macOS 走苹方、Linux 走 Noto CJK，**同一份脚本在 Linux 上
渲染出的像素与 Windows 完全不同**，比对必然失败。所以 CI 把这一步放在
windows-latest 上，并锁定与生成时一致的 pillow / imageio-ffmpeg 版本。
ffmpeg 另需 `-threads 1`：libx264 的帧级多线程在不同核数机器上输出不同字节。

版本不对时代价是**误报**：库里真实发生过一次——video-06-cloud.mp4 用另一版
ffmpeg 生成，逐帧解码与脚本输出完全相同（1800 帧，md5 全同），只是编码字节
不同（272KB vs 284KB），检查却说「仓库里的是旧版本」，把工具链问题报成了
资产漂移。所以在动 docs/assets 之前，先核对本机 pillow / imageio-ffmpeg 版本，
与 CI 锁定值（.github/workflows/check.yml 的 assets 作业）不符就直接拒绝。

用法：python tools/check_assets_fresh.py
退出码：0 = 全部一致；1 = 存在漂移或工具链不符
"""
import pathlib
import shutil
import subprocess
import sys
import time

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = pathlib.Path(__file__).resolve().parent.parent
ASSETS = ROOT / "docs" / "assets"
ASSETS_REL = "docs/assets"
TOOLS = ROOT / "tools"

# 顺序有意义：statics/diagrams 各写各的文件，animations 与 videos 最后
GENERATORS = ["gen_statics.py", "gen_diagrams.py", "gen_animations.py", "gen_videos.py"]

# 与 .github/workflows/check.yml 的 assets 作业锁定同一套版本——资产就是这套
# 工具链的产物（Pillow 决定像素，imageio-ffmpeg 决定封装字节）。改 workflow 里
# 的 pin 时必须同步这里，并且重新生成全部资产，否则本检查会把版本差异当成漂移。
PINNED_TOOLCHAIN = {"pillow": "12.3.0", "imageio-ffmpeg": "0.6.0"}


def git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True,
                          text=True, encoding="utf-8", errors="replace")


def check_toolchain():
    """核对本机 pillow / imageio-ffmpeg 版本，与 CI 锁定值不符即拒绝比对。

    只认版本，不试渲染：版本一致就假定字节一致（ffmpeg 已锁 -threads 1），
    版本不同则明确说清「是工具链问题，不是资产漂移」。两个库都没装时返回
    True——缺依赖会由后面的生成脚本自己报错，这里不抢先失败。
    """
    try:
        import PIL
        import imageio_ffmpeg
    except ImportError:
        print("⚠️ 未检测到 Pillow / imageio-ffmpeg，跳过节链路指纹"
              "（生成阶段缺依赖会直接报错）")
        return True

    fp = {"pillow": PIL.__version__,
          "imageio-ffmpeg": getattr(imageio_ffmpeg, "__version__", "unknown")}
    try:
        v = imageio_ffmpeg.get_ffmpeg_version()
        # 不同版本返回类型不一：元组 (7, 1) 或字符串 "7.1"——按字符串迭代会得到
        # 逐字符的 "7...1...-" 这种垃圾输出，必须分清
        fp["ffmpeg"] = v if isinstance(v, str) else ".".join(str(p) for p in v)
    except Exception:
        fp["ffmpeg"] = "unknown"
    print(f"工具链: Pillow {fp['pillow']} / imageio-ffmpeg {fp['imageio-ffmpeg']}"
          f"（ffmpeg {fp['ffmpeg']}）")

    drift = {k: (v, PINNED_TOOLCHAIN[k]) for k, v in fp.items()
             if k in PINNED_TOOLCHAIN and v != PINNED_TOOLCHAIN[k]}
    if drift:
        print("❌ 本机工具链与 CI 锁定版本不一致，比对无意义：")
        for k, (got, want) in drift.items():
            print(f"   {k}: 本机 {got}，CI 锁定 {want}")
        print("   渲染库/编码器版本不同时，同样的画面也会产出不同字节，")
        print("   那会被误报成『资产是旧版本』。请按 CI 锁定的版本建环境再跑。")
        return False
    return True


def dirty_assets():
    """docs/assets 相对 HEAD 的改动。返回 {状态码: [路径]}，空 dict 表示干净。"""
    r = git("status", "--porcelain", "--", ASSETS_REL)
    if r.returncode != 0:
        raise SystemExit(f"git status 失败：{r.stderr.strip()}")
    out = {}
    for line in r.stdout.splitlines():
        if not line.strip():
            continue
        code, path = line[:2], line[3:].strip()
        out.setdefault(code, []).append(path)
    return out


def clear_assets():
    """清空 docs/assets（调用前已确认全部内容都在 HEAD 里，可 git checkout 还原）"""
    for f in sorted(ASSETS.rglob("*")):
        if f.is_file():
            f.unlink()


def run_generators():
    for name in GENERATORS:
        t0 = time.time()
        r = subprocess.run([sys.executable, str(TOOLS / name)],
                           capture_output=True, text=True, encoding="utf-8",
                           errors="replace")
        if r.returncode != 0:
            print(f"❌ {name} 执行失败（退出码 {r.returncode}）")
            print((r.stdout or "")[-2000:])
            print((r.stderr or "")[-2000:])
            return False
        print(f"  {name}: {time.time() - t0:.1f}s")
    return True


def main():
    if not check_toolchain():
        return 1

    if git("rev-parse", "--is-inside-work-tree").returncode != 0:
        print("❌ 不在 git 仓库中：本检查以 HEAD 为基准，必须有 git")
        return 1

    before = dirty_assets()
    if before:
        print("❌ docs/assets 相对 HEAD 有未提交改动，比对基准不成立。")
        print("   请先提交或还原这些改动，再跑本检查：")
        for code, paths in sorted(before.items()):
            for p in paths:
                print(f"   {code} {p}")
        return 1

    n = len([f for f in ASSETS.rglob("*") if f.is_file()])
    print(f"清空后重新生成 {n} 个视觉资产…")
    clear_assets()
    if not run_generators():
        print("提示：`git checkout -- docs/assets` 可还原")
        return 1

    after = dirty_assets()
    if not after:
        print(f"✅ 已提交的资产与脚本输出一致（{n} 个文件逐字节相同）")
        return 0

    added = after.get("??", [])
    removed = [p for c, ps in after.items() if "D" in c for p in ps]
    changed = [p for c, ps in after.items() if c != "??" and "D" not in c for p in ps]
    print(f"❌ 已提交的资产与脚本输出不一致："
          f"内容变化 {len(changed)}、新增 {len(added)}、消失 {len(removed)}")
    for p in changed:
        print(f"  ~ {p}（仓库里的是旧版本）")
    for p in added:
        print(f"  + {p}（脚本新产出，未提交）")
    for p in removed:
        print(f"  - {p}（脚本已不再产出，应从仓库删除）")
    print("\n修复：把重新生成后的文件一并提交（`git add docs/assets && git commit`）")
    return 1


if __name__ == "__main__":
    sys.exit(main())
