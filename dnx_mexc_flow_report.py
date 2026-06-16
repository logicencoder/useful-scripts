#!/usr/bin/env python3
"""SQLite IN/OUT flow report for dnx-mexc-in-out without interactive menu."""

from __future__ import annotations

import argparse
import os
import sqlite3
import sys
from pathlib import Path


def _print_rows(title: str, rows: list) -> None:
    print(f"\n=== {title} ({len(rows)} rows) ===")
    if not rows:
        print("  (empty)")
        return
    for row in rows:
        print("  " + " | ".join(str(x) for x in row))


def main() -> int:
    parser = argparse.ArgumentParser(description="DNX MEXC flow SQLite report")
    parser.add_argument(
        "--db",
        default=os.environ.get("DNX_MEXC_DB", ""),
        help="Path to mexc_monitor.db",
    )
    parser.add_argument("--period", choices=("hourly", "daily", "weekly"), default="daily")
    parser.add_argument("--limit", type=int, default=14)
    parser.add_argument("--recent-tx", type=int, default=10)
    args = parser.parse_args()

    db_path = Path(args.db or "").expanduser()
    if not db_path.is_file():
        default = Path.home() / "githelper" / "dnx-mexc-in-out" / "mexc_monitor.db"
        if default.is_file():
            db_path = default
        else:
            print(f"DB not found: {args.db or db_path}", file=sys.stderr)
            return 2

    table_map = {
        "hourly": ("mexc_hourly_stats", "hour"),
        "daily": ("mexc_daily_stats", "date"),
        "weekly": ("mexc_weekly_stats", "week"),
    }
    table, time_field = table_map[args.period]

    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        cur.execute(
            f"""
            SELECT {time_field}, total_in, total_out, net_flow, tx_count_in, tx_count_out
            FROM {table}
            ORDER BY {time_field} DESC
            LIMIT ?
            """,
            (args.limit,),
        )
        _print_rows(f"{args.period} stats", cur.fetchall())

        cur.execute(
            """
            SELECT timestamp, block_number, direction, amount, substr(other_address,1,16), substr(tx_hash,1,16)
            FROM mexc_transactions
            ORDER BY block_number DESC, id DESC
            LIMIT ?
            """,
            (args.recent_tx,),
        )
        _print_rows("recent transactions", cur.fetchall())

        cur.execute("SELECT COUNT(*) FROM mexc_transactions")
        total_tx = cur.fetchone()[0]
        cur.execute("SELECT MAX(block_number) FROM scanned_blocks")
        max_block = cur.fetchone()[0]
        print(f"\nSUMMARY: db={db_path} total_tx={total_tx} max_scanned_block={max_block}")
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
