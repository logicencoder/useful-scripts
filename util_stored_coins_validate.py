#!/usr/bin/env python3
"""Validate stored_coins.json structure without importing arb engine."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

REQUIRED = ("mexc_pair", "token_symbol")


def load_rows(path: Path) -> list:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(raw, dict) and "coins" in raw:
        return raw["coins"]
    if isinstance(raw, list):
        return raw
    raise ValueError("Expected list or {coins: [...]}")


def main() -> int:
    parser = argparse.ArgumentParser(description="stored_coins.json validator")
    parser.add_argument(
        "--json",
        default=os.environ.get("MULTICOIN_COINS_JSON", ""),
    )
    parser.add_argument("--strict", action="store_true", help="Exit 1 on any issue")
    args = parser.parse_args()
    if not args.json:
        print("Set MULTICOIN_COINS_JSON or --json", file=sys.stderr)
        return 2

    path = Path(args.json).expanduser()
    if not path.is_file():
        print(f"Not found: {path}", file=sys.stderr)
        return 2

    rows = load_rows(path)
    enabled = 0
    issues = 0
    pairs: set[str] = set()

    for idx, row in enumerate(rows):
        if not isinstance(row, dict):
            print(f"row {idx}: not an object")
            issues += 1
            continue
        if not row.get("enabled", True):
            continue
        enabled += 1
        missing = [k for k in REQUIRED if not row.get(k)]
        if missing:
            print(f"row {idx}: missing {missing}")
            issues += 1
        pair = str(row.get("mexc_pair", ""))
        if pair in pairs:
            print(f"row {idx}: duplicate mexc_pair {pair}")
            issues += 1
        pairs.add(pair)

    print(f"file={path} total={len(rows)} enabled={enabled} unique_pairs={len(pairs)} issues={issues}")
    return 1 if issues and args.strict else 0


if __name__ == "__main__":
    sys.exit(main())
