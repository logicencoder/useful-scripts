# useful-scripts — architecture

Private Logic Encoder personal toolbox. Not a deployed product — scripts run manually from WSL or SOL under `~/useful_scripts` (WSL) or `/home/sol/lojzo/useful_scripts` (SOL prod host).

https://logicencoder.com

## Layout

```
useful_scripts/
├── mexc_*.py, gate_*.py     # Exchange monitors and trading helpers
├── eth_*.py, dex_*.py       # Chain utilities
├── mexc_proto_*.py          # MEXC GitHub API schema download + compile + inspect
├── protobuf_*.py/.sh        # Tooling (VS Code paths, pip protobuf downgrade)
├── util_*.py                # Generic CLI/terminal helpers
├── mexc_api_schema_from_github/   # 16× .proto from mexcdevelop/websocket-proto
├── generated_proto/               # 16× *_pb2.py — fixed path; all monitors import here
├── mexc_proto_loader.py           # Single Python import entry for monitors
├── config/                        # mexc_keys.json (gitignored), example template
├── !old/                          # Superseded script names and backup snapshots
├── discord/, docs/, assets/
└── logs/ (gitignored)
```

## MEXC protobuf pipeline

1. **Sources:** `mexc_api_schema_from_github/*.proto` downloaded from  
   `https://github.com/mexcdevelop/websocket-proto`
2. **Compile:** `mexc_proto_auto_setup.py` runs `protoc` → `generated_proto/*_pb2.py`
3. **Load:** `mexc_proto_loader.py` sets `PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python`, adds `generated_proto/` to `sys.path`, imports wrapper + depth/account modules
4. **Do not rename** `generated_proto/` — every monitor depends on that directory name

## Active monitors (canonical scripts)

| Script | Role | Default port |
|--------|------|--------------|
| `mexc_gate_dual_orderbook_dashboard.py` | FastAPI MEXC+Gate depth + arbitrage UI | 8017 |
| `mexc_protodepth_tui_single.py` | Textual TUI single-symbol depth | — |
| `mexc_protodepth_tui_multi.py` | Textual TUI multi-symbol depth | — |
| `mexc_protodepth_web_dashboard.py` | FastAPI web depth | 8010 |
| `gate_orderbook_terminal.py` | Gate WS depth → terminal | — |
| `mexc_ws_depth_and_trades.py` | MEXC depth + trades asyncio | — |
| `mexc_trades_fetcher_v3.py` | MEXC agg trades + file log | — |
| `gate_trades_fetcher.py` | Gate trades + file log | — |
| `mexc_balance_monitor_v3.py` | Private WS balance (protobuf) | — |
| `mexc_balance_monitor_v3_textual.py` | Balance monitor Textual UI | — |

## Configuration

| File | Purpose |
|------|---------|
| `config/mexc_keys.json` | MEXC API key + secret (never commit) |
| `config/mexc_keys.example.json` | Template |

Scripts must be started with cwd = repo root so `generated_proto/`, `config/`, and `logs/` resolve.

## Archive policy (`!old/`)

Older naming (`protodepth_20_1a`, `bal_mon_mexc_*`, `mexc_depth_*`, `scripts_backup_20250806_043439/`) kept for reference. Mapping table in `!old/README.md`. Do not run archived scripts unless recovering an old port (e.g. 8007).

## Environments

| Host | Path | Notes |
|------|------|-------|
| WSL dev | `/home/lojzo/useful_scripts` | Primary edit target |
| SOL | `/home/sol/lojzo/useful_scripts` | Synced from WSL; preserves `data/dex_monitor.db` and prod keys |

## Dependencies (typical)

Python 3.10+, `orjson`, `websocket-client` or `websockets`, `fastapi`+`uvicorn` (dashboards), `textual` (TUI), `protobuf`, system `protoc`. Some scripts auto-`pip install` missing packages.

## Security

- API keys only in `config/mexc_keys.json` (gitignored)
- Private GitHub repo — no keys in overview repo
- Dashboards bind `0.0.0.0` — firewall/tunnel discipline on SOL
