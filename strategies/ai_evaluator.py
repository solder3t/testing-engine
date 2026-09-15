"""
strategies/ai_evaluator.py — Replay and Counterfactual Evaluator for AI Snapshots.

Replays recorded Gemini AI decisions from trade.db, evaluating performance
across different confidence thresholds and execution rules.
"""

from typing import Dict, List, Any, Optional
import json
import logging

from execution.order import OrderSide, InstrumentType
from execution.portfolio import Portfolio
from strategies.base_strategy import BaseStrategy
from data.data_loader import DataLoader

logger = logging.getLogger("ai_evaluator")


class AiSnapshotStrategy(BaseStrategy):
    """Replays and evaluates the 2,800+ recorded Gemini AI decisions."""

    def __init__(self, params: Optional[Dict[str, Any]] = None, data_loader: Optional[Any] = None):
        # Support either order of parameters or dictionary as first argument
        if isinstance(params, DataLoader):
            actual_loader = params
            actual_params = data_loader
        elif isinstance(data_loader, dict) and params is None:
            actual_params = data_loader
            actual_loader = None
        else:
            actual_params = params
            actual_loader = data_loader

        default_params = {
            "min_confidence": 0.70,
            "allow_breakout_mode": True
        }
        if actual_params and isinstance(actual_params, dict):
            default_params.update(actual_params)
        super().__init__(name="AiSnapshotEvaluator", params=default_params)

        self.data_loader = actual_loader if isinstance(actual_loader, DataLoader) else DataLoader()
        self.snapshots_by_time: Dict[str, Dict] = {}

    def on_session_start(self, date_str: str, portfolio: Portfolio, context: Dict[str, Any]):
        if context and "data_loader" in context and isinstance(context["data_loader"], DataLoader):
            self.data_loader = context["data_loader"]
        self.snapshots_by_time.clear()
        df_ai = self.data_loader.get_ai_snapshots(date_str)
        if df_ai.empty:
            return

        for _, row in df_ai.iterrows():
            ts = str(row["snapshot_time"])
            action = str(row.get("parsed_action", "NONE"))
            conf = float(row.get("parsed_confidence") or 0.0)
            sig_raw = row.get("parsed_signal_json")
            sig_dict = {}
            if sig_raw and isinstance(sig_raw, str):
                try:
                    sig_dict = json.loads(sig_raw)
                except Exception:
                    pass

            self.snapshots_by_time[ts] = {
                "action": action,
                "confidence": conf,
                "bias": str(row.get("parsed_bias", "NEUTRAL")),
                "reasoning": str(row.get("parsed_reasoning", "")),
                "signal": sig_dict,
                "nifty_ltp": float(row.get("nifty_ltp") or 0.0)
            }

    def on_bar(
        self,
        timestamp: str,
        quotes: Dict[str, Dict],
        portfolio: Portfolio,
        context: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        # Search for any action within this minute, prioritizing ENTER
        snap = None
        for snap_ts, s in self.snapshots_by_time.items():
            if snap_ts.startswith(timestamp[:16]):
                if s["action"] == "ENTER" or snap is None:
                    snap = s
                if s["action"] == "ENTER":
                    break

        if not snap:
            return []

        action = snap["action"]
        conf = snap["confidence"]

        if action == "ENTER" and conf >= self.params["min_confidence"]:
            sig = snap["signal"]
            opt_type = sig.get("option_type", "CE")
            strike = sig.get("strike")
            entry_range = sig.get("entry_price_range", [100.0, 110.0])
            entry_price = float(entry_range[0] if isinstance(entry_range, list) else 100.0)
            sl = float(sig.get("stop_loss", entry_price - 15.0))
            tgt = float(sig.get("target", entry_price + 25.0))

            strike_val = float(strike) if strike else 23250.0
            symbol = f"NIFTY-{int(strike_val)}-{opt_type}"

            return [{
                "symbol": symbol,
                "security_id": 0,
                "side": OrderSide.BUY,
                "price": entry_price,
                "sl": sl,
                "target": tgt,
                "score": int(conf * 100),
                "instrument_type": InstrumentType.OPTION_CE if opt_type == "CE" else InstrumentType.OPTION_PE,
                "metadata": {
                    "strike": strike_val,
                    "option_type": opt_type,
                    "reasoning": snap["reasoning"],
                    "confidence": conf,
                    "strategy": self.name
                }
            }]

        return []

    def on_session_end(self, date_str: str, portfolio: Portfolio, context: Dict[str, Any]):
        self.snapshots_by_time.clear()
