#!/usr/bin/env python3
"""Smoke bundle for dnx-swap-webapp FastAPI (:8024 default)."""

from __future__ import annotations

import argparse
import json
import os
import sys

from util_smoke_http import get_json, print_header, tcp_open


def main() -> int:
    parser = argparse.ArgumentParser(description="DNX swap webapp smoke")
    parser.add_argument(
        "--base-url",
        default=os.environ.get("DNX_SWAP_URL", "http://127.0.0.1:8024"),
    )
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()
    base = args.base_url.rstrip("/")
    host = base.split("://", 1)[-1].split("/")[0]
    host_part, _, port_str = host.partition(":")
    port = int(port_str or "8024")
    failures = 0

    print_header("TCP")
    ok, msg = tcp_open(host_part, port)
    print(f"  {'OK' if ok else 'FAIL'} {host_part}:{port} ({msg})")
    if not ok:
        return 1

    for path in ("/api/status", "/api/nonce_status", "/api/config"):
        print_header(path)
        data, code, raw = get_json(f"{base}{path}")
        if data is None:
            print(f"  FAIL HTTP {code}: {raw}")
            failures += 1
            continue
        print(f"  OK HTTP {code}")
        print(json.dumps(data, indent=2)[:1500])

    print_header("POST /api/check_node_health")
    data, code, raw = get_json(f"{base}/api/check_node_health", method="POST", body=b"{}")
    if data is None and code not in (200, 201):
        print(f"  FAIL HTTP {code}: {raw}")
        failures += 1
    else:
        print(f"  OK HTTP {code}")
        if data:
            print(json.dumps(data, indent=2)[:1200])
            if args.strict and not data.get("success", True):
                failures += 1

    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
