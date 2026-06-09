# mexc_api_schema_from_github

**MEXC API message definitions downloaded from GitHub.**

Official source: https://github.com/mexcdevelop/websocket-proto

These `.proto` files describe how MEXC WebSocket messages are structured (orderbook, trades, balance, etc.). Scripts compile them into `generated_proto/` — that folder name stays fixed because monitors depend on it.

| Action | Command |
|--------|---------|
| Re-download from GitHub + recompile | `python3 mexc_proto_auto_setup.py` |

**Plain English:** API blueprint from GitHub, included locally.
