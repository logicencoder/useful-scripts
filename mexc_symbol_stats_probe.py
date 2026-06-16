#!/usr/bin/env python3
"""Probe /api/debug/symbol and /api/stats/memory for one MEXC live-stats symbol."""

from __future__ import annotations

import argparse
import json
import os
import sys

from util_smoke_http import get_json, print_header


def main() -> int:
    parser = argparse.ArgumentParser(description="MEXC live-stats per-symbol probe")
    parser.add_argument(
        "--base-url",
        default=os.environ.get("MEXC_TD_URL", "http://127.0.0.1:8080"),
    )
    parser.add_argument("--symbol", default=os.environ.get("MEXC_PROBE_SYMBOL", "DNXUSDT"))
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    base = args.base_url.rstrip("/")
    sym = args.symbol
    failures = 0

    print_header(f"/api/debug/symbol/{sym}")
    debug, code, raw = get_json(f"{base}/api/debug/symbol/{sym}")
    if debug is None:
        print(f"  FAIL HTTP {code}: {raw}")
        failures += 1
    else:
        print(json.dumps(debug, indent=2)[:2000])

    print_header(f"/api/stats/memory/{sym}")
    stats, code2, raw2 = get_json(f"{base}/api/stats/memory/{sym}")
    if stats is None:
        print(f"  FAIL HTTP {code2}: {raw2}")
        failures += 1
    else:
        if args.json:
            print(json.dumps(stats, indent=2)[:4000])
        else:
            keys = ("symbol", "last_price", "volume_24h", "trade_count", "high_24h", "low_24h")
            summary = {k: stats.get(k) for k in keys if k in stats}
            print(json.dumps(summary, indent=2)[:2000])

    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
