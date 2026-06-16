#!/usr/bin/env python3
"""Probe MEV builder endpoints: init (eth_chainId) + bundle RPC reachability."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from typing import Any, Dict, List, Tuple

try:
    import aiohttp
except ImportError:
    print("aiohttp required: pip install aiohttp", file=sys.stderr)
    raise SystemExit(2)

CANDIDATES: Dict[str, Dict[str, Any]] = {
    "beaver_build": {"url": "https://rpc.beaverbuild.org", "method": "eth_sendBundle", "label": "Beaver"},
    "titan_builder": {"url": "https://rpc.titanbuilder.xyz", "method": "eth_sendBundle", "label": "Titan"},
    "buildernet_builder": {"url": "https://rpc.buildernet.org", "method": "eth_sendBundle", "label": "Buildernet"},
    "bobthebuilder": {"url": "https://rpc.bobthebuilder.xyz", "method": "eth_sendBundle", "label": "Bob"},
    "quasar_builder": {"url": "https://rpc.quasar.win", "method": "eth_sendBundle", "label": "Quasar"},
    "btcs_builder": {"url": "https://rpc.btcs.com", "method": "eth_sendBundle", "label": "BTCS"},
    "flashbots_fast": {
        "url": "https://rpc.flashbots.net/fast",
        "method": "eth_sendRawTransaction",
        "label": "Flashbots Fast",
        "type": "raw",
    },
}


async def probe_init(session: aiohttp.ClientSession, cfg: Dict[str, Any]) -> Tuple[bool, float, str]:
    payload = {"jsonrpc": "2.0", "method": "eth_chainId", "params": [], "id": 1}
    t0 = time.perf_counter()
    try:
        async with session.post(cfg["url"], json=payload, timeout=aiohttp.ClientTimeout(total=10)) as resp:
            ms = (time.perf_counter() - t0) * 1000
            body = await resp.text()
            ok_status = resp.status in (200, 400, 403, 405)
            detail = f"HTTP {resp.status}"
            if body:
                try:
                    parsed = json.loads(body)
                    if "result" in parsed:
                        detail += f" chain={parsed['result']}"
                except Exception:
                    detail += f" body={body[:60]}"
            return ok_status, ms, detail
    except Exception as exc:
        return False, (time.perf_counter() - t0) * 1000, str(exc)[:120]


async def probe_bundle_rpc(session: aiohttp.ClientSession, cfg: Dict[str, Any]) -> Tuple[bool, float, str]:
    if cfg.get("type") == "raw":
        payload = {"jsonrpc": "2.0", "method": "eth_sendRawTransaction", "params": ["0x02"], "id": 2}
    else:
        payload = {
            "jsonrpc": "2.0",
            "method": cfg.get("method", "eth_sendBundle"),
            "params": [{"txs": [], "blockNumber": "0x1000000"}],
            "id": 2,
        }
    t0 = time.perf_counter()
    try:
        async with session.post(cfg["url"], json=payload, timeout=aiohttp.ClientTimeout(total=10)) as resp:
            ms = (time.perf_counter() - t0) * 1000
            body = await resp.text()
            if resp.status not in (200, 400, 403, 405):
                return False, ms, f"HTTP {resp.status}"
            try:
                parsed = json.loads(body) if body else {}
            except Exception:
                parsed = {}
            alive = "result" in parsed or "error" in parsed
            err = parsed.get("error", {})
            err_msg = err.get("message", str(err))[:80] if err else ""
            detail = f"HTTP {resp.status}"
            if "result" in parsed:
                detail += " result=ok"
            elif err_msg:
                detail += f" err={err_msg}"
            return alive, ms, detail
    except Exception as exc:
        return False, (time.perf_counter() - t0) * 1000, str(exc)[:120]


async def run_probe(names: List[str], strict: bool) -> int:
    rows: List[Dict[str, Any]] = []
    async with aiohttp.ClientSession(
        connector=aiohttp.TCPConnector(limit=20),
        timeout=aiohttp.ClientTimeout(total=15),
        headers={"Content-Type": "application/json"},
    ) as session:
        for name in names:
            cfg = CANDIDATES[name]
            init_ok, init_ms, init_detail = await probe_init(session, cfg)
            bundle_ok, bundle_ms, bundle_detail = await probe_bundle_rpc(session, cfg)
            rows.append(
                {
                    "name": name,
                    "init_ok": init_ok,
                    "init_ms": init_ms,
                    "bundle_ok": bundle_ok,
                    "bundle_ms": bundle_ms,
                    "detail": init_detail,
                }
            )

    print(f"{'name':<18} {'init':>5} {'ms':>7}  {'bundle':>6} {'b_ms':>7}  detail")
    failures = 0
    for r in rows:
        init = "OK" if r["init_ok"] else "FAIL"
        bundle = "OK" if r["bundle_ok"] else "FAIL"
        print(
            f"{r['name']:<18} {init:>5} {r['init_ms']:7.0f}  {bundle:>6} {r['bundle_ms']:7.0f}  {r['detail'][:50]}"
        )
        if strict and (not r["init_ok"] or not r["bundle_ok"]):
            failures += 1
    return 1 if failures else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="MEV builder RPC probe")
    parser.add_argument(
        "--builders",
        default=",".join(CANDIDATES.keys()),
        help="Comma-separated builder keys",
    )
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()
    names = [n.strip() for n in args.builders.split(",") if n.strip()]
    unknown = [n for n in names if n not in CANDIDATES]
    if unknown:
        print(f"Unknown builders: {unknown}", file=sys.stderr)
        return 2
    return asyncio.run(run_probe(names, args.strict))


if __name__ == "__main__":
    sys.exit(main())
