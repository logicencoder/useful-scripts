#!/usr/bin/env python3
"""Ping configured Ethereum HTTP/WS providers and print latency table."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
import urllib.request
from typing import Dict, List, Optional, Tuple


HTTP_PROVIDERS: Dict[str, str] = {
    "local": "http://127.0.0.1:8545",
    "ankr": "https://rpc.ankr.com/eth",
    "drpc": "https://lb.drpc.org/ogrpc?network=ethereum&dkey={api_key}",
    "infura": "https://mainnet.infura.io/v3/{api_key}",
    "alchemy": "https://eth-mainnet.g.alchemy.com/v2/{api_key}",
    "quicknode": "https://{api_key}.quiknode.pro/",
}

WS_PROVIDERS: Dict[str, str] = {
    "local": "ws://127.0.0.1:8546",
    "ankr": "wss://rpc.ankr.com/eth/ws",
    "drpc": "wss://lb.drpc.org/ogrpc?network=ethereum&dkey={api_key}",
    "infura": "wss://mainnet.infura.io/ws/v3/{api_key}",
    "alchemy": "wss://eth-mainnet.g.alchemy.com/v2/{api_key}",
    "quicknode": "wss://{api_key}.quiknode.pro/",
}


def _api_key() -> str:
    for name in ("DRPC_API_KEY", "INFURA_API_KEY", "ALCHEMY_API_KEY", "QUICKNODE_API_KEY"):
        value = os.environ.get(name, "").strip()
        if value:
            return value
    return ""


def _resolve_url(template: str, geth_custom: str) -> Optional[str]:
    if "{api_key}" in template:
        key = _api_key()
        if not key:
            return None
        return template.format(api_key=key)
    if template.endswith(":8545") or template.endswith(":8546"):
        return template
    return template


def _http_block_number(url: str, timeout: float) -> Tuple[bool, float, str]:
    payload = json.dumps({"jsonrpc": "2.0", "method": "eth_blockNumber", "params": [], "id": 1}).encode()
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = json.loads(resp.read().decode())
        elapsed = (time.perf_counter() - t0) * 1000
        block = body.get("result")
        if not block:
            return False, elapsed, str(body)[:80]
        return True, elapsed, str(int(block, 16))
    except Exception as exc:
        elapsed = (time.perf_counter() - t0) * 1000
        return False, elapsed, str(exc)[:80]


async def _ws_smoke(url: str, timeout: float) -> Tuple[bool, float, str]:
    try:
        import websockets
    except ImportError:
        return False, 0.0, "websockets missing"
    t0 = time.perf_counter()
    try:
        async with websockets.connect(url, open_timeout=timeout, close_timeout=2) as ws:
            await ws.send(json.dumps({"jsonrpc": "2.0", "method": "eth_blockNumber", "params": [], "id": 1}))
            raw = await asyncio.wait_for(ws.recv(), timeout=timeout)
            elapsed = (time.perf_counter() - t0) * 1000
            body = json.loads(raw)
            block = body.get("result")
            return bool(block), elapsed, str(int(block, 16)) if block else raw[:60]
    except Exception as exc:
        elapsed = (time.perf_counter() - t0) * 1000
        return False, elapsed, str(exc)[:80]


def main() -> int:
    parser = argparse.ArgumentParser(description="Ethereum RPC provider probe")
    parser.add_argument(
        "--providers",
        default=os.environ.get("RPC_PROBE_PROVIDERS", "local,ankr,drpc,infura,alchemy"),
        help="Comma-separated provider keys",
    )
    parser.add_argument("--timeout", type=float, default=8.0)
    parser.add_argument("--skip-ws", action="store_true")
    parser.add_argument(
        "--geth-custom",
        default=os.environ.get("GETH_CUSTOM_HOST", ""),
        help="Override local host (e.g. 192.168.1.103)",
    )
    args = parser.parse_args()

    if args.geth_custom:
        HTTP_PROVIDERS["local"] = f"http://{args.geth_custom}:8545"
        WS_PROVIDERS["local"] = f"ws://{args.geth_custom}:8546"

    names = [n.strip() for n in args.providers.split(",") if n.strip()]
    failures = 0
    print(f"{'provider':<12} {'http':<6} {'http_ms':>8}  {'block':>8}  {'ws':<6} {'ws_ms':>8}  note")
    for name in names:
        http_tpl = HTTP_PROVIDERS.get(name)
        ws_tpl = WS_PROVIDERS.get(name)
        if not http_tpl:
            print(f"{name:<12} unknown provider key")
            failures += 1
            continue
        http_url = _resolve_url(http_tpl, args.geth_custom)
        if not http_url:
            print(f"{name:<12} skip (missing API key)")
            continue
        ok_h, ms_h, note_h = _http_block_number(http_url, args.timeout)
        ok_w, ms_w, note_w = False, 0.0, "-"
        if not args.skip_ws and ws_tpl:
            ws_url = _resolve_url(ws_tpl, args.geth_custom)
            if ws_url:
                ok_w, ms_w, note_w = asyncio.run(_ws_smoke(ws_url, args.timeout))
        print(
            f"{name:<12} {'OK' if ok_h else 'FAIL':<6} {ms_h:8.0f}  {note_h:>8}  "
            f"{'OK' if ok_w else 'FAIL':<6} {ms_w:8.0f}  {note_w}"
        )
        if not ok_h:
            failures += 1
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
