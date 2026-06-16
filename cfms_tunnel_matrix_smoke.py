#!/usr/bin/env python3
"""CFMS /api/status plus HTTP probe of tunnel ingress hostnames."""

from __future__ import annotations

import argparse
import os
import sys
import urllib.request

from util_smoke_http import get_json, print_header


def probe_url(url: str, timeout: float) -> tuple[bool, int, str]:
    try:
        req = urllib.request.Request(url, method="HEAD")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return True, resp.getcode(), ""
    except Exception as exc:
        return False, 0, str(exc)


def main() -> int:
    parser = argparse.ArgumentParser(description="CFMS tunnel matrix smoke")
    parser.add_argument(
        "--cfms-url",
        default=os.environ.get("CFMS_URL", "http://127.0.0.1:5055"),
    )
    parser.add_argument("--timeout", type=float, default=8.0)
    parser.add_argument("--skip-http-probe", action="store_true")
    args = parser.parse_args()
    base = args.cfms_url.rstrip("/")
    failures = 0

    print_header("CFMS status")
    status, code, raw = get_json(f"{base}/api/status", timeout=args.timeout)
    if status is None:
        print(f"  FAIL /api/status: {raw}")
        failures += 1
    else:
        print(f"  OK HTTP {code}")
        for key in ("tunnel_running", "tunnel_pid", "tunnel_uptime", "config_path"):
            if key in status:
                print(f"    {key}: {status[key]}")

    print_header("Ingress endpoints")
    eps, code2, raw2 = get_json(f"{base}/api/endpoints", timeout=args.timeout)
    if eps is None:
        print(f"  FAIL /api/endpoints: {raw2}")
        failures += 1
        endpoints = []
    else:
        endpoints = eps.get("endpoints") or []
        print(f"  OK {len(endpoints)} hostname rules")

    if not args.skip_http_probe:
        print_header("HTTP probe (HEAD https://hostname/)")
        for rule in endpoints:
            host = rule.get("hostname")
            if not host:
                continue
            url = f"https://{host}/"
            ok, status_code, err = probe_url(url, args.timeout)
            mark = "OK" if ok else "FAIL"
            print(f"  [{mark}] {url} -> {status_code or err}")
            if not ok:
                failures += 1

    print_header("Summary")
    print(f"  failures: {failures}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
