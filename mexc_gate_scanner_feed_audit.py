#!/usr/bin/env python3
"""Live audit: scanner MEXC/Gate feeds via arb /api/diagnostics/scanner-feeds."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.request

from util_smoke_http import get_json, print_header


def _base_url() -> str:
    port = os.environ.get("ARB_DASHBOARD_PORT", "8000")
    return os.environ.get("ARB_URL", f"http://127.0.0.1:{port}").rstrip("/")


def _http_post(base: str, path: str, body: dict | None = None) -> dict:
    data = json.dumps(body or {}).encode()
    req = urllib.request.Request(
        f"{base}{path}",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.loads(resp.read().decode())


def _cex_rest_ping(mexc_symbol: str, gate_pair: str) -> dict:
    out: dict = {}
    try:
        with urllib.request.urlopen(
            f"https://api.mexc.com/api/v3/ticker/bookTicker?symbol={mexc_symbol}",
            timeout=10,
        ) as resp:
            out["mexc_rest"] = {"ok": True, "body": json.loads(resp.read().decode())}
    except Exception as exc:
        out["mexc_rest"] = {"ok": False, "error": str(exc)[:120]}
    try:
        with urllib.request.urlopen(
            f"https://api.gateio.ws/api/v4/spot/tickers?currency_pair={gate_pair}",
            timeout=10,
        ) as resp:
            rows = json.loads(resp.read().decode())
            out["gate_rest"] = {"ok": bool(rows), "last": rows[0] if rows else None}
    except Exception as exc:
        out["gate_rest"] = {"ok": False, "error": str(exc)[:120]}
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Scanner feed audit for arb dashboard")
    parser.add_argument("--base-url", default=_base_url())
    parser.add_argument("--symbol-mexc", default=os.environ.get("AUDIT_MEXC_SYMBOL", "FORTHUSDT"))
    parser.add_argument("--symbol-gate", default=os.environ.get("AUDIT_GATE_PAIR", "FORTH_USDT"))
    parser.add_argument("--start-scanner", action="store_true", help="POST /api/scanner/start if idle")
    parser.add_argument("--with-cex-ping", action="store_true", help="Public REST ping for one symbol")
    parser.add_argument("--wait-seconds", type=float, default=90.0)
    args = parser.parse_args()
    base = args.base_url.rstrip("/")

    print_header("Scanner status")
    snap, code, raw = get_json(f"{base}/api/scanner/status")
    if snap is None:
        print(f"FAIL backend not reachable: HTTP {code} {raw}")
        return 1

    if not snap.get("running"):
        if not args.start_scanner:
            print("Scanner not running (use --start-scanner to auto-start)")
        else:
            print("Starting scanner…")
            try:
                _http_post(base, "/api/scanner/start", {})
            except Exception as exc:
                print(f"FAIL start: {exc}")
                return 1
            deadline = time.time() + args.wait_seconds
            while time.time() < deadline:
                time.sleep(2)
                snap, _, _ = get_json(f"{base}/api/scanner/status")
                if snap and snap.get("running"):
                    fa = snap.get("feed_audit") or {}
                    if (fa.get("mexc_orderbook_depth") or 0) > 0 or (fa.get("gate_bid_ask_only") or 0) > 0:
                        break
                print(f"  waiting running={snap.get('running') if snap else None}")

    print_header("/api/diagnostics/scanner-feeds")
    diag, code2, raw2 = get_json(f"{base}/api/diagnostics/scanner-feeds")
    if diag is None:
        print(f"FAIL HTTP {code2}: {raw2}")
        return 1
    print(json.dumps(diag, indent=2)[:8000])

    if args.with_cex_ping:
        print_header(f"CEX REST ping {args.symbol_mexc} / {args.symbol_gate}")
        print(json.dumps(_cex_rest_ping(args.symbol_mexc, args.symbol_gate), indent=2))

    fa = (diag.get("scanner") or {}).get("feed_audit") or {}
    ok_mexc = (fa.get("mexc_orderbook_depth") or 0) + (fa.get("mexc_bid_ask_only") or 0) > 0
    ok_gate = (fa.get("gate_orderbook_depth") or 0) + (fa.get("gate_bid_ask_only") or 0) > 0
    print(f"\nSUMMARY: MEXC feeds active={ok_mexc} Gate feeds active={ok_gate}")
    print(f"Gate WS pairs subscribed: {(diag.get('scanner') or {}).get('gate_ws_pairs')}")
    return 0 if ok_mexc and ok_gate else 2


if __name__ == "__main__":
    sys.exit(main())
