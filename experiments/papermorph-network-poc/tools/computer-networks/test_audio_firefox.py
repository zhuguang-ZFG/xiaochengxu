import asyncio
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
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


class FirefoxAudioRunTests(IsolatedAsyncioTestCase):
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
