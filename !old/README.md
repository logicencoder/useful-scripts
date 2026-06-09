# Archive

Superseded script versions. Kept for reference — prefer the renamed scripts in the parent directory.

| Old file | Replaced by |
|----------|-------------|
| `mexc_depth_1aaaa_OK.py` | `mexc_gate_dual_orderbook_dashboard.py` (port 8017) |
| `mexc_depth_1a.py` … `1aaaaa.py` | Same family, older iterations (port 8007) |
| `multi_orderbook_mexc_and_gate_ok_1a.py` | Duplicate of `mexc_depth_1a.py` |
| `protodepth_20_1a.py` … `1aaa.py` | `mexc_protodepth_tui_single.py` |
| `bal_mon_mexc_V3_ok_1aaa.py` etc. | `mexc_balance_monitor_v3.py` |
| `ws_depth_trades_ok_1a.py`, `1b.py` | `mexc_ws_depth_and_trades.py` |
| `multi_gate_ws_orderbook_1a.py` | `gate_orderbook_terminal.py` |
| `base_fetchrealtime_trades_MEXC_API_V3_ok.py` | `mexc_trades_fetcher_v3.py` |
| `base_fetchrealtime_trades_gate1.py` | `gate_trades_fetcher.py` |
| `scripts_backup_20250806_043439/` | Full snapshot from 2025-08-06 |
| `protobuf_checker_and_fix.py` | `mexc_proto_auto_setup.py` + `mexc_proto_inspector.py` |
| `protobuf_aggressive_fix.py`, `protobuf_version_fix.py` | Superseded fixers |
| `mexc_proto_manual_setup.py` | Use `mexc_proto_auto_setup.py` |
| `mexc_protodepth_archive.zip` | Old script bundle (replaced by `mexc_protodepth_tui_single.py`) |

Archived scripts still expect `mexc_keys.json` in the repo root (old path). Active scripts use `config/mexc_keys.json`.
