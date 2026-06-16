#!/usr/bin/env python3
"""Smoke checklist for eth-chain-swaps-monitor HTTP API."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time

from util_smoke_http import get_json, print_header, tcp_open


def main() -> int:
    parser = argparse.ArgumentParser(description="ETH chain swaps monitor smoke")
    parser.add_argument(
        "--base-url",
        default=os.environ.get("ETH_SWAP_MONITOR_URL", "http://127.0.0.1:8059"),
    )
    parser.add_argument("--latency-loops", type=int, default=3)
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()
    base = args.base_url.rstrip("/")
    host = base.split("://", 1)[-1].split("/")[0]
    host_part, _, port_str = host.partition(":")
    port = int(port_str or ("443" if base.startswith("https") else "80"))
    failures = 0

    print_header("TCP")
    ok, msg = tcp_open(host_part, port)
    print(f"  {'OK' if ok else 'FAIL'} {host_part}:{port} ({msg})")
    if not ok:
        return 1

    print_header("GET /api/mode")
    mode, code, raw = get_json(f"{base}/api/mode")
    if mode is None:
        print(f"  FAIL HTTP {code}: {raw}")
        failures += 1
    else:
        print(
            f"  mode={mode.get('mode') or mode.get('active_mode')} "
            f"watched={mode.get('watched_wallets') or mode.get('wallet_count')}"
        )

    print_header("GET /api/stats")
    stats, code2, raw2 = get_json(f"{base}/api/stats")
    if stats is None:
        print(f"  FAIL HTTP {code2}: {raw2}")
        failures += 1
    else:
        top = stats.get("top_addresses") or []
        print(
            f"  watched_wallets={stats.get('watched_wallets')} "
            f"top_addresses={len(top)} mode={stats.get('mode')}"
        )
        if args.strict:
            if stats.get("watched_wallets") is None:
                failures += 1
            if not isinstance(top, list):
                failures += 1

    if args.latency_loops > 0 and stats is not None:
        print_header("/api/stats latency")
        for idx in range(args.latency_loops):
            t0 = time.perf_counter()
            body, code3, _ = get_json(f"{base}/api/stats")
            elapsed_ms = (time.perf_counter() - t0) * 1000
            size = len(json.dumps(body or {}))
            print(f"  loop {idx + 1}: {elapsed_ms:.0f}ms payload={size}B HTTP {code3}")

    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
