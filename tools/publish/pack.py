# -*- coding: utf-8 -*-
"""投放物料打包：SRT、章节轴、三平台投稿文案、B站合并长版。

对齐 `D:\\Users\\STM32\\final-videos\\` 的交付形态：
    epNN-v.mp4 / epNN-h.mp4      正片（内嵌字幕）
    epNN.srt                     外挂字幕（与内嵌同一份稿）
    epNN-cover-{9x16,3x4,16x9}.png
    epNN-chapters.txt            章节时间轴（贴 B站「分段章节」）
    epNN-bilibili.md             B站投稿文案（标题/分区/标签/简介）
    epNN-douyin.md / epNN-xhs.md 抖音 / 小红书文案
    long-NN-*.mp4                B站横屏合并长版
"""
from __future__ import annotations

import json
import pathlib
import re
import subprocess

# B站分区（官方公告 cv11530396 的定义：「任何计算机技术的教学、演示、经验分享」）
BILI_TID = "231"          # 科技区 → 计算机技术
BILI_TID_ALT = "208"      # 知识区 → 校园学习（备选）

# 合并长版分组：按学习阶段合并，与 docs/00-学习路线 的五阶段一致
LONG_GROUPS = [
    ("01", "入门篇 · 认知与准备", ["01", "02", "03"]),
    ("02", "视图与组件篇", ["04", "05"]),
    ("03", "性能与调试篇", ["07", "13"]),
    ("04", "云开发篇", ["06", "11"]),
    ("05", "上线与合规篇", ["09", "08", "12"]),
    ("06", "实战篇", ["10"]),
]


def _probe(path):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries",
         "format=duration,size:stream=codec_type,codec_name,width,height,r_frame_rate",
         "-of", "json", str(path)], capture_output=True, text=True, check=True).stdout
    j = json.loads(out)
    v = next(s for s in j["streams"] if s.get("codec_type") == "video")
    return {"dur": float(j["format"]["duration"]),
            "size": int(j["format"]["size"]),
            "w": v["width"], "h": v["height"],
            "fps": v["r_frame_rate"]}


def _mmss(sec):
    return f"{int(sec) // 60:02d}:{int(sec) % 60:02d}"


def chapters_from(segments):
    """按段落在时间轴上生成章节（用于 B站「分段章节」）"""
    lines = []
    for i, seg in enumerate(segments, start=1):
        head = (seg["scene"].get("head") or seg["scene"].get("title") or f"第 {i} 节")
        lines.append(f"{_mmss(seg['start'])} {head}")
    return "\n".join(lines) + "\n"


def bilibili_md(ep, meta_v, cues):
    title = f"【小程序零基础{ep['id']}】{ep['title']}"
    if len(title) > 80:
        title = title[:80]
    tags = ["微信小程序", "小程序开发", "零基础", "WXML", "云开发",
            "前端", "教程", "小程序入门", "微信开发", "编程教学"]
    desc = [
        f"{ep.get('cover_sub', '')}",
        "",
        "本集讲了什么：",
        *[f"· {s['scene'].get('head') or s['scene'].get('title')}"
          for s in ep["segments"][1:10] if s["scene"].get("head") or s["scene"].get("title")],
        "",
        f"配套文档与代码：github.com/zhuguang-ZFG/xiaochengxu"
        f"（{ep.get('article', '')}）",
        f"正片内嵌字幕；外挂字幕见 ep{ep['id']}.srt。",
        "画面与配音均由脚本生成，非真人出镜、非实拍。",
        "",
        f"上一集 / 下一集见合集。",
    ]
    lines = [
        f"# 第 {ep['id']} 集 · B站投稿信息",
        "",
        f"## 标题（≤ 80 字）",
        title,
        "",
        "## 分区",
        f"科技 → 计算机技术（tid {BILI_TID}）。备选：知识 → 校园学习（tid {BILI_TID_ALT}）。"
        "投稿时以 B 站当前分区列表为准。",
        "",
        f"## 标签（10 个）",
        ", ".join(tags),
        "",
        "## 简介",
        "\n".join(desc),
        "",
        "## 分段章节（复制到「分段章节」）",
        f"见 ep{ep['id']}-chapters.txt",
        "",
        "## 投稿文件",
        f"- 正片（16:9 横屏，内嵌字幕）：ep{ep['id']}-h.mp4 —— {meta_v['w']}x{meta_v['h']}，"
        f"{meta_v['dur'] / 60:.1f} 分钟，{meta_v['size'] / 1048576:.1f} MB",
        f"- 外挂字幕：ep{ep['id']}.srt（{len(cues)} 条）——二选一，别同时用内嵌字幕和 CC",
        f"- 封面：ep{ep['id']}-cover-16x9.png（1920x1080）",
    ]
    return "\n".join(lines) + "\n"


def douyin_md(ep, meta_v):
    title = f"{ep['title']}｜小程序零基础第{ep['id']}集"
    desc = (f"{ep.get('cover_sub', '')}\n"
            f"本集 5 分钟讲清：{', '.join([s['scene'].get('head', '') for s in ep['segments'][1:5] if s['scene'].get('head')])}\n"
            "#微信小程序 #小程序开发 #零基础学编程 #前端 #程序员")
    return (f"# 第 {ep['id']} 集 · 抖音投稿信息\n\n"
            f"## 标题（{len(title)} 字）\n{title}\n\n"
            f"## 文案\n{desc}\n\n"
            f"## 投稿文件\n"
            f"- ep{ep['id']}-v.mp4（9:16，{meta_v['w']}x{meta_v['h']}，{meta_v['dur'] / 60:.1f} 分钟）\n"
            f"- 封面 ep{ep['id']}-cover-9x16.png\n\n"
            f"## 注意\n"
            f"- 正文不要出现微信号 / QQ / 二维码 / 站外链接，抖音对站外引流判定很重。\n"
            f"- 时长超过 1 分钟需要电脑端 creator.douyin.com 上传，或账号有长视频权限。\n")


def xhs_md(ep, meta_v):
    title = f"{ep['title']}"[:20]
    body = (f"{ep.get('cover_sub', '')}\n\n"
            f"零基础学小程序第 {ep['id']} 集。\n"
            f"视频里讲了：\n"
            + "\n".join(f"{i}. {s['scene'].get('head')}"
                        for i, s in enumerate(ep["segments"][1:8], start=1) if s["scene"].get("head"))
            + "\n\n收藏起来慢慢看，评论区可以问。\n\n"
            "#微信小程序 #小程序开发 #零基础编程 #自学编程 #前端入门")
    return (f"# 第 {ep['id']} 集 · 小红书投稿信息\n\n"
            f"## 标题（≤ 20 字硬上限，当前 {len(title)} 字）\n{title}\n\n"
            f"## 正文（≤ 1000 字，当前 {len(body)} 字）\n{body}\n\n"
            f"## 投稿文件\n"
            f"- ep{ep['id']}-v.mp4（9:16，{meta_v['w']}x{meta_v['h']}，{meta_v['dur'] / 60:.1f} 分钟）\n"
            f"- 首图 ep{ep['id']}-cover-3x4.png（3:4 才占满发现页信息流）\n\n"
            f"## 注意\n"
            f"- 标题 20 字是硬上限，超了会被截断。\n"
            f"- 不要在正文或视频里放站外链接 / 联系方式。\n")


def concat_mp4(paths, out, log=print):
    """无损拼接（同编码同参数，stream copy）"""
    lst = out.with_suffix(".txt")
    lst.write_text("".join(f"file '{p.as_posix()}'\n" for p in paths), encoding="utf-8")
    r = subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
                        "-i", str(lst), "-c", "copy", "-movflags", "+faststart", str(out)],
                       capture_output=True, text=True)
    lst.unlink(missing_ok=True)
    if r.returncode != 0:
        raise SystemExit(f"合并失败：\n{r.stderr[-1200:]}")
    log(f"  合并 → {out.name}  {out.stat().st_size / 1048576:.1f} MB")
    return out


def video_path(dist, ep, orient):
    """成片路径：epNN-slug-v.mp4 / epNN-slug-h.mp4（slug 由旁白稿给）"""
    return dist / f"ep{ep['id']}" / f"ep{ep['id']}-{ep['slug']}-{orient}.mp4"


def find_video(dist, ep_id, orient):
    """按集号找成片，不依赖 slug——长版合并时手上只有 id"""
    hits = sorted(dist.glob(f"ep{ep_id}/ep{ep_id}-*-{orient}.mp4"))
    return hits[0] if hits else None


def write_episode_pack(ep, out_dir: pathlib.Path, cues, segments, log=print):
    """写一集的 SRT / 章节轴 / 三平台文案"""
    import voice
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"ep{ep['id']}.srt").write_text(voice.srt(cues), encoding="utf-8")
    (out_dir / f"ep{ep['id']}-chapters.txt").write_text(
        chapters_from(segments), encoding="utf-8")

    mv = video_path(out_dir.parent, ep, "v")
    mh = video_path(out_dir.parent, ep, "h")
    meta_v = _probe(mv) if mv.is_file() else {"w": 1080, "h": 1920, "dur": 0, "size": 0}
    meta_h = _probe(mh) if mh.is_file() else meta_v
    (out_dir / f"ep{ep['id']}-bilibili.md").write_text(
        bilibili_md(ep, meta_h, cues), encoding="utf-8")
    (out_dir / f"ep{ep['id']}-douyin.md").write_text(
        douyin_md(ep, meta_v), encoding="utf-8")
    (out_dir / f"ep{ep['id']}-xhs.md").write_text(
        xhs_md(ep, meta_v), encoding="utf-8")
    log(f"  物料 ep{ep['id']}: srt {len(cues)} 条 · 章节 {len(segments)} 段 · 三平台文案")


def write_long_versions(episodes, dist: pathlib.Path, log=print):
    """把横屏正片按学习阶段合并成 B站长版"""
    by_id = {e["id"]: e for e in episodes}
    made = []
    for num, name, ids in LONG_GROUPS:
        parts = []
        for i in ids:
            p = find_video(dist, i, "h")
            if p is not None:
                parts.append(p)
        if not parts:
            continue
        out = dist / f"long-{num}-{ids[0]}-{ids[-1]}.mp4"
        if len(parts) == 1:
            # 单集分组：不必合并，直接把横屏正片作为长版（同名引用即可）
            out.write_bytes(parts[0].read_bytes())
            log(f"  长版《{name}》单集，直接复制 {out.name}")
        else:
            concat_mp4(parts, out, log)
        heads = []
        cursor = 0.0
        for i in ids:
            p = find_video(dist, i, "h")
            if p is None:
                continue
            heads.append(f"{_mmss(cursor)} 第 {i} 集 · {by_id[i]['title']}")
            cursor += _probe(p)["dur"]
        (dist / f"long-{num}-chapters.txt").write_text(
            f"# {name}\n" + "\n".join(heads) + "\n", encoding="utf-8")
        made.append((name, out, cursor))
        log(f"  长版《{name}》{cursor / 60:.1f} 分钟，{len(parts)} 集")
    return made
