import asyncio
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import types
import unittest
from unittest import IsolatedAsyncioTestCase, mock

import audio_firefox


class FakePage:
    def __init__(self):
        self.listeners = {}

    def on(self, event, callback):
        self.listeners.setdefault(event, []).append(callback)

    def emit(self, event, value=None):
        for callback in self.listeners.get(event, []):
            callback(value)


def audible_row():
    return {
        "beat": "intro",
        "page_url": "http://localhost:8765/computer-networks/ch01/",
        "source": "http://localhost:8765/computer-networks/ch01/audio/zh/intro.mp3?v=13.392",
        "duration": 13.392,
        "current_time": 13.392,
        "volume": 1.0,
        "muted": False,
        "media_error": None,
        "afail": False,
        "sound_note_hidden": True,
        "context_state": "running",
        "playback_completed": True,
        "sample_count": 268,
        "audible_samples": 200,
        "first_audible_time": 0.3,
        "max_rms": 0.2,
        "max_peak": 0.5,
    }


class FirefoxAudioGateTests(unittest.TestCase):
    def test_audible_row_passes(self):
        self.assertEqual(audio_firefox.validate(audible_row()), [])

    def test_silent_row_fails(self):
        row = audible_row()
        row.update(audible_samples=0, max_rms=0.0, max_peak=0.0)
        self.assertTrue(any("PCM" in error for error in audio_firefox.validate(row)))

    def test_wrong_clip_source_fails(self):
        row = audible_row()
        row["source"] = row["source"].replace("intro.mp3", "packet.mp3")
        self.assertTrue(any("source" in error for error in audio_firefox.validate(row)))

    def test_same_basename_from_another_chapter_fails(self):
        row = audible_row()
        row["source"] = row["source"].replace("/ch01/", "/ch02/")
        self.assertTrue(any("source" in error for error in audio_firefox.validate(row)))

    def test_source_query_string_is_allowed(self):
        row = audible_row()
        row["source"] = row["source"].replace("?v=13.392", "?v=99")
        self.assertEqual(audio_firefox.validate(row), [])

    def test_nonzero_burst_then_stall_fails(self):
        row = audible_row()
        row.update(current_time=3.2, playback_completed=False)
        self.assertTrue(any("complete" in error for error in audio_firefox.validate(row)))

    def test_clock_must_reach_clip_end(self):
        row = audible_row()
        row["current_time"] = 12.0
        self.assertTrue(any("end" in error for error in audio_firefox.validate(row)))

    def test_muted_or_quiet_playback_fails(self):
        for change in ({"muted": True}, {"volume": 0.0}):
            with self.subTest(change=change):
                row = audible_row()
                row.update(change)
                errors = audio_firefox.validate(row)
                self.assertTrue(any("muted" in error or "volume" in error for error in errors))

    def test_playback_failure_fields_fail(self):
        changes = (
            {"media_error": 4},
            {"afail": True},
            {"sound_note_hidden": False},
            {"context_state": "suspended"},
            {"sample_count": 0},
            {"audible_samples": 0},
            {"playback_completed": False},
        )
        for change in changes:
            with self.subTest(change=change):
                row = audible_row()
                row.update(change)
                self.assertTrue(audio_firefox.validate(row))

    def test_error_count_includes_nested_clip_failures(self):
        result = {
            "errors": ["page failed"],
            "chapters": {
                "ch01": {
                    "details": [
                        {"errors": ["silent clip", "stalled clip"]},
                        {"errors": []},
                    ]
                }
            },
        }
        self.assertEqual(audio_firefox.error_count(result), 3)

    def test_expected_clip_count_tracks_selected_chapters(self):
        self.assertEqual(audio_firefox.expected_clip_count(audio_firefox.CHAPTERS), 36)
        self.assertEqual(audio_firefox.expected_clip_count(("ch01",)), 12)
        self.assertEqual(audio_firefox.expected_clip_count(("ch02", "ch03")), 24)

    def test_resume_expression_records_async_rejection_without_returning_promise(self):
        node = shutil.which("node")
        if node is None:
            self.skipTest("Node.js is required for the JavaScript contract test")
        script = r"""
const fs = require('node:fs');
const vm = require('node:vm');
const expression = fs.readFileSync(0, 'utf8');
let rejectResume;
const pending = new Promise((_, reject) => { rejectResume = reject; });
const probe = {
  ctx: {state: 'suspended', resume: () => pending},
  resumeError: null,
  resumeDone: false,
};
const fn = vm.runInNewContext(`(${expression})`, {window: {__audioProbe: probe}});
if (fn() !== undefined) throw new Error('resume expression returned a promise');
if (probe.resumeDone !== false) throw new Error('resume expression did not stay pending');
rejectResume('resume rejected');
setImmediate(() => {
  if (probe.resumeDone !== true) throw new Error('resume rejection was not observed');
  if (probe.resumeError !== 'resume rejected') throw new Error('resume error was lost');
});
"""
        completed = subprocess.run(
            [node, "-e", script], input=audio_firefox.RESUME_AUDIO,
            text=True, capture_output=True, timeout=10,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)


class FirefoxAudioCliTests(unittest.TestCase):
    def test_chapter_option_limits_the_run(self):
        captured = {}

        async def fake_run(out, chapters):
            captured.update(out=out, chapters=chapters)
            return 0

        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "ch02.json"
            with mock.patch.object(audio_firefox, "run", fake_run), mock.patch.object(
                sys, "argv", ["audio_firefox.py", "--chapter", "ch02", "--out", str(out)]
            ):
                self.assertEqual(audio_firefox.main(), 0)
        self.assertEqual(captured, {"out": out, "chapters": ("ch02",)})

    def test_default_run_keeps_all_chapters(self):
        captured = {}

        async def fake_run(out, chapters):
            captured.update(out=out, chapters=chapters)
            return 0

        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "all.json"
            with mock.patch.object(audio_firefox, "run", fake_run), mock.patch.object(
                sys, "argv", ["audio_firefox.py", "--out", str(out)]
            ):
                self.assertEqual(audio_firefox.main(), 0)
        self.assertEqual(captured, {"out": out, "chapters": audio_firefox.CHAPTERS})

    def test_distinct_chapter_options_preserve_order(self):
        captured = {}

        async def fake_run(out, chapters):
            captured.update(chapters=chapters)
            return 0

        argv = [
            "audio_firefox.py", "--chapter", "ch03", "--chapter", "ch01",
            "--out", "selected.json",
        ]
        with mock.patch.object(audio_firefox, "run", fake_run), \
                mock.patch.object(sys, "argv", argv):
            self.assertEqual(audio_firefox.main(), 0)
        self.assertEqual(captured["chapters"], ("ch03", "ch01"))

    def test_duplicate_chapter_option_is_rejected(self):
        async def fake_run(out, chapters):
            self.fail("duplicate chapter selection reached the audio run")

        argv = [
            "audio_firefox.py", "--chapter", "ch01", "--chapter", "ch01",
            "--out", "duplicate.json",
        ]
        with mock.patch.object(audio_firefox, "run", fake_run), \
                mock.patch.object(sys, "argv", argv), \
                mock.patch.object(sys, "stderr", io.StringIO()) as stderr:
            with self.assertRaises(SystemExit) as raised:
                audio_firefox.main()
        self.assertEqual(raised.exception.code, 2)
        self.assertIn("duplicate chapter", stderr.getvalue().lower())


class SamplingPage:
    def __init__(self, samples, hang=False):
        self.samples = iter(samples)
        self.hang = hang

    async def wait_for_function(self, expression, timeout=None):
        pass

    async def evaluate(self, expression, arg=None):
        if expression == audio_firefox.START_CLIP:
            return None
        if expression == audio_firefox.SAMPLE_PCM:
            if self.hang:
                await asyncio.sleep(1)
            return next(self.samples)
        if expression == "() => { if (P.playing) setPlaying(false); }":
            return None
        raise AssertionError(f"unexpected evaluate: {expression}")


class FirefoxAudioSamplingTests(IsolatedAsyncioTestCase):
    def sample(self, **changes):
        row = audible_row()
        row.update(rms=row["max_rms"], peak=row["max_peak"], wall_timeout=False)
        row.update(changes)
        return row

    async def test_python_sampling_aggregates_until_clip_ends(self):
        page = SamplingPage([
            self.sample(
                current_time=0.3, playback_completed=False,
                rms=0.1, peak=0.2, max_rms=0.1, max_peak=0.2,
            ),
            self.sample(
                current_time=6.0, playback_completed=False,
                rms=0.15, peak=0.3, max_rms=0.15, max_peak=0.3,
            ),
            self.sample(rms=0.05, peak=0.1, max_rms=0.05, max_peak=0.1),
        ])
        with mock.patch.object(audio_firefox, "SAMPLE_INTERVAL_MS", 1):
            row = await audio_firefox.measure_clip(page, 0, "intro")
        self.assertTrue(row["passed"], row["errors"])
        self.assertEqual(row["sample_count"], 3)
        self.assertEqual(row["audible_samples"], 3)
        self.assertEqual(row["first_audible_time"], 0.3)
        self.assertEqual(row["last_audible_time"], 13.392)
        self.assertEqual(row["max_rms"], 0.15)
        self.assertEqual(row["max_peak"], 0.3)

    async def test_stalled_media_clock_hits_python_deadline(self):
        page = SamplingPage([
            self.sample(current_time=0.3, playback_completed=False),
        ])
        with mock.patch.object(audio_firefox, "SAMPLE_INTERVAL_MS", 1), \
                mock.patch.object(audio_firefox, "monotonic", side_effect=[0.0, 30.0]):
            row = await audio_firefox.measure_clip(page, 0, "intro")
        self.assertTrue(row["wall_timeout"])
        self.assertFalse(row["passed"])
        self.assertTrue(any("complete" in error for error in row["errors"]))

    async def test_unresponsive_browser_evaluate_has_hard_timeout(self):
        page = SamplingPage([], hang=True)
        with mock.patch.object(audio_firefox, "EVALUATE_TIMEOUT", 0.01):
            with self.assertRaisesRegex(TimeoutError, "browser evaluation exceeded"):
                await audio_firefox.measure_clip(page, 0, "intro")

    async def test_cleanup_failure_does_not_mask_sampling_failure(self):
        class FailingSamplingPage(SamplingPage):
            async def evaluate(self, expression, arg=None):
                if expression == audio_firefox.SAMPLE_PCM:
                    raise RuntimeError("sample failed")
                if expression == "() => { if (P.playing) setPlaying(false); }":
                    raise RuntimeError("cleanup failed")
                return await super().evaluate(expression, arg)

        with self.assertRaisesRegex(RuntimeError, "sample failed"):
            await audio_firefox.measure_clip(FailingSamplingPage([]), 0, "intro")


class FakeAudioPage:
    def __init__(
        self, chapter, hang_final=False, hang_setup=None, hang_context=False,
        resume_error=None, hang_close=False, cancel_on_close=False,
        needs_activation=False,
    ):
        self.chapter = chapter
        self.hang_final = hang_final
        self.hang_setup = hang_setup
        self.hang_context = hang_context
        self.resume_error = resume_error
        self.hang_close = hang_close
        self.cancel_on_close = cancel_on_close
        self.needs_activation = needs_activation
        self.activated = False
        self.resume_pending = False
        self.cancel_clip_count = 0
        self.listeners = {}
        self.keyboard = types.SimpleNamespace(press=mock.AsyncMock(side_effect=self.press))

    def on(self, event, callback):
        self.listeners.setdefault(event, []).append(callback)

    async def goto(self, url):
        pass

    async def press(self, key):
        self.activated = True

    async def wait_for_function(self, expression, timeout=None):
        if self.hang_context and "__audioProbe.ctx.state" in expression:
            await asyncio.sleep(1)
        if "resumeDone" in expression and self.resume_pending:
            await asyncio.sleep(1)

    async def evaluate(self, expression, arg=None):
        if self.hang_setup and self.hang_setup in expression:
            await asyncio.sleep(1)
        if expression == audio_firefox.RESUME_AUDIO:
            self.resume_pending = self.needs_activation and not self.activated
        if "BEATS.map" in expression:
            return [
                {"index": index, "id": f"beat-{index}", "silent": False}
                for index in range(audio_firefox.EXPECTED_CLIPS[self.chapter])
            ]
        if expression == "() => 0" and self.hang_final:
            await asyncio.sleep(1)
        if expression.startswith("() => ({state:"):
            return {"state": "running", "error": self.resume_error}
        return None

    async def close(self):
        if self.cancel_on_close:
            asyncio.current_task().cancel()
        if self.hang_close or self.cancel_on_close:
            await asyncio.sleep(1)


class FirefoxAudioRunTests(IsolatedAsyncioTestCase):
    async def run_audit(
        self, chapters, failed_chapter=None, hang_final_chapter=None,
        hang_setup_chapter=None, hang_setup=None, hang_context_chapter=None,
        resume_error_chapter=None, hang_close=None, cancel_chapter=None,
        cancel_after_clips=None, cancel_cleanup=None, capture_cancel=False,
        needs_activation_chapter=None,
    ):
        pages = [
            FakeAudioPage(
                chapter,
                hang_final=chapter == hang_final_chapter,
                hang_setup=hang_setup if chapter == hang_setup_chapter else None,
                hang_context=chapter == hang_context_chapter,
                resume_error="resume rejected" if chapter == resume_error_chapter else None,
                hang_close=hang_close == f"page:{chapter}",
                cancel_on_close=cancel_cleanup == f"page:{chapter}",
                needs_activation=chapter == needs_activation_chapter,
            )
            for chapter in chapters
        ]

        async def close_context():
            if cancel_cleanup == "context":
                asyncio.current_task().cancel("cleanup cancelled")
            if hang_close == "context" or cancel_cleanup == "context":
                await asyncio.sleep(1)

        async def close_browser():
            if cancel_cleanup == "browser":
                asyncio.current_task().cancel()
            if hang_close == "browser" or cancel_cleanup == "browser":
                await asyncio.sleep(1)

        async def exit_playwright(*args):
            if cancel_cleanup == "playwright":
                asyncio.current_task().cancel()
            if hang_close == "playwright" or cancel_cleanup == "playwright":
                await asyncio.sleep(1)

        context = types.SimpleNamespace(
            new_page=mock.AsyncMock(side_effect=pages), close=mock.AsyncMock(side_effect=close_context)
        )
        browser = types.SimpleNamespace(
            new_context=mock.AsyncMock(return_value=context), close=mock.AsyncMock(side_effect=close_browser)
        )
        playwright_api = types.SimpleNamespace(
            firefox=types.SimpleNamespace(launch=mock.AsyncMock(return_value=browser))
        )
        manager = mock.MagicMock()
        manager.__aenter__ = mock.AsyncMock(return_value=playwright_api)
        manager.__aexit__ = mock.AsyncMock(side_effect=exit_playwright)
        async_api = types.ModuleType("playwright.async_api")
        async_api.async_playwright = lambda: manager
        playwright = types.ModuleType("playwright")
        playwright.async_api = async_api
        browsers = types.ModuleType("browsers")
        browsers.answers = lambda url: None
        browsers.firefox = lambda: {}
        browsers.missing = lambda page, callback: None

        async def fake_measure(page, index, beat):
            if page.chapter == cancel_chapter:
                page.cancel_clip_count += 1
                if cancel_after_clips is None or page.cancel_clip_count >= cancel_after_clips:
                    raise asyncio.CancelledError("playback cancelled")
            passed = page.chapter != failed_chapter
            return {
                "beat": beat,
                "passed": passed,
                "errors": [] if passed else ["failed clip"],
            }

        cancel_message = None
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "audio.json"
            with mock.patch.dict(sys.modules, {
                "playwright": playwright,
                "playwright.async_api": async_api,
                "browsers": browsers,
            }), mock.patch.object(audio_firefox, "measure_clip", fake_measure), \
                    redirect_stdout(io.StringIO()):
                try:
                    status = await audio_firefox.run(out, chapters)
                except asyncio.CancelledError as exc:
                    if cancel_chapter is None and cancel_cleanup is None:
                        raise
                    status = "cancelled"
                    cancel_message = str(exc)
            evidence = json.loads(out.read_text(encoding="utf-8"))
        if capture_cancel:
            return status, evidence, cancel_message
        return status, evidence

    async def test_selected_chapters_aggregate_counts_and_exit_status(self):
        status, evidence = await self.run_audit(("ch02", "ch03"))
        self.assertEqual(status, 0)
        self.assertTrue(evidence["passed"])
        self.assertEqual(evidence["clip_count"], 24)
        self.assertEqual(tuple(evidence["chapters"]), ("ch02", "ch03"))
        self.assertEqual(evidence["chapters"]["ch02"]["clips"], 12)
        self.assertEqual(evidence["chapters"]["ch03"]["clips"], 12)

    async def test_failed_chapter_makes_run_fail(self):
        status, evidence = await self.run_audit(("ch02", "ch03"), failed_chapter="ch03")
        self.assertEqual(status, 1)
        self.assertFalse(evidence["passed"])
        self.assertEqual(evidence["clip_count"], 24)
        self.assertTrue(evidence["chapters"]["ch02"]["passed"])
        self.assertFalse(evidence["chapters"]["ch03"]["passed"])
        self.assertEqual(evidence["error_count"], 12)

    async def test_preflight_exit_writes_failed_evidence(self):
        async_api = types.ModuleType("playwright.async_api")
        async_api.async_playwright = lambda: None
        playwright = types.ModuleType("playwright")
        playwright.async_api = async_api
        browsers = types.ModuleType("browsers")

        def offline(_):
            raise SystemExit("server offline")

        browsers.answers = offline
        browsers.firefox = lambda: {}
        browsers.missing = lambda *args: None
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "failed.json"
            with mock.patch.dict(sys.modules, {
                "playwright": playwright,
                "playwright.async_api": async_api,
                "browsers": browsers,
            }), redirect_stdout(io.StringIO()):
                try:
                    status = await audio_firefox.run(out)
                except SystemExit:
                    self.fail("preflight SystemExit bypassed failed evidence")
            evidence = json.loads(out.read_text(encoding="utf-8"))
        self.assertEqual(status, 1)
        self.assertFalse(evidence["passed"])
        self.assertEqual(evidence["error_count"], 1)
        self.assertIn("server offline", evidence["errors"][0])

    async def test_unresponsive_final_probe_has_hard_timeout(self):
        with mock.patch.object(audio_firefox, "EVALUATE_TIMEOUT", 0.01):
            status, evidence = await self.run_audit(
                ("ch01",), hang_final_chapter="ch01"
            )
        self.assertEqual(status, 1)
        self.assertFalse(evidence["passed"])
        self.assertEqual(evidence["clip_count"], 12)
        self.assertEqual(evidence["chapters"]["ch01"]["clips"], 12)
        self.assertEqual(evidence["error_count"], 1)
        self.assertIn("final browser probe", evidence["errors"][0])
        self.assertIn("browser evaluation exceeded", evidence["errors"][0])

    async def test_unresponsive_audio_resume_has_hard_timeout(self):
        with mock.patch.object(audio_firefox, "EVALUATE_TIMEOUT", 0.01):
            status, evidence = await asyncio.wait_for(
                self.run_audit(
                    ("ch01",), hang_setup_chapter="ch01",
                    hang_setup="probe.ctx.resume()",
                ),
                timeout=0.5,
            )
        self.assertEqual(status, 1)
        self.assertFalse(evidence["passed"])
        self.assertEqual(evidence["clip_count"], 0)
        self.assertFalse(evidence["chapters"]["ch01"]["passed"])
        self.assertEqual(evidence["error_count"], 1)
        self.assertIn("resume AudioContext", evidence["errors"][0])
        self.assertIn("browser evaluation exceeded", evidence["errors"][0])

    async def test_unresponsive_probe_install_has_hard_timeout(self):
        with mock.patch.object(audio_firefox, "EVALUATE_TIMEOUT", 0.01):
            status, evidence = await asyncio.wait_for(
                self.run_audit(
                    ("ch01",), hang_setup_chapter="ch01",
                    hang_setup=audio_firefox.INSTALL_PROBE,
                ),
                timeout=0.5,
            )
        self.assertEqual(status, 1)
        self.assertEqual(evidence["clip_count"], 0)
        self.assertEqual(evidence["error_count"], 1)
        self.assertIn("install audio probe", evidence["errors"][0])
        self.assertIn("browser evaluation exceeded", evidence["errors"][0])

    async def test_suspended_audio_context_has_bounded_wait(self):
        with mock.patch.object(audio_firefox, "CONTEXT_TIMEOUT", 0.01):
            status, evidence = await asyncio.wait_for(
                self.run_audit(("ch01",), hang_context_chapter="ch01"),
                timeout=0.5,
            )
        self.assertEqual(status, 1)
        self.assertEqual(evidence["clip_count"], 0)
        self.assertEqual(evidence["error_count"], 1)
        self.assertIn("AudioContext did not start", evidence["errors"][0])
        self.assertIn("0.01s", evidence["errors"][0])

    async def test_rejected_audio_resume_fails_even_if_context_reports_running(self):
        status, evidence = await self.run_audit(
            ("ch01",), resume_error_chapter="ch01"
        )
        self.assertEqual(status, 1)
        self.assertEqual(evidence["clip_count"], 0)
        self.assertFalse(evidence["chapters"]["ch01"]["passed"])
        self.assertEqual(evidence["error_count"], 1)
        self.assertIn("resume failed", evidence["errors"][0])
        self.assertIn("resume rejected", evidence["errors"][0])

    async def test_audio_context_resume_requires_browser_activation(self):
        with mock.patch.object(audio_firefox, "CONTEXT_TIMEOUT", 0.01):
            status, evidence = await self.run_audit(
                ("ch01",), needs_activation_chapter="ch01",
            )
        self.assertEqual(status, 0)
        self.assertTrue(evidence["passed"])
        self.assertEqual(evidence["clip_count"], 12)

    async def test_cleanup_timeouts_are_bounded_and_preserve_evidence(self):
        for resource in ("page:ch01", "context", "browser", "playwright"):
            with self.subTest(resource=resource):
                with mock.patch.object(audio_firefox, "CLOSE_TIMEOUT", 0.01, create=True):
                    status, evidence = await asyncio.wait_for(
                        self.run_audit(("ch01",), hang_close=resource),
                        timeout=0.5,
                    )
                self.assertEqual(status, 1)
                self.assertFalse(evidence["passed"])
                self.assertEqual(evidence["clip_count"], 12)
                self.assertIn("cleanup", evidence["errors"][0])
                self.assertIn("0.01s", evidence["errors"][0])

    async def test_cancellation_writes_partial_evidence_and_reraises(self):
        status, evidence = await asyncio.wait_for(
            self.run_audit(("ch01", "ch02"), cancel_chapter="ch02"),
            timeout=0.5,
        )
        self.assertEqual(status, "cancelled")
        self.assertFalse(evidence["passed"])
        self.assertEqual(evidence["clip_count"], 12)
        self.assertTrue(evidence["chapters"]["ch01"]["passed"])
        self.assertFalse(evidence["chapters"]["ch02"]["passed"])
        self.assertIn("ch02: expected 12 audible clips, found 0", evidence["errors"])
        self.assertEqual(evidence["errors"][-1], "audio audit cancelled")

    async def test_cancellation_after_partial_clips_preserves_completed_rows(self):
        status, evidence = await asyncio.wait_for(
            self.run_audit(("ch01",), cancel_chapter="ch01", cancel_after_clips=3),
            timeout=0.5,
        )
        self.assertEqual(status, "cancelled")
        self.assertEqual(evidence["clip_count"], 2)
        self.assertEqual(len(evidence["chapters"]["ch01"]["details"]), 2)
        self.assertFalse(evidence["chapters"]["ch01"]["passed"])
        self.assertEqual(evidence["errors"][-1], "audio audit cancelled")

    async def test_cancellation_during_cleanup_still_writes_evidence(self):
        for resource in ("page:ch01", "context", "browser", "playwright"):
            with self.subTest(resource=resource):
                with mock.patch.object(audio_firefox, "CLOSE_TIMEOUT", 0.01):
                    status, evidence = await asyncio.wait_for(
                        self.run_audit(("ch01",), cancel_cleanup=resource),
                        timeout=0.5,
                    )
                self.assertEqual(status, "cancelled")
                self.assertFalse(evidence["passed"])
                self.assertEqual(evidence["clip_count"], 12)
                self.assertEqual(evidence["chapters"]["ch01"]["clips"], 12)
                self.assertTrue(any("cleanup" in error and "cancelled" in error
                                    for error in evidence["errors"]))
                self.assertEqual(evidence["errors"][-1], "audio audit cancelled")

    async def test_cleanup_cancellation_does_not_replace_playback_cancellation(self):
        status, evidence, cancel_message = await self.run_audit(
            ("ch01", "ch02"), cancel_chapter="ch02", cancel_cleanup="context",
            capture_cancel=True,
        )
        self.assertEqual(status, "cancelled")
        self.assertEqual(cancel_message, "playback cancelled")
        self.assertEqual(evidence["clip_count"], 12)
        self.assertIn("cleanup: browser context cancelled", evidence["errors"])
        self.assertEqual(evidence["errors"].count("audio audit cancelled"), 1)

    async def test_request_tracker_waits_for_late_events(self):
        page = FakePage()
        pending = audio_firefox.track_requests(page)
        page.emit("request", object())
        late_errors = []

        async def finish_request():
            await asyncio.sleep(0.03)
            late_errors.append("missing file (404)")
            page.emit("requestfinished", object())

        task = asyncio.create_task(finish_request())
        settled = await audio_firefox.wait_for_requests(pending, timeout=1)
        await task
        self.assertTrue(settled)
        self.assertEqual(pending["pending"], 0)
        self.assertEqual(late_errors, ["missing file (404)"])

    async def test_unsettled_requests_fail_the_drain(self):
        page = FakePage()
        pending = audio_firefox.track_requests(page)
        page.emit("request", object())
        self.assertFalse(await audio_firefox.wait_for_requests(pending, timeout=0.01))


if __name__ == "__main__":
    unittest.main()
