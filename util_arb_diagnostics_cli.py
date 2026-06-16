#!/usr/bin/env python3
"""Compact CLI for cex_dex_arb_app /api/diagnostics/* endpoints."""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any, Dict, Optional

from util_smoke_http import get_json, print_header


DIAG_PATHS = {
    "scanner-feeds": "/api/diagnostics/scanner-feeds",
    "market-data-hub": "/api/diagnostics/market-data-hub",
    "scanner-rank": "/api/diagnostics/scanner-rank",
    "arb-parity": "/api/diagnostics/arb-parity",
    "api-timing": "/api/diagnostics/api-timing",
}


def _base_url() -> str:
    port = os.environ.get("ARB_DASHBOARD_PORT", "8000")
    return os.environ.get("ARB_URL", f"http://127.0.0.1:{port}").rstrip("/")


def _summarize(name: str, data: Dict[str, Any]) -> str:
    if name == "scanner-feeds":
        scanner = data.get("scanner") or {}
        fa = scanner.get("feed_audit") or {}
        return (
            f"running={scanner.get('running')} "
            f"mexc_ws_pairs={scanner.get('mexc_ws_pairs')} "
            f"gate_ws_pairs={scanner.get('gate_ws_pairs')} "
            f"mexc_depth={fa.get('mexc_orderbook_depth')} "
            f"gate_depth={fa.get('gate_orderbook_depth')}"
        )
    if name == "market-data-hub":
        hub = data.get("market_data_hub") or data.get("hub") or data
        return (
            f"hub_driven_rank={hub.get('hub_driven_rank')} "
            f"pairs_tracked={hub.get('pairs_tracked') or hub.get('tracked_pairs')} "
            f"tick_age_ms={hub.get('last_tick_age_ms') or hub.get('tick_age_ms')}"
        )
    if name == "scanner-rank":
        rank = data.get("scanner_rank") or {}
        return (
            f"scanner_running={rank.get('scanner_running')} "
            f"hub_driven_rank={rank.get('hub_driven_rank')} "
            f"p50_ms={rank.get('rank_p50_ms') or rank.get('p50_ms')}"
        )
    if name == "arb-parity":
        parity = data.get("arb_parity") or data
        return f"status={parity.get('status')} mismatches={parity.get('mismatch_count')}"
    if name == "api-timing":
        timing = data.get("api_timing") or data
        routes = timing.get("routes") or timing.get("samples") or {}
        count = len(routes) if isinstance(routes, dict) else 0
        return f"route_samples={count}"
    return f"keys={list(data.keys())[:8]}"


def _fetch(base: str, name: str) -> tuple[Optional[Dict[str, Any]], int, str]:
    return get_json(f"{base}{DIAG_PATHS[name]}")


def _run_one(base: str, name: str, full: bool, strict: bool) -> int:
    print_header(name)
    data, code, raw = _fetch(base, name)
    if data is None:
        print(f"  FAIL HTTP {code}: {raw}")
        return 1
    print(f"  OK HTTP {code} — {_summarize(name, data)}")
    if full:
        print(json.dumps(data, indent=2)[:6000])
    if strict and name == "scanner-feeds":
        scanner = data.get("scanner") or {}
        fa = scanner.get("feed_audit") or {}
        mexc_ok = (fa.get("mexc_orderbook_depth") or 0) + (fa.get("mexc_bid_ask_only") or 0) > 0
        gate_ok = (fa.get("gate_orderbook_depth") or 0) + (fa.get("gate_bid_ask_only") or 0) > 0
        if scanner.get("running") and not (mexc_ok and gate_ok):
            print("  WARN scanner running but feed audit looks empty")
            return 1
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Arb dashboard diagnostics CLI")
    parser.add_argument(
        "command",
        nargs="?",
        choices=list(DIAG_PATHS) + ["all"],
        default="all",
        help="Diagnostic endpoint (default: all)",
    )
    parser.add_argument("--base-url", default=_base_url())
    parser.add_argument("--json", action="store_true", help="Print full JSON bodies")
    parser.add_argument("--strict", action="store_true", help="Exit 1 on scanner-feed warnings")
    args = parser.parse_args()
    base = args.base_url.rstrip("/")

    names = list(DIAG_PATHS) if args.command == "all" else [args.command]
    failures = 0
    for name in names:
        failures += _run_one(base, name, args.json, args.strict and name == "scanner-feeds")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
