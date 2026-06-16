#!/usr/bin/env python3
"""Kill stale telegrt Chrome / monitor processes (sol-pump-app feeder)."""

from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Iterable, List, Set, Tuple


def _pgrep(pattern: str) -> List[Tuple[int, str]]:
    try:
        proc = subprocess.run(
            ["pgrep", "-af", pattern],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    rows: List[Tuple[int, str]] = []
    for line in proc.stdout.splitlines():
        parts = line.strip().split(None, 1)
        if not parts:
            continue
        try:
            pid = int(parts[0])
        except ValueError:
            continue
        rows.append((pid, parts[1] if len(parts) > 1 else ""))
    return rows


def _kill_pid(pid: int, sig: int) -> None:
    try:
        os.kill(pid, sig)
    except (ProcessLookupError, PermissionError):
        pass


def kill_stale_telegrt_processes(
    telegrt_dir: Path,
    keep_pids: Iterable[int] | None = None,
    *,
    preserve_monitor: bool = False,
) -> Tuple[List[int], List[str]]:
    telegrt_dir = telegrt_dir.expanduser().resolve()
    profile = telegrt_dir / "chrome_profile"
    profile_s = str(profile)
    telegrt_s = str(telegrt_dir)
    keep: Set[int] = set(keep_pids or ()) | {os.getpid()}
    targets: List[int] = []

    for pid, cmd in _pgrep("telegram_sol_signal_monitor"):
        if pid in keep or preserve_monitor:
            continue
        if telegrt_s in cmd or "telegram_sol_signal_monitor.py" in cmd:
            targets.append(pid)

    for pid, cmd in _pgrep("chrome"):
        if pid in keep:
            continue
        if profile_s in cmd or "telegrt/chrome_profile" in cmd:
            targets.append(pid)

    if targets:
        for pid, _cmd in _pgrep("chromedriver"):
            if pid not in keep:
                targets.append(pid)

    targets = sorted(set(targets))
    log: List[str] = []
    for pid in targets:
        _kill_pid(pid, signal.SIGTERM)
        log.append(f"TERM {pid}")

    if targets:
        time.sleep(0.8)
        for pid in targets:
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                continue
            except PermissionError:
                continue
            _kill_pid(pid, signal.SIGKILL)
            log.append(f"KILL {pid}")

    lock = profile / "SingletonLock"
    if lock.exists() or lock.is_symlink():
        profile_alive = any(profile_s in cmd for _pid, cmd in _pgrep("chrome"))
        if not profile_alive:
            try:
                lock.unlink(missing_ok=True)
                log.append("removed SingletonLock")
            except OSError:
                pass

    killed = []
    for pid in targets:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            killed.append(pid)
        except PermissionError:
            pass
    return killed, log


def main() -> int:
    parser = argparse.ArgumentParser(description="Telegrt stale process cleanup")
    parser.add_argument("--telegrt-dir", default=os.environ.get("TELEGRT_DIR", ""))
    parser.add_argument("--preserve-monitor", action="store_true")
    args = parser.parse_args()

    if args.telegrt_dir:
        telegrt_dir = Path(args.telegrt_dir)
    else:
        telegrt_dir = Path(os.environ.get("SOL_PUMP_HOME", str(Path.home() / "sol-pump-app"))) / "telegrt"

    if not telegrt_dir.is_dir():
        print(f"telegrt dir not found: {telegrt_dir}", file=sys.stderr)
        return 2

    killed, log = kill_stale_telegrt_processes(
        telegrt_dir,
        preserve_monitor=args.preserve_monitor,
    )
    for line in log:
        print(line)
    print(f"Cleaned {len(killed)} process(es)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
