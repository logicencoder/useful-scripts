#!/usr/bin/env python3
"""Verify WP Visitor Stats tracking snippet is present on public pages."""

from __future__ import annotations

import argparse
import os
import re
import sys
import urllib.request

MARKERS = (
    "wpVisitorStats",
    "wp-visitor-stats",
    "wp_visitor_stats",
    "visitor-stats-track",
)


def fetch(url: str, timeout: float) -> tuple[int, str]:
    req = urllib.request.Request(url, headers={"User-Agent": "LE-VisitorStats-Verify/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.getcode(), resp.read().decode("utf-8", errors="replace")


def main() -> int:
    parser = argparse.ArgumentParser(description="WP Visitor Stats remote verify")
    parser.add_argument("--url", default=os.environ.get("WP_URL", ""))
    parser.add_argument("--path", default="/", help="Path to check (default /)")
    parser.add_argument("--timeout", type=float, default=15.0)
    args = parser.parse_args()
    if not args.url:
        print("Set WP_URL or --url", file=sys.stderr)
        return 2

    base = args.url.rstrip("/")
    target = f"{base}{args.path if args.path.startswith('/') else '/' + args.path}"
    try:
        code, html = fetch(target, args.timeout)
    except Exception as exc:
        print(f"FAIL fetch {target}: {exc}")
        return 1

    found = [m for m in MARKERS if m in html]
    ajax = re.search(r"admin-ajax\.php", html) is not None
    print(f"HTTP {code} bytes={len(html)}")
    print(f"tracking_markers={found or 'NONE'} admin_ajax_ref={ajax}")
    if not found:
        print("WARN: no visitor-stats marker in HTML — plugin inactive or page excluded")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
