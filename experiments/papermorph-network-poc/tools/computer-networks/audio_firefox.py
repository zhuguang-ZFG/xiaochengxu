"""Verify that every Firefox narration clip plays to completion and renders non-zero PCM."""
import argparse
import asyncio
import json
import math
import os
from pathlib import Path
import sys
from time import monotonic
from urllib.parse import urljoin, urlsplit

ROOT = Path(__file__).resolve().parents[2]
SITE = ROOT / "site" / "computer-networks"
CHAPTERS = ("ch01", "ch02", "ch03")
EXPECTED_CLIPS = {chapter: 12 for chapter in CHAPTERS}
URL = os.environ.get("URL", "http://localhost:8765/computer-networks/").rstrip("/") + "/"
MIN_SAMPLES = 2
SAMPLE_INTERVAL_MS = 50
MIN_RMS = 0.0001
MIN_PEAK = 0.001
EVALUATE_TIMEOUT = 5

INSTALL_PROBE = r"""() => {
  const ctx = new AudioContext();
  const analyser = ctx.createAnalyser();
  analyser.fftSize = 2048;
  analyser.connect(ctx.destination);
  window.__audioProbe = {
    ctx, analyser, data: new Float32Array(analyser.fftSize), sources: new WeakMap()
  };
}"""

START_CLIP = r"""i => {
  seek(i, false);
  const probe = window.__audioProbe, audio = P.audio;
  if (!probe.sources.has(audio)) {
    probe.sources.set(audio, probe.ctx.createMediaElementSource(audio).connect(probe.analyser));
  }
  setPlaying(true);
  P.waiting = true;
}"""

SAMPLE_PCM = r"""() => {
  const probe = window.__audioProbe, audio = P.audio;
  probe.analyser.getFloatTimeDomainData(probe.data);
  let sum = 0, peak = 0;
  for (const value of probe.data) {
    sum += value * value;
    peak = Math.max(peak, Math.abs(value));
  }
  return {
    page_url: location.href,
    source: audio.currentSrc,
    duration: audio.duration,
    current_time: audio.currentTime,
    ready_state: audio.readyState,
    volume: audio.volume,
    muted: audio.muted,
    media_error: audio.error?.code ?? null,
    afail: P.afail,
    sound_note_hidden: document.getElementById('soundNote').hidden,
    context_state: probe.ctx.state,
    playback_completed: audio.ended,
    rms: Math.sqrt(sum / probe.data.length),
    peak,
  };
}"""


def source_id(value):
    parsed = urlsplit(value)
    return parsed.scheme, parsed.netloc, parsed.path


def expected_clip_count(chapters):
    return sum(EXPECTED_CLIPS[chapter] for chapter in chapters)


def validate(row):
    errors = []
    beat = row["beat"]
    expected = urljoin(row["page_url"], f"audio/zh/{beat}.mp3")
    if source_id(row["source"]) != source_id(expected):
        errors.append(f"unexpected audio source for {beat}")
    if not math.isfinite(row["duration"]) or row["duration"] <= 0:
        errors.append(f"invalid media duration for {beat}")
    if row["current_time"] <= 0.2:
        errors.append(f"audio clock did not advance for {beat}")
    if not row["playback_completed"]:
        errors.append(f"audio playback did not complete for {beat}")
    elif not math.isclose(row["current_time"], row["duration"], abs_tol=0.1):
        errors.append(f"audio clock did not reach the clip end for {beat}")
    if row["muted"]:
        errors.append(f"audio is muted for {beat}")
    if not math.isclose(row["volume"], 1.0, abs_tol=1e-9):
        errors.append(f"audio volume is not full for {beat}")
    if row["media_error"] is not None:
        errors.append(f"media error {row['media_error']} for {beat}")
    if row["afail"]:
        errors.append(f"engine reported audio failure for {beat}")
    if not row["sound_note_hidden"]:
        errors.append(f"sound failure note is visible for {beat}")
    if row["context_state"] != "running":
        errors.append(f"AudioContext is {row['context_state']} for {beat}")
    if row["sample_count"] < MIN_SAMPLES:
        errors.append(f"insufficient PCM samples for {beat}")
    if row["audible_samples"] < 1:
        errors.append(f"no audible PCM samples for {beat}")
    if (not math.isfinite(row["max_rms"]) or not math.isfinite(row["max_peak"])
            or row["max_rms"] <= MIN_RMS or row["max_peak"] <= MIN_PEAK):
        errors.append(f"silent or inaudible PCM for {beat}")
    return errors


def error_count(result):
    nested = sum(
        len(row.get("errors", []))
        for chapter in result["chapters"].values()
        for row in chapter.get("details", [])
    )
    return len(result["errors"]) + nested


def track_requests(page):
    state = {"pending": 0}

    def started(_):
        state["pending"] += 1

    def finished(_):
        state["pending"] -= 1

    page.on("request", started)
    page.on("requestfinished", finished)
    page.on("requestfailed", finished)
    return state


async def wait_for_requests(state, timeout=10):
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while state["pending"] > 0:
        if loop.time() >= deadline:
            return False
        await asyncio.sleep(0.01)
    await asyncio.sleep(0)
    return state["pending"] == 0


async def evaluate_with_timeout(page, expression, arg=None):
    try:
        return await asyncio.wait_for(page.evaluate(expression, arg), timeout=EVALUATE_TIMEOUT)
    except TimeoutError as exc:
        raise TimeoutError(f"browser evaluation exceeded {EVALUATE_TIMEOUT:g}s") from exc


async def measure_clip(page, index, beat):
    failure = None
    try:
        await evaluate_with_timeout(page, START_CLIP, index)
        await page.wait_for_function(
            "P.audio && !P.audio.paused && P.audio.currentTime > .2", timeout=10000
        )
        sample_count = 0
        audible_samples = 0
        max_rms = 0.0
        max_peak = 0.0
        first_audible_time = None
        last_audible_time = None
        wall_timeout = False
        deadline = None
        row = None
        while True:
            sample = await evaluate_with_timeout(page, SAMPLE_PCM)
            if deadline is None:
                duration = sample["duration"]
                timeout = max(5.0, (duration if math.isfinite(duration) else 30) * 2 + 2)
                deadline = monotonic() + timeout
            sample_count += 1
            max_rms = max(max_rms, sample["rms"])
            max_peak = max(max_peak, sample["peak"])
            if sample["rms"] > MIN_RMS and sample["peak"] > MIN_PEAK:
                audible_samples += 1
                if first_audible_time is None:
                    first_audible_time = sample["current_time"]
                last_audible_time = sample["current_time"]
            row = sample
            if row["playback_completed"]:
                break
            if monotonic() >= deadline:
                wall_timeout = True
                break
            await asyncio.sleep(SAMPLE_INTERVAL_MS / 1000)
        row.update({
            "wall_timeout": wall_timeout,
            "sample_count": sample_count,
            "audible_samples": audible_samples,
            "first_audible_time": first_audible_time,
            "last_audible_time": last_audible_time,
            "max_rms": max_rms,
            "max_peak": max_peak,
        })
        row.pop("rms")
        row.pop("peak")
        row["beat"] = beat
        row["errors"] = validate(row)
        row["passed"] = not row["errors"]
        return row
    except BaseException as exc:
        failure = exc
        raise
    finally:
        try:
            await evaluate_with_timeout(page, "() => { if (P.playing) setPlaying(false); }")
        except BaseException:
            if failure is None:
                raise


async def run(out, chapters=CHAPTERS):
    result = {
        "schema": 1,
        "browser": "firefox",
        "url": URL,
        "passed": False,
        "clip_count": 0,
        "chapters": {},
        "errors": [],
        "warnings": [],
        "thresholds": {
            "min_samples": MIN_SAMPLES,
            "sample_interval_ms": SAMPLE_INTERVAL_MS,
            "min_rms": MIN_RMS,
            "min_peak": MIN_PEAK,
        },
        "limitations": [
            "PCM sampled every 50 ms proves Firefox rendered audible signal during playback, not human listening quality or real-device speaker output."
        ],
    }
    try:
        from playwright.async_api import async_playwright
        sys.path.insert(0, str(ROOT / ".qoder" / "skills" / "papermorph" / "scripts"))
        from browsers import answers, firefox, missing

        answers(URL)
        async with async_playwright() as p:
            browser = await p.firefox.launch(**firefox())
            context = await browser.new_context(
                viewport={"width": 1440, "height": 900}, reduced_motion="reduce"
            )
            for chapter in chapters:
                print(f"firefox: start {chapter} ({EXPECTED_CLIPS[chapter]} audible clips)", flush=True)
                page = await context.new_page()
                page_errors, warnings, absent = [], [], []
                pending = track_requests(page)
                page.on("pageerror", lambda error: page_errors.append(str(error)))
                page.on("console", lambda message: page_errors.append(message.text)
                        if message.type == "error" else warnings.append(message.text)
                        if message.type == "warning" else None)
                missing(page, absent.append)
                await page.goto(URL + chapter + "/")
                await page.wait_for_function("typeof BEATS !== 'undefined'")
                await page.evaluate("""() => {
                  const volume = document.getElementById('volume');
                  volume.value = '1';
                  volume.dispatchEvent(new Event('input', {bubbles: true}));
                }""")
                await page.evaluate(INSTALL_PROBE)
                await page.evaluate("window.__audioProbe.ctx.resume()")
                await page.wait_for_function("window.__audioProbe.ctx.state === 'running'")
                beats = await page.evaluate(
                    "BEATS.map((b, i) => ({index:i, id:b.id, silent:!!TIMINGS[b.id]?.silent}))"
                )
                rows = []
                for beat in beats:
                    if beat["silent"]:
                        continue
                    started = monotonic()
                    try:
                        row = await measure_clip(page, beat["index"], beat["id"])
                        rows.append(row)
                        print(f"firefox: {chapter}/{beat['id']}: {monotonic() - started:.1f}s wall, "
                              f"passed={row['passed']}", flush=True)
                    except Exception as exc:
                        row = {
                            "beat": beat["id"], "passed": False,
                            "errors": [f"{chapter}/{beat['id']}: {exc}"],
                        }
                        rows.append(row)
                        print(f"firefox: {chapter}/{beat['id']}: {monotonic() - started:.1f}s wall, "
                              f"error={exc}", flush=True)
                chapter_errors = []
                if not await wait_for_requests(pending):
                    chapter_errors.append(f"{chapter}: page requests did not settle")
                try:
                    await evaluate_with_timeout(page, "() => 0")
                except Exception as exc:
                    chapter_errors.append(f"{chapter}: final browser probe failed: {exc}")
                await asyncio.sleep(0)
                chapter_errors.extend(f"{chapter}: {error}" for error in page_errors + absent)
                if len(rows) != EXPECTED_CLIPS[chapter]:
                    chapter_errors.append(
                        f"{chapter}: expected {EXPECTED_CLIPS[chapter]} audible clips, found {len(rows)}"
                    )
                result["warnings"].extend(f"{chapter}: {warning}" for warning in warnings)
                result["errors"].extend(chapter_errors)
                result["chapters"][chapter] = {
                    "passed": len(rows) == EXPECTED_CLIPS[chapter] and not chapter_errors
                              and all(row["passed"] for row in rows),
                    "clips": len(rows),
                    "details": rows,
                }
                result["clip_count"] += len(rows)
                await page.close()
            await context.close()
            await browser.close()
        result["passed"] = (
            result["clip_count"] == expected_clip_count(chapters) and not result["errors"]
            and all(chapter["passed"] for chapter in result["chapters"].values())
        )
    except (Exception, SystemExit) as exc:
        result["errors"].append(f"audio audit aborted: {exc}")
    result["error_count"] = error_count(result)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"firefox: {result['clip_count']} clips, {result['error_count']} errors, "
          f"passed={result['passed']}")
    print(f"evidence: {out.relative_to(ROOT) if out.is_relative_to(ROOT) else out}")
    return 0 if result["passed"] else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out", type=Path,
        default=ROOT / "tools/computer-networks/evidence/firefox-audio.json",
    )
    parser.add_argument(
        "--chapter", action="append", choices=CHAPTERS,
        help="run only the selected chapter; repeat to select more than one",
    )
    args = parser.parse_args()
    chapters = tuple(args.chapter or CHAPTERS)
    if len(set(chapters)) != len(chapters):
        parser.error("duplicate chapter selections are not allowed")
    return asyncio.run(run(args.out, chapters))


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())
