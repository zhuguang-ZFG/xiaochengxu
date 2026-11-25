#!/usr/bin/env python3
"""Audit the private static delivery: local references, audio decode/timings and a SHA-256 manifest.

    python tools/computer-networks/verify_delivery.py [--out tools/computer-networks/evidence/delivery.json]
"""
import argparse
from collections import Counter
from decimal import Decimal
from html.parser import HTMLParser
import hashlib
import json
import math
from pathlib import Path
import re
import subprocess
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[2]
SITE = ROOT / "site" / "computer-networks"
ALLOWED = {".html", ".js", ".css", ".mp3", ".svg"}
W3 = "http://www.w3.org/2000/svg"
ALLOWED_TEMPLATE_FETCHES = {"audio/sfx/${name}.mp3"}
SCRIPT_LOAD = re.compile(
    r"Object\.assign\s*\(\s*document\.createElement\s*\(\s*(['\"])script\1\s*\)\s*,"
    r"\s*\{\s*src\s*:\s*new\s+URL\s*\(\s*(['\"])(volume\.js)\2\s*,"
    r"\s*document\.currentScript\.src\s*\)\s*\}\s*\)",
    flags=re.S,
)


def srcset_urls(value):
    urls = []
    i = 0
    while i < len(value):
        while i < len(value) and (value[i].isspace() or value[i] == ","):
            i += 1
        start = i
        while i < len(value) and not value[i].isspace():
            i += 1
        url = value[start:i]
        if url.endswith(","):
            urls.append(url.rstrip(","))
            continue
        if not url:
            break
        urls.append(url)
        depth = 0
        while i < len(value):
            char = value[i]
            if char == "(":
                depth += 1
            elif char == ")" and depth:
                depth -= 1
            elif char == "," and not depth:
                i += 1
                break
            i += 1
    return urls


class References(HTMLParser):
    def __init__(self):
        super().__init__()
        self.refs = []
        self.inline_css = []
        self.inline_js = []
        self.forbidden = []
        self.style_depth = 0
        self.script_depth = 0

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag == "base":
            self.forbidden.append("base element changes URL resolution")
        for key, value in attrs:
            if key in {"src", "href", "xlink:href"} and value:
                if (tag == "link" and key == "href" and value.lower().startswith("data:image/")
                        and "icon" in values.get("rel", "").lower()):
                    continue
                self.refs.append((tag, key, value))
            elif tag == "object" and key == "data" and value:
                self.refs.append((tag, key, value))
            elif key == "srcset" and value:
                self.refs.extend((tag, key, url) for url in srcset_urls(value))
            elif key == "style" and value:
                self.inline_css.append(value)
            elif key.startswith("on") and value:
                self.inline_js.append(value)
            elif key == "srcdoc":
                self.forbidden.append("srcdoc embeds an unaudited active document")
        if tag == "style":
            self.style_depth += 1
        elif tag == "script" and not values.get("src"):
            self.script_depth += 1

    def handle_endtag(self, tag):
        if tag == "style":
            self.style_depth = max(0, self.style_depth - 1)
        elif tag == "script":
            self.script_depth = max(0, self.script_depth - 1)

    def handle_data(self, data):
        if self.style_depth:
            self.inline_css.append(data)
        elif self.script_depth:
            self.inline_js.append(data)


def local_target(source, value):
    parsed = urlsplit(value)
    if parsed.scheme or parsed.netloc:
        return None
    if not parsed.path:
        return source
    path = unquote(parsed.path)
    if path.startswith("/"):
        return (SITE / path.lstrip("/")).resolve()
    return (source.parent / path).resolve()


def css_without_comments(text):
    output = []
    i, quote = 0, None
    while i < len(text):
        char = text[i]
        if quote:
            output.append(char)
            if char == "\\" and i + 1 < len(text):
                i += 1
                output.append(text[i])
            elif char == quote:
                quote = None
        elif text.startswith("/*", i):
            end = text.find("*/", i + 2)
            i = len(text) if end < 0 else end + 2
            continue
        elif char in "\"'":
            quote = char
            output.append(char)
        else:
            output.append(char)
        i += 1
    return "".join(output)


def css_has_escape(text):
    return "\\" in text


def css_unquote(value):
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1]
    return value


def css_urls(text):
    values = []
    i = 0
    while i < len(text):
        if text.startswith("/*", i):
            end = text.find("*/", i + 2)
            i = len(text) if end < 0 else end + 2
            continue
        if text[i] in "\"'":
            quote = text[i]
            i += 1
            while i < len(text):
                if text[i] == "\\":
                    i += 2
                elif text[i] == quote:
                    i += 1
                    break
                else:
                    i += 1
            continue
        if text[i:i + 4].lower() != "url(":
            i += 1
            continue
        i += 4
        depth, quote, buffer = 1, None, []
        while i < len(text) and depth:
            char = text[i]
            if char == "\\":
                buffer.append(char)
                i += 1
                if i < len(text):
                    buffer.append(text[i])
            elif quote:
                buffer.append(char)
                if char == quote:
                    quote = None
            elif char in "\"'":
                quote = char
                buffer.append(char)
            elif char == "(":
                depth += 1
                buffer.append(char)
            elif char == ")":
                depth -= 1
                if depth:
                    buffer.append(char)
            else:
                buffer.append(char)
            i += 1
        value = "".join(buffer).strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        values.append(value)
    return values


def css_imports(text):
    pattern = r"@import\s+(?:\"([^\"]*)\"|'([^']*)')"
    return [css_unquote(next(value for value in match.groups() if value is not None))
            for match in re.finditer(pattern, text, flags=re.I)]


def css_image_sets(text):
    values = []
    i = 0
    while i < len(text):
        if text.startswith("/*", i):
            end = text.find("*/", i + 2)
            i = len(text) if end < 0 else end + 2
            continue
        if text[i] in "\"'":
            quote = text[i]
            i += 1
            while i < len(text):
                if text[i] == "\\":
                    i += 2
                elif text[i] == quote:
                    i += 1
                    break
                else:
                    i += 1
            continue
        if not re.match(r"(?:-webkit-)?image-set\(", text[i:], flags=re.I):
            i += 1
            continue
        i = text.find("(", i) + 1
        depth, quote = 1, None
        while i < len(text) and depth:
            char = text[i]
            if quote:
                if char == "\\":
                    i += 2
                    continue
                if char == quote:
                    quote = None
            elif char in "\"'":
                quote = char
                start = i + 1
                i += 1
                while i < len(text):
                    if text[i] == "\\":
                        i += 2
                        continue
                    if text[i] == quote:
                        break
                    i += 1
                if depth == 1 and i < len(text):
                    values.append(text[start:i])
                quote = None
            elif char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
            i += 1
    return values


def script_loads(text):
    targets = [match.group(3) for match in SCRIPT_LOAD.finditer(text)]
    remainder = SCRIPT_LOAD.sub("", text)
    unsafe = bool(re.search(
        r"\bcreateElement\s*\(\s*['\"](?:script|iframe|object|embed)\b",
        remainder,
        flags=re.I,
    ))
    return targets, unsafe


def runtime_bases(path):
    relative = path.relative_to(SITE)
    if len(relative.parts) == 1:
        return [SITE / "index.html"]
    chapter = relative.parts[0]
    if re.fullmatch(r"ch\d+", chapter):
        return [SITE / chapter / "index.html"]
    if chapter == "lib":
        return [SITE / ch / "index.html" for ch in ("ch01", "ch02", "ch03")]
    return []


def scan_js(path, rel, text):
    errors, fetches = [], []
    if re.search(
        r"\b(?:XMLHttpRequest|WebSocket|EventSource|Worker|SharedWorker|sendBeacon)\b|"
        r"\[\s*['\"](?:fetch|XMLHttpRequest|WebSocket|EventSource|Worker|SharedWorker|sendBeacon)['\"]\s*\]|"
        r"\bimport\b|\bexport\s*(?:\*|\{|default\b|const\b|let\b|var\b|function\b|class\b)|"
        r"\brequire\s*\(|\beval\s*\(|\bFunction\s*\(",
        text,
    ):
        errors.append(f"unreviewed runtime dependency mechanism: {rel}")
    targets, unsafe_script = script_loads(text)
    if unsafe_script:
        errors.append(f"unreviewed runtime dependency mechanism: {rel}")
    for value in targets:
        fetches.append({"source": rel, "kind": "script", "target": value})
        target = local_target(path, value)
        if target is None or not target.is_relative_to(SITE) or not target.is_file():
            errors.append(f"non-local or missing runtime script: {rel}: {value}")
    for match in re.finditer(r"\bfetch\s*(?:\?\.)?\s*\(", text):
        rest = text[match.end():]
        literal = re.match(r"\s*([`'\"])(.*?)\1", rest, flags=re.S)
        if not literal or not re.match(r"\s*(?:,|\))", rest[literal.end():], flags=re.S):
            errors.append(f"dynamic fetch requires a literal local target: {rel}")
            continue
        quote, value = literal.group(1), literal.group(2)
        if ((quote == "`" and value not in ALLOWED_TEMPLATE_FETCHES) or
                (quote != "`" and (not value or "\\" in value))):
            errors.append(f"dynamic fetch requires a literal local target: {rel}: {value}")
            continue
        fetches.append({"source": rel, "kind": "fetch", "target": value})
        bases = runtime_bases(path)
        if not bases:
            errors.append(f"runtime fetch has no reviewed document base: {rel}: {value}")
            continue
        targets = [local_target(base, value) for base in bases]
        if any(target is None or not target.is_relative_to(SITE) for target in targets):
            errors.append(f"non-local runtime fetch: {rel}: {value}")
        elif value not in ALLOWED_TEMPLATE_FETCHES and any(not target.is_file() for target in targets):
            errors.append(f"missing runtime fetch target: {rel}: {value}")
    return errors, fetches


def scan_css(path, rel, text, add_ref):
    errors = []
    if css_has_escape(text):
        errors.append(f"CSS escape requires review: {rel}")
    css = css_without_comments(text)
    dependencies = ([("css.import", value) for value in css_imports(css)] +
                    [("css.url", value) for value in css_urls(text)] +
                    [("css.image-set", value) for value in css_image_sets(css)])
    for attribute, value in dependencies:
        if value.lower().startswith("data:"):
            if value.lower().startswith("data:image/"):
                continue
            errors.append(f"active data reference requires review: {rel}: {value}")
            continue
        target = local_target(path, value)
        add_ref(rel, attribute, value)
        if target is None or not target.is_relative_to(SITE) or not target.is_file():
            errors.append(f"non-local or missing CSS reference: {rel}: {value}")
    return errors


def sha256(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def probe(path):
    raw = subprocess.check_output([
        "ffprobe", "-v", "error", "-protocol_whitelist", "file,pipe", "-f", "mp3",
        "-show_entries", "format=duration:stream=codec_name,sample_rate,channels",
        "-of", "json", str(path),
    ], text=True)
    value = json.loads(raw)
    streams = value.get("streams", [])
    if len(streams) != 1:
        raise ValueError(f"{path}: expected exactly one audio stream, found {len(streams)}")
    return value["format"]["duration"], streams[0]


def decode(path, stream, expected):
    run = subprocess.run([
        "ffmpeg", "-hide_banner", "-nostats", "-xerror", "-protocol_whitelist", "file,pipe",
        "-f", "mp3", "-i", str(path), "-map", "0:a:0", "-vn",
        "-af", "volumedetect", "-f", "s16le", "pipe:1",
    ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stderr = run.stderr.decode("utf-8", errors="replace")
    if run.returncode:
        raise ValueError(f"decode failed: {stderr.strip()}")
    sample_rate = int(stream["sample_rate"])
    sample_bytes = int(stream["channels"]) * 2
    if not run.stdout or len(run.stdout) % sample_bytes:
        raise ValueError("decoder produced no complete PCM frames")
    decoded = Decimal(len(run.stdout)) / Decimal(sample_rate * sample_bytes)
    if abs(decoded - expected) > Decimal(1) / Decimal(sample_rate):
        raise ValueError(f"decoded duration {decoded} != container duration {expected}")
    match = re.search(r"mean_volume:\s*(-?[\d.]+) dB", stderr)
    if not match:
        raise ValueError("decoder produced no mean-volume measurement")
    mean = float(match.group(1))
    if not math.isfinite(mean) or mean <= -70:
        raise ValueError(f"silent or invalid audio: mean volume {mean}")
    return mean


def audio(ch):
    folder = SITE / ch / "audio" / "zh"
    text = (folder / "timings.js").read_text(encoding="utf-8")
    timings = json.loads(text[text.index("{"):text.rindex("}") + 1], parse_float=Decimal)
    rows = []
    for beat, timing in timings.items():
        path = folder / f"{beat}.mp3"
        duration, stream = probe(path)
        measured = Decimal(duration)
        expected = Decimal(str(timing["dur"]))
        if measured != expected:
            raise ValueError(f"{path.relative_to(ROOT)}: MP3 {measured} != timing {expected}")
        points = list(timing["marks"].values()) + [cue[0] for cue in timing["cues"]]
        if any(not 0 <= point <= expected for point in points):
            raise ValueError(f"{path.relative_to(ROOT)}: cue or mark outside duration")
        if any(a[0] > b[0] for a, b in zip(timing["cues"], timing["cues"][1:])):
            raise ValueError(f"{path.relative_to(ROOT)}: cues are not chronological")
        if stream["codec_name"] != "mp3":
            raise ValueError(f"{path.relative_to(ROOT)}: unexpected codec {stream['codec_name']}")
        rows.append({"beat": beat, "duration": float(measured), "bytes": path.stat().st_size,
                     "mean_volume_db": decode(path, stream, measured), "sha256": sha256(path)})
    referenced = {row["beat"] for row in rows}
    present = {path.stem for path in folder.glob("*.mp3")}
    if referenced != set(timings) or present != referenced or len(rows) != 12:
        raise ValueError(f"{ch}: MP3 and timing beat sets differ or do not contain 12 clips")
    return {"clips": len(rows), "seconds": round(sum(row["duration"] for row in rows), 3),
            "bytes": sum(row["bytes"] for row in rows), "details": rows}


def audit(a):
    errors, refs, fetches = [], [], []
    ref_rows = {}

    def add_ref(source, attribute, target):
        key = (source, target)
        if key in ref_rows:
            ref_rows[key]["occurrences"] += 1
        else:
            row = {"source": source, "attribute": attribute, "target": target, "occurrences": 1}
            ref_rows[key] = row
            refs.append(row)

    files = sorted(path for path in SITE.rglob("*") if path.is_file())
    for path in files:
        rel = path.relative_to(ROOT).as_posix()
        if path.is_symlink() or path.suffix.lower() not in ALLOWED:
            errors.append(f"unsafe delivery entry: {rel}")
        if path.suffix.lower() not in {".html", ".css", ".js", ".svg"}:
            continue
        text = path.read_text(encoding="utf-8")
        for url in re.findall(r"https?://[^\s\"'`)]+", text, flags=re.I):
            if url.lower() != W3:
                errors.append(f"external URL literal: {rel}: {url}")
        if re.search(r"[\"'`]//[A-Za-z0-9]", text):
            errors.append(f"protocol-relative URL literal: {rel}")
        if path.suffix.lower() in {".html", ".svg"}:
            parser = References()
            parser.feed(text)
            errors.extend(f"forbidden markup in {rel}: {reason}" for reason in parser.forbidden)
            for tag, key, value in parser.refs:
                if value.startswith("#"):
                    continue
                if value.lower().startswith("data:"):
                    if ((tag in {"img", "source"} and key in {"src", "srcset"}) or
                            (tag == "image" and key in {"href", "xlink:href"})):
                        continue
                    errors.append(f"active data reference requires review: {rel}: {value}")
                    continue
                target = local_target(path, value)
                add_ref(rel, f"{tag}.{key}", value)
                if target is None or not target.is_relative_to(SITE) or not target.is_file():
                    errors.append(f"non-local or missing HTML/SVG reference: {rel}: {value}")
            for inline in parser.inline_css:
                errors.extend(scan_css(path, rel, inline, add_ref))
            for inline in parser.inline_js:
                inline_errors, inline_fetches = scan_js(path, rel, inline)
                errors.extend(inline_errors)
                fetches.extend(inline_fetches)
        elif path.suffix.lower() == ".css":
            errors.extend(scan_css(path, rel, text, add_ref))
        elif path.suffix.lower() == ".js":
            js_errors, js_fetches = scan_js(path, rel, text)
            errors.extend(js_errors)
            fetches.extend(js_fetches)
    chapters = {}
    for ch in ("ch01", "ch02", "ch03"):
        try:
            chapters[ch] = audio(ch)
        except Exception as exc:
            errors.append(f"{ch}: audio audit failed: {exc}")
            chapters[ch] = {"clips": 0, "seconds": 0.0, "bytes": 0,
                            "details": [], "error": str(exc)}
    counts = Counter(path.suffix.lower() for path in files)
    mp3_files = {path for path in files if path.suffix.lower() == ".mp3"}
    expected_mp3 = {
        SITE / ch / "audio" / "zh" / f"{row['beat']}.mp3"
        for ch, chapter in chapters.items() for row in chapter["details"]
    }
    if len(mp3_files) != 36 or mp3_files != expected_mp3:
        extras = sorted(path.relative_to(ROOT).as_posix() for path in mp3_files - expected_mp3)
        missing = sorted(path.relative_to(ROOT).as_posix() for path in expected_mp3 - mp3_files)
        errors.append(f"MP3 set must contain exactly the 36 audited clips; extra={extras}; missing={missing}")
    audio_bytes = sum(path.stat().st_size for path in mp3_files)
    static_bytes = sum(path.stat().st_size for path in files if path.suffix.lower() != ".mp3")
    total_bytes = sum(path.stat().st_size for path in files)
    if audio_bytes + static_bytes != total_bytes:
        errors.append("audio and static byte accounting does not equal total delivery size")
    result = {
        "site": SITE.relative_to(ROOT).as_posix(), "files": len(files),
        "bytes": total_bytes, "by_extension": dict(sorted(counts.items())),
        "audio_bytes": audio_bytes, "static_code_and_markup_bytes": static_bytes,
        "chapters": chapters,
        "html_and_css_references": refs, "runtime_fetches": fetches,
        "manifest": [{"path": path.relative_to(ROOT).as_posix(), "bytes": path.stat().st_size, "sha256": sha256(path)} for path in files],
        "errors": errors,
    }
    result["passed"] = not errors
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{len(files)} files, {result['bytes']} bytes; audio {audio_bytes} bytes; "
          f"narration {sum(row['seconds'] for row in chapters.values()):.2f} s")
    for ch, row in chapters.items():
        if "error" in row:
            print(f"{ch}: audio audit failed: {row['error']}")
        else:
            print(f"{ch}: {row['clips']} decoded MP3s, {row['seconds']:.2f} s, exact timing match")
    print(f"HTML/CSS local references: {len(refs)}; runtime loads: {len(fetches)}; errors: {len(errors)}")
    print(f"evidence: {a.out.relative_to(ROOT).as_posix()}")
    if errors:
        print("\n".join(errors))
    return 1 if errors else 0


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, default=ROOT / "tools/computer-networks/evidence/delivery.json")
    a = ap.parse_args()
    try:
        return audit(a)
    except Exception as exc:
        try:
            site = SITE.relative_to(ROOT).as_posix()
        except ValueError:
            site = str(SITE)
        result = {"site": site, "passed": False, "errors": [f"audit aborted: {exc}"]}
        a.out.parent.mkdir(parents=True, exist_ok=True)
        a.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"audit aborted: {exc}")
        print(f"evidence: {a.out}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
