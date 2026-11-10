# -*- coding: utf-8 -*-
"""成片引擎：时间轴 → 逐帧渲染 → 编码 → 混音 → SRT。

渲染策略（速度的关键）：每帧只做
    底图拷贝 → 画正在入场的那个元素 → 画持续动效 → 画进度条与字幕
底图（已落定元素）由 `scenes.Scene` 按需缓存，实测单帧 ~20ms，
一集 4 分钟约 2 分钟渲完。
"""
from __future__ import annotations

import json
import pathlib
import subprocess
import sys

from PIL import Image

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import scenes as S  # noqa: E402
import voice  # noqa: E402

FPS = 30
SS = 2                    # 超采样倍率（与仓库既有资产同标准）
PAD = 0.42                # 每段尾部留白，避免旁白咬着下一段
FADE = 0.45               # 片头片尾黑场时长


# ---------- 版式微调 ----------
def _fix_layout():
    S.Layout.prog_v = None


def timeline(episode, work: pathlib.Path, voice_name, rate, pitch, concurrency=4):
    """合成旁白并构造时间轴。

    返回 (segments, cues, total)：
      segments[i] = {mp3, dur, start, scene, cues}
      cues       = 全片字幕条（绝对时间）
    """
    segs = episode["segments"]
    spoken = voice.synthesize_all(
        [{"say": s["say"]} for s in segs], voice_name, rate, pitch, work, concurrency)

    segments, cues, cursor = [], [], 0.0
    for i, (spec, (mp3, marks, dur)) in enumerate(zip(segs, spoken)):
        seg_dur = dur + PAD
        local = voice.build_cues(spec["say"], marks)
        segments.append({"mp3": mp3, "audio": dur, "dur": seg_dur,
                         "start": cursor, "scene": spec["scene"], "cues": local})
        for (s, e, lines) in local:
            cues.append((cursor + s, cursor + e, lines))
        cursor += seg_dur
    return segments, cues, cursor


# ---------- 页眉底图 ----------
def header_bg(lay: S.Layout, ss: int, series: str, ep_label: str):
    img = S._bg_for(lay, ss)
    c = S.Canvas(img, ss)
    x0 = lay.box[0]
    c.text(x0, lay.head_y, series, lay.f["small"], S.DIM)
    label = ep_label
    w = S.text_w(label, lay.f["small"]) / ss
    c.rrect((lay.box[2] - w - 28, lay.head_y - 7, lay.box[2], lay.head_y + 33), 20,
            fill=S.GREEN_D)
    c.text(lay.box[2] - w - 14, lay.head_y, label, lay.f["small"], S.GREEN)
    px0, py0, px1, py1 = lay.prog
    c.rrect((px0, py0, px1, py1), 3, fill=(40, 44, 54))
    return img


def draw_chrome(c: S.Canvas, lay: S.Layout, frac: float):
    px0, py0, px1, py1 = lay.prog
    c.rrect((px0, py0, px0 + (px1 - px0) * max(0.0, min(1.0, frac)), py1), 3, fill=S.GREEN)


def draw_caption(c: S.Canvas, lay: S.Layout, lines, alpha=1.0, frac=0.0):
    """字幕 + 跟读进度条。

    进度条是两条目的合一：观众看得见「这句话讲到哪了」（教学片里真有用），
    同时它逐帧增长——字幕区因此每秒都有变化，不会出现「入场放完就冻住」。
    """
    if not lines:
        return
    pitch = int(lay.f["cap"] * 1.34)
    n = len(lines)
    top = lay.cap_bottom - n * pitch
    total = sum(len(x) for x in lines)
    spoken = max(0.0, min(float(total), frac * total))
    for i, ln in enumerate(lines):
        y = top + i * pitch
        if lay.kind == "v":
            x = lay.cap_x0 + 32
            c.rrect((lay.cap_x0, y + 6, lay.cap_x0 + 10, y + lay.f["cap"] + 8), 5,
                    fill=S.GREEN + (int(235 * alpha),))
        else:
            w = S.text_w(ln, lay.f["cap"], True) / c.ss
            x = (lay.w - w) / 2
        # 底：未念到的部分用暗色；面：已念到的前缀用亮色覆盖
        c.text(x, y, ln, lay.f["cap"], S.MUTED, True, alpha=alpha)
        before = sum(len(x2) for x2 in lines[:i])
        k = int(max(0.0, min(float(len(ln)), spoken - before)))
        if k > 0:
            c.text(x, y, ln[:k], lay.f["cap"], S.TEXT, True, alpha=alpha)
    # 跟读进度条：贴在字幕块下方
    bx0 = lay.cap_x0 + 32 if lay.kind == "v" else (lay.w - 420) / 2
    bx1 = lay.cap_x1 if lay.kind == "v" else (lay.w + 420) / 2
    by = lay.cap_bottom + 16
    c.rrect((bx0, by, bx1, by + 5), 2, fill=(44, 48, 60))
    c.rrect((bx0, by, bx0 + (bx1 - bx0) * max(0.0, min(1.0, frac)), by + 5), 2,
            fill=S.GREEN + (int(230 * alpha),))


# ---------- 逐帧 ----------
def frames(segments, total, lay: S.Layout, bg, ss: int, fps: int = FPS):
    """逐帧生成器。

    **必须在切换场景时清掉上一场的底图缓存**：一张 1080×1920 的 2× 超采样底图
    是 33 MB，一个场景有 `元素数 + 1` 张。一集 13 个场景全留着，单进程能涨到
    4 GB 以上——6 路并行就是内存打穿。场景是顺序渲染的，离开就可以释放。
    """
    built = []
    for seg in segments:
        sc = S.make_scene(seg["scene"], lay, seg["dur"], ss)
        sc.bg = bg
        built.append(sc)

    n = int(round(total * fps))
    black = Image.new("RGB", (lay.w, lay.h), (0, 0, 0))
    last_idx = -1
    for i in range(n):
        t = i / fps
        idx = 0
        for j, seg in enumerate(segments):
            if t >= seg["start"]:
                idx = j
        if idx != last_idx:
            for j in range(last_idx + 1 if last_idx >= 0 else 0, idx):
                built[j]._bases.clear()          # 释放已离开场景的底图
            last_idx = idx
        seg, sc = segments[idx], built[idx]
        local = t - seg["start"]
        k = sc.step_at(local)
        img = sc.base(k).copy()
        c = S.Canvas(img, ss)
        if k < sc.n:
            e = S.ease_out(max(0.0, min(1.0, (local - sc.enter_at[k]) / S.ENTER_DUR)))
            sc.entering(c, k, e)
        sc.live(c, local)
        draw_chrome(c, lay, t / total)

        active, frac = None, 0.0
        for (s, e2, lines) in seg["cues"]:
            if s <= local <= e2 + 0.25:
                active = lines
                span = max(0.05, e2 - s)
                frac = max(0.0, min(1.0, (local - s) / span))
        if active:
            a = min(1.0, max(0.0, local / 0.18)) if local < 0.18 else 1.0
            draw_caption(c, lay, active, a, frac)

        out = img.convert("RGB")
        if out.width != lay.w:                 # 从超采样空间降回输出尺寸
            out = out.reduce(ss) if ss > 1 else out.resize((lay.w, lay.h), Image.LANCZOS)
        fade = 1.0
        if t < FADE:
            fade = t / FADE
        elif t > total - FADE:
            fade = max(0.0, (total - t) / FADE)
        if fade < 0.999:
            out = Image.blend(black, out, fade)
        yield out


def encode(frames_it, out_path: pathlib.Path, lay: S.Layout, dur: float, fps: int = FPS,
           threads: int = 2):
    """原始帧 → H.264。先写临时文件，成功才落地（同仓库既有契约）。

    `threads` 默认 2 而不是 0：批量渲染时会同时跑多路进程，让每路 ffmpeg
    只吃两个线程，否则 16 线程全被编码器抢走、PIL 逐帧生成反而饿死。

    内存：一帧 1080×1920 RGB 是 6.2 MB，但场景底图 + 超采样中间帧会让单进程
    峰值到 1~2 GB。6 路并行就是 12 GB，实测在 15 GB 机器上会 MemoryError
    （而且是 `tobytes()` 里炸的，不是渲染逻辑错）。所以并行度由 build.py 的
    `--jobs` 控制，默认降到 3。
    """
    tmp = out_path.with_suffix(".part.mp4")
    cmd = ["ffmpeg", "-y", "-loglevel", "error",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{lay.w}x{lay.h}",
           "-framerate", str(fps), "-i", "pipe:0",
           "-c:v", "libx264", "-preset", "medium", "-crf", "20",
           "-threads", str(threads),
           "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(tmp)]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                         stderr=subprocess.PIPE)
    count = 0
    try:
        for fr in frames_it:
            try:
                p.stdin.write(fr.tobytes())
            except MemoryError:
                raise SystemExit(
                    "渲染进程内存不足：并行任务太多。把 --jobs 调小"
                    "（15 GB 机器建议 3）后重跑；已渲染完的集会被跳过。")
            count += 1
    except BrokenPipeError:
        pass
    finally:
        try:
            p.stdin.close()
        except BrokenPipeError:
            pass
        err = p.stderr.read().decode("utf-8", "replace")
        rc = p.wait()
    if rc != 0:
        tmp.unlink(missing_ok=True)
        raise SystemExit(f"ffmpeg 编码失败：\n{err[-1200:]}")
    tmp.replace(out_path)
    return count


def mux(silent_video: pathlib.Path, segments, total: float, out: pathlib.Path,
        loudness=True):
    """铺旁白音轨并混流：各段按起始时间对齐，响度归一到 -16 LUFS（与既有成片一致）"""
    inputs, filters, labels = [], [], []
    for k, seg in enumerate(segments):
        inputs += ["-i", str(seg["mp3"])]
        ms = int(seg["start"] * 1000)
        filters.append(f"[{k + 1}:a]adelay={ms}|{ms}[a{k}]")
        labels.append(f"[a{k}]")
    chain = "".join(labels) + f"amix=inputs={len(segments)}:normalize=0"
    if loudness:
        chain += ":dropout_transition=0" if False else ""
    chain += ",apad"
    if loudness:
        chain += ",loudnorm=I=-16:TP=-1.5:LRA=11"
    chain += f",atrim=0:{total:.3f}[aout]"
    filters.append(chain)
    cmd = (["ffmpeg", "-y", "-loglevel", "error", "-i", str(silent_video)] + inputs +
           ["-filter_complex", ";".join(filters), "-map", "0:v", "-map", "[aout]",
            "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-ac", "2", "-ar", "48000",
            "-movflags", "+faststart", "-t", f"{total:.3f}", str(out)])
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit(f"混流失败：\n{r.stderr[-1500:]}")
    return out


def render(episode, out_dir: pathlib.Path, lay: S.Layout, work: pathlib.Path,
           voice_name, rate, pitch, ss=SS, fps=FPS, concurrency=4, log=print):
    out_dir.mkdir(parents=True, exist_ok=True)
    segments, cues, total = timeline(episode, work, voice_name, rate, pitch, concurrency)
    bad = voice.check_cues(cues)
    if bad:
        raise SystemExit("字幕不合规：\n  " + "\n  ".join(bad[:10]))

    bg = header_bg(lay, ss, episode.get("series", "小程序开发之路"),
                   f"第 {episode['id']} 集 · {episode['title']}")
    name = f"ep{episode['id']}-{episode['slug']}-{'v' if lay.kind == 'v' else 'h'}"
    silent = work / f"{name}.silent.mp4"
    log(f"  [{lay.kind}] 渲染 {int(round(total * fps))} 帧 / {total:.1f}s …")
    encode(frames(segments, total, lay, bg, ss, fps), silent, lay, total, fps)
    final = out_dir / f"{name}.mp4"
    mux(silent, segments, total, final)
    srt_path = out_dir / f"ep{episode['id']}.srt"
    srt_path.write_text(voice.srt(cues), encoding="utf-8")
    meta = {"id": episode["id"], "slug": episode["slug"], "orient": lay.kind,
            "dur": round(total, 2), "segments": len(segments), "cues": len(cues),
            "size": final.stat().st_size}
    (out_dir / f"{name}.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    silent.unlink(missing_ok=True)
    log(f"  [{lay.kind}] {final.name}  {total / 60:.1f} 分钟  "
        f"{final.stat().st_size / 1048576:.1f} MB  字幕 {len(cues)} 条")
    return final, cues, total, segments
