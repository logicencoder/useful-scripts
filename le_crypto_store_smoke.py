#!/usr/bin/env python3
"""LE Crypto App Store backend smoke (shop + admin)."""

from __future__ import annotations

import argparse
import json
import os
import sys

from util_smoke_http import get_json, print_header


def main() -> int:
    parser = argparse.ArgumentParser(description="LE crypto app store smoke")
    parser.add_argument(
        "--backend-url",
        default=os.environ.get("LE_BACKEND_URL", "http://127.0.0.1:8020"),
    )
    parser.add_argument("--admin-key", default=os.environ.get("LE_ADMIN_KEY", ""))
    args = parser.parse_args()
    base = args.backend_url.rstrip("/")
    failures = 0

    print_header("GET /shop/products")
    data, code, raw = get_json(f"{base}/shop/products")
    if data is None:
        print(f"  FAIL HTTP {code}: {raw[:400]}")
        failures += 1
    else:
        items = data if isinstance(data, list) else data.get("products") or data
        n = len(items) if isinstance(items, list) else "?"
        print(f"  OK HTTP {code} — products {n}")

    print_header("GET /admin/stats")
    if not args.admin_key:
        print("  SKIP — set LE_ADMIN_KEY")
    else:
        data, code, raw = get_json(
            f"{base}/admin/stats",
            headers={"x-admin-key": args.admin_key},
        )
        if code == 403:
            print("  FAIL forbidden")
            failures += 1
        elif data is None:
            print(f"  FAIL HTTP {code}: {raw[:300]}")
            failures += 1
        else:
            print(f"  OK HTTP {code}")
            print(json.dumps(data, indent=2)[:2000])

    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
