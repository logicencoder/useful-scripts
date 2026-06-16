#!/usr/bin/env python3
"""Print UniV3 buy/sell USD ladders for one pool (DNX amounts by default)."""

from __future__ import annotations

import argparse
import os
import sys

from util_univ3_quoter import fetch_eth_usd, init_univ3, quoter_ladder_dnx


def main() -> int:
    parser = argparse.ArgumentParser(description="UniV3 quoter ladder for one pool")
    parser.add_argument(
        "--amounts",
        default=os.environ.get("UNIV3_AMOUNTS", "1000,3000,5000,7000,9000"),
        help="Comma-separated DNX token amounts",
    )
    parser.add_argument(
        "--mexc-symbol",
        default=os.environ.get("MEXC_SYMBOL", "DNXUSDT"),
        help="Optional MEXC symbol for mid compare",
    )
    parser.add_argument("--compare-mexc", action="store_true")
    args = parser.parse_args()

    amounts = [int(x.strip()) for x in args.amounts.split(",") if x.strip()]
    try:
        web3, uniswap, pool = init_univ3()
        eth_usd = fetch_eth_usd()
    except Exception as exc:
        print(f"FAIL init: {exc}", file=sys.stderr)
        return 1

    ladder = quoter_ladder_dnx(web3, uniswap, pool, eth_usd, amounts)
    mexc_mid = None
    if args.compare_mexc:
        from util_univ3_quoter import fetch_cex_mids

        bid, ask, _, _ = fetch_cex_mids(args.mexc_symbol, "DNX_USDT")
        if bid and ask:
            mexc_mid = (bid + ask) / 2

    print(f"pool={pool.address} eth_usd={eth_usd}")
    if mexc_mid:
        print(f"mexc_mid({args.mexc_symbol})={mexc_mid}")
    print(f"{'DNX':>8}  {'buy':>10}  {'sell':>10}  {'vs_mexc':>10}")
    for amount, prices in sorted(ladder.items()):
        vs = ""
        if mexc_mid:
            spread_buy = ((mexc_mid - prices["buy"]) / prices["buy"]) * 100
            vs = f"{spread_buy:+.2f}%"
        print(f"{amount:8d}  {prices['buy']:10.5f}  {prices['sell']:10.5f}  {vs:>10}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
