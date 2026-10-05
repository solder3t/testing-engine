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
    def to_dataframe(trades: Any) -> pd.DataFrame:
        if not trades:
            return pd.DataFrame()

        records = []
        for t in trades:
            records.append({
                "trade_id": getattr(t, "trade_id", ""),
                "symbol": getattr(t, "symbol", ""),
                "security_id": getattr(t, "security_id", 0),
                "instrument_type": getattr(getattr(t, "instrument_type", ""), "value", str(getattr(t, "instrument_type", ""))),
                "side": getattr(getattr(t, "side", ""), "value", str(getattr(t, "side", ""))),
                "qty": getattr(t, "qty", getattr(t, "quantity", 0)),
                "entry_time": getattr(t, "entry_time", ""),
                "entry_price": getattr(t, "entry_price", 0.0),
                "exit_time": getattr(t, "exit_time", ""),
                "exit_price": getattr(t, "exit_price", 0.0),
                "exit_reason": getattr(t, "exit_reason", ""),
                "initial_sl": getattr(t, "initial_sl", 0.0),
                "target": getattr(t, "target", 0.0),
                "gross_pnl": getattr(t, "gross_pnl", getattr(t, "pnl_gross", 0.0)),
                "charges": getattr(t, "charges", 0.0),
                "charges_breakdown": (getattr(t, "metadata", None) or {}).get("charges_breakdown", {}),
                "net_pnl": getattr(t, "net_pnl", getattr(t, "pnl_net", 0.0)),
                "pnl_pct": getattr(t, "pnl_pct", 0.0),
                "mfe_pts": getattr(t, "mfe_pts", 0.0),
                "mfe_pct": getattr(t, "mfe_pct", 0.0),
                "mae_pts": getattr(t, "mae_pts", 0.0),
                "mae_pct": getattr(t, "mae_pct", 0.0),
                "holding_bars": getattr(t, "holding_bars", 0),
                "status": getattr(t, "status", ""),
                "metadata": getattr(t, "metadata", None) or {}
            })
        return pd.DataFrame(records)

    @classmethod
    def export_csv(cls, trades: Any, file_path: str):
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
