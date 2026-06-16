#!/usr/bin/env python3
"""POST /api/reload-symbols and poll monitoring until stable."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time

from util_smoke_http import get_json, print_header


def main() -> int:
    parser = argparse.ArgumentParser(description="MEXC live stats symbol reload")
    parser.add_argument(
        "--base-url",
        default=os.environ.get("MEXC_TD_URL", "http://127.0.0.1:8080"),
    )
    parser.add_argument("--wait-seconds", type=float, default=15.0)
    args = parser.parse_args()
    base = args.base_url.rstrip("/")

    print_header("Before")
    before, _, _ = get_json(f"{base}/api/monitoring")
    if before:
        print(json.dumps(before.get("server", before), indent=2))

    print_header("Reload")
    data, code, raw = get_json(f"{base}/api/reload-symbols", method="POST")
    if data is None and code not in (200, 201):
        print(f"FAIL reload HTTP {code}: {raw}")
        return 1
    print(f"OK reload HTTP {code}")
    if data:
        print(json.dumps(data, indent=2)[:1500])

    deadline = time.time() + args.wait_seconds
    print_header("Polling /api/monitoring")
    last = None
    while time.time() < deadline:
        snap, _, _ = get_json(f"{base}/api/monitoring")
        if snap:
            last = snap
            server = snap.get("server", {})
            print(
                f"  active_symbols={server.get('active_symbols')} "
                f"clients={server.get('connected_clients')}"
            )
        time.sleep(2)

    print_header("After")
    if last:
        print(json.dumps(last, indent=2)[:2000])
    return 0


if __name__ == "__main__":
    sys.exit(main())
