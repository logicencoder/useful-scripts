# useful-scripts

**Private** Logic Encoder repo — personal script toolbox (MEXC/Gate monitors, protobuf helpers, small dev utilities). Public feature map: [useful-scripts-overview](https://github.com/logicencoder/useful-scripts-overview).

**Always run scripts from this directory** (`cd ~/useful_scripts`).

## MEXC API files from GitHub (the two folders that matter)

MEXC WebSocket data is binary. These two folders are the **only** copy you need:

| Folder | Plain English | What it is |
|--------|---------------|------------|
| **`mexc_api_schema_from_github/`** | **API blueprint from GitHub** | 16 `.proto` files from [mexcdevelop/websocket-proto](https://github.com/mexcdevelop/websocket-proto) |
| **`generated_proto/`** | **Python decoder (do not rename)** | 16 `*_pb2.py` — all `mexc_*` scripts import from here |

```text
GitHub  →  mexc_api_schema_from_github/*.proto
              ↓ protoc compile
         generated_proto/*_pb2.py  →  used by monitors
```

Refresh everything: `python3 mexc_proto_auto_setup.py`  
Load in code: `mexc_proto_loader.py` (one import path for every script)

## Folder layout

```
useful_scripts/
├── mexc_*.py              # MEXC exchange tools
├── gate_*.py              # Gate.io tools
├── eth_*.py, dex_*.py     # Chain / DEX
├── mexc_proto_*.py        # Download + compile + inspect GitHub API files
├── protobuf_*.py/.sh      # VS Code fix, pip version downgrade
├── util_*.py              # Small helpers
├── mexc_api_schema_from_github/   # ← API definitions FROM GITHUB (renamed, clear name)
├── generated_proto/               # ← compiled decoders (fixed name — scripts depend on it)
├── config/                # API keys (mexc_keys.json)
├── logs/                  # Runtime logs
├── discord/ docs/ assets/
└── !old/                  # Archived old scripts
```

## MEXC + Gate.io — orderbooks and trades

| Script | What it does | Port |
|--------|----------------|------|
| `mexc_gate_dual_orderbook_dashboard.py` | MEXC + Gate dashboard + arbitrage | `:8017` |
| `mexc_protodepth_tui_single.py` | Single-symbol orderbook (terminal UI) | — |
| `mexc_protodepth_tui_multi.py` | Multi-symbol orderbook (terminal UI) | — |
| `mexc_protodepth_web_dashboard.py` | Web orderbook dashboard | `:8010` |
| `gate_orderbook_terminal.py` | Gate orderbook → terminal | — |
| `mexc_ws_depth_and_trades.py` | MEXC depth + trades | — |
| `mexc_trades_fetcher_v3.py` | MEXC trades + logging | — |
| `gate_trades_fetcher.py` | Gate trades + logging | — |

## MEXC — balance and orders

| Script | What it does |
|--------|----------------|
| `mexc_balance_monitor_v3.py` | Balance monitor |
| `mexc_balance_monitor_v3_textual.py` | Balance monitor (Textual UI) |
| `mexc_listen_key_checker.py` | Listen key check |
| `mexc_ensure_single_buy_order.py` | Single buy order guard |
| `mexc_single_immediate_buy.py` | Immediate buy |
| `mexc_dynamic_avgbuy.py` | Dynamic avg buy |

## GitHub API setup scripts

| Script | What it does |
|--------|----------------|
| `mexc_proto_auto_setup.py` | Download from GitHub → `mexc_api_schema_from_github/` → compile → `generated_proto/` |
| `mexc_proto_loader.py` | Single loader for all monitors |
| `mexc_proto_inspector.py` | Check folders and imports |
| `protobuf_vscode_import_fix.py` | VS Code import paths |
| `protobuf_downgrade_to_3_20.sh` | pip protobuf downgrade for old protoc |

## Quick start

```bash
cd ~/useful_scripts

# First time or after MEXC API update on GitHub:
python3 mexc_proto_auto_setup.py

# Run monitors:
python3 mexc_gate_dual_orderbook_dashboard.py
python3 mexc_protodepth_tui_single.py
```

https://logicencoder.com
