#!/usr/bin/env python3
"""DNX CEX vs UniV3 spread board — lightweight terminal refresh loop."""

from __future__ import annotations

import argparse
import os
import sys
import time

try:
    from colorama import Fore, Style, init as colorama_init
except ImportError:
    Fore = Style = None  # type: ignore

    def colorama_init() -> None:
        return None

from util_univ3_quoter import (
    fetch_cex_mids,
    fetch_eth_usd,
    init_univ3,
    quoter_ladder_dnx,
)


def _c(text: str, color: str) -> str:
    if Fore is None:
        return text
    return f"{color}{text}{Style.RESET_ALL}"


def render_once(
    mexc_symbol: str,
    gate_pair: str,
    amounts: list[int],
    web3,
    uniswap,
    pool,
    eth_usd,
) -> None:
    mexc_bid, mexc_ask, gate_bid, gate_ask = fetch_cex_mids(mexc_symbol, gate_pair)
    ladder = quoter_ladder_dnx(web3, uniswap, pool, eth_usd, amounts)

    print(_c(f"DNX spread board  eth=${eth_usd}", Fore.CYAN))
    print(
        f"MEXC {mexc_symbol}: bid={mexc_bid} ask={mexc_ask}   "
        f"Gate {gate_pair}: bid={gate_bid} ask={gate_ask}"
    )
    print(f"{'amt':>6}  {'uni_buy':>9}  {'uni_sell':>9}  {'mexc_sell→uni_buy':>18}")
    for amount in amounts:
        prices = ladder[amount]
        edge = ""
        if mexc_ask and prices["buy"]:
            pct = ((mexc_ask - prices["buy"]) / prices["buy"]) * 100
            edge = f"{pct:+.2f}%"
            if pct > 0.3:
                edge = _c(edge + " CEX→DEX", Fore.GREEN)
        print(
            f"{amount:6d}  {prices['buy']:9.5f}  {prices['sell']:9.5f}  {edge:>18}"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="DNX CEX/DEX spread terminal board")
    parser.add_argument("--mexc-symbol", default=os.environ.get("MEXC_SYMBOL", "DNXUSDT"))
    parser.add_argument("--gate-pair", default=os.environ.get("GATE_PAIR", "DNX_USDT"))
    parser.add_argument(
        "--amounts",
        default=os.environ.get("SPREAD_AMOUNTS", "1000,3000,5000"),
    )
    parser.add_argument("--interval", type=float, default=5.0)
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    amounts = [int(x.strip()) for x in args.amounts.split(",") if x.strip()]

    colorama_init()
    try:
        web3, uniswap, pool = init_univ3()
        eth_usd = fetch_eth_usd()
    except Exception as exc:
        print(f"FAIL init: {exc}", file=sys.stderr)
        return 1

    while True:
        if not args.once:
            print("\033[2J\033[H", end="")
        render_once(
            args.mexc_symbol,
            args.gate_pair,
            amounts,
            web3,
            uniswap,
            pool,
            eth_usd,
        )
        if args.once:
            break
        eth_usd = fetch_eth_usd()
        time.sleep(args.interval)
    return 0


if __name__ == "__main__":
    sys.exit(main())
