"""
analytics/trade_exporter.py — Exports Trades to CSV, SQLite, and JSON.
"""

import os
import json
import sqlite3
from typing import List, Dict, Any
import pandas as pd

from execution.order import Trade


class TradeExporter:
    """Exports trades and backtest run summaries."""

    @staticmethod
    def to_dataframe(trades: List[Trade]) -> pd.DataFrame:
        if not trades:
            return pd.DataFrame()

        records = []
        for t in trades:
            records.append({
                "trade_id": t.trade_id,
                "symbol": t.symbol,
                "security_id": t.security_id,
                "instrument_type": getattr(t.instrument_type, "value", str(t.instrument_type)),
                "side": getattr(t.side, "value", str(t.side)),
                "qty": t.qty,
                "entry_time": t.entry_time,
                "entry_price": t.entry_price,
                "exit_time": t.exit_time,
                "exit_price": t.exit_price,
                "exit_reason": t.exit_reason,
                "initial_sl": t.initial_sl,
                "target": t.target,
                "gross_pnl": t.gross_pnl,
                "charges": t.charges,
                "charges_breakdown": t.metadata.get("charges_breakdown", {}),
                "net_pnl": t.net_pnl,
                "pnl_pct": t.pnl_pct,
                "holding_bars": t.holding_bars,
                "status": t.status,
                "metadata": t.metadata
            })
        return pd.DataFrame(records)

    @classmethod
    def export_csv(cls, trades: List[Trade], file_path: str):
        df = cls.to_dataframe(trades)
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        df.to_csv(file_path, index=False)

    @classmethod
    def export_json(cls, result_dict: Dict[str, Any], file_path: str):
        from dataclasses import asdict, is_dataclass
        from enum import Enum

        def _json_serializer(obj):
            if is_dataclass(obj):
                return asdict(obj)
            if isinstance(obj, Enum):
                return obj.value
            return str(obj)

        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, "w") as f:
            json.dump(result_dict, f, default=_json_serializer, indent=2)

    @classmethod
    def export_sqlite(cls, trades: List[Trade], db_path: str, table_name: str = "backtest_trades"):
        df = cls.to_dataframe(trades)
        if df.empty:
            return
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        with sqlite3.connect(db_path) as conn:
            df.to_sql(table_name, conn, if_exists="replace", index=False)
