#!/usr/bin/env python3
"""Capture N messages from live-stats /ws-dashboard (MEXC and/or Gate)."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from typing import Any, Dict, List
from urllib.parse import urlparse


def _ws_url(base: str, path: str) -> str:
    parsed = urlparse(base)
    scheme = "wss" if parsed.scheme == "https" else "ws"
    host = parsed.netloc or parsed.path
    return f"{scheme}://{host}{path}"


async def capture(
    label: str,
    url: str,
    max_messages: int,
    max_seconds: float,
) -> Dict[str, Any]:
    try:
        import websockets
    except ImportError:
        return {"label": label, "ok": False, "error": "websockets missing"}

    counts: Dict[str, int] = {}
    samples: List[str] = []
    t0 = time.time()
    try:
        async with websockets.connect(url, ping_interval=20) as ws:
            while len(samples) < max_messages and (time.time() - t0) < max_seconds:
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=3.0)
                except asyncio.TimeoutError:
                    continue
                try:
                    msg = json.loads(raw)
                    msg_type = str(msg.get("type", "unknown"))
                except json.JSONDecodeError:
                    msg_type = "non_json"
                counts[msg_type] = counts.get(msg_type, 0) + 1
                if len(samples) < 5:
                    samples.append(raw[:200])
    except Exception as exc:
        return {
            "label": label,
            "ok": False,
            "url": url,
            "error": str(exc)[:160],
            "counts": counts,
        }
    return {
        "label": label,
        "ok": sum(counts.values()) > 0,
        "url": url,
        "messages": sum(counts.values()),
        "counts": counts,
        "elapsed_s": round(time.time() - t0, 2),
        "samples": samples,
    }


async def run_all(targets: List[tuple[str, str]], max_messages: int, max_seconds: float) -> int:
    tasks = [capture(label, url, max_messages, max_seconds) for label, url in targets]
    results = await asyncio.gather(*tasks)
    failures = 0
    for row in results:
        print(f"\n=== {row['label']} ===")
        print(f"url={row.get('url')} ok={row.get('ok')} messages={row.get('messages', 0)}")
        if row.get("counts"):
            print(f"types={row['counts']}")
        if row.get("error"):
            print(f"error={row['error']}")
            failures += 1
        elif not row.get("ok"):
            failures += 1
    return 1 if failures else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="MEXC/Gate live-stats dashboard WS probe")
    parser.add_argument("--mexc-url", default=os.environ.get("MEXC_TD_URL", "http://127.0.0.1:8080"))
    parser.add_argument("--gate-url", default=os.environ.get("GATE_TD_URL", "http://127.0.0.1:8083"))
    parser.add_argument("--only", choices=("mexc", "gate", "both"), default="both")
    parser.add_argument("--messages", type=int, default=10)
    parser.add_argument("--seconds", type=float, default=30.0)
    parser.add_argument("--path", default="/ws-dashboard")
    args = parser.parse_args()

    targets: List[tuple[str, str]] = []
    if args.only in ("mexc", "both"):
        targets.append(("mexc", _ws_url(args.mexc_url.rstrip("/"), args.path)))
    if args.only in ("gate", "both"):
        targets.append(("gate", _ws_url(args.gate_url.rstrip("/"), args.path)))
    return asyncio.run(run_all(targets, args.messages, args.seconds))


if __name__ == "__main__":
    sys.exit(main())
