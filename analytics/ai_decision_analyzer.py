"""
analytics/ai_decision_analyzer.py — Gemini AI Decision Evaluation and Counterfactual Analytics.

Analyzes 4,500+ Gemini AI decision snapshots against forward index returns,
evaluates confidence calibration, constructs counterfactual confusion matrices,
determines optimal confidence gating thresholds, and attributes reasoning keywords.
"""

import math
import logging
import re
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
import pandas as pd
import numpy as np

from data.data_loader import DataLoader

logger = logging.getLogger("ai_decision_analyzer")


def parse_snapshot_time(t_val: Any) -> Optional[datetime]:
    """Parse snapshot timestamp string to datetime."""
    if t_val is None or pd.isna(t_val):
        return None
    if isinstance(t_val, datetime):
        return t_val
    s = str(t_val).strip().split("+")[0].split(".")[0].replace("T", " ")
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y_%m_%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


class AIDecisionAnalyzer:
    """
    Evaluates AI decision accuracy, confidence reliability, and counterfactual outcomes.
    """

    def __init__(self, data_loader: Optional[DataLoader] = None):
        self.data_loader = data_loader or DataLoader()

    def analyze_session(
        self,
        date_str: str,
        forward_horizons_min: List[int] = [5, 15, 30, 60],
        confidence_threshold: float = 0.70,
    ) -> Dict[str, Any]:
        """
        Analyzes AI snapshots for a single market session.
        """
        df_snaps = self.data_loader.get_ai_snapshots(date_str)
        if df_snaps.empty:
            return {
                "date": date_str,
                "total_snapshots": 0,
                "summary": {"message": f"No AI snapshots recorded for {date_str}"},
                "calibration": [],
                "counterfactual_matrix": {},
                "optimal_threshold": None,
                "threshold_sweep": [],
                "reasoning_insights": [],
                "decisions": [],
            }

        df_nifty = self.data_loader.get_index_ohlc(date_str, "NIFTY")
        return self._evaluate_snapshots(
            df_snaps=df_snaps,
            df_nifty=df_nifty,
            date_str=date_str,
            forward_horizons_min=forward_horizons_min,
            confidence_threshold=confidence_threshold,
        )

    def analyze_multi_session(
        self,
        date_strings: Optional[List[str]] = None,
        forward_horizons_min: List[int] = [5, 15, 30, 60],
        confidence_threshold: float = 0.70,
    ) -> Dict[str, Any]:
        """
        Aggregates AI snapshot evaluation across multiple dates.
        """
        if date_strings is None:
            date_strings = self.data_loader.get_available_dates()

        all_enriched = []
        date_counts = {}

        for d in date_strings:
            df_snaps = self.data_loader.get_ai_snapshots(d)
            if df_snaps.empty:
                continue
            df_nifty = self.data_loader.get_index_ohlc(d, "NIFTY")
            if df_nifty.empty:
                continue
            date_counts[d] = len(df_snaps)
            enriched_records = self._enrich_snapshots_with_returns(df_snaps, df_nifty, forward_horizons_min)
            all_enriched.extend(enriched_records)

        if not all_enriched:
            return {
                "total_snapshots": 0,
                "sessions_analyzed": 0,
                "summary": {"message": "No AI snapshot data found across requested dates"},
                "calibration": [],
                "counterfactual_matrix": {},
                "optimal_threshold": None,
                "threshold_sweep": [],
                "reasoning_insights": [],
            }

        return self._aggregate_enriched_analytics(
            enriched_records=all_enriched,
            forward_horizons_min=forward_horizons_min,
            confidence_threshold=confidence_threshold,
            sessions_count=len(date_counts),
            date_counts=date_counts,
        )

    def _enrich_snapshots_with_returns(
        self,
        df_snaps: pd.DataFrame,
        df_nifty: pd.DataFrame,
        forward_horizons_min: List[int],
    ) -> List[Dict[str, Any]]:
        """Matches each snapshot with subsequent NIFTY price bars."""
        if df_nifty.empty or "timestamp" not in df_nifty.columns:
            return []

        df_bars = df_nifty.copy()
        df_bars["dt"] = df_bars["timestamp"].apply(parse_snapshot_time)
        df_bars = df_bars.dropna(subset=["dt"]).sort_values("dt").reset_index(drop=True)
        bar_times = df_bars["dt"].tolist()
        bar_closes = df_bars["close"].astype(float).tolist()

        enriched = []

        for _, row in df_snaps.iterrows():
            snap_time = parse_snapshot_time(row.get("snapshot_time"))
            if not snap_time:
                continue

            nifty_ltp = float(row.get("nifty_ltp") or 0.0)
            if nifty_ltp <= 0:
                continue

            action = str(row.get("parsed_action") or "NONE").upper()
            bias = str(row.get("parsed_bias") or "NEUTRAL").upper()
            confidence = float(row.get("parsed_confidence") or 0.0)
            reasoning = str(row.get("parsed_reasoning") or "")
            trigger = str(row.get("trigger_reason") or "")

            # If bias is not explicitly set, infer from action/reasoning
            if bias in ("NEUTRAL", "NONE", ""):
                if action == "ENTER":
                    bias = "BEARISH" if "PE" in reasoning or "PUT" in reasoning else "BULLISH"
                elif "BULLISH" in reasoning.upper():
                    bias = "BULLISH"
                elif "BEARISH" in reasoning.upper():
                    bias = "BEARISH"

            # Compute forward returns at each horizon
            fwd_returns = {}
            fwd_points = {}
            for h in forward_horizons_min:
                target_dt = snap_time + timedelta(minutes=h)
                # Find closest bar at or after target_dt (within 4 minutes tolerance)
                best_idx = None
                for idx, bt in enumerate(bar_times):
                    if bt >= target_dt:
                        if (bt - target_dt).total_seconds() <= 300:
                            best_idx = idx
                        break

                if best_idx is not None:
                    fut_price = bar_closes[best_idx]
                    pts_diff = round(fut_price - nifty_ltp, 2)
                    pct_diff = round((pts_diff / nifty_ltp) * 100, 3)

                    # Directional return: positive if market aligned with bias
                    if bias == "BULLISH":
                        dir_pct = pct_diff
                        dir_pts = pts_diff
                    elif bias == "BEARISH":
                        dir_pct = -pct_diff
                        dir_pts = -pts_diff
                    else:
                        # For neutral/wait: measure absolute market volatility
                        dir_pct = -abs(pct_diff)
                        dir_pts = -abs(pts_diff)

                    fwd_returns[f"{h}m_pct"] = dir_pct
                    fwd_returns[f"{h}m_raw_pct"] = pct_diff
                    fwd_points[f"{h}m_pts"] = dir_pts
                else:
                    fwd_returns[f"{h}m_pct"] = None
                    fwd_returns[f"{h}m_raw_pct"] = None
                    fwd_points[f"{h}m_pts"] = None

            enriched.append({
                "id": str(row.get("id") or ""),
                "snapshot_time": str(row.get("snapshot_time") or ""),
                "trigger_reason": trigger,
                "nifty_ltp": nifty_ltp,
                "action": action,
                "bias": bias,
                "confidence": confidence,
                "reasoning": reasoning,
                "signal_acted_on": int(row.get("signal_acted_on") or 0),
                "returns": fwd_returns,
                "points": fwd_points,
            })

        return enriched

    def _evaluate_snapshots(
        self,
        df_snaps: pd.DataFrame,
        df_nifty: pd.DataFrame,
        date_str: str,
        forward_horizons_min: List[int],
        confidence_threshold: float,
    ) -> Dict[str, Any]:
        enriched = self._enrich_snapshots_with_returns(df_snaps, df_nifty, forward_horizons_min)
        res = self._aggregate_enriched_analytics(
            enriched_records=enriched,
            forward_horizons_min=forward_horizons_min,
            confidence_threshold=confidence_threshold,
            sessions_count=1,
            date_counts={date_str: len(enriched)},
        )
        res["date"] = date_str
        res["decisions"] = enriched[:100]  # sample of individual decisions
        return res

    def _aggregate_enriched_analytics(
        self,
        enriched_records: List[Dict[str, Any]],
        forward_horizons_min: List[int],
        confidence_threshold: float,
        sessions_count: int,
        date_counts: Dict[str, int],
    ) -> Dict[str, Any]:
        total_snaps = len(enriched_records)
        if total_snaps == 0:
            return {"total_snapshots": 0}

        # 1. Action Counts
        action_counts = {}
        for r in enriched_records:
            act = r["action"]
            action_counts[act] = action_counts.get(act, 0) + 1

        # Primary horizon for calibration and matrix (15 minutes default)
        prim_h = "15m_pct" if "15m_pct" in enriched_records[0]["returns"] else f"{forward_horizons_min[0]}m_pct"

        # 2. Confidence Calibration Buckets
        bins = [0.0, 0.3, 0.5, 0.6, 0.7, 0.8, 1.01]
        bin_labels = ["0.0-0.3", "0.3-0.5", "0.5-0.6", "0.6-0.7", "0.7-0.8", "0.8-1.0"]
        calibration = []

        for i in range(len(bins) - 1):
            low, high = bins[i], bins[i + 1]
            bucket_records = [
                r for r in enriched_records if low <= r["confidence"] < high
            ]
            count = len(bucket_records)
            valid_returns = [
                r["returns"][prim_h]
                for r in bucket_records
                if r["returns"].get(prim_h) is not None
            ]
            if valid_returns:
                win_count = sum(1 for ret in valid_returns if ret > 0)
                win_rate = round((win_count / len(valid_returns)) * 100, 1)
                avg_ret = round(float(np.mean(valid_returns)), 3)
            else:
                win_rate = 0.0
                avg_ret = 0.0

            calibration.append({
                "bucket": bin_labels[i],
                "count": count,
                "pct_of_total": round((count / total_snaps) * 100, 1),
                "win_rate": win_rate,
                "avg_return_pct": avg_ret,
                "valid_samples": len(valid_returns),
            })

        # 3. Counterfactual Matrix (Confusion Matrix)
        # Evaluated at confidence_threshold & directional action (ENTER or confidence >= threshold)
        tp, fp, tn, fn = 0, 0, 0, 0
        pnl_taken = []
        pnl_avoided = []

        for r in enriched_records:
            ret = r["returns"].get(prim_h)
            if ret is None:
                continue

            conf = r["confidence"]
            action = r["action"]
            predicted_trade = (action == "ENTER") or (conf >= confidence_threshold and r["bias"] in ("BULLISH", "BEARISH"))

            if predicted_trade:
                pnl_taken.append(ret)
                if ret > 0:
                    tp += 1
                else:
                    fp += 1
            else:
                pnl_avoided.append(ret)
                if ret <= 0:
                    tn += 1
                else:
                    # Missed profitable opportunity
                    fn += 1

        total_eval = tp + fp + tn + fn
        precision = round((tp / (tp + fp)) * 100, 1) if (tp + fp) > 0 else 0.0
        recall = round((tp / (tp + fn)) * 100, 1) if (tp + fn) > 0 else 0.0
        accuracy = round(((tp + tn) / total_eval) * 100, 1) if total_eval > 0 else 0.0
        f1 = (
            round(2 * (precision * recall) / (precision + recall), 1)
            if (precision + recall) > 0
            else 0.0
        )

        valid_taken = [x for x in pnl_taken if x is not None and not math.isnan(x)]
        valid_avoided = [x for x in pnl_avoided if x is not None and not math.isnan(x)]
        counterfactual_matrix = {
            "threshold": confidence_threshold,
            "true_positives": tp,    # AI entered & market won
            "false_positives": fp,   # AI entered & market lost
            "true_negatives": tn,    # AI passed & avoided loss/chop
            "false_negatives": fn,   # AI passed & missed winning move
            "precision": precision,
            "recall": recall,
            "accuracy": accuracy,
            "f1_score": f1,
            "signals_triggered": tp + fp,
            "signals_filtered": tn + fn,
            "avg_trade_pnl_pct": round(float(np.mean(valid_taken)), 3) if valid_taken else 0.0,
            "avg_avoided_move_pct": round(float(np.mean(valid_avoided)), 3) if valid_avoided else 0.0,
        }

        # 4. Threshold Sweep (Optimization for Best Confidence Cutoff)
        threshold_sweep = []
        sweep_values = [0.40, 0.45, 0.50, 0.55, 0.60, 0.65, 0.70, 0.75, 0.80, 0.85]
        best_threshold = 0.70
        best_utility = -float("inf")

        for th in sweep_values:
            th_returns = [
                r["returns"][prim_h]
                for r in enriched_records
                if r["confidence"] >= th
                and r["returns"].get(prim_h) is not None
                and r["bias"] in ("BULLISH", "BEARISH")
            ]
            cnt = len(th_returns)
            if cnt >= 3:
                wins = sum(1 for x in th_returns if x > 0)
                wr = round((wins / cnt) * 100, 1)
                mean_r = float(np.mean(th_returns))
                # Expectancy = win_rate * avg_win - loss_rate * avg_loss
                win_rets = [x for x in th_returns if x > 0]
                loss_rets = [abs(x) for x in th_returns if x < 0]
                avg_win = float(np.mean(win_rets)) if win_rets else 0.0
                avg_loss = float(np.mean(loss_rets)) if loss_rets else 0.0
                expectancy = round(((wr / 100.0) * avg_win) - (((100.0 - wr) / 100.0) * avg_loss), 3)

                # Utility balances expectancy with trade frequency: expectancy * log2(count + 1)
                utility = expectancy * math.log2(cnt + 1)
                if utility > best_utility and cnt >= 5:
                    best_utility = utility
                    best_threshold = th

                threshold_sweep.append({
                    "threshold": th,
                    "trade_count": cnt,
                    "win_rate": wr,
                    "avg_return_pct": round(mean_r, 3),
                    "expectancy_pct": expectancy,
                    "avg_win_pct": round(avg_win, 3),
                    "avg_loss_pct": round(avg_loss, 3),
                })

        # 5. Reasoning Keywords & Pattern Attribution
        keywords = [
            "opening range",
            "vwap",
            "rsi",
            "volume surge",
            "momentum",
            "data age",
            "consolidation",
            "chop",
            "breakout",
            "support",
            "resistance",
            "ema cross",
            "rejection",
        ]
        reasoning_insights = []
        for kw in keywords:
            kw_records = [
                r for r in enriched_records
                if kw in r["reasoning"].lower() and r["returns"].get(prim_h) is not None
            ]
            if len(kw_records) >= 5:
                rets = [r["returns"][prim_h] for r in kw_records]
                wins = sum(1 for x in rets if x > 0)
                wr = round((wins / len(rets)) * 100, 1)
                reasoning_insights.append({
                    "keyword": kw,
                    "occurrences": len(kw_records),
                    "win_rate": wr,
                    "avg_return_pct": round(float(np.mean(rets)), 3),
                    "alpha_rating": "HIGH" if wr >= 60.0 else ("NEUTRAL" if wr >= 45.0 else "POOR"),
                })

        reasoning_insights.sort(key=lambda x: x["occurrences"], reverse=True)

        return {
            "total_snapshots": total_snaps,
            "sessions_analyzed": sessions_count,
            "date_counts": date_counts,
            "action_breakdown": action_counts,
            "primary_horizon": prim_h,
            "summary": {
                "total_decisions": total_snaps,
                "enter_actions": action_counts.get("ENTER", 0),
                "wait_actions": action_counts.get("WAIT", 0),
                "hold_actions": action_counts.get("HOLD", 0),
                "recommended_confidence_threshold": best_threshold,
                "precision_at_threshold": counterfactual_matrix["precision"],
                "accuracy_at_threshold": counterfactual_matrix["accuracy"],
            },
            "calibration": calibration,
            "counterfactual_matrix": counterfactual_matrix,
            "optimal_threshold": best_threshold,
            "threshold_sweep": threshold_sweep,
            "reasoning_insights": reasoning_insights,
        }
