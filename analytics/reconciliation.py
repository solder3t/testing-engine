"""
analytics/reconciliation.py — Live vs Simulated Execution Reconciliation Engine.

Analyzes execution drift, slippage, latency, exit timing realization, and
signal omission (missed vs unprompted trades) between live/paper recordings
in trade.db and the testing-engine backtest simulations.
"""

import math
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional, Union
import pandas as pd

from data.data_loader import DataLoader
from execution.order import Trade
from engine.backtest_engine import BacktestEngine
from strategies.trading_engine_v4 import TradingEngineV4Strategy

logger = logging.getLogger("reconciliation")


def parse_datetime(dt_val: Any) -> Optional[datetime]:
    """Parse various datetime representations into a datetime object."""
    if dt_val is None or pd.isna(dt_val):
        return None
    if isinstance(dt_val, datetime):
        return dt_val
    s = str(dt_val).strip()
    if not s:
        return None
    # Handle ISO format with timezone or standard YYYY-MM-DD HH:MM:SS
    s_clean = s.split("+")[0].split(".")[0].replace("T", " ")
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y_%m_%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(s_clean, fmt)
        except ValueError:
            continue
    return None


class ReconciliationEngine:
    """
    Reconciles live/paper recorded trades against backtest simulation trades.
    """

    def __init__(self, data_loader: Optional[DataLoader] = None):
        self.data_loader = data_loader or DataLoader()

    def run_reconciliation(
        self,
        date_str: str,
        sim_trades: Optional[List[Union[Trade, Dict[str, Any]]]] = None,
        strategy_params: Optional[Dict[str, Any]] = None,
        symbols: Optional[List[str]] = None,
        max_entry_diff_seconds: int = 1800,  # 30 min matching window
    ) -> Dict[str, Any]:
        """
        Reconciles live trades from trade.db against simulated trades for a date.
        If sim_trades is None, runs BacktestEngine with TradingEngineV4Strategy.
        """
        live_df = self.data_loader.get_recorded_trades(date_str)
        live_trades = self._normalize_live_trades(live_df)

        if sim_trades is None:
            # Auto-infer symbols from live trades if not provided
            if symbols is None:
                has_nifty_options = any(
                    "NIFTY" in str(t.get("symbol", "")).upper() for t in live_trades
                )
                if has_nifty_options or not live_trades:
                    symbols = ["NIFTY"]
                else:
                    symbols = list({str(t.get("symbol", "")) for t in live_trades if t.get("symbol")})

            sim_trades = self._run_simulation_for_date(date_str, strategy_params, symbols=symbols)

        normalized_sim = self._normalize_sim_trades(sim_trades)
        return self.reconcile(live_trades, normalized_sim, max_entry_diff_seconds=max_entry_diff_seconds)

    def reconcile(
        self,
        live_trades: List[Dict[str, Any]],
        sim_trades: List[Dict[str, Any]],
        max_entry_diff_seconds: int = 1800,
    ) -> Dict[str, Any]:
        """
        Pairs live trades with simulated trades and computes execution drift.
        """
        matched_pairs: List[Dict[str, Any]] = []
        unmatched_live: List[Dict[str, Any]] = []
        matched_sim_indices = set()

        for live in live_trades:
            live_entry_dt = parse_datetime(live.get("entry_time"))
            best_sim_idx = None
            best_diff = float("inf")

            for idx, sim in enumerate(sim_trades):
                if idx in matched_sim_indices:
                    continue

                sim_entry_dt = parse_datetime(sim.get("entry_time"))
                if not live_entry_dt or not sim_entry_dt:
                    continue

                # Check date match
                if live_entry_dt.date() != sim_entry_dt.date():
                    continue

                # Check side alignment if present
                live_side = str(live.get("side", "")).upper()
                sim_side = str(sim.get("side", "")).upper()
                if live_side and sim_side and live_side != sim_side:
                    continue

                # Check symbol / strike matching:
                # Option symbols may match exactly or strike/type match
                live_sym = str(live.get("symbol", "")).upper()
                sim_sym = str(sim.get("symbol", "")).upper()
                symbol_compatible = (
                    live_sym == sim_sym
                    or ("NIFTY" in live_sym and "NIFTY" in sim_sym)
                    or not live_sym
                    or not sim_sym
                )
                if not symbol_compatible:
                    continue

                diff_seconds = abs((live_entry_dt - sim_entry_dt).total_seconds())
                if diff_seconds <= max_entry_diff_seconds and diff_seconds < best_diff:
                    best_diff = diff_seconds
                    best_sim_idx = idx

            if best_sim_idx is not None:
                matched_sim_indices.add(best_sim_idx)
                sim_match = sim_trades[best_sim_idx]
                sim_entry_dt = parse_datetime(sim_match.get("entry_time"))

                latency_sec = (
                    (live_entry_dt - sim_entry_dt).total_seconds()
                    if live_entry_dt and sim_entry_dt
                    else 0.0
                )

                live_entry_p = float(live.get("entry_price") or 0.0)
                sim_entry_p = float(sim_match.get("entry_price") or 0.0)
                entry_slippage_rs = round(live_entry_p - sim_entry_p, 2)
                entry_slippage_pct = (
                    round((entry_slippage_rs / sim_entry_p) * 100, 2)
                    if sim_entry_p > 0
                    else 0.0
                )

                live_exit_p = float(live.get("exit_price") or 0.0)
                sim_exit_p = float(sim_match.get("exit_price") or 0.0)
                exit_drift_rs = round(live_exit_p - sim_exit_p, 2)

                live_pnl = float(live.get("net_pnl") or 0.0)
                sim_pnl = float(sim_match.get("net_pnl") or 0.0)
                pnl_variance = round(live_pnl - sim_pnl, 2)

                # Execution efficiency: 100 max, penalized by slippage %, latency, and exit alignment
                slip_penalty = min(40.0, abs(entry_slippage_pct) * 5.0)
                latency_penalty = min(30.0, abs(latency_sec) / 30.0)  # 30s latency = 1pt penalty
                pnl_pen = 0.0
                if sim_pnl > 0 and live_pnl < sim_pnl:
                    pnl_pen = min(30.0, ((sim_pnl - live_pnl) / abs(sim_pnl)) * 20.0)
                eff_score = max(0.0, round(100.0 - slip_penalty - latency_penalty - pnl_pen, 1))

                matched_pairs.append({
                    "live_trade": live,
                    "sim_trade": sim_match,
                    "latency_seconds": round(latency_sec, 1),
                    "entry_slippage_rs": entry_slippage_rs,
                    "entry_slippage_pct": entry_slippage_pct,
                    "exit_drift_rs": exit_drift_rs,
                    "pnl_variance": pnl_variance,
                    "execution_efficiency": eff_score,
                    "exit_reason_match": live.get("exit_reason") == sim_match.get("exit_reason"),
                })
            else:
                unmatched_live.append(live)

        unmatched_sim = [
            sim for idx, sim in enumerate(sim_trades) if idx not in matched_sim_indices
        ]

        # Aggregate Metrics
        total_live_pnl = round(sum(float(t.get("net_pnl") or 0.0) for t in live_trades), 2)
        total_sim_pnl = round(sum(float(t.get("net_pnl") or 0.0) for t in sim_trades), 2)
        matched_live_pnl = round(
            sum(float(p["live_trade"].get("net_pnl") or 0.0) for p in matched_pairs), 2
        )
        matched_sim_pnl = round(
            sum(float(p["sim_trade"].get("net_pnl") or 0.0) for p in matched_pairs), 2
        )

        avg_slippage_rs = (
            round(sum(p["entry_slippage_rs"] for p in matched_pairs) / len(matched_pairs), 2)
            if matched_pairs
            else 0.0
        )
        avg_slippage_pct = (
            round(sum(p["entry_slippage_pct"] for p in matched_pairs) / len(matched_pairs), 2)
            if matched_pairs
            else 0.0
        )
        avg_latency_sec = (
            round(sum(p["latency_seconds"] for p in matched_pairs) / len(matched_pairs), 1)
            if matched_pairs
            else 0.0
        )
        avg_efficiency = (
            round(sum(p["execution_efficiency"] for p in matched_pairs) / len(matched_pairs), 1)
            if matched_pairs
            else 100.0 if not live_trades else 0.0
        )

        return {
            "summary": {
                "total_live_trades": len(live_trades),
                "total_sim_trades": len(sim_trades),
                "matched_count": len(matched_pairs),
                "missed_signals_count": len(unmatched_sim),  # Signaled in sim but not executed live
                "unprompted_live_count": len(unmatched_live),  # Executed live without sim signal
                "total_live_pnl": total_live_pnl,
                "total_sim_pnl": total_sim_pnl,
                "matched_live_pnl": matched_live_pnl,
                "matched_sim_pnl": matched_sim_pnl,
                "net_pnl_drift": round(total_live_pnl - total_sim_pnl, 2),
                "avg_entry_slippage_rs": avg_slippage_rs,
                "avg_entry_slippage_pct": avg_slippage_pct,
                "avg_latency_seconds": avg_latency_sec,
                "overall_execution_efficiency": avg_efficiency,
            },
            "matched_pairs": matched_pairs,
            "missed_signals": unmatched_sim,
            "unprompted_live": unmatched_live,
        }

    def _normalize_live_trades(self, live_df: pd.DataFrame) -> List[Dict[str, Any]]:
        """Normalizes live trades dataframe from trade.db into standard dicts."""
        if live_df.empty:
            return []

        trades = []
        for _, row in live_df.iterrows():
            entry_p = (
                row.get("entry_premium")
                if pd.notna(row.get("entry_premium"))
                else row.get("entry_price", 0.0)
            )
            exit_p = (
                row.get("exit_premium")
                if pd.notna(row.get("exit_premium"))
                else row.get("exit_price", 0.0)
            )
            pnl = (
                row.get("pnl_net_rs")
                if pd.notna(row.get("pnl_net_rs"))
                else row.get("pnl", 0.0)
            )
            qty = row.get("quantity") or (
                int(row.get("lots", 1)) * int(row.get("lot_size", 65))
                if pd.notna(row.get("lots"))
                else 65
            )

            trades.append({
                "trade_id": str(row.get("id", "")),
                "symbol": str(row.get("symbol", "")),
                "side": str(row.get("direction") or row.get("action") or "BUY").upper(),
                "entry_time": str(row.get("entry_time") or row.get("open_time") or ""),
                "entry_price": float(entry_p or 0.0),
                "exit_time": str(row.get("exit_time") or row.get("close_time") or ""),
                "exit_price": float(exit_p or 0.0) if pd.notna(exit_p) else None,
                "net_pnl": float(pnl or 0.0) if pd.notna(pnl) else 0.0,
                "qty": int(qty or 0),
                "exit_reason": str(row.get("exit_reason", "")),
                "duration_seconds": int(row.get("duration_seconds") or 0)
                if pd.notna(row.get("duration_seconds"))
                else 0,
                "gemini_confidence": float(row.get("gemini_confidence") or 0.0)
                if pd.notna(row.get("gemini_confidence"))
                else None,
                "gemini_bias": str(row.get("gemini_bias", ""))
                if pd.notna(row.get("gemini_bias"))
                else None,
            })
        return trades

    def _normalize_sim_trades(
        self, sim_trades: List[Union[Trade, Dict[str, Any]]]
    ) -> List[Dict[str, Any]]:
        """Converts Trade objects or dicts into standard comparison dicts."""
        out = []
        for t in sim_trades:
            if hasattr(t, "to_dict"):
                d = t.to_dict()
            elif isinstance(t, dict):
                d = t
            else:
                continue

            entry_p = float(d.get("entry_price") or 0.0)
            exit_p = float(d.get("exit_price") or 0.0) if d.get("exit_price") is not None else None
            out.append({
                "trade_id": str(d.get("trade_id", "")),
                "symbol": str(d.get("symbol", "")),
                "side": str(d.get("side", "BUY")).upper(),
                "entry_time": str(d.get("entry_time", "")),
                "entry_price": entry_p,
                "exit_time": str(d.get("exit_time", "")),
                "exit_price": exit_p,
                "net_pnl": float(d.get("net_pnl") or 0.0),
                "qty": int(d.get("qty") or 0),
                "exit_reason": str(d.get("exit_reason", "")),
                "holding_bars": int(d.get("holding_bars") or 0),
                "metadata": d.get("metadata", {}),
            })
        return out

    def _run_simulation_for_date(
        self,
        date_str: str,
        strategy_params: Optional[Dict[str, Any]] = None,
        symbols: Optional[List[str]] = None,
    ) -> List[Trade]:
        """Runs BacktestEngine with TradingEngineV4Strategy for the specified date."""
        params = strategy_params or {}
        strategy = TradingEngineV4Strategy(params=params)
        engine = BacktestEngine(
            data_loader=self.data_loader,
            capital=100000.0,
        )
        try:
            target_symbols = symbols or ["NIFTY"]
            results = engine.run_session(date_str=date_str, strategy=strategy, symbols=target_symbols)
            return results.get("trades", [])
        except Exception as e:
            logger.error(f"Error running simulation for {date_str}: {e}")
            return []
