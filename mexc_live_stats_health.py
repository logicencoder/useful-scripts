#!/usr/bin/env python3
"""Health bundle for mexc-live-stats-backend (mexc_td_app)."""

from __future__ import annotations

import argparse
import json
import os
import sys

from util_smoke_http import get_json, print_header


def main() -> int:
    parser = argparse.ArgumentParser(description="MEXC live stats health smoke")
    parser.add_argument(
        "--base-url",
        default=os.environ.get("MEXC_TD_URL", "http://127.0.0.1:8080"),
    )
    parser.add_argument(
        "--fail-on-dead",
        action="store_true",
        help="Exit 1 when /api/dead-symbols reports dead symbols",
    )
    args = parser.parse_args()
    base = args.base_url.rstrip("/")
    failures = 0

    for path in ("/api/monitoring", "/api/dead-symbols"):
        print_header(path)
        data, code, raw = get_json(f"{base}{path}")
        if data is None:
            print(f"  FAIL HTTP {code}: {raw}")
            failures += 1
            continue
        print(f"  OK HTTP {code}")
        print(json.dumps(data, indent=2)[:2000])

        if path == "/api/dead-symbols" and args.fail_on_dead:
            dead = data.get("dead") or []
            if data.get("ready") and dead:
                print(f"  WARN dead symbols: {len(dead)}")
                failures += 1

    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
