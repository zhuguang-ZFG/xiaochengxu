# -*- coding: utf-8 -*-
"""发布管线入口。

```bash
python tools/publish/build.py --check                 # 只校验旁白稿，不联网
python tools/publish/build.py --list                  # 列出各集估算时长
python tools/publish/build.py --ep 02 --orient v h    # 渲染第 2 集两个方向
python tools/publish/build.py --all --jobs 6          # 全部集，6 路并行
python tools/publish/build.py --cover                 # 三种比例封面
python tools/publish/build.py --pack                  # SRT / 章节轴 / 三平台文案
python tools/publish/build.py --merge                 # B站横屏合并长版
python tools/publish/build.py --verify                # 对标 STM32 的指标验收
```

产物落在仓库根的 `dist/`（已进 .gitignore，不进版本库）；
`docs/assets/videos/` 的既有资产与契约完全不动。
"""
from __future__ import annotations

import argparse
import pathlib
import subprocess
import sys
import time

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))

import engine  # noqa: E402
import scenes as S  # noqa: E402
import spec  # noqa: E402

NARR = HERE / "narration"
DIST = ROOT / "dist"
WORK = HERE / ".cache"
VOICE = "zh-CN-XiaoxiaoNeural"
RATE = "-2%"
PITCH = "+0Hz"


def _episodes(which=None):
    eps = spec.load_all(NARR)
    if not eps:
        raise SystemExit(f"{NARR} 下没有 epNN.py")
    if which:
        want = {str(w).zfill(2) for w in which}
        eps = [e for e in eps if e["id"] in want]
        if not eps:
            raise SystemExit(f"没有匹配的集：{sorted(want)}")
    return eps


# ---------- 校验 ----------
def cmd_check(verbose=False):
    eps = _episodes()
    bad_all = []
    for e in eps:
        chars, est = spec.estimate(e)
        bad = spec.check(e, verbose=verbose)
        flag = "ok  " if not bad else "FAIL"
        print(f"[{flag}] ep{e['id']} {e['title']}  {len(e['segments'])} 段 "
              f"{chars} 字  估算 {est / 60:.2f} 分钟")
        for b in bad:
            print(f"        !! {b}")
        bad_all += bad
    if bad_all:
        raise SystemExit(f"共 {len(bad_all)} 处问题")
    print("全部通过")


def cmd_list():
    for e in _episodes():
        chars, est = spec.estimate(e)
        kinds = {}
        for s in e["segments"]:
            k = s["scene"]["kind"]
            kinds[k] = kinds.get(k, 0) + 1
        print(f"ep{e['id']}  {e['title']:<8} {len(e['segments']):>2} 段  {chars:>5} 字  "
              f"~{est / 60:.2f} 分钟  {kinds}")


# ---------- 渲染 ----------
def render_one(ep, orient, force=False):
    bad = spec.check(ep)
    if bad:
        raise SystemExit(f"ep{ep['id']} 校验不通过：{bad[:5]}")
    out = DIST / f"ep{ep['id']}"
    lay = S.Layout(orient)
    tag = "v" if orient == "v" else "h"
    final = out / f"ep{ep['id']}-{ep['slug']}-{tag}.mp4"
    meta = final.with_suffix(".json")
    if not force and final.is_file() and meta.is_file() and final.stat().st_size > 100_000:
        print(f"  跳过 {final.name}（已存在，加 --force 可重渲）", flush=True)
        return
    WORK.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    engine.render(ep, out, lay, WORK, VOICE, RATE, PITCH,
                  ss=2, fps=engine.FPS, concurrency=4,
                  log=lambda s: print(s, flush=True))
    print(f"  用时 {time.time() - t0:.0f}s", flush=True)


def cmd_render(which, orients, jobs=1, force=False):
    """渲染任务队列。

    并行度是**同时存活的子进程数**，不是「分几组」——第一版按分片一次性
    把所有子进程都 Popen 起来，`--jobs 3` 实际起了 8 个进程，在 15 GB 机器上
    直接把内存打穿（`MemoryError` 出现在编码阶段，看起来像渲染逻辑的错）。
    现在用「有槽就补」的队列：最多 jobs 个在跑，完成一个补一个。
    """
    eps = _episodes(which)
    tasks = [(e["id"], o) for e in eps for o in orients]
    by_id = {e["id"]: e for e in eps}

    if jobs <= 1:
        for eid, o in tasks:
            render_one(by_id[eid], o, force)
        return

    DIST.mkdir(exist_ok=True)
    pending = list(tasks)
    running = []                     # [(proc, fh, log, eid, orient)]
    fails = []
    while pending or running:
        while pending and len(running) < jobs:
            eid, o = pending.pop(0)
            cmd = [sys.executable, str(HERE / "build.py"), "--one", eid, o]
            if force:
                cmd.append("--force")
            log = DIST / f".render-{eid}-{o}.log"
            fh = open(log, "w", encoding="utf-8")
            proc = subprocess.Popen(cmd, stdout=fh, stderr=subprocess.STDOUT)
            running.append((proc, fh, log, eid, o))
            print(f"  启动 {eid}/{o}（在跑 {len(running)}/{jobs}）", flush=True)
        time.sleep(0.5)
        for item in running[:]:
            proc, fh, log, eid, o = item
            if proc.poll() is None:
                continue
            fh.close()
            running.remove(item)
            print(f"  完成 {eid}/{o} → exit {proc.returncode}", flush=True)
            if proc.returncode != 0:
                fails.append(log)
    if fails:
        for log in fails:
            print(f"\n--- {log.name} 尾部 ---")
            print(log.read_text(encoding="utf-8", errors="replace")[-1500:])
        raise SystemExit(f"{len(fails)} 个任务失败")


# ---------- 物料 ----------
def cmd_cover(which):
    import covers
    bad = []
    for e in _episodes(which):
        _made, b = covers.write_covers(e, DIST / f"ep{e['id']}")
        bad += b
    if bad:
        raise SystemExit("封面自检不通过：\n  " + "\n  ".join(bad))
    print("封面自检通过（墨迹未贴边）")


def cmd_pack(which):
    import pack
    for e in _episodes(which):
        segs, cues, total = engine.timeline(e, WORK, VOICE, RATE, PITCH)
        pack.write_episode_pack(e, DIST / f"ep{e['id']}", cues, segs)
    pack.write_long_versions(_episodes(), DIST)


def cmd_verify():
    import measure
    paths = sorted(str(p) for p in DIST.rglob("*.mp4"))
    if not paths:
        raise SystemExit("dist/ 里没有成片")
    rows = measure.main(paths)
    bad = [r for r in rows if r["verdict"] != "达标"]
    print(f"\n达标 {len(rows) - len(bad)} / {len(rows)}")
    if bad:
        print("未达标：")
        for r in bad:
            print(f"  {pathlib.Path(r['file']).name}  帧差 {r['mean_diff']}  "
                  f"动效 {r['moving_pct']}%  最长静止 {r['longest_still']}s")


def main():
    ap = argparse.ArgumentParser(description="小程序开发之路 · 发布管线")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--ep", nargs="+")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--orient", nargs="+", default=["v"], choices=["v", "h"])
    ap.add_argument("--jobs", type=int, default=3,
                    help="并行进程数：15 GB 机器建议 3，镜头密集时单进程峰值 ~2 GB")
    ap.add_argument("--force", action="store_true", help="已渲染完的也重渲")
    ap.add_argument("--cover", action="store_true")
    ap.add_argument("--pack", action="store_true")
    ap.add_argument("--merge", action="store_true")
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--one", nargs=2, metavar=("EP", "ORIENT"), help=argparse.SUPPRESS)
    args = ap.parse_args()

    if args.one:
        eid, o = args.one
        if o not in ("v", "h"):
            raise SystemExit(f"--one 的方向只能是 v/h，收到 {o!r}")
        return render_one(_episodes([eid])[0], o, args.force)
    if args.check:
        return cmd_check(args.verbose)
    if args.list:
        return cmd_list()
    which = None if args.all else args.ep
    if args.cover:
        return cmd_cover(which)
    if args.pack:
        return cmd_pack(which)
    if args.merge:
        import pack
        return pack.write_long_versions(_episodes(), DIST)
    if args.verify:
        return cmd_verify()
    if args.all or args.ep:
        return cmd_render(which, args.orient, args.jobs, args.force)
    return cmd_list()


if __name__ == "__main__":
    main()
