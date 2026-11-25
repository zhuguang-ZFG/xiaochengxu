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
CONTEXT_TIMEOUT = 10
PAGE_TIMEOUT = 30
CLOSE_TIMEOUT = 5

INSTALL_PROBE = r"""() => {
  const ctx = new AudioContext();
  const analyser = ctx.createAnalyser();
  analyser.fftSize = 2048;
  analyser.connect(ctx.destination);
  window.__audioProbe = {
    ctx, analyser, data: new Float32Array(analyser.fftSize), sources: new WeakMap()
  };
}"""

RESUME_AUDIO = r"""() => {
  const probe = window.__audioProbe;
  probe.resumeError = null;
  if (probe.ctx.state === 'running') {
    probe.resumeDone = true;
    return;
  }
  probe.resumeDone = false;
  probe.ctx.resume().then(
    () => { probe.resumeDone = true; },
    error => { probe.resumeError = String(error); probe.resumeDone = true; }
  );
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


async def evaluate_stage(page, chapter, stage, expression, arg=None):
    print(f"firefox: {chapter}: {stage}", flush=True)
    try:
        return await evaluate_with_timeout(page, expression, arg)
    except Exception as exc:
        raise RuntimeError(f"{chapter}: {stage} failed: {exc}") from exc


async def wait_stage(page, chapter, stage, expression, timeout):
    print(f"firefox: {chapter}: {stage}", flush=True)
    try:
        return await asyncio.wait_for(page.wait_for_function(expression), timeout=timeout)
    except TimeoutError as exc:
        raise RuntimeError(f"{chapter}: {stage} exceeded {timeout:g}s") from exc
    except Exception as exc:
        raise RuntimeError(f"{chapter}: {stage} failed: {exc}") from exc


async def wait_for_audio_context(page, chapter):
    print(f"firefox: {chapter}: wait for AudioContext", flush=True)
    try:
        await asyncio.wait_for(
            page.wait_for_function(
                "window.__audioProbe.resumeDone && "
                "(window.__audioProbe.resumeError !== null || "
                "window.__audioProbe.ctx.state === 'running')"
            ),
            timeout=CONTEXT_TIMEOUT,
        )
    except TimeoutError as exc:
        raise RuntimeError(
            f"{chapter}: AudioContext did not start within {CONTEXT_TIMEOUT:g}s"
        ) from exc
    except Exception as exc:
        raise RuntimeError(f"{chapter}: wait for AudioContext failed: {exc}") from exc
    state = await evaluate_stage(
        page, chapter, "read AudioContext state",
        "() => ({state: window.__audioProbe.ctx.state, error: window.__audioProbe.resumeError})",
    )
    if state["error"] is not None:
        raise RuntimeError(f"{chapter}: AudioContext resume failed: {state['error']}")
    if state["state"] != "running":
        raise RuntimeError(
            f"{chapter}: AudioContext did not start: state={state['state']}, "
            f"error={state['error']}"
        )


async def bounded_cleanup(label, operation):
    try:
        await asyncio.wait_for(operation, timeout=CLOSE_TIMEOUT)
    except TimeoutError:
        return f"cleanup: {label} exceeded {CLOSE_TIMEOUT:g}s"
    except Exception as exc:
        return f"cleanup: {label} failed: {exc}"
    return None


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
    page = context = browser = manager = None
    cancelled = None
    try:
        from playwright.async_api import async_playwright
        sys.path.insert(0, str(ROOT / ".qoder" / "skills" / "papermorph" / "scripts"))
        from browsers import answers, firefox, missing

        answers(URL)
        manager = async_playwright()
        p = await manager.__aenter__()
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
            rows = []
            chapter_errors = []
            setup_complete = False
            try:
                print(f"firefox: {chapter}: load page", flush=True)
                try:
                    await asyncio.wait_for(page.goto(URL + chapter + "/"), timeout=PAGE_TIMEOUT)
                except TimeoutError as exc:
                    raise RuntimeError(f"{chapter}: load page exceeded {PAGE_TIMEOUT:g}s") from exc
                except Exception as exc:
                    raise RuntimeError(f"{chapter}: load page failed: {exc}") from exc
                await wait_stage(
                    page, chapter, "wait for page scripts",
                    "typeof BEATS !== 'undefined'", PAGE_TIMEOUT,
                )
                await evaluate_stage(page, chapter, "set volume", """() => {
                  const volume = document.getElementById('volume');
                  volume.value = '1';
                  volume.dispatchEvent(new Event('input', {bubbles: true}));
                }""")
                await evaluate_stage(
                    page, chapter, "install audio probe", INSTALL_PROBE
                )
                await evaluate_stage(
                    page, chapter, "resume AudioContext", RESUME_AUDIO
                )
                await wait_for_audio_context(page, chapter)
                beats = await evaluate_stage(
                    page, chapter, "read beats",
                    "BEATS.map((b, i) => ({index:i, id:b.id, silent:!!TIMINGS[b.id]?.silent}))",
                )
                setup_complete = True
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
                if not await wait_for_requests(pending):
                    chapter_errors.append(f"{chapter}: page requests did not settle")
                try:
                    await evaluate_with_timeout(page, "() => 0")
                except Exception as exc:
                    chapter_errors.append(f"{chapter}: final browser probe failed: {exc}")
                await asyncio.sleep(0)
            except asyncio.CancelledError as exc:
                cancelled = cancelled or exc
            except Exception as exc:
                chapter_errors.append(str(exc))
            finally:
                chapter_errors.extend(f"{chapter}: {error}" for error in page_errors + absent)
                if setup_complete and len(rows) != EXPECTED_CLIPS[chapter]:
                    chapter_errors.append(
                        f"{chapter}: expected {EXPECTED_CLIPS[chapter]} audible clips, found {len(rows)}"
                    )
                try:
                    cleanup_error = await bounded_cleanup(f"{chapter} page", page.close())
                except asyncio.CancelledError as exc:
                    cancelled = cancelled or exc
                    cleanup_error = f"cleanup: {chapter} page cancelled"
                if cleanup_error:
                    chapter_errors.append(cleanup_error)
                page = None
                result["warnings"].extend(f"{chapter}: {warning}" for warning in warnings)
                result["errors"].extend(chapter_errors)
                result["chapters"][chapter] = {
                    "passed": setup_complete and len(rows) == EXPECTED_CLIPS[chapter]
                              and not chapter_errors and all(row["passed"] for row in rows),
                    "clips": len(rows),
                    "details": rows,
                }
                result["clip_count"] += len(rows)
            if cancelled is not None:
                raise cancelled
    except asyncio.CancelledError as exc:
        cancelled = cancelled or exc
        result["errors"].append("audio audit cancelled")
        raise
    except (Exception, SystemExit) as exc:
        result["errors"].append(f"audio audit aborted: {exc}")
    finally:
        cleanup_errors = []
        cleanup_cancel = None
        operations = []
        if page is not None:
            operations.append(("page", page.close))
        if context is not None:
            operations.append(("browser context", context.close))
        if browser is not None:
            operations.append(("browser", browser.close))
        if manager is not None:
            operations.append(("Playwright", lambda: manager.__aexit__(None, None, None)))
        for label, close in operations:
            try:
                error = await bounded_cleanup(label, close())
            except asyncio.CancelledError as exc:
                cleanup_cancel = cleanup_cancel or exc
                error = f"cleanup: {label} cancelled"
            if error:
                cleanup_errors.append(error)
        result["errors"].extend(cleanup_errors)
        if cleanup_cancel is not None and "audio audit cancelled" not in result["errors"]:
            result["errors"].append("audio audit cancelled")
        result["error_count"] = error_count(result)
        result["passed"] = (
            result["clip_count"] == expected_clip_count(chapters) and not result["errors"]
            and len(result["chapters"]) == len(chapters)
            and all(chapter["passed"] for chapter in result["chapters"].values())
        )
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        if cleanup_cancel is not None:
            raise cancelled if cancelled is not None else cleanup_cancel
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
