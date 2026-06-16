#!/usr/bin/env python3
"""IndexNow queue status for MEXC/Gate live-stats WP plugins (remote wp-cli)."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys


PLUGINS = (
    ("mexc", "mexc_indexnow_pending_urls", "mexc_indexnow_queue_updated_at"),
    ("gate", "gate_indexnow_pending_urls", "gate_indexnow_queue_updated_at"),
)


def _ssh_wp(remote: str, wp_root: str, option: str) -> str:
    proc = subprocess.run(
        ["ssh", remote, f"cd {wp_root} && wp option get {option} --format=json 2>/dev/null"],
        capture_output=True,
        text=True,
        timeout=45,
    )
    return (proc.stdout or "").strip()


def main() -> int:
    parser = argparse.ArgumentParser(description="IndexNow queue status (MEXC/Gate plugins)")
    parser.add_argument("--ssh", default=os.environ.get("HOSTINGER_SSH", ""))
    parser.add_argument("--wp-root", default=os.environ.get("WP_REMOTE_ROOT", ""))
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    if not args.ssh or not args.wp_root:
        print("Set HOSTINGER_SSH and WP_REMOTE_ROOT", file=sys.stderr)
        return 2

    report = {}
    for label, queue_opt, updated_opt in PLUGINS:
        raw = _ssh_wp(args.ssh, args.wp_root, queue_opt)
        try:
            queue = json.loads(raw) if raw else []
        except json.JSONDecodeError:
            queue = []
        updated = _ssh_wp(args.ssh, args.wp_root, updated_opt)
        pending = len(queue) if isinstance(queue, list) else 0
        report[label] = {"pending": pending, "updated_at": updated}
        print(f"{label}: pending={pending} updated_at={updated or '-'}")

    if args.json:
        print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
