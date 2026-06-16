"""Shared UniV3 quoter helpers for operator ladder/spread scripts."""

from __future__ import annotations

import os
from decimal import Decimal
from typing import Dict, List, Tuple

PRICE_ADJUSTMENT = Decimal("1.00444")


def get_http_rpc() -> str:
    return os.environ.get("GETH_HTTP", "http://127.0.0.1:8545")


def get_pool_address() -> str:
    return os.environ.get(
        "UNIV3_POOL",
        "0xa29d18f6a73f6f65c9f0eeae2dd0563d6f615c0f",
    )


def init_univ3():
    from web3 import Web3
    from eth_defi.uniswap_v3.constants import UNISWAP_V3_DEPLOYMENTS
    from eth_defi.uniswap_v3.deployment import fetch_deployment
    from eth_defi.uniswap_v3.pool import fetch_pool_details

    rpc = get_http_rpc()
    web3 = Web3(Web3.HTTPProvider(rpc, request_kwargs={"timeout": 20}))
    if not web3.is_connected():
        raise ConnectionError(f"HTTP RPC unreachable: {rpc}")
    details = UNISWAP_V3_DEPLOYMENTS["ethereum"]
    uniswap = fetch_deployment(
        web3,
        factory_address=details["factory"],
        router_address=details["router"],
        position_manager_address=details["position_manager"],
        quoter_address=details["quoter"],
    )
    pool = fetch_pool_details(web3, get_pool_address())
    return web3, uniswap, pool


def fetch_eth_usd() -> Decimal:
    import json
    import urllib.request

    url = os.environ.get(
        "ETH_USD_URL",
        "https://api.binance.com/api/v3/ticker/price?symbol=ETHUSDT",
    )
    with urllib.request.urlopen(url, timeout=10) as resp:
        data = json.loads(resp.read().decode())
    return Decimal(str(data["price"]))


def quoter_ladder_dnx(
    web3,
    uniswap,
    pool,
    eth_usd: Decimal,
    amounts: List[int],
) -> Dict[int, Dict[str, Decimal]]:
    from eth_defi.uniswap_v3.price import get_onchain_price, estimate_buy_received_amount

    block_num = web3.eth.block_number
    out: Dict[int, Dict[str, Decimal]] = {}
    for amount in amounts:
        mid_price = get_onchain_price(web3, pool.address)
        approx_weth = Decimal(str(amount)) * mid_price
        weth_raw = pool.token1.convert_to_raw(approx_weth)
        dnx_out_raw = estimate_buy_received_amount(
            uniswap=uniswap,
            base_token_address=pool.token0.address,
            quote_token_address=pool.token1.address,
            quantity=weth_raw,
            target_pair_fee=pool.get_fee_bps() * 100,
            block_identifier=block_num,
        )
        dnx_received = pool.token0.convert_to_decimals(dnx_out_raw)
        actual_weth = (approx_weth * Decimal(str(amount))) / dnx_received
        buy_price = (
            (actual_weth / Decimal(str(amount))) * eth_usd * PRICE_ADJUSTMENT
        ).quantize(Decimal("0.00001"))

        sell_amount_raw = pool.token0.convert_to_raw(Decimal(str(amount)))
        weth_out_raw = estimate_buy_received_amount(
            uniswap=uniswap,
            base_token_address=pool.token1.address,
            quote_token_address=pool.token0.address,
            quantity=sell_amount_raw,
            target_pair_fee=pool.get_fee_bps() * 100,
            block_identifier=block_num,
        )
        weth_received = pool.token1.convert_to_decimals(weth_out_raw)
        sell_price = (
            (weth_received / Decimal(str(amount))) * eth_usd / PRICE_ADJUSTMENT
        ).quantize(Decimal("0.00001"))
        out[amount] = {"buy": buy_price, "sell": sell_price}
    return out


def fetch_cex_mids(
    mexc_symbol: str,
    gate_pair: str,
) -> Tuple[Decimal | None, Decimal | None, Decimal | None, Decimal | None]:
    import json
    import urllib.request

    mexc_bid = mexc_ask = gate_bid = gate_ask = None
    try:
        with urllib.request.urlopen(
            f"https://api.mexc.com/api/v3/ticker/bookTicker?symbol={mexc_symbol}",
            timeout=10,
        ) as resp:
            row = json.loads(resp.read().decode())
            mexc_bid = Decimal(str(row["bidPrice"]))
            mexc_ask = Decimal(str(row["askPrice"]))
    except Exception:
        pass
    try:
        with urllib.request.urlopen(
            f"https://api.gateio.ws/api/v4/spot/order_book?currency_pair={gate_pair}&limit=1",
            timeout=10,
        ) as resp:
            row = json.loads(resp.read().decode())
            if row.get("bids"):
                gate_bid = Decimal(str(row["bids"][0][0]))
            if row.get("asks"):
                gate_ask = Decimal(str(row["asks"][0][0]))
    except Exception:
        pass
    return mexc_bid, mexc_ask, gate_bid, gate_ask
