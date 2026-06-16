#!/usr/bin/env python3
"""Terminal summary of mexc_trading_app connection + bot perf feeds."""

from __future__ import annotations

import argparse
import json
import os
import sys

from util_smoke_http import get_json, print_header


def _fmt_bool(value: object) -> str:
    return "OK" if value else "FAIL"


def main() -> int:
    parser = argparse.ArgumentParser(description="MEXC trading app feed health")
    parser.add_argument(
        "--base-url",
        default=os.environ.get("MEXC_TRADING_URL", "http://127.0.0.1:8005"),
    )
    parser.add_argument("--json", action="store_true")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit 1 when any core feed flag is false",
    )
    args = parser.parse_args()
    base = args.base_url.rstrip("/")
    failures = 0

    print_header("/api/status")
    status, code, raw = get_json(f"{base}/api/status")
    if status is None:
        print(f"  FAIL HTTP {code}: {raw}")
        return 1
    feeds = {
        "trades_feed": status.get("trades_feed"),
        "account_feed": status.get("account_feed"),
        "order_book_feed": status.get("order_book_feed"),
        "api_access": status.get("api_access"),
    }
    for key, ok in feeds.items():
        mark = _fmt_bool(ok)
        print(f"  {key}: {mark}")
        if args.strict and not ok:
            failures += 1
    print(
        f"  reconnect_count={status.get('reconnect_count')} "
        f"messages={status.get('messages_received')} "
        f"listen_key_expires={status.get('listen_key_expires')}"
    )
    if args.json:
        print(json.dumps(status, indent=2)[:3000])

    print_header("/api/bot/perf")
    perf_body, code2, raw2 = get_json(f"{base}/api/bot/perf")
    if perf_body is None:
        print(f"  FAIL HTTP {code2}: {raw2}")
        failures += 1
    else:
        perf = (perf_body.get("perf") or {}).get("metrics") or {}
        if perf:
            for name, stats in sorted(perf.items()):
                if isinstance(stats, dict):
                    print(
                        f"  {name}: p50={stats.get('p50_ms')} "
                        f"p95={stats.get('p95_ms')} n={stats.get('count')}"
                    )
                else:
                    print(f"  {name}: {stats}")
        else:
            print(f"  status={perf_body.get('status')} (no perf metrics)")
        if args.json and perf_body:
            print(json.dumps(perf_body, indent=2)[:3000])

    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
