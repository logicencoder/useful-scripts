#!/usr/bin/env python3
"""Probe MEXC protobuf WS shards (50 symbols each) from stored_coins JSON."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import List

try:
    import aiohttp
except ImportError:
    aiohttp = None  # type: ignore


def chunk_pairs(pairs: List[str], size: int) -> List[List[str]]:
    return [pairs[i : i + size] for i in range(0, len(pairs), size)]


def load_pairs(path: Path) -> List[str]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(raw, dict) and "coins" in raw:
        rows = raw["coins"]
    elif isinstance(raw, list):
        rows = raw
    else:
        raise ValueError("Expected list or {coins: [...]} JSON")
    pairs = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        if row.get("enabled", True) is False:
            continue
        pair = row.get("mexc_pair") or row.get("symbol")
        if pair:
            pairs.append(str(pair))
    return pairs


@dataclass
class ShardStats:
    shard_id: int
    pairs: List[str]
    connected: bool = False
    subscribe_ok: bool = False
    messages: int = 0
    binary_messages: int = 0
    last_message_at: float = 0.0
    error: str = ""


async def _probe_shard(
    session: "aiohttp.ClientSession",
    ws_url: str,
    shard_id: int,
    pairs: List[str],
    probe_seconds: float,
) -> ShardStats:
    stats = ShardStats(shard_id=shard_id, pairs=pairs)
    if not pairs:
        stats.error = "empty shard"
        return stats
    try:
        async with session.ws_connect(ws_url, heartbeat=30, timeout=30) as ws:
            stats.connected = True
            params = []
            for pair in pairs:
                params.append(f"spot@public.aggre.deals.v3.api.pb@100ms@{pair}")
            await ws.send_json({"method": "SUBSCRIPTION", "params": params})
            deadline = time.time() + probe_seconds
            while time.time() < deadline:
                try:
                    msg = await asyncio.wait_for(ws.recv(), timeout=2.0)
                except asyncio.TimeoutError:
                    continue
                if msg.type == aiohttp.WSMsgType.TEXT:
                    stats.messages += 1
                    stats.last_message_at = time.time()
                    try:
                        data = json.loads(msg.data)
                        if data.get("code") == 0 and data.get("msg") != "PONG":
                            stats.subscribe_ok = True
                    except json.JSONDecodeError:
                        pass
                elif msg.type == aiohttp.WSMsgType.BINARY:
                    stats.binary_messages += 1
                    stats.last_message_at = time.time()
                elif msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                    break
    except Exception as exc:
        stats.error = str(exc)[:160]
    return stats


async def run_probe(
    pairs: List[str],
    ws_url: str,
    chunk_size: int,
    max_shards: int,
    probe_seconds: float,
) -> List[ShardStats]:
    shards = chunk_pairs(pairs, chunk_size)[:max_shards]
    if aiohttp is None:
        raise RuntimeError("aiohttp required: pip install aiohttp")
    async with aiohttp.ClientSession() as session:
        tasks = [
            _probe_shard(session, ws_url, idx + 1, chunk, probe_seconds)
            for idx, chunk in enumerate(shards)
        ]
        return await asyncio.gather(*tasks)


def main() -> int:
    parser = argparse.ArgumentParser(description="MEXC multi-connection shard probe")
    parser.add_argument(
        "--coins-json",
        default=os.environ.get("MULTICOIN_COINS_JSON", ""),
        help="Path to stored_coins.json (list or {coins:[]})",
    )
    parser.add_argument(
        "--ws-url",
        default=os.environ.get("MEXC_WS_URL", "wss://wbs-api.mexc.com/ws"),
    )
    parser.add_argument("--chunk-size", type=int, default=50)
    parser.add_argument("--max-shards", type=int, default=10)
    parser.add_argument("--probe-seconds", type=float, default=8.0)
    parser.add_argument(
        "--multicoin-url",
        default=os.environ.get("MULTICOIN_URL", ""),
        help="Optional cross-check GET /api/stats",
    )
    args = parser.parse_args()

    if not args.coins_json:
        print("Set --coins-json or MULTICOIN_COINS_JSON", file=sys.stderr)
        return 2
    path = Path(args.coins_json).expanduser()
    if not path.is_file():
        print(f"Coins file not found: {path}", file=sys.stderr)
        return 2

    pairs = load_pairs(path)
    print(f"Loaded {len(pairs)} enabled pairs from {path}")
    if args.multicoin_url:
        from util_smoke_http import get_json

        stats, code, raw = get_json(f"{args.multicoin_url.rstrip('/')}/api/stats")
        if stats:
            print(f"Multi-coin /api/stats HTTP {code}: keys={list(stats.keys())[:8]}")
        else:
            print(f"Multi-coin stats unavailable: {raw}")

    results = asyncio.run(
        run_probe(pairs, args.ws_url, args.chunk_size, args.max_shards, args.probe_seconds)
    )
    failures = 0
    for row in results:
        age = (
            f"{time.time() - row.last_message_at:.1f}s ago"
            if row.last_message_at
            else "never"
        )
        print(
            f"shard={row.shard_id} pairs={len(row.pairs)} connected={row.connected} "
            f"sub_ok={row.subscribe_ok} text={row.messages} binary={row.binary_messages} "
            f"last={age} err={row.error or '-'}"
        )
        if not row.connected or (row.binary_messages == 0 and row.messages <= 1):
            failures += 1
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
