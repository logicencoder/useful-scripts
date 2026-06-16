#!/usr/bin/env python3
"""Geth HTTP + optional WebSocket block smoke."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time

from util_smoke_http import print_header

try:
    import requests
except ImportError:
    requests = None


def rpc_http(url: str, method: str, params: list, timeout: float) -> dict:
    if requests is None:
        raise RuntimeError("pip install requests")
    payload = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
    started = time.time()
    resp = requests.post(url, json=payload, timeout=timeout)
    ms = (time.time() - started) * 1000
    resp.raise_for_status()
    data = resp.json()
    return {"result": data.get("result"), "error": data.get("error"), "ms": ms}


def rpc_ws_block(ws_url: str, timeout: float) -> dict:
    import asyncio
    import websockets

    async def _run() -> dict:
        started = time.time()
        async with websockets.connect(ws_url, open_timeout=timeout, close_timeout=timeout) as ws:
            await ws.send(json.dumps({"jsonrpc": "2.0", "id": 1, "method": "eth_blockNumber", "params": []}))
            raw = await asyncio.wait_for(ws.recv(), timeout=timeout)
        ms = (time.time() - started) * 1000
        block = json.loads(raw).get("result")
        return {"block": block, "ms": ms}

    return asyncio.run(_run())


def main() -> int:
    parser = argparse.ArgumentParser(description="Geth RPC smoke")
    parser.add_argument("--http", default=os.environ.get("GETH_HTTP", "http://127.0.0.1:8545"))
    parser.add_argument("--ws", default=os.environ.get("GETH_WS", ""))
    parser.add_argument("--timeout", type=float, default=10.0)
    args = parser.parse_args()
    failures = 0

    print_header("HTTP eth_blockNumber")
    try:
        out = rpc_http(args.http, "eth_blockNumber", [], args.timeout)
        print(f"  OK block={out['result']} ({out['ms']:.0f} ms)")
    except Exception as exc:
        print(f"  FAIL: {exc}")
        failures += 1

    print_header("HTTP eth_gasPrice")
    try:
        out = rpc_http(args.http, "eth_gasPrice", [], args.timeout)
        print(f"  OK gasPrice={out['result']} ({out['ms']:.0f} ms)")
    except Exception as exc:
        print(f"  FAIL: {exc}")
        failures += 1

    if args.ws:
        print_header(f"WebSocket {args.ws}")
        try:
            out = rpc_ws_block(args.ws, args.timeout)
            print(f"  OK block={out['block']} ({out['ms']:.0f} ms)")
        except Exception as exc:
            print(f"  FAIL: {exc}")
            failures += 1

    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
