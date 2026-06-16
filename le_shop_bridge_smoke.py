#!/usr/bin/env python3
"""LE Shop WordPress catalogue + crypto-store backend bridge smoke."""

from __future__ import annotations

import argparse
import json
import os
import sys

from util_smoke_http import get_json, print_header


def main() -> int:
    parser = argparse.ArgumentParser(description="LE Shop bridge smoke")
    parser.add_argument("--wp-url", default=os.environ.get("WP_URL", "https://logicencoder.com"))
    parser.add_argument(
        "--backend-url",
        default=os.environ.get("LE_BACKEND_URL", "http://127.0.0.1:8020"),
    )
    parser.add_argument("--webhook-secret", default=os.environ.get("LE_WEBHOOK_SECRET", ""))
    parser.add_argument("--admin-key", default=os.environ.get("LE_ADMIN_KEY", ""))
    args = parser.parse_args()
    failures = 0

    wp = args.wp_url.rstrip("/")
    backend = args.backend_url.rstrip("/")

    print_header("WP REST applications")
    data, code, raw = get_json(f"{wp}/wp-json/wp/v2/application?per_page=5&status=publish")
    if data is None:
        print(f"  FAIL HTTP {code}: {raw[:300]}")
        failures += 1
    else:
        count = len(data) if isinstance(data, list) else "?"
        print(f"  OK HTTP {code} — sample count {count}")

    print_header("Backend webhook ping")
    if not args.webhook_secret:
        print("  SKIP — set LE_WEBHOOK_SECRET")
    else:
        body = json.dumps({"action": "ping", "post_id": 0}).encode("utf-8")
        headers = {"X-Webhook-Secret": args.webhook_secret}
        data, code, raw = get_json(
            f"{backend}/webhook/wp-changed",
            method="POST",
            headers=headers,
            body=body,
        )
        if code >= 500 or (data is None and code == 0):
            print(f"  FAIL HTTP {code}: {raw[:400]}")
            failures += 1
        else:
            print(f"  OK HTTP {code}")
            if data:
                print(json.dumps(data, indent=2)[:800])

    print_header("Backend admin stats")
    if not args.admin_key:
        print("  SKIP — set LE_ADMIN_KEY")
    else:
        data, code, raw = get_json(
            f"{backend}/admin/stats",
            headers={"x-admin-key": args.admin_key},
        )
        if code == 403:
            print("  FAIL forbidden — bad admin key")
            failures += 1
        elif data is None:
            print(f"  FAIL HTTP {code}: {raw[:300]}")
            failures += 1
        else:
            print(f"  OK HTTP {code}")
            print(json.dumps(data, indent=2)[:1500])

    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
