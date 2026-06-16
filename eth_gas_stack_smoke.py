#!/usr/bin/env python3
"""ETH gas tracker stack smoke: Python API + Node SSR health."""

from __future__ import annotations

import argparse
import json
import os
import sys

from util_smoke_http import get_json, print_header


def main() -> int:
    parser = argparse.ArgumentParser(description="ETH gas live stack smoke")
    parser.add_argument(
        "--py-url",
        default=os.environ.get("GAS_PY_URL", "http://127.0.0.1:8031"),
    )
    parser.add_argument(
        "--node-url",
        default=os.environ.get("GAS_NODE_URL", "http://127.0.0.1:3001"),
    )
    args = parser.parse_args()
    failures = 0

    for label, base, path in (
        ("Python", args.py_url, "/api/health"),
        ("Python monitoring", args.py_url, "/api/monitoring/overview"),
        ("Node SSR", args.node_url, "/health"),
    ):
        print_header(f"{label} {path}")
        data, code, raw = get_json(f"{base.rstrip('/')}{path}")
        if data is None and code == 0:
            print(f"  FAIL: {raw}")
            failures += 1
        elif code >= 400:
            print(f"  FAIL HTTP {code}: {raw[:300]}")
            failures += 1
        else:
            print(f"  OK HTTP {code}")
            if data:
                snippet = json.dumps(data, indent=2)
                print(snippet[:2500])

    print_header("Python current gas")
    data, code, raw = get_json(f"{args.py_url.rstrip('/')}/api/gas/current")
    if data is None:
        print(f"  FAIL: {raw}")
        failures += 1
    else:
        tiers = {k: data.get(k) for k in ("standard_gwei", "network_status") if k in data}
        print(f"  OK HTTP {code} {tiers}")

    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
