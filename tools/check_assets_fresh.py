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

用法：python tools/check_assets_fresh.py
退出码：0 = 全部一致；1 = 存在漂移
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


def git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True,
                          text=True, encoding="utf-8", errors="replace")


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
