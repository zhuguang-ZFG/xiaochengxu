#!/usr/bin/env python3
"""Verify the pinned Papermorph Skill and engine trees against provenance.json."""
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
TREES = (
    ("skill_tree_sha256", Path(".qoder/skills/papermorph")),
    ("engine_tree_sha256", Path("engine")),
)
TEXT_SUFFIXES = frozenset({".css", ".html", ".js", ".json", ".md", ".py", ".txt"})
TEXT_NAMES = frozenset({"LICENSE"})


def tree_hash(path):
    """Hash files in POSIX path order, normalizing line endings only for known text files."""
    digest = hashlib.sha256()
    for file in sorted((p for p in path.rglob("*") if p.is_file()), key=lambda p: p.relative_to(path).as_posix()):
        digest.update(file.relative_to(path).as_posix().encode("utf-8"))
        digest.update(b"\0")
        data = file.read_bytes()
        if (file.suffix.lower() in TEXT_SUFFIXES or file.name in TEXT_NAMES) and b"\0" not in data:
            data = data.replace(b"\r\n", b"\n")
        digest.update(data)
        digest.update(b"\0")
    return digest.hexdigest()


def verify(root, record):
    errors = []
    for key, relative in TREES:
        path = root / relative
        if not path.is_dir():
            errors.append(f"{relative.as_posix()}: missing tree")
            continue
        actual = tree_hash(path)
        if actual != record.get(key):
            errors.append(f"{relative.as_posix()}: {key} mismatch (expected {record.get(key)}, got {actual})")
    return errors


def main():
    record = json.loads((ROOT / "provenance.json").read_text(encoding="utf-8"))
    errors = verify(ROOT, record)
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    counts = [sum(1 for p in (ROOT / relative).rglob("*") if p.is_file()) for _, relative in TREES]
    print(f"provenance: OK ({counts[0]} Skill files, {counts[1]} engine files)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
