# -*- coding: utf-8 -*-
"""成片验收：用同一套指标量成片，对标 `D:\\Users\\STM32\\final-videos`。

指标定义（与评估报告一致）：
  - **平均帧差**：相邻采样帧的平均像素差。衡量「画面一直在动」的整体密度。
  - **有动效占比**：帧差 > 0.3 的采样点比例。衡量「有多少时间在动」。
  - **最长静止**：连续帧差 ≤ 0.3 的最长时长。这是完播率杀手。
  - **文字压平台 UI**：落在平台 UI 保留区内的亮像素 / 全帧亮像素。

标杆（STM32 ch01 B站版，1920x1080@30fps / 14:21，本次实测）：
  平均帧差 0.782 · 有动效 39.0% · 最长静止 7.4s
"""
from __future__ import annotations

import json
import pathlib
import subprocess
import sys

import numpy as np

# 平台 UI 保留区（比例坐标）。竖屏与横屏是两套：
#   竖屏（9:16）：顶部状态栏+tab 0~12.5%，底部昵称/文案/音乐 68.75% 起（距底 600px），右侧按钮栏
#   横屏（16:9）：顶部播放条 0~8%，底部控制条 88% 起；左右无竖栏
UI_ZONES_V = [(0.0, 0.0, 1.0, 0.125), (0.0, 0.6875, 1.0, 1.0), (0.86, 0.41, 1.0, 0.79)]
UI_ZONES_H = [(0.0, 0.0, 1.0, 0.08), (0.0, 0.88, 1.0, 1.0)]
BAR = {"mean_diff": 0.782, "moving_pct": 39.0, "longest_still": 7.4}


def _zones(w, h):
    return UI_ZONES_V if h > w else UI_ZONES_H


def probe(path):
    j = json.loads(subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json",
         "-show_format", "-show_streams", str(path)],
        capture_output=True, text=True, check=True).stdout)
    v = next(s for s in j["streams"] if s["codec_type"] == "video")
    a = next((s for s in j["streams"] if s["codec_type"] == "audio"), None)
    return {"w": v["width"], "h": v["height"], "dur": float(j["format"]["duration"]),
            "mb": round(int(j["format"]["size"]) / 1048576, 2),
            "audio": f'{a["codec_name"]}/{a["channels"]}ch' if a else "NONE"}


def measure(path, fps_sample=5, sw=180, sh=320):
    p = probe(path)
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path),
                          "-vf", f"fps={fps_sample},scale={sw}:{sh}",
                          "-pix_fmt", "gray", "-f", "rawvideo", "pipe:1"],
                         capture_output=True, check=True).stdout
    n = len(raw) // (sw * sh)
    a = np.frombuffer(raw[:n * sw * sh], dtype=np.uint8).reshape(n, sh, sw).astype(np.int16)
    d = np.abs(np.diff(a, axis=0)).mean(axis=(1, 2))
    moving = d > 0.3
    longest = cur = 0
    for m in moving:
        cur = 0 if m else cur + 1
        longest = max(longest, cur)
    zones = np.zeros((sh, sw), dtype=bool)
    for x0, y0, x1, y1 in _zones(p["w"], p["h"]):
        zones[int(y0 * sh):int(y1 * sh), int(x0 * sw):int(x1 * sw)] = True
    lit_all = lit_ui = 0
    for i in range(0, n, 3):
        lit = a[i] > 70
        lit_all += int(lit.sum())
        lit_ui += int((lit & zones).sum())
    return {**p,
            "mean_diff": round(float(d.mean()), 3),
            "moving_pct": round(100 * float(moving.mean()), 1),
            "longest_still": round(longest / fps_sample, 1),
            "text_in_ui_pct": round(100 * lit_ui / max(1, lit_all), 2)}


def verdict(m):
    ok = (m["mean_diff"] >= BAR["mean_diff"]
          and m["moving_pct"] >= BAR["moving_pct"]
          and m["longest_still"] <= BAR["longest_still"])
    return "达标" if ok else "未达标"


def main(paths):
    print(f"标杆：平均帧差 {BAR['mean_diff']} · 有动效 {BAR['moving_pct']}% · "
          f"最长静止 {BAR['longest_still']}s")
    print(f"{'文件':<28}{'规格':>11}{'时长':>8}{'MB':>7}{'平均帧差':>9}"
          f"{'有动效%':>9}{'最长静止':>9}{'文字压UI%':>10}{'判定':>7}")
    rows = []
    for p in paths:
        p = pathlib.Path(p)
        if not p.is_file():
            continue
        m = measure(p)
        rows.append({"file": str(p), **m, "verdict": verdict(m)})
        print(f"{p.name:<28}{str(m['w']) + 'x' + str(m['h']):>11}"
              f"{m['dur']:>7.0f}s{m['mb']:>7}{m['mean_diff']:>9}{m['moving_pct']:>9}"
              f"{m['longest_still']:>9}{m['text_in_ui_pct']:>10}{verdict(m):>7}")
    return rows


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        root = pathlib.Path(__file__).resolve().parent.parent.parent / "dist"
        args = sorted(str(p) for p in root.rglob("*.mp4"))
    rows = main(args)
    out = pathlib.Path(__file__).resolve().parent / ".cache" / "measure.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
