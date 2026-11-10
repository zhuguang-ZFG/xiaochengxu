# -*- coding: utf-8 -*-
"""旁白合成与字幕切分。

为什么不用现成的 SubMaker：我们需要的不是「WordBoundary → SRT」，而是
**逐字回映射**。edge-tts 开 `boundary="WordBoundary"` 后，每个词片段的
`text` 拼起来恰好等于旁白稿去掉标点后的字符串（实测逐字相同）。于是
「旁白稿的第 i 个去标点字符」↔「第 i 个时间点」是一一对应的，任意字符
区间都能换算出起止时间——字幕因此可以按语义切分，而不是按词边界硬切。

本模块不联网也能工作：`--offline` 用已缓存的 mp3 + marks。
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import pathlib
import re
import subprocess

# 中文字幕不用逗号句号（Netflix 简体中文规范：Do not use commas or periods.
# Use one single space instead.）。分号冒号同属「阅读停顿」，一并按空格处理。
PUNCT_ALL = "，。、；：！？【】（）《》〈〉—…·「」『』“”‘’,.;:!?()[]<>\"'"
PUNCT_DROP = "，。、；：！？【】（）《》〈〉—…·「」『』“”‘’,.;:!?()[]<>\"'"
SPACE_FOR = "，、；：,;:"

MAX_LINE_CHARS = 16      # 每行 ≤16 字（Netflix，可放宽到 18）
MAX_LINES = 2            # 对白最多 2 行
MAX_CUE_CHARS = MAX_LINE_CHARS * MAX_LINES
MAX_CUE_SEC = 6.5        # 单条字幕最长停留（按 ≤9 字/秒，32 字 ≈ 3.6 秒）


def is_spoken(ch: str) -> bool:
    """这个字符会不会产生词边界。

    标点不会、空白也不会——实测 edge-tts 的 WordBoundary 只覆盖发音字符，
    「微信里的 App」里那个空格不在任何词边界里。把这个定义统一到一处，
    否则「去标点序列」和「词边界拼接」会差一个空格，对齐整段作废。
    """
    return ch not in PUNCT_ALL and not ch.isspace()


def spoken_of(say: str) -> str:
    """旁白稿里会发音的字符序列——词边界拼接应当与它逐字相同"""
    return "".join(ch for ch in say if is_spoken(ch))


def display_of(say: str) -> str:
    """上屏文本：逗号分号类换成单个空格，句末标点直接去掉"""
    out = []
    for ch in say:
        if ch in SPACE_FOR:
            out.append(" ")
        elif ch in PUNCT_DROP:
            continue
        else:
            out.append(ch)
    return re.sub(r"\s+", " ", "".join(out)).strip()


async def _stream(text: str, voice: str, rate: str, pitch: str):
    import edge_tts
    com = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch, boundary="WordBoundary")
    bounds, audio = [], bytearray()
    async for chunk in com.stream():
        if chunk["type"] == "WordBoundary":
            bounds.append({"offset": chunk["offset"] / 1e7,
                           "dur": chunk["duration"] / 1e7,
                           "text": chunk["text"]})
        elif chunk["type"] == "audio":
            audio.extend(chunk["data"])
    return bounds, bytes(audio)


async def synthesize(text, voice, rate, pitch, work: pathlib.Path, retries=4):
    """合成一段旁白，返回 (mp3 路径, marks, duration)。

    marks = [(旁白稿字符下标, 该字符的起始秒), …, (len(say), 结束秒)]。

    `ALIGN_VERSION` 必须跟着对齐算法走：缓存键里带上它，改了对齐规则之后
    旧缓存自动失效。不加这个版本号会踩到一个很隐蔽的坑——mp3 照旧命中缓存，
    但 marks 是上一版规则算的（下标含义都变了），字幕时间整体错位却没有人报错。
    """
    ALIGN_VERSION = 2
    key = hashlib.sha1(
        f"v{ALIGN_VERSION}|{voice}|{rate}|{pitch}|{text}".encode()).hexdigest()[:16]
    mp3 = work / f"{key}.mp3"
    meta = work / f"{key}.json"
    if mp3.is_file() and meta.is_file():
        raw = json.loads(meta.read_text(encoding="utf-8"))
        return mp3, [tuple(m) for m in raw["marks"]], raw["dur"]

    last = None
    bounds = None
    for attempt in range(retries):
        try:
            bounds, audio = await _stream(text, voice, rate, pitch)
            if not bounds:
                raise RuntimeError("没有词边界，无法对齐字幕")
            if len(audio) < 800:
                raise RuntimeError("音频过小")
            mp3.write_bytes(audio)
            break
        except Exception as exc:               # 在线服务偶发断开
            last = exc
            await asyncio.sleep(1.5 * (attempt + 1))
    if bounds is None:
        raise RuntimeError(f"配音失败：{last}")

    # 词边界拼接与旁白稿的对齐用**双指针**，不再要求逐字相等：
    # TTS 对「2.2.3」这种带点的版本号会把点号也算进词边界（一个词就是 "2.2.3"），
    # 而「，。」这类标点永远不出现在词边界里。所以规则是：
    #   字符相等 → 对上，两个指针一起走；
    #   稿这边是标点/空白 → 跳过（它不发音）；
    #   其余情况 → 真错位，报错。
    joined = "".join(b["text"] for b in bounds)
    say_pos, j, pairs = 0, 0, []
    while j < len(joined):
        if say_pos >= len(text):
            raise ValueError(f"词边界比旁白稿长，对不齐：{joined[j:j + 40]!r}")
        ch = text[say_pos]
        if ch == joined[j]:
            pairs.append(say_pos)
            say_pos += 1
            j += 1
        elif ch in PUNCT_ALL or ch.isspace():
            say_pos += 1
        else:
            raise ValueError(
                "词边界与旁白稿对不上，字幕时间会错位：\n"
                f"  稿：{text[max(0, say_pos - 20):say_pos + 40]!r}\n"
                f"  回：{joined[max(0, j - 20):j + 40]!r}")

    # marks = [(旁白稿字符下标, 该字符的起始秒)]，按稿下标单调递增
    marks = []
    k = 0
    for b in bounds:
        n = len(b["text"])
        for m in range(n):
            marks.append((pairs[k], b["offset"] + b["dur"] * m / max(1, n)))
            k += 1
    end = bounds[-1]["offset"] + bounds[-1]["dur"]
    marks.append((len(text), end))
    dur = float(subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", str(mp3)],
        capture_output=True, text=True, check=True).stdout.strip())
    meta.write_text(json.dumps({"marks": marks, "dur": dur}, ensure_ascii=False),
                    encoding="utf-8")
    return mp3, marks, dur


def _time_at(marks, idx):
    """去标点串下标 → 秒（越界时钳到两端）"""
    if idx <= marks[0][0]:
        return marks[0][1]
    for (i0, t0), (i1, t1) in zip(marks, marks[1:]):
        if i0 <= idx <= i1:
            span = i1 - i0
            return t0 if span <= 0 else t0 + (t1 - t0) * (idx - i0) / span
    return marks[-1][1]


LATIN = re.compile(r"[A-Za-z0-9_+\-./]+")


def _atoms(text):
    """把上屏文本切成不可再分的原子：拉丁标识符整体算一个，中文逐字。

    「绝不把标识符从中间劈开」——仓库 `docs/_契约.md` 对折行的硬要求，
    第一代成片就在这里把 `cloud.getWXContext()` 劈成两截，屏幕上凭空多了
    一个不存在的 API 名。这里把拉丁串当原子，折行点只会落在它两侧。
    """
    out, i = [], 0
    while i < len(text):
        m = LATIN.match(text, i)
        if m:
            out.append(m.group())
            i = m.end()
        else:
            out.append(text[i])
            i += 1
    return out


def _cjk_count(text):
    return sum(1 for ch in text if "\u4e00" <= ch <= "\u9fff")


def _split_lines(text, limit=MAX_LINE_CHARS):
    """把一条字幕折成 ≤2 行。

    折行顺序（重要）：
      ① 优先断在空格处——那是从句边界，中文里唯一自然的断点；
      ② 空格断不开（无空格或空格两侧有一边仍超 16 汉字）才从句中切；
      ③ 拉丁标识符作为原子永不劈开（`setUpdatePerformanceListener` 整行放）。
    第一版按「两行字符数最接近」切，结果把「今天」劈成「今 / 天」——
    屏幕上读起来是断的，和把 API 名劈开是同一类毛病。
    """
    if _cjk_count(text) <= limit and len(text) <= limit:
        return [text]
    atoms = _atoms(text)
    if len(atoms) < 2:
        return [text]

    def ok(left, right):
        return (_cjk_count(left) <= limit and _cjk_count(right) <= limit
                and left and right)

    # ① 空格断点：选「两行最均衡」的那个空格
    best = None
    for i, ch in enumerate(text):
        if ch != " ":
            continue
        left, right = text[:i].strip(), text[i + 1:].strip()
        if not ok(left, right):
            continue
        cost = abs(len(left) - len(right))
        if best is None or cost < best[0]:
            best = (cost, left, right)
    if best:
        return [best[1], best[2]]

    # ② 没有可用空格：按原子均分，代价 = 长度差 + 超限惩罚
    total_cjk = _cjk_count(text)
    best, best_cost = None, None
    for cut in range(1, len(atoms)):
        left = "".join(atoms[:cut]).strip()
        right = "".join(atoms[cut:]).strip()
        if not left or not right:
            continue
        lc = _cjk_count(left)
        cost = (abs(len(left) - len(right))
                + 40 * max(0, lc - limit)
                + 40 * max(0, (total_cjk - lc) - limit))
        if best_cost is None or cost < best_cost:
            best, best_cost = (left, right), cost
    return list(best) if best else [text]


def _clauses(say):
    """按标点把旁白稿切成小句：[(稿起始下标, 稿结束下标, 上屏文本, 显示→稿下标映射)]

    映射留着是为了后面「上屏文本按字数再切块」时能把切点换算回稿下标，
    进而换算回时间。上一版用「去标点后的发音下标」做这件事，一遇到 `2.2.3`
    这种 TTS 会把点号算进词边界的版本号就整体错位。
    """
    out, disp, say_idx = [], [], []

    def flush():
        if not disp:
            return
        text = "".join(disp).strip()
        if text:
            out.append((say_idx[0], say_idx[-1] + 1, text, list(say_idx)))
        disp.clear()
        say_idx.clear()

    for i, ch in enumerate(say):
        if ch in PUNCT_ALL:
            flush()
        elif ch.isspace():
            if disp and disp[-1] != " ":
                disp.append(" ")
                say_idx.append(i)
        else:
            disp.append(ch)
            say_idx.append(i)
    flush()
    return out


def build_cues(say, marks, seg_start=0.0, min_sec=0.9):
    """把一段旁白切成字幕条：[(start, end, [line, …])]，时间为秒（相对段首）。

    先按小句聚合到 ≤32 字宽且 ≤6.5 秒，再折成最多 2 行。行业标准来自
    Netflix 简体中文规范与 BBC Subtitle Guidelines。
    """
    chunks = []
    for (s0, s1, text, d2s) in _clauses(say):
        if len(text) <= MAX_CUE_CHARS:
            chunks.append((s0, s1, text))
        else:
            for a in range(0, len(text), MAX_CUE_CHARS):
                piece = text[a:a + MAX_CUE_CHARS].strip()
                if not piece:
                    continue
                cs = d2s[min(a, len(d2s) - 1)]
                ce = d2s[min(a + len(piece), len(d2s) - 1)] + 1
                chunks.append((cs, ce, piece))

    groups, cur = [], []
    for ch in chunks:
        if cur:
            trial = " ".join(c[2] for c in cur + [ch])
            dur_trial = _time_at(marks, ch[1]) - _time_at(marks, cur[0][0])
            # 必须先试算再决定：先 append 后判断会冲过上限一次（两个 20 字小句
            # 拼成 41 字一条），下游再怎么折行都折不回 16 字/行。
            if len(trial) > MAX_CUE_CHARS or dur_trial > MAX_CUE_SEC:
                groups.append(cur)
                cur = [ch]
                continue
        cur.append(ch)
    if cur:
        groups.append(cur)

    out = []
    for group in groups:
        text = " ".join(c[2] for c in group)
        start = _time_at(marks, group[0][0])
        end = _time_at(marks, group[-1][1])
        if end - start < min_sec:
            end = start + min_sec
        out.append((seg_start + start, seg_start + end, _split_lines(text)))
    return out


def check_cues(cues):
    """断言字幕合规：每行汉字 ≤16、每屏 ≤2 行、无逗号句号、阅读速度合规。

    阅读速度要按**加权字数**算，不能把拉丁字母当汉字：
    Netflix 的「9 字符/秒」是中文规范，英文的等价上限约为 20 字符/秒。
    按 1 个拉丁字母 ≈ 0.45 个汉字宽的阅读量折算，混排文本才不会误报
    （`Hello World` 11 个字母 ≈ 5 个汉字宽，绝不是 11 字/秒）。
    """
    bad = []
    for start, end, lines in cues:
        if len(lines) > MAX_LINES:
            bad.append(f"{len(lines)} 行 > {MAX_LINES}: {lines}")
        for ln in lines:
            cjk = _cjk_count(ln)
            if cjk > MAX_LINE_CHARS:
                bad.append(f"「{ln}」{cjk} 个汉字 > {MAX_LINE_CHARS}")
            for ch in "，。；、":
                if ch in ln:
                    bad.append(f"字幕含标点「{ch}」: {ln}")
        weight = sum(_cjk_count(x) + 0.45 * (len(x) - _cjk_count(x)) for x in lines)
        span = max(0.001, end - start)
        if weight / span > 9.0:
            bad.append(f"阅读速度 {weight / span:.1f} 汉字宽/秒 > 9: {lines}")
    return bad


def srt(cues):
    """cue 列表 → SRT 文本"""
    def ts(sec):
        ms = int(round(max(0.0, sec) * 1000))
        h, ms = divmod(ms, 3600000)
        m, ms = divmod(ms, 60000)
        s, ms = divmod(ms, 1000)
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

    blocks = []
    for i, (start, end, lines) in enumerate(cues, start=1):
        blocks.append(f"{i}\n{ts(start)} --> {ts(end)}\n" + "\n".join(lines) + "\n")
    return "\n".join(blocks)


def synthesize_all(segments, voice, rate, pitch, work, concurrency=4):
    """并发合成一集的所有段，返回 [(mp3, marks, dur), …]（保持顺序）"""
    async def run():
        sem = asyncio.Semaphore(concurrency)

        async def one(seg):
            async with sem:
                return await synthesize(seg["say"], voice, rate, pitch, work)

        return await asyncio.gather(*(one(s) for s in segments))

    return asyncio.run(run())
