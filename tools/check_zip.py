#!/usr/bin/env python3
"""Check that gpt-image.zip matches the gpt-image/ skill folder.

  python3 tools/check_zip.py          check (exit 1 on any problem)
  python3 tools/check_zip.py --build  rebuild gpt-image.zip from the folder, then check

Checks:
  - the zip holds exactly the files in gpt-image/ (minus .env, caches, OS files),
    under a single top-level gpt-image/ folder, with identical contents
  - SKILL.md has a frontmatter name matching the folder and a description
  - no .env file and no OpenAI key-like strings are in the zip

Standard library only.
"""

import argparse
import re
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILL_DIR = ROOT / "gpt-image"
ZIP_PATH = ROOT / "gpt-image.zip"

EXCLUDED_NAMES = {".env", ".DS_Store"}
EXCLUDED_DIRS = {"__pycache__"}
KEY_PATTERN = re.compile(rb"sk-[A-Za-z0-9_-]{20,}")
FIXED_DATE = (2026, 1, 1, 0, 0, 0)  # stable timestamps so rebuilds are byte-identical


def skill_files():
    """Map of archive name -> bytes for every file that belongs in the zip."""
    files = {}
    for path in sorted(SKILL_DIR.rglob("*")):
        rel = path.relative_to(ROOT)
        if not path.is_file():
            continue
        if path.name in EXCLUDED_NAMES or path.suffix == ".pyc":
            continue
        if EXCLUDED_DIRS.intersection(rel.parts):
            continue
        files[rel.as_posix()] = path.read_bytes()
    return files


def build():
    with zipfile.ZipFile(ZIP_PATH, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, data in skill_files().items():
            info = zipfile.ZipInfo(name, FIXED_DATE)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            zf.writestr(info, data)
    print(f"Built {ZIP_PATH.name}")


def check():
    problems = []
    if not ZIP_PATH.is_file():
        return [f"{ZIP_PATH.name} is missing"]

    expected = skill_files()
    with zipfile.ZipFile(ZIP_PATH) as zf:
        bad = zf.testzip()
        if bad:
            problems.append(f"corrupt entry in zip: {bad}")
        actual = {
            info.filename: zf.read(info)
            for info in zf.infolist()
            if not info.is_dir()
        }

    for name in actual:
        if not name.startswith(f"{SKILL_DIR.name}/"):
            problems.append(f"entry outside the {SKILL_DIR.name}/ folder: {name}")
        if Path(name).name == ".env":
            problems.append(f"zip contains a .env file: {name}")
        if KEY_PATTERN.search(actual[name]):
            problems.append(f"key-like string (sk-...) found in {name}")

    for name in sorted(expected.keys() - actual.keys()):
        problems.append(f"missing from zip: {name}")
    for name in sorted(actual.keys() - expected.keys()):
        problems.append(f"in zip but not in {SKILL_DIR.name}/: {name}")
    for name in sorted(expected.keys() & actual.keys()):
        if expected[name] != actual[name]:
            problems.append(f"outdated in zip (differs from {name})")

    skill_md = actual.get(f"{SKILL_DIR.name}/SKILL.md", b"").decode("utf-8", "replace")
    front = re.match(r"---\n(.*?)\n---\n", skill_md, re.S)
    if not front:
        problems.append("SKILL.md in zip has no YAML frontmatter")
    else:
        meta = dict(
            line.split(":", 1) for line in front.group(1).splitlines() if ":" in line
        )
        name = meta.get("name", "").strip()
        if name != SKILL_DIR.name:
            problems.append(f"SKILL.md name is '{name}', expected '{SKILL_DIR.name}'")
        if not meta.get("description", "").strip():
            problems.append("SKILL.md has no description")
    return problems


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--build", action="store_true", help="rebuild the zip first")
    args = parser.parse_args()
    if args.build:
        build()

    problems = check()
    if problems:
        print(f"{ZIP_PATH.name} does not match {SKILL_DIR.name}/:")
        for p in problems:
            print(f"  - {p}")
        print("Fix: python3 tools/check_zip.py --build, then commit gpt-image.zip")
        return 1
    print(f"{ZIP_PATH.name} OK ({len(skill_files())} files match {SKILL_DIR.name}/)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
