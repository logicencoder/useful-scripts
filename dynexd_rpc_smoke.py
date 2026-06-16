#!/usr/bin/env python3
"""Dynex daemon JSON-RPC smoke (getinfo + block height)."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time

try:
    import requests
except ImportError:
    requests = None


def main() -> int:
    parser = argparse.ArgumentParser(description="Dynexd RPC smoke")
    parser.add_argument(
        "--url",
        default=os.environ.get("DYNEX_NODE_URL", "http://127.0.0.1:18333"),
    )
    parser.add_argument("--timeout", type=float, default=10.0)
    args = parser.parse_args()
    if requests is None:
        print("pip install requests", file=sys.stderr)
        return 2

    base = args.url.rstrip("/")
    failures = 0

    print("=== GET /getinfo ===")
    try:
        t0 = time.time()
        r = requests.get(f"{base}/getinfo", timeout=args.timeout)
        ms = (time.time() - t0) * 1000
        r.raise_for_status()
        info = r.json()
        height = info.get("height")
        print(f"  OK height={height} ({ms:.0f} ms)")
    except Exception as exc:
        print(f"  FAIL: {exc}")
        failures += 1
        height = None

    print("=== POST getblockbyheight (tip) ===")
    if height is not None:
        try:
            payload = {
                "jsonrpc": "2.0",
                "id": "1",
                "method": "getblockbyheight",
                "params": {"blockHeight": int(height) - 1},
            }
            t0 = time.time()
            r = requests.post(
                f"{base}/json_rpc",
                json=payload,
                timeout=args.timeout,
                headers={"Content-Type": "application/json"},
            )
            ms = (time.time() - t0) * 1000
            r.raise_for_status()
            block = r.json().get("result", {}).get("block", {})
            print(f"  OK block index={block.get('index')} ({ms:.0f} ms)")
        except Exception as exc:
            print(f"  FAIL: {exc}")
            failures += 1

    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
