#!/usr/bin/env python3
"""Poll or stream mexc_trading_app debug logs without opening the browser tab."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from typing import Any, Dict, Iterable, List, Optional
from urllib.parse import urlparse

from util_smoke_http import get_json


def _ws_url(base: str) -> str:
    parsed = urlparse(base)
    scheme = "wss" if parsed.scheme == "https" else "ws"
    host = parsed.netloc or parsed.path
    return f"{scheme}://{host}/ws/debug_logs"


def _matches(item: Dict[str, Any], level: str, source: str, grep: str) -> bool:
    lvl = str(item.get("level", "")).upper()
    if level == "warn" and lvl not in ("WARN", "WARNING"):
        return False
    if level == "error" and lvl not in ("ERROR", "CRITICAL"):
        return False
    if level == "order":
        msg = f"{item.get('message', '')} {item.get('args_text', '')}"
        if "ORDER_TRACE" not in msg:
            return False
    if source != "all":
        if str(item.get("source", "")).lower() != source:
            return False
    if grep:
        blob = json.dumps(item, default=str)
        if grep.lower() not in blob.lower():
            return False
    return True


def _format_line(item: Dict[str, Any]) -> str:
    ts = item.get("timestamp")
    level = item.get("level", "LOG")
    source = item.get("source", "?")
    message = item.get("message", "")
    args_text = item.get("args_text", "")
    suffix = f" {args_text}" if args_text else ""
    return f"{ts} [{level}] ({source}) {message}{suffix}"


def _print_items(items: Iterable[Dict[str, Any]], level: str, source: str, grep: str) -> int:
    count = 0
    for item in items:
        if _matches(item, level, source, grep):
            print(_format_line(item))
            count += 1
    return count


def poll_recent(base: str, limit: int, level: str, source: str, grep: str, watch: float) -> int:
    seen: set[str] = set()
    while True:
        data, code, raw = get_json(f"{base}/api/debug-logs/recent?limit={limit}")
        if data is None:
            print(f"FAIL HTTP {code}: {raw}", file=sys.stderr)
            return 1
        items: List[Dict[str, Any]] = data.get("items") or []
        counters = data.get("counters") or {}
        new_items = []
        for item in items:
            key = json.dumps(item, sort_keys=True, default=str)
            if key not in seen:
                seen.add(key)
                new_items.append(item)
        printed = _print_items(new_items, level, source, grep)
        if not watch:
            print(f"\nCounters: {counters}")
            return 0
        if printed == 0:
            print(f"... waiting ({counters.get('total', 0)} total)", flush=True)
        time.sleep(watch)


async def stream_ws(base: str, level: str, source: str, grep: str) -> int:
    try:
        import websockets
    except ImportError:
        print("websockets required: pip install websockets", file=sys.stderr)
        return 2

    url = _ws_url(base)
    async with websockets.connect(url, ping_interval=20) as ws:
        print(f"Connected {url}", flush=True)
        while True:
            raw = await ws.recv()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue
            msg_type = msg.get("type")
            if msg_type == "debug_snapshot":
                _print_items(msg.get("items") or [], level, source, grep)
            elif msg_type == "debug_log":
                if _matches(msg, level, source, grep):
                    print(_format_line(msg))
            elif msg_type == "ping":
                continue


def main() -> int:
    parser = argparse.ArgumentParser(description="MEXC trading app debug log tail")
    parser.add_argument(
        "--base-url",
        default=os.environ.get("MEXC_TRADING_URL", "http://127.0.0.1:8005"),
    )
    parser.add_argument("--limit", type=int, default=400)
    parser.add_argument(
        "--level",
        choices=("all", "warn", "error", "order"),
        default="all",
    )
    parser.add_argument(
        "--source",
        choices=("all", "server", "client"),
        default="all",
    )
    parser.add_argument("--grep", default="")
    parser.add_argument("--watch", type=float, default=0.0, help="Poll interval seconds")
    parser.add_argument("--ws", action="store_true", help="Live tail via /ws/debug_logs")
    args = parser.parse_args()
    base = args.base_url.rstrip("/")

    if args.ws:
        return asyncio.run(stream_ws(base, args.level, args.source, args.grep))
    return poll_recent(base, args.limit, args.level, args.source, args.grep, args.watch)


if __name__ == "__main__":
    sys.exit(main())
