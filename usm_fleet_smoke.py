#!/usr/bin/env python3
"""TCP + optional USM API smoke for services listed in services.yaml."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from urllib.parse import urlparse

import yaml

from util_smoke_http import get_json, print_header, tcp_open


def load_services(path: Path) -> dict:
    with path.open() as fh:
        data = yaml.safe_load(fh) or {}
    return data.get("services") or {}


def main() -> int:
    parser = argparse.ArgumentParser(description="USM fleet port smoke test")
    parser.add_argument(
        "--yaml",
        default=os.environ.get("USM_SERVICES_YAML", ""),
        help="Path to services.yaml (required unless USM_SERVICES_YAML set)",
    )
    parser.add_argument(
        "--host",
        default=os.environ.get("USM_SMOKE_HOST", "127.0.0.1"),
        help="Host for TCP port checks (default 127.0.0.1 on SOL)",
    )
    parser.add_argument(
        "--usm-url",
        default=os.environ.get("USM_URL", "http://127.0.0.1:5566"),
        help="USM dashboard base URL",
    )
    parser.add_argument("--group", default="", help="Only check services in this group")
    parser.add_argument("--skip-usm-api", action="store_true")
    args = parser.parse_args()

    yaml_path = Path(args.yaml).expanduser() if args.yaml else None
    if not yaml_path or not yaml_path.is_file():
        print("Set --yaml or USM_SERVICES_YAML to a services.yaml file", file=sys.stderr)
        return 2

    services = load_services(yaml_path)
    failures = 0
    checked = 0

    print_header(f"Port checks on {args.host}")
    for name, cfg in sorted(services.items()):
        if args.group and cfg.get("group") != args.group:
            continue
        port = cfg.get("port")
        if not port:
            continue
        checked += 1
        ok, detail = tcp_open(args.host, int(port))
        status = "OK" if ok else "FAIL"
        print(f"  [{status}] {name:28} :{port}  ({cfg.get('type', '?')})  {detail}")
        if not ok:
            failures += 1

    if not args.skip_usm_api:
        print_header("USM API")
        data, code, raw = get_json(f"{args.usm_url.rstrip('/')}/api/status")
        if data is None:
            print(f"  [FAIL] GET /api/status -> {raw}")
            failures += 1
        else:
            print(f"  [OK] GET /api/status HTTP {code}")
            if isinstance(data, dict):
                svc = data.get("services") or data.get("service_count")
                if svc is not None:
                    print(f"       services snapshot: {svc}")

    print_header("Summary")
    print(f"  Ports checked: {checked}, failures: {failures}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
