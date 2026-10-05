"""
data/corporate_actions.py — Historical Corporate Actions Adjustment Engine.

Calculates backward-adjustment factors for equities experiencing Stock Splits
and Bonus issues, ensuring unskewed technical indicator values and clean backtests.
"""

import json
from pathlib import Path
from typing import Dict, List, Optional
import pandas as pd


class CorporateActionsManager:
    """
    Loads historical corporate actions from JSON and computes point-in-time
    price and volume adjustment multipliers.
    """

    _registry: Optional[Dict[str, List[Dict]]] = None
    _DEFAULT_JSON_PATH = Path(__file__).resolve().parent / "corporate_actions.json"

    @classmethod
    def load_registry(cls, path: Optional[Path] = None) -> Dict[str, List[Dict]]:
        if cls._registry is not None and path is None:
            return cls._registry

        target_path = path or cls._DEFAULT_JSON_PATH
        if not target_path.exists():
            cls._registry = {}
            return cls._registry

        try:
            with open(target_path, "r", encoding="utf-8") as f:
                cls._registry = json.load(f)
        except Exception:
            cls._registry = {}
        return cls._registry

    @classmethod
    def _normalize_date(cls, date_str: str) -> str:
        """Normalizes date string to YYYY_MM_DD format for lexicographical comparison."""
        d = date_str.split(" ")[0].strip()
        d = d.replace("-", "_").replace("/", "_")
        return d

    @classmethod
    def get_adjustment_factor(cls, symbol: str, date_str: str) -> float:
        """
        Calculates cumulative backward-adjustment factor for historical prices prior to ex-dates.

        Rule:
        - If query date is PRIOR to ex-date:
            * SPLIT A:B -> Price factor = A / B
            * BONUS A:B -> Price factor = A / (A + B) (i.e. B bonus shares given for A held)
        - If query date is ON OR AFTER ex-date:
            * Factor = 1.0 (prices already traded in post-action terms)

        Cumulative factor = product of all subsequent corporate action factors.
        """
        if not symbol or not date_str:
            return 1.0

        registry = cls.load_registry()
        events = registry.get(symbol.upper(), [])
        if not events:
            return 1.0

        norm_date = cls._normalize_date(date_str)
        cumulative_factor = 1.0

        for event in events:
            ex_date = cls._normalize_date(event.get("date", ""))
            if not ex_date:
                continue

            # Corporate action applies to all historical dates strictly prior to ex-date
            if norm_date < ex_date:
                action_type = str(event.get("type", "")).upper()
                ratio_str = str(event.get("ratio", "1:1"))
                parts = [float(p.strip()) for p in ratio_str.split(":") if p.strip()]
                if len(parts) != 2 or parts[1] <= 0:
                    continue
                a, b = parts[0], parts[1]

                if action_type == "SPLIT":
                    # e.g., 1:2 split -> 1 share became 2 -> historical prices halved (factor 0.5)
                    factor = a / b
                elif action_type == "BONUS":
                    # e.g., 1:1 bonus -> 1 bonus for 1 held = total 2 -> factor = 1 / 2 = 0.5
                    factor = a / (a + b)
                else:
                    factor = 1.0

                cumulative_factor *= factor

        return round(cumulative_factor, 6)

    @classmethod
    def adjust_dataframe(cls, df: pd.DataFrame, factor: float) -> pd.DataFrame:
        """
        Applies corporate action adjustment to OHLCV DataFrame in-place or on a copy.
        Multiplies prices by factor; divides volume by factor.
        """
        if df.empty or abs(factor - 1.0) < 1e-6:
            return df

        adjusted = df.copy()
        price_cols = [c for c in ["open", "high", "low", "close", "vwap", "ltp"] if c in adjusted.columns]
        for col in price_cols:
            adjusted[col] = (adjusted[col] * factor).round(2)

        if "volume" in adjusted.columns and factor > 0:
            adjusted["volume"] = (adjusted["volume"] / factor).round(0).astype(int)

        return adjusted


def get_adjustment_factor(symbol: str, date_str: str) -> float:
    return CorporateActionsManager.get_adjustment_factor(symbol, date_str)


def adjust_equity_ohlc(df: pd.DataFrame, symbol: str, date_str: str) -> pd.DataFrame:
    factor = CorporateActionsManager.get_adjustment_factor(symbol, date_str)
    return CorporateActionsManager.adjust_dataframe(df, factor)
