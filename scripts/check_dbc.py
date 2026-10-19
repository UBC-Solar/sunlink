#!/usr/bin/env python3
"""
Validate DBC files so broken CAN definitions can't be merged.

Usage: python scripts/check_dbc.py [path/to/file.dbc ...]   (defaults to dbc/*.dbc)

Fails on:
  - DBC syntax errors
  - signals that don't fit in their message's byte length (DLC)
  - signals that overlap each other within a message
  - duplicate CAN frame IDs
Warns on:
  - duplicate message names
"""
import os
import sys
import logging
from collections import defaultdict
from pathlib import Path

import cantools

# cantools reports duplicates through logging; we check for them ourselves below
logging.getLogger("cantools").setLevel(logging.ERROR)

IN_CI = bool(os.environ.get("GITHUB_ACTIONS"))


def annotate(level, path, msg):
    # GitHub Actions annotation so the error shows up inline on the PR
    if IN_CI:
        print(f"::{level} file={path}::{msg}")
    else:
        print(f"{level.upper()}: {path}: {msg}")


def check_file(path):
    try:
        # strict=True (default) rejects overlapping signals and signals outside the DLC
        db = cantools.database.load_file(str(path), strict=True)
    except Exception as e:
        annotate("error", path, f"{type(e).__name__}: {e}")
        return False

    ok = True

    by_id = defaultdict(list)
    by_name = defaultdict(list)
    for m in db.messages:
        by_id[m.frame_id].append(m.name)
        by_name[m.name].append(m.frame_id)

    for frame_id, names in by_id.items():
        if len(names) > 1:
            annotate("error", path, f"Duplicate frame ID {frame_id} (0x{frame_id:X}) used by: {', '.join(names)}")
            ok = False

    for name, ids in by_name.items():
        if len(ids) > 1:
            annotate("warning", path, f"Duplicate message name '{name}' used by IDs: {', '.join(map(str, ids))}")

    if ok:
        print(f"OK: {path} ({len(db.messages)} messages)")
    return ok


def main():
    paths = [Path(p) for p in sys.argv[1:]] or sorted(Path("dbc").glob("*.dbc"))
    if not paths:
        print("No DBC files found")
        return 1
    results = [check_file(p) for p in paths]
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
