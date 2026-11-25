import contextlib
from decimal import Decimal
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import verify_delivery as delivery


ROOT = delivery.ROOT
SCRATCH = ROOT / "tools" / "computer-networks"


class DeliveryAuditTests(unittest.TestCase):
    def temporary_directory(self):
        value = tempfile.TemporaryDirectory(dir=SCRATCH)
        self.addCleanup(value.cleanup)
        return Path(value.name)

    def copied_site(self):
        target = self.temporary_directory() / "computer-networks"
        shutil.copytree(delivery.SITE, target)
        return target

    def run_main(self, site):
        output = site.parent / "delivery.json"
        audio_bytes = sum(
            path.stat().st_size for path in site.rglob("*.mp3") if path.is_file()
        )
        def chapter(ch):
            timing_text = (site / ch / "audio" / "zh" / "timings.js").read_text(encoding="utf-8")
            timings = json.loads(timing_text[timing_text.index("{"):timing_text.rindex("}") + 1])
            return {"clips": 12, "seconds": 0.0, "bytes": audio_bytes,
                    "details": [{"beat": beat} for beat in timings]}

        stdout = io.StringIO()
        with patch.object(delivery, "SITE", site), \
                patch.object(delivery, "audio", side_effect=chapter), \
                patch.object(sys, "argv", ["verify_delivery.py", "--out", str(output)]), \
                contextlib.redirect_stdout(stdout):
            status = delivery.main()
        return status, stdout.getvalue(), output

    def test_relative_output_path_is_resolved(self):
        site = self.copied_site()
        output = site.parent / "relative-delivery.json"
        previous = Path.cwd()
        try:
            os.chdir(site.parent)
            with patch.object(delivery, "SITE", site), \
                    patch.object(sys, "argv", [
                        "verify_delivery.py", "--out", "relative-delivery.json",
                    ]), contextlib.redirect_stdout(io.StringIO()):
                status = delivery.main()
        finally:
            os.chdir(previous)
        self.assertEqual(status, 0)
        self.assertTrue(output.is_file())
        self.assertTrue(json.loads(output.read_text(encoding="utf-8"))["passed"])

    def test_timing_requires_decimal_exact_match(self):
        root = self.temporary_directory()
        source = delivery.SITE / "ch01" / "audio" / "zh"
        folder = root / "ch01" / "audio" / "zh"
        shutil.copytree(source, folder)
        timing_path = folder / "timings.js"
        text = timing_path.read_text(encoding="utf-8")
        start = text.index("{")
        timings = json.loads(text[start:text.rindex("}") + 1])
        timings["intro"]["dur"] += 0.0004
        timing_path.write_text(text[:start] + json.dumps(timings), encoding="utf-8")
        with patch.object(delivery, "SITE", root):
            with self.assertRaisesRegex(ValueError, "!="):
                delivery.audio("ch01")

    def test_decode_rejects_truncated_mp3(self):
        path = self.temporary_directory() / "truncated.mp3"
        subprocess.run([
            "ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=440:duration=1",
            "-c:a", "libmp3lame", str(path),
        ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        duration, stream = delivery.probe(path)
        data = path.read_bytes()
        path.write_bytes(data[:len(data) // 2])
        with self.assertRaisesRegex(ValueError, "decoded duration"):
            delivery.decode(path, stream, Decimal(duration))

    def test_extra_mp3_is_rejected(self):
        site = self.copied_site()
        (site / "ch01" / "audio" / "zh" / "unexpected.mp3").write_bytes(b"not audio")
        status, output, _ = self.run_main(site)
        self.assertEqual(status, 1, output)
        self.assertIn("unexpected.mp3", output)

    def test_missing_css_import_is_rejected(self):
        site = self.copied_site()
        path = site / "lib" / "contents.css"
        path.write_text(path.read_text(encoding="utf-8") + '\n@import "missing.css";\n', encoding="utf-8")
        status, output, _ = self.run_main(site)
        self.assertEqual(status, 1, output)
        self.assertIn("missing.css", output)

    def test_dynamic_fetch_requires_literal_local_target(self):
        site = self.copied_site()
        path = site / "lib" / "network.js"
        path.write_text(path.read_text(encoding="utf-8") + "\nfetch(runtimeTarget);\n", encoding="utf-8")
        status, output, _ = self.run_main(site)
        self.assertEqual(status, 1, output)
        self.assertIn("dynamic fetch", output)

    def test_fetch_rejects_concatenated_target(self):
        site = self.copied_site()
        path = site / "lib" / "network.js"
        path.write_text(path.read_text(encoding="utf-8") + '\nfetch("" + runtimeTarget);\n', encoding="utf-8")
        status, output, _ = self.run_main(site)
        self.assertEqual(status, 1, output)
        self.assertIn("dynamic fetch", output)

    def test_fetch_rejects_template_expression(self):
        site = self.copied_site()
        path = site / "lib" / "network.js"
        path.write_text(path.read_text(encoding="utf-8") + "\nfetch(`${runtimeTarget}`);\n", encoding="utf-8")
        status, output, _ = self.run_main(site)
        self.assertEqual(status, 1, output)
        self.assertIn("dynamic fetch", output)

    def test_optional_fetch_is_scanned(self):
        site = self.copied_site()
        path = site / "lib" / "network.js"
        path.write_text(path.read_text(encoding="utf-8") + "\nfetch?.(runtimeTarget);\n", encoding="utf-8")
        status, output, _ = self.run_main(site)
        self.assertEqual(status, 1, output)
        self.assertIn("dynamic fetch", output)

    def test_beacon_is_rejected(self):
        site = self.copied_site()
        path = site / "lib" / "network.js"
        path.write_text(path.read_text(encoding="utf-8") + "\nnavigator.sendBeacon(runtimeTarget);\n", encoding="utf-8")
        status, output, _ = self.run_main(site)
        self.assertEqual(status, 1, output)
        self.assertIn("runtime dependency mechanism", output)

    def test_uppercase_external_url_is_rejected(self):
        site = self.copied_site()
        path = site / "lib" / "network.js"
        path.write_text(path.read_text(encoding="utf-8") + '\nconst remote = "HTTP://example.invalid/x";\n', encoding="utf-8")
        status, output, _ = self.run_main(site)
        self.assertEqual(status, 1, output)
        self.assertIn("external URL literal", output)

    def test_dynamic_script_requires_reviewed_local_pattern(self):
        site = self.copied_site()
        path = site / "lib" / "network.js"
        path.write_text(path.read_text(encoding="utf-8") + "\nObject.assign(document.createElement('script'), { src: runtimeTarget });\n", encoding="utf-8")
        status, output, _ = self.run_main(site)
        self.assertEqual(status, 1, output)
        self.assertIn("runtime dependency mechanism", output)

    def test_quoted_css_import_url_is_not_misreported(self):
        site = self.copied_site()
        path = site / "lib" / "contents.css"
        path.write_text(path.read_text(encoding="utf-8") + '\n@import url("volume.css");\n', encoding="utf-8")
        status, output, _ = self.run_main(site)
        self.assertEqual(status, 0, output)

    def test_commented_css_import_is_ignored(self):
        site = self.copied_site()
        path = site / "lib" / "contents.css"
        path.write_text(path.read_text(encoding="utf-8") + '\n/* @import "missing.css"; */\n', encoding="utf-8")
        status, output, _ = self.run_main(site)
        self.assertEqual(status, 0, output)

    def test_css_comment_removal_consumes_closing_delimiter(self):
        self.assertEqual(delivery.css_without_comments("a/* comment */b"), "ab")

    def test_image_set_string_dependency_is_checked(self):
        site = self.copied_site()
        path = site / "lib" / "contents.css"
        path.write_text(path.read_text(encoding="utf-8") + '\n.x { background-image: image-set("missing.png" 1x); }\n', encoding="utf-8")
        status, output, _ = self.run_main(site)
        self.assertEqual(status, 1, output)
        self.assertIn("missing.png", output)

    def test_escaped_css_url_requires_review(self):
        site = self.copied_site()
        path = site / "lib" / "contents.css"
        path.write_text(path.read_text(encoding="utf-8") + '\n.x { background: u\\72l(missing.png); }\n', encoding="utf-8")
        status, output, _ = self.run_main(site)
        self.assertEqual(status, 1, output)
        self.assertIn("CSS escape", output)

    def test_active_data_css_dependency_requires_review(self):
        site = self.copied_site()
        path = site / "lib" / "contents.css"
        path.write_text(path.read_text(encoding="utf-8") +
                        '\n@import "data:text/css,body%7Bcolor:red%7D";\n', encoding="utf-8")
        status, output, _ = self.run_main(site)
        self.assertEqual(status, 1, output)
        self.assertIn("active data", output)

    def test_data_image_css_dependency_is_allowed(self):
        site = self.copied_site()
        path = site / "lib" / "contents.css"
        path.write_text(path.read_text(encoding="utf-8") +
                        '\n.x { background: url("data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///ywAAAAAAQABAAACAUwAOw=="); }\n',
                        encoding="utf-8")
        status, output, _ = self.run_main(site)
        self.assertEqual(status, 0, output)

    def test_probe_forces_mp3_and_blocks_remote_protocols(self):
        payload = {"format": {"duration": "1.0"}, "streams": [
            {"codec_name": "mp3", "sample_rate": "44100", "channels": 2}
        ]}
        with patch.object(delivery.subprocess, "check_output", return_value=json.dumps(payload)) as run:
            delivery.probe(Path("clip.mp3"))
        args = run.call_args.args[0]
        self.assertIn("-f", args)
        self.assertEqual(args[args.index("-f") + 1], "mp3")
        self.assertIn("-protocol_whitelist", args)
        self.assertEqual(args[args.index("-protocol_whitelist") + 1], "file,pipe")

    def test_probe_rejects_multiple_streams(self):
        payload = {"format": {"duration": "1.0"}, "streams": [
            {"codec_name": "mp3", "sample_rate": "44100", "channels": 2},
            {"codec_name": "mp3", "sample_rate": "44100", "channels": 2},
        ]}
        with patch.object(delivery.subprocess, "check_output", return_value=json.dumps(payload)):
            with self.assertRaisesRegex(ValueError, "exactly one audio stream"):
                delivery.probe(Path("clip.mp3"))

    def test_dynamic_script_allowlist_requires_volume(self):
        site = self.copied_site()
        path = site / "lib" / "network.js"
        path.write_text(path.read_text(encoding="utf-8") +
                        "\nObject.assign(document.createElement('script'), { src: new URL('contents.js', document.currentScript.src) });\n",
                        encoding="utf-8")
        status, output, _ = self.run_main(site)
        self.assertEqual(status, 1, output)
        self.assertIn("runtime dependency mechanism", output)

    def test_uppercase_dynamic_script_is_rejected(self):
        site = self.copied_site()
        path = site / "lib" / "network.js"
        path.write_text(path.read_text(encoding="utf-8") +
                        "\nObject.assign(document.createElement('SCRIPT'), { src: runtimeTarget });\n",
                        encoding="utf-8")
        status, output, _ = self.run_main(site)
        self.assertEqual(status, 1, output)
        self.assertIn("runtime dependency mechanism", output)

    def test_bracket_fetch_is_rejected(self):
        site = self.copied_site()
        path = site / "lib" / "network.js"
        path.write_text(path.read_text(encoding="utf-8") + '\nwindow["fetch"](runtimeTarget);\n', encoding="utf-8")
        status, output, _ = self.run_main(site)
        self.assertEqual(status, 1, output)
        self.assertIn("runtime dependency mechanism", output)

    def test_static_import_is_rejected(self):
        site = self.copied_site()
        path = site / "lib" / "network.js"
        path.write_text(path.read_text(encoding="utf-8") + '\nimport value from "runtime-target";\n', encoding="utf-8")
        status, output, _ = self.run_main(site)
        self.assertEqual(status, 1, output)
        self.assertIn("runtime dependency mechanism", output)

    def test_inline_style_block_dependency_is_checked(self):
        site = self.copied_site()
        path = site / "ch01" / "index.html"
        path.write_text(path.read_text(encoding="utf-8") +
                        '\n<style>.x { background: url("missing.png"); }</style>\n', encoding="utf-8")
        status, output, _ = self.run_main(site)
        self.assertEqual(status, 1, output)
        self.assertIn("missing.png", output)

    def test_inline_style_attribute_dependency_is_checked(self):
        site = self.copied_site()
        path = site / "ch01" / "index.html"
        path.write_text(path.read_text(encoding="utf-8") +
                        '\n<div style="background: url(missing.png)"></div>\n', encoding="utf-8")
        status, output, _ = self.run_main(site)
        self.assertEqual(status, 1, output)
        self.assertIn("missing.png", output)

    def test_srcset_dependency_is_checked(self):
        site = self.copied_site()
        path = site / "ch01" / "index.html"
        path.write_text(path.read_text(encoding="utf-8") +
                        '\n<img src="../lib/book.css" srcset="missing.png 1x">\n', encoding="utf-8")
        status, output, _ = self.run_main(site)
        self.assertEqual(status, 1, output)
        self.assertIn("missing.png", output)

    def test_object_data_dependency_is_checked(self):
        site = self.copied_site()
        path = site / "ch01" / "index.html"
        path.write_text(path.read_text(encoding="utf-8") +
                        '\n<object data="missing.svg"></object>\n', encoding="utf-8")
        status, output, _ = self.run_main(site)
        self.assertEqual(status, 1, output)
        self.assertIn("missing.svg", output)

    def test_svg_xlink_dependency_is_checked(self):
        site = self.copied_site()
        path = site / "ch01" / "index.html"
        path.write_text(path.read_text(encoding="utf-8") +
                        '\n<svg><a xlink:href="missing.svg"></a></svg>\n', encoding="utf-8")
        status, output, _ = self.run_main(site)
        self.assertEqual(status, 1, output)
        self.assertIn("missing.svg", output)

    def test_inline_script_runtime_dependency_is_checked(self):
        site = self.copied_site()
        path = site / "ch01" / "index.html"
        path.write_text(path.read_text(encoding="utf-8") +
                        '\n<script>fetch(runtimeTarget);</script>\n', encoding="utf-8")
        status, output, _ = self.run_main(site)
        self.assertEqual(status, 1, output)
        self.assertIn("dynamic fetch", output)

    def test_inline_event_handler_runtime_dependency_is_checked(self):
        site = self.copied_site()
        path = site / "ch01" / "index.html"
        path.write_text(path.read_text(encoding="utf-8") +
                        '\n<button onclick="navigator.sendBeacon(runtimeTarget)">x</button>\n', encoding="utf-8")
        status, output, _ = self.run_main(site)
        self.assertEqual(status, 1, output)
        self.assertIn("runtime dependency mechanism", output)

    def test_all_image_set_candidates_are_checked(self):
        site = self.copied_site()
        path = site / "lib" / "contents.css"
        path.write_text(path.read_text(encoding="utf-8") +
                        '\n.x { background-image: image-set("volume.css" 1x, "missing.svg" 2x); }\n', encoding="utf-8")
        status, output, _ = self.run_main(site)
        self.assertEqual(status, 1, output)
        self.assertIn("missing.svg", output)

    def test_css_comment_inside_unquoted_url_is_preserved(self):
        site = self.copied_site()
        path = site / "lib" / "contents.css"
        path.write_text(path.read_text(encoding="utf-8") +
                        '\n.x { background: url(missing/*comment*/.png); }\n', encoding="utf-8")
        status, output, _ = self.run_main(site)
        self.assertEqual(status, 1, output)
        self.assertIn("missing/*comment*/.png", output)
        self.assertNotIn("missing/.png", output)

    def test_site_root_relative_reference_resolves_inside_site(self):
        site = self.copied_site()
        path = site / "ch01" / "index.html"
        path.write_text(path.read_text(encoding="utf-8") +
                        '\n<link rel="stylesheet" href="/lib/book.css">\n', encoding="utf-8")
        status, output, _ = self.run_main(site)
        self.assertEqual(status, 0, output)

    def test_aborted_audio_audit_replaces_stale_pass_evidence(self):
        site = self.copied_site()
        output = site.parent / "delivery.json"
        output.write_text('{"passed": true}\n', encoding="utf-8")
        with patch.object(delivery, "SITE", site), \
                patch.object(delivery, "audio", side_effect=ValueError("broken clip")), \
                patch.object(sys, "argv", ["verify_delivery.py", "--out", str(output)]), \
                contextlib.redirect_stdout(io.StringIO()):
            try:
                status = delivery.main()
            except ValueError:
                self.fail("audio audit aborted without replacing stale evidence")
        self.assertEqual(status, 1)
        evidence = json.loads(output.read_text(encoding="utf-8"))
        self.assertFalse(evidence["passed"])
        self.assertIn("broken clip", " ".join(evidence["errors"]))

    def test_active_data_script_is_rejected(self):
        site = self.copied_site()
        path = site / "ch01" / "index.html"
        path.write_text(path.read_text(encoding="utf-8") +
                        '\n<script src="data:text/javascript,fetch(runtimeTarget)"></script>\n', encoding="utf-8")
        status, output, _ = self.run_main(site)
        self.assertEqual(status, 1, output)
        self.assertIn("active data", output)

    def test_iframe_srcdoc_is_rejected(self):
        site = self.copied_site()
        path = site / "ch01" / "index.html"
        path.write_text(path.read_text(encoding="utf-8") +
                        '\n<iframe srcdoc="<script>fetch(runtimeTarget)</script>"></iframe>\n', encoding="utf-8")
        status, output, _ = self.run_main(site)
        self.assertEqual(status, 1, output)
        self.assertIn("srcdoc", output)

    def test_base_element_is_rejected(self):
        site = self.copied_site()
        path = site / "ch01" / "index.html"
        path.write_text(path.read_text(encoding="utf-8") +
                        '\n<base href="/ch01/index.html">\n', encoding="utf-8")
        status, output, _ = self.run_main(site)
        self.assertEqual(status, 1, output)
        self.assertIn("base", output)

    def test_data_first_srcset_still_checks_later_candidates(self):
        site = self.copied_site()
        path = site / "ch01" / "index.html"
        path.write_text(path.read_text(encoding="utf-8") +
                        '\n<img src="../lib/book.css" srcset="data:image/gif;base64,R0lGODlhAQABAAAAACw= 1x, missing.png 2x">\n',
                        encoding="utf-8")
        status, output, _ = self.run_main(site)
        self.assertEqual(status, 1, output)
        self.assertIn("missing.png", output)

    def test_regex_literal_does_not_hide_runtime_dependency(self):
        site = self.copied_site()
        path = site / "lib" / "network.js"
        path.write_text(path.read_text(encoding="utf-8") +
                        '\nconst re = /[/*]/; fetch(runtimeTarget);\n', encoding="utf-8")
        status, output, _ = self.run_main(site)
        self.assertEqual(status, 1, output)
        self.assertIn("dynamic fetch", output)

    def test_carriage_return_does_not_hide_runtime_dependency(self):
        site = self.copied_site()
        path = site / "lib" / "network.js"
        path.write_text(path.read_text(encoding="utf-8") +
                        '\n// comment\rfetch(runtimeTarget);\n', encoding="utf-8")
        status, output, _ = self.run_main(site)
        self.assertEqual(status, 1, output)
        self.assertIn("dynamic fetch", output)

    def test_reexport_is_rejected(self):
        site = self.copied_site()
        path = site / "lib" / "network.js"
        path.write_text(path.read_text(encoding="utf-8") +
                        '\nexport * from "runtime-target";\n', encoding="utf-8")
        status, output, _ = self.run_main(site)
        self.assertEqual(status, 1, output)
        self.assertIn("runtime dependency mechanism", output)

    def test_compact_reexport_forms_are_rejected(self):
        site = self.copied_site()
        path = site / "lib" / "network.js"
        original = path.read_text(encoding="utf-8")
        for statement in ('export*from"runtime-target";', 'export{foo}from"runtime-target";'):
            with self.subTest(statement=statement):
                path.write_text(original + "\n" + statement + "\n", encoding="utf-8")
                status, output, _ = self.run_main(site)
                self.assertEqual(status, 1, output)
                self.assertIn("runtime dependency mechanism", output)

    def test_external_script_fetch_uses_document_base(self):
        site = self.copied_site()
        path = site / "lib" / "network.js"
        path.write_text(path.read_text(encoding="utf-8") + '\nfetch("contents.css");\n', encoding="utf-8")
        status, output, _ = self.run_main(site)
        self.assertEqual(status, 1, output)
        self.assertIn("missing runtime fetch target", output)

    def test_nested_chapter_script_fetch_uses_document_base(self):
        site = self.copied_site()
        folder = site / "ch01" / "assets"
        folder.mkdir()
        (folder / "payload.js").write_text("", encoding="utf-8")
        path = folder / "network.js"
        path.write_text('fetch("payload.js");\n', encoding="utf-8")
        status, output, _ = self.run_main(site)
        self.assertEqual(status, 1, output)
        self.assertIn("missing runtime fetch target", output)

    def test_unreviewed_script_location_fetch_fails_closed(self):
        site = self.copied_site()
        folder = site / "assets"
        folder.mkdir()
        (folder / "payload.js").write_text("", encoding="utf-8")
        (folder / "network.js").write_text('fetch("payload.js");\n', encoding="utf-8")
        status, output, _ = self.run_main(site)
        self.assertEqual(status, 1, output)
        self.assertIn("no reviewed document base", output)

    def test_standalone_svg_dependency_is_checked(self):
        site = self.copied_site()
        (site / "linked.svg").write_text(
            '<svg xmlns="http://www.w3.org/2000/svg"><a href="missing.svg"/></svg>\n',
            encoding="utf-8",
        )
        status, output, _ = self.run_main(site)
        self.assertEqual(status, 1, output)
        self.assertIn("missing.svg", output)

    def test_quoted_css_escape_requires_review(self):
        site = self.copied_site()
        path = site / "lib" / "contents.css"
        path.write_text(path.read_text(encoding="utf-8") +
                        '\n.x { background: url("foo\\qbar.png"); }\n', encoding="utf-8")
        status, output, _ = self.run_main(site)
        self.assertEqual(status, 1, output)
        self.assertIn("CSS escape", output)

    def test_import_url_occurrence_is_counted_once(self):
        site = self.copied_site()
        status, output, evidence = self.run_main(site)
        self.assertEqual(status, 0, output)
        refs = json.loads(evidence.read_text(encoding="utf-8"))["html_and_css_references"]
        rows = [row for row in refs if row["source"].endswith("lib/engine.css")
                and row["target"] in {"volume.css", "book.css"}]
        self.assertEqual(len(rows), 2)
        self.assertTrue(all(row["occurrences"] == 1 for row in rows))

    def test_non_audio_exception_replaces_stale_pass_evidence(self):
        site = self.copied_site()
        (site / "lib" / "network.js").write_bytes(b"\xff")
        output = site.parent / "delivery.json"
        output.write_text('{"passed": true}\n', encoding="utf-8")
        with patch.object(delivery, "SITE", site), \
                patch.object(sys, "argv", ["verify_delivery.py", "--out", str(output)]), \
                contextlib.redirect_stdout(io.StringIO()):
            try:
                status = delivery.main()
            except UnicodeDecodeError:
                self.fail("audit aborted without replacing stale evidence")
        self.assertEqual(status, 1)
        evidence = json.loads(output.read_text(encoding="utf-8"))
        self.assertFalse(evidence["passed"])
        self.assertIn("audit aborted", " ".join(evidence["errors"]))

    def test_reference_records_are_unique(self):
        site = self.copied_site()
        path = site / "lib" / "contents.css"
        path.write_text(path.read_text(encoding="utf-8") +
                        '\n.x { background: url("volume.css"); }\n.y { background: url("volume.css"); }\n',
                        encoding="utf-8")
        status, output, evidence = self.run_main(site)
        self.assertEqual(status, 0, output)
        refs = json.loads(evidence.read_text(encoding="utf-8"))["html_and_css_references"]
        keys = {(row["source"], row["target"]) for row in refs}
        self.assertEqual(len(keys), len(refs))
        row = next(row for row in refs if row["source"].endswith("lib/contents.css")
                   and row["target"] == "volume.css")
        self.assertEqual(row["occurrences"], 2)


if __name__ == "__main__":
    unittest.main()
