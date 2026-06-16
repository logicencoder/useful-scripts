#!/usr/bin/env python3
"""Remote le-settings ops checks over SSH + wp-cli (no wp-admin browser)."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys


def _ssh_cmd(remote: str, wp_root: str, inner: str) -> tuple[int, str]:
    script = f"cd {wp_root} && {inner}"
    proc = subprocess.run(
        ["ssh", remote, script],
        capture_output=True,
        text=True,
        timeout=60,
    )
    out = (proc.stdout or "") + (proc.stderr or "")
    return proc.returncode, out.strip()


def main() -> int:
    parser = argparse.ArgumentParser(description="LE Settings remote ops smoke")
    parser.add_argument("--ssh", default=os.environ.get("HOSTINGER_SSH", ""))
    parser.add_argument("--wp-root", default=os.environ.get("WP_REMOTE_ROOT", ""))
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    if not args.ssh or not args.wp_root:
        print("Set HOSTINGER_SSH and WP_REMOTE_ROOT", file=sys.stderr)
        return 2

    failures = 0
    report: dict = {}

    code, out = _ssh_cmd(
        args.ssh,
        args.wp_root,
        "wp option get le_settings --format=json 2>/dev/null || echo '{}'",
    )
    settings = {}
    try:
        settings = json.loads(out.splitlines()[-1]) if out else {}
    except json.JSONDecodeError:
        failures += 1
    report["telegram_enabled"] = bool(settings.get("telegram_enabled"))
    report["debug_log_enabled"] = bool(settings.get("debug_log_enabled"))
    print(f"telegram_enabled={report['telegram_enabled']} debug_log_enabled={report['debug_log_enabled']}")

    code2, out2 = _ssh_cmd(
        args.ssh,
        args.wp_root,
        "wp config get WP_DEBUG --type=constant 2>/dev/null; wp config get WP_DEBUG_LOG --type=constant 2>/dev/null",
    )
    report["wp_debug_lines"] = out2
    print(f"wp-config debug:\n{out2}")

    for table in ("le_bot_log", "le_bf_log", "le_visitor_log"):
        code3, out3 = _ssh_cmd(
            args.ssh,
            args.wp_root,
            f"wp db query \"SELECT COUNT(*) AS c FROM {{prefix}}{table}\" --skip-column-names 2>/dev/null || echo -1",
        )
        try:
            count = int(out3.splitlines()[-1].strip())
        except ValueError:
            count = -1
        report[f"{table}_rows"] = count
        print(f"{table}_rows={count}")
        if count < 0:
            failures += 1

    if args.json:
        print(json.dumps(report, indent=2))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
