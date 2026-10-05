"""
analytics/matrix_analyzer.py — Multi-Dimensional Performance Matrix Analysis.

Analyzes ranked mass-iteration results to produce:
1. Per-instrument aggregate breakdowns
2. Per-date temporal performance breakdowns
3. Instrument x Date heatmap matrices
4. Parameter sensitivity correlations
5. 2-parameter interaction heatmaps
6. 3D scatter plots (PnL vs Sharpe vs Win Rate)
7. Equity curve bundles
8. Statistical distribution histograms
9. Monte Carlo permutations on trade order
"""

import math
import random
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple


class MatrixAnalyzer:
    """Stateless multi-dimensional analytics engine."""

    # -----------------------------------------------------------------------
    # 1. Per-instrument breakdown
    # -----------------------------------------------------------------------

    @staticmethod
    def per_instrument_stats(results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Aggregate metrics grouped by instrument."""
        buckets: Dict[str, List[Dict]] = defaultdict(list)
        for r in results:
            if "error" not in r:
                buckets[r.get("instrument", r.get("symbol", "UNKNOWN"))].append(r)

        out = []
        for inst, runs in buckets.items():
            pnls = [r.get("pnl_net", 0.0) for r in runs]
            sharpes = [r.get("sharpe_ratio", 0.0) for r in runs]
            win_rates = [r.get("win_rate_pct", 0.0) for r in runs]
            trades = [r.get("total_trades", 0) for r in runs]
            best = max(runs, key=lambda x: x.get("pnl_net", 0.0))
            worst = min(runs, key=lambda x: x.get("pnl_net", 0.0))

            out.append({
                "instrument": inst,
                "total_runs": len(runs),
                "avg_pnl_net": round(sum(pnls) / len(pnls), 2),
                "max_pnl_net": round(max(pnls), 2),
                "min_pnl_net": round(min(pnls), 2),
                "median_pnl": round(sorted(pnls)[len(pnls) // 2], 2),
                "avg_sharpe": round(sum(sharpes) / len(sharpes), 3),
                "avg_win_rate": round(sum(win_rates) / len(win_rates), 2),
                "avg_trades": round(sum(trades) / len(trades), 1),
                "profitable_runs_pct": round(
                    sum(1 for p in pnls if p > 0) / len(pnls) * 100, 2
                ),
                "best_params": best.get("parameters", {}),
                "best_pnl": round(best.get("pnl_net", 0.0), 2),
                "worst_pnl": round(worst.get("pnl_net", 0.0), 2),
            })

        out.sort(key=lambda x: x["avg_pnl_net"], reverse=True)
        return out

    # -----------------------------------------------------------------------
    # 2. Per-date breakdown
    # -----------------------------------------------------------------------

    @staticmethod
    def per_date_stats(results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Aggregate per-date performance across all runs."""
        date_buckets: Dict[str, List[Dict]] = defaultdict(list)
        for r in results:
            if "error" in r:
                continue
            for date, stats in (r.get("per_date_breakdown") or {}).items():
                date_buckets[date].append(stats)

        out = []
        for date, snapshots in sorted(date_buckets.items()):
            pnls = [s.get("pnl_net", 0.0) for s in snapshots]
            win_rates = [s.get("win_rate_pct", 0.0) for s in snapshots]
            trades = [s.get("total_trades", 0) for s in snapshots]

            out.append({
                "date": date,
                "runs_with_this_date": len(snapshots),
                "avg_pnl_net": round(sum(pnls) / len(pnls), 2),
                "max_pnl_net": round(max(pnls), 2),
                "min_pnl_net": round(min(pnls), 2),
                "avg_win_rate": round(sum(win_rates) / len(win_rates), 2),
                "avg_trades": round(sum(trades) / len(trades), 1),
                "profitable_runs_pct": round(
                    sum(1 for p in pnls if p > 0) / len(pnls) * 100, 2
                ),
            })
        return out

    # -----------------------------------------------------------------------
    # 3. Instrument x Date heatmap
    # -----------------------------------------------------------------------

    @staticmethod
    def instrument_date_heatmap(
        results: List[Dict[str, Any]],
        metric: str = "pnl_net"
    ) -> Dict[str, Any]:
        """Returns heatmap matrix data: rows = instruments, cols = dates."""
        instruments = sorted(set(
            r.get("instrument", r.get("symbol", "UNKNOWN"))
            for r in results if "error" not in r
        ))
        dates: set = set()
        for r in results:
            if "error" not in r:
                dates.update((r.get("per_date_breakdown") or {}).keys())
        dates_sorted = sorted(dates)

        lookup: Dict[Tuple[str, str], List[float]] = defaultdict(list)
        for r in results:
            if "error" in r:
                continue
            inst = r.get("instrument", r.get("symbol", "UNKNOWN"))
            for date, stats in (r.get("per_date_breakdown") or {}).items():
                val = stats.get(metric, stats.get("pnl_net", 0.0))
                lookup[(inst, date)].append(float(val))

        matrix = []
        for inst in instruments:
            row = []
            for date in dates_sorted:
                vals = lookup.get((inst, date), [0.0])
                row.append(round(sum(vals) / len(vals), 2))
            matrix.append(row)

        return {
            "x_axis_title": "Date",
            "y_axis_title": "Instrument",
            "metric": metric,
            "x_labels": dates_sorted,
            "y_labels": instruments,
            "matrix": matrix,
        }

    # -----------------------------------------------------------------------
    # 4. Parameter sensitivity
    # -----------------------------------------------------------------------

    @staticmethod
    def parameter_sensitivity(
        results: List[Dict[str, Any]],
        metric: str = "pnl_net"
    ) -> Dict[str, Any]:
        """Analyzes sensitivity of objective metric to variations in each parameter."""
        param_buckets: Dict[str, Dict[str, List[float]]] = defaultdict(lambda: defaultdict(list))

        for r in results:
            if "error" in r:
                continue
            val = float(r.get(metric, 0.0))
            for pk, pv in (r.get("parameters") or {}).items():
                param_buckets[pk][str(pv)].append(val)

        sensitivity: Dict[str, Any] = {}
        for param, val_map in param_buckets.items():
            entries = []
            for pval, metric_vals in sorted(val_map.items()):
                avg = sum(metric_vals) / len(metric_vals)
                entries.append({
                    "param_value": pval,
                    "count": len(metric_vals),
                    "avg_metric": round(avg, 3),
                    "max_metric": round(max(metric_vals), 3),
                    "min_metric": round(min(metric_vals), 3),
                })

            avgs = [e["avg_metric"] for e in entries]
            if len(avgs) > 1:
                mean_a = sum(avgs) / len(avgs)
                std_a = math.sqrt(sum((a - mean_a) ** 2 for a in avgs) / len(avgs))
            else:
                std_a = 0.0

            sensitivity[param] = {
                "entries": entries,
                "sensitivity_score": round(std_a, 4),
                "most_sensitive": std_a > 0.1,
            }

        return {
            "metric": metric,
            "parameters": sensitivity,
            "ranked_params": sorted(
                sensitivity.keys(),
                key=lambda p: sensitivity[p]["sensitivity_score"],
                reverse=True
            )
        }

    # -----------------------------------------------------------------------
    # 5. 2-parameter interaction heatmap
    # -----------------------------------------------------------------------

    @staticmethod
    def two_param_heatmap(
        results: List[Dict[str, Any]],
        param1: str,
        param2: str,
        metric: str = "pnl_net"
    ) -> Dict[str, Any]:
        """2D heatmap grid of param1 (x) vs param2 (y)."""
        lookup: Dict[Tuple[str, str], List[float]] = defaultdict(list)
        p1_vals: set = set()
        p2_vals: set = set()

        for r in results:
            if "error" in r:
                continue
            params = r.get("parameters", {})
            if param1 not in params or param2 not in params:
                continue
            pv1 = str(params[param1])
            pv2 = str(params[param2])
            p1_vals.add(pv1)
            p2_vals.add(pv2)
            lookup[(pv1, pv2)].append(float(r.get(metric, 0.0)))

        def try_numeric_sort(vals):
            try:
                return sorted(vals, key=float)
            except Exception:
                return sorted(vals)

        x_labels = try_numeric_sort(p1_vals)
        y_labels = try_numeric_sort(p2_vals)

        matrix = []
        for yv in y_labels:
            row = []
            for xv in x_labels:
                vals = lookup.get((xv, yv), [0.0])
                row.append(round(sum(vals) / len(vals), 3))
            matrix.append(row)

        return {
            "x_axis_title": param1,
            "y_axis_title": param2,
            "metric": metric,
            "x_labels": x_labels,
            "y_labels": y_labels,
            "matrix": matrix,
        }

    # -----------------------------------------------------------------------
    # 6. 3D scatter data
    # -----------------------------------------------------------------------

    @staticmethod
    def scatter_3d(results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """3D scatter coordinates for Pareto frontier analysis."""
        points = []
        for r in results:
            if "error" in r:
                continue
            points.append({
                "run_id": r.get("run_id", 0),
                "instrument": r.get("instrument", ""),
                "x": float(r.get("pnl_net", 0.0)),
                "y": float(r.get("sharpe_ratio", 0.0)),
                "z": float(r.get("win_rate_pct", 0.0)),
                "profit_factor": float(r.get("profit_factor", 0.0)),
                "max_dd_pct": float(r.get("max_drawdown_pct", 0.0)),
                "total_trades": int(r.get("total_trades", 0)),
                "parameters": r.get("parameters", {}),
            })
        return {
            "x_label": "Net PnL (₹)",
            "y_label": "Sharpe Ratio",
            "z_label": "Win Rate %",
            "points": points,
        }

    # -----------------------------------------------------------------------
    # 7. Distribution histograms
    # -----------------------------------------------------------------------

    @staticmethod
    def distribution_histograms(
        results: List[Dict[str, Any]],
        n_bins: int = 20
    ) -> Dict[str, Any]:
        """Histogram distributions for metrics."""
        def _histogram(vals: List[float], bins: int) -> Dict[str, Any]:
            if not vals:
                return {"bins": [], "counts": [], "min": 0, "max": 0}
            lo, hi = min(vals), max(vals)
            if lo == hi:
                return {"bins": [lo], "counts": [len(vals)], "min": lo, "max": hi}
            width = (hi - lo) / bins
            counts = [0] * bins
            bin_edges = [round(lo + i * width, 4) for i in range(bins + 1)]
            for v in vals:
                idx = min(int((v - lo) / width), bins - 1)
                counts[idx] += 1
            return {
                "bins": bin_edges[:-1],
                "counts": counts,
                "min": round(lo, 3),
                "max": round(hi, 3),
                "mean": round(sum(vals) / len(vals), 3),
            }

        valid = [r for r in results if "error" not in r]
        return {
            "pnl_net": _histogram([float(r.get("pnl_net", 0.0)) for r in valid], n_bins),
            "sharpe_ratio": _histogram([float(r.get("sharpe_ratio", 0.0)) for r in valid], n_bins),
            "win_rate_pct": _histogram([float(r.get("win_rate_pct", 0.0)) for r in valid], n_bins),
            "profit_factor": _histogram([float(r.get("profit_factor", 0.0)) for r in valid], n_bins),
            "max_drawdown_pct": _histogram([float(r.get("max_drawdown_pct", 0.0)) for r in valid], n_bins),
        }

    # -----------------------------------------------------------------------
    # 8. Monte Carlo Simulation
    # -----------------------------------------------------------------------

    @staticmethod
    def monte_carlo(
        trades: List[Dict[str, Any]],
        n_simulations: int = 1000,
        starting_capital: float = 100000.0,
        seed: int = 42
    ) -> Dict[str, Any]:
        """Randomly shuffles trade execution sequence to project drawdowns and tail risk."""
        rng = random.Random(seed)
        pnls = [float(t.get("pnl_net", t.get("net_pnl", 0.0))) for t in trades]
        if not pnls:
            return {"simulations": 0, "paths": [], "stats": {}}

        n = len(pnls)
        final_equities: List[float] = []
        max_dds: List[float] = []
        sampled_paths: List[List[float]] = []

        for sim_idx in range(n_simulations):
            shuffled = list(pnls)
            rng.shuffle(shuffled)
            eq = starting_capital
            peak = eq
            max_dd = 0.0
            path = [eq]
            for p in shuffled:
                eq += p
                if eq > peak:
                    peak = eq
                dd = (peak - eq) / peak * 100.0 if peak > 0 else 0.0
                max_dd = max(max_dd, dd)
                path.append(eq)

            final_equities.append(eq)
            max_dds.append(max_dd)
            if sim_idx < 20:
                sampled_paths.append(path)

        final_equities.sort()
        max_dds.sort()

        def pctile(lst, p):
            idx = int(len(lst) * p / 100)
            return round(lst[min(idx, len(lst) - 1)], 2)

        return {
            "simulations": n_simulations,
            "trades": n,
            "starting_capital": starting_capital,
            "stats": {
                "final_equity_p5": pctile(final_equities, 5),
                "final_equity_p25": pctile(final_equities, 25),
                "final_equity_median": pctile(final_equities, 50),
                "final_equity_p75": pctile(final_equities, 75),
                "final_equity_p95": pctile(final_equities, 95),
                "final_equity_best": round(final_equities[-1], 2),
                "final_equity_worst": round(final_equities[0], 2),
                "max_dd_p95": pctile(max_dds, 95),
                "max_dd_median": pctile(max_dds, 50),
                "pct_profitable": round(
                    sum(1 for e in final_equities if e > starting_capital) / len(final_equities) * 100, 2
                ),
            },
            "sampled_paths": sampled_paths,
        }

    # -----------------------------------------------------------------------
    # Full analysis bundle
    # -----------------------------------------------------------------------

    @classmethod
    def full_analysis(
        cls,
        results: List[Dict[str, Any]],
        param1: Optional[str] = None,
        param2: Optional[str] = None
    ) -> Dict[str, Any]:
        """Runs all matrix analyses and returns unified dictionary."""
        if not param1 or not param2:
            for r in results:
                if "error" not in r and r.get("parameters"):
                    keys = list(r["parameters"].keys())
                    param1 = param1 or (keys[0] if len(keys) > 0 else None)
                    param2 = param2 or (keys[1] if len(keys) > 1 else keys[0] if keys else None)
                    break

        analysis: Dict[str, Any] = {
            "instrument_stats": cls.per_instrument_stats(results),
            "date_stats": cls.per_date_stats(results),
            "instrument_date_heatmap": cls.instrument_date_heatmap(results, "pnl_net"),
            "parameter_sensitivity": cls.parameter_sensitivity(results, "pnl_net"),
            "scatter_3d": cls.scatter_3d(results),
            "distributions": cls.distribution_histograms(results),
        }

        if param1 and param2 and param1 != param2:
            analysis["two_param_heatmap"] = cls.two_param_heatmap(results, param1, param2, "pnl_net")
            analysis["two_param_heatmap_sharpe"] = cls.two_param_heatmap(results, param1, param2, "sharpe_ratio")

        return analysis
