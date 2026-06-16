#!/usr/bin/env python3
"""GET /api/reload_coins on multi-coin-monitor and poll /api/stats."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time

from util_smoke_http import get_json, print_header


def main() -> int:
    parser = argparse.ArgumentParser(description="Multi-coin monitor reload CLI")
    parser.add_argument(
        "--base-url",
        default=os.environ.get("MULTICOIN_URL", "http://127.0.0.1:8765"),
    )
    parser.add_argument("--wait-seconds", type=float, default=20.0)
    args = parser.parse_args()
    base = args.base_url.rstrip("/")

    print_header("Before /api/stats")
    before, _, _ = get_json(f"{base}/api/stats")
    if before:
        print(json.dumps(before, indent=2)[:1500])

    print_header("GET /api/reload_coins")
    data, code, raw = get_json(f"{base}/api/reload_coins")
    if data is None and code not in (200, 201):
        print(f"FAIL reload HTTP {code}: {raw}")
        return 1
    print(f"OK reload HTTP {code}")
    if data:
        print(json.dumps(data, indent=2)[:1500])

    deadline = time.time() + args.wait_seconds
    print_header("Polling /api/stats")
    last = None
    while time.time() < deadline:
        snap, _, _ = get_json(f"{base}/api/stats")
        if snap:
            last = snap
            print(
                f"  total_coins={snap.get('total_coins')} "
                f"connections={snap.get('active_connections')} "
                f"messages={snap.get('total_messages')}"
            )
        time.sleep(2)

    print_header("After")
    if last:
        print(json.dumps(last, indent=2)[:2000])
    return 0


if __name__ == "__main__":
    sys.exit(main())
