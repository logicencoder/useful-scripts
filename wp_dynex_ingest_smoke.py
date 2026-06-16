#!/usr/bin/env python3
"""WordPress Dynex ingest endpoint smoke (transactions or richlist)."""

from __future__ import annotations

import argparse
import json
import os
import sys

from util_smoke_http import get_json, print_header

ENDPOINTS = {
    "transactions": "/wp-json/dynex/v1/transactions",
    "richlist": "/wp-json/0xdnxdhip/v1/richlist",
}


def main() -> int:
    parser = argparse.ArgumentParser(description="WP Dynex ingest smoke")
    parser.add_argument(
        "--wp-url",
        default=os.environ.get("WP_URL", "https://logicencoder.com"),
        help="WordPress site base URL",
    )
    parser.add_argument(
        "--api-key",
        default=os.environ.get("DYNEX_WP_API_KEY", ""),
        help="X-API-Key header value",
    )
    parser.add_argument(
        "--endpoint",
        choices=sorted(ENDPOINTS.keys()),
        default="transactions",
    )
    parser.add_argument(
        "--dry-auth-only",
        action="store_true",
        help="POST empty body — expect 400/401 distinction only",
    )
    args = parser.parse_args()

    base = args.wp_url.rstrip("/")
    path = ENDPOINTS[args.endpoint]
    url = f"{base}{path}"

    headers = {}
    if args.api_key:
        headers["X-API-Key"] = args.api_key

    body = json.dumps({"transactions": []}).encode("utf-8")
    if args.endpoint == "richlist":
        body = json.dumps({"richlist": [], "total_balance": 0}).encode("utf-8")

    print_header(f"POST {path}")
    data, code, raw = get_json(url, method="POST", headers=headers, body=body)

    if code == 401 or (raw and "rest_forbidden" in raw):
        print(f"  AUTH FAIL HTTP {code} — check API key")
        return 1
    if code == 403:
        print(f"  FORBIDDEN HTTP {code}")
        return 1
    if code >= 500:
        print(f"  SERVER FAIL HTTP {code}: {raw[:500]}")
        return 1

    print(f"  HTTP {code}")
    if data:
        print(json.dumps(data, indent=2)[:1500])
    elif raw:
        print(raw[:500])

    if not args.api_key:
        print("  WARN: no DYNEX_WP_API_KEY — auth not fully tested")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
