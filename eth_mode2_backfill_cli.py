#!/usr/bin/env python3
"""Mode 2 status from eth-chain-swaps-monitor + optional proof log tail."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from util_smoke_http import get_json, print_header


def tail_proof(path: Path, lines: int) -> None:
    if not path.is_file():
        print(f"Proof log not found: {path}")
        return
    rows = path.read_text(encoding="utf-8", errors="replace").splitlines()
    print_header(f"tail {path} ({lines} lines)")
    for line in rows[-lines:]:
        print(line[:500])


def main() -> int:
    parser = argparse.ArgumentParser(description="ETH swap monitor Mode 2 status")
    parser.add_argument(
        "--base-url",
        default=os.environ.get("ETH_SWAP_MONITOR_URL", "http://127.0.0.1:8059"),
    )
    parser.add_argument(
        "--proof-log",
        default=os.environ.get("ETH_MODE2_PROOF_LOG", ""),
        help="Path to mode2_proof_log.jsonl on disk",
    )
    parser.add_argument("--tail", type=int, default=0, help="Tail N proof log lines")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    base = args.base_url.rstrip("/")

    print_header("GET /api/mode")
    mode, code, raw = get_json(f"{base}/api/mode")
    if mode is None:
        print(f"FAIL HTTP {code}: {raw}")
        return 1
    print(json.dumps(mode, indent=2)[:1200])

    print_header("GET /api/stats (mode2 counters)")
    stats, code2, raw2 = get_json(f"{base}/api/stats")
    if stats is None:
        print(f"FAIL HTTP {code2}: {raw2}")
        return 1

    mode2_keys = sorted(k for k in stats.keys() if str(k).startswith("mode2"))
    subset = {k: stats[k] for k in mode2_keys}
    subset["watched_wallets"] = stats.get("watched_wallets")
    subset["mode"] = stats.get("mode")
    print(json.dumps(subset, indent=2)[:3000])
    if args.json:
        print(json.dumps(stats, indent=2)[:8000])

    if args.tail > 0:
        proof = Path(args.proof_log).expanduser() if args.proof_log else Path("mode2_proof_log.jsonl")
        tail_proof(proof, args.tail)

    print("\nNOTE: Mode 2 backfill runs on monitor process:")
    print("  python3 eth_chain_swaps_monitor.py --mode2-backfill-blocks N [--mode2-backfill-only]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
