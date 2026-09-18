"""
engine/multi_day_runner.py — Coordinates Backtests Across Multiple Sessions.
"""

from typing import List, Dict, Any, Optional
import logging

from config import DEFAULT_CAPITAL, DEFAULT_RISK_PCT_PER_TRADE
from execution.portfolio import Portfolio
from execution.simulator import ExecutionSimulator
from strategies.base_strategy import BaseStrategy
from engine.backtest_engine import BacktestEngine
from analytics.metrics import calculate_performance_metrics

logger = logging.getLogger("multi_day_runner")


class MultiDayRunner:
    """Orchestrates multi-day backtest runs across multiple recorded archives."""

    def __init__(
        self,
        engine: Optional[BacktestEngine] = None,
        capital: float = DEFAULT_CAPITAL,
        risk_pct: float = DEFAULT_RISK_PCT_PER_TRADE,
        compound_capital: bool = True,
        source_dir: Optional[str] = None,
        parallel: bool = False
    ):
        self.source_dir = source_dir
        self.engine = engine or BacktestEngine(capital=capital, risk_pct=risk_pct, source_dir=source_dir)
        self.capital = capital
        self.risk_pct = risk_pct
        self.compound_capital = compound_capital
        self.parallel = parallel

    def run(
        self,
        dates: List[str],
        strategy: BaseStrategy,
        symbols: Optional[List[str]] = None,
        timeframe: str = "1min"
    ) -> Dict[str, Any]:
        """
        Runs the backtest across all specified dates in chronological order.
        If parallel=True and compound_capital=False, runs independent sessions in parallel.
        """
        sorted_dates = sorted(dates)
        current_capital = self.capital
        all_closed_trades = []
        full_equity_curve = []
        daily_summaries = []

        # Parallel path for independent sessions (compound_capital=False)
        if self.parallel and not self.compound_capital and len(sorted_dates) > 1:
            from concurrent.futures import ThreadPoolExecutor

            def _run_single_day(d_str: str):
                p = Portfolio(
                    initial_capital=self.capital,
                    risk_pct_per_trade=self.risk_pct,
                    simulator=self.engine.simulator
                )
                return d_str, self.engine.run_session(
                    date_str=d_str,
                    strategy=strategy,
                    symbols=symbols,
                    portfolio=p,
                    timeframe=timeframe
                )

            max_workers = min(len(sorted_dates), 8)
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                parallel_results = list(executor.map(_run_single_day, sorted_dates))

            # Maintain strict chronological ordering
            parallel_results.sort(key=lambda x: x[0])
            for d, session_res in parallel_results:
                day_trades = session_res["trades"]
                for t in day_trades:
                    if hasattr(t, "metadata") and isinstance(t.metadata, dict):
                        if "date" not in t.metadata:
                            t.metadata["date"] = d
                all_closed_trades.extend(day_trades)
                full_equity_curve.extend(session_res["equity_curve"])

                m = session_res["metrics"]
                start_cap = self.capital
                end_cap = session_res["final_equity"]
                ret_pct = round(((end_cap - start_cap) / start_cap) * 100, 2) if start_cap > 0 else 0.0
                daily_summaries.append({
                    "date": d,
                    "starting_equity": round(start_cap, 2),
                    "ending_equity": round(end_cap, 2),
                    "gross_pnl": round(m["gross_pnl"], 2),
                    "charges": round(m["total_charges"], 2),
                    "net_pnl": round(m["net_pnl"], 2),
                    "pnl": round(m["net_pnl"], 2),
                    "return_pct": ret_pct,
                    "trades": m["total_trades"],
                    "trades_count": m["total_trades"],
                    "win_rate": round(m["win_rate"], 2)
                })
                current_capital = end_cap

            overall_metrics = calculate_performance_metrics(
                trades=all_closed_trades,
                initial_capital=self.capital,
                equity_curve=full_equity_curve
            )

            return {
                "strategy": strategy.name,
                "dates_tested": sorted_dates,
                "source_directory": self.source_dir,
                "initial_capital": self.capital,
                "final_equity": round(current_capital, 2),
                "metrics": overall_metrics,
                "daily_breakdown": daily_summaries,
                "trades": all_closed_trades,
                "equity_curve": full_equity_curve
            }

        portfolio = Portfolio(
            initial_capital=current_capital,
            risk_pct_per_trade=self.risk_pct,
            simulator=self.engine.simulator
        )

        for d in sorted_dates:
            logger.info(f"Running backtest for session {d}...")
            # Reset daily P&L counter each session so intraday risk limits work correctly
            portfolio.daily_pnl = 0.0

            if not self.compound_capital:
                # Reset portfolio per day
                portfolio = Portfolio(
                    initial_capital=self.capital,
                    risk_pct_per_trade=self.risk_pct,
                    simulator=self.engine.simulator
                )

            start_cap = current_capital if self.compound_capital else self.capital

            session_res = self.engine.run_session(
                date_str=d,
                strategy=strategy,
                symbols=symbols,
                portfolio=portfolio,
                timeframe=timeframe
            )

            # Extract day results
            day_trades = session_res["trades"]
            for t in day_trades:
                if hasattr(t, "metadata") and isinstance(t.metadata, dict):
                    if "date" not in t.metadata:
                        t.metadata["date"] = d
            all_closed_trades.extend(day_trades)
            full_equity_curve.extend(session_res["equity_curve"])

            m = session_res["metrics"]
            end_cap = session_res["final_equity"]
            ret_pct = round(((end_cap - start_cap) / start_cap) * 100, 2) if start_cap > 0 else 0.0
            daily_summaries.append({
                "date": d,
                "starting_equity": round(start_cap, 2),
                "ending_equity": round(end_cap, 2),
                "gross_pnl": round(m["gross_pnl"], 2),
                "charges": round(m["total_charges"], 2),
                "net_pnl": round(m["net_pnl"], 2),
                "pnl": round(m["net_pnl"], 2),
                "return_pct": ret_pct,
                "trades": m["total_trades"],
                "trades_count": m["total_trades"],
                "win_rate": round(m["win_rate"], 2)
            })

            current_capital = end_cap

        # Aggregate metrics across the full multi-day period
        overall_metrics = calculate_performance_metrics(
            trades=all_closed_trades,
            initial_capital=self.capital,
            equity_curve=full_equity_curve
        )

        return {
            "strategy": strategy.name,
            "dates_tested": sorted_dates,
            "source_directory": self.source_dir,
            "initial_capital": self.capital,
            "final_equity": round(current_capital, 2),
            "metrics": overall_metrics,
            "daily_breakdown": daily_summaries,
            "trades": all_closed_trades,
            "equity_curve": full_equity_curve
        }
    def stream(
        self,
        dates: List[str],
        strategy: BaseStrategy,
        symbols: Optional[List[str]] = None,
        timeframe: str = "1min"
    ):
        """
        Generator version of run(). Yields one dict per processed date so callers
        can stream SSE progress events, then yields a final 'complete' dict containing
        the full aggregated result (identical shape to what run() returns).

        Yields dicts:
          {"type": "progress", "day": 1, "total": 5, "date": "2026_09_15",
           "trades": 3, "net_pnl": 1234.5, "equity": 501234.5}
          ...
          {"type": "complete", "result": {...}}   ← identical to run() return value
        """
        sorted_dates = sorted(dates)
        total = len(sorted_dates)
        current_capital = self.capital
        all_closed_trades = []
        full_equity_curve = []
        daily_summaries = []

        portfolio = Portfolio(
            initial_capital=current_capital,
            risk_pct_per_trade=self.risk_pct,
            simulator=self.engine.simulator
        )

        for i, d in enumerate(sorted_dates, start=1):
            logger.info(f"[stream] Session {i}/{total}: {d}")
            portfolio.daily_pnl = 0.0
            if not self.compound_capital:
                portfolio = Portfolio(
                    initial_capital=self.capital,
                    risk_pct_per_trade=self.risk_pct,
                    simulator=self.engine.simulator
                )
            start_cap = current_capital if self.compound_capital else self.capital

            session_res = self.engine.run_session(
                date_str=d,
                strategy=strategy,
                symbols=symbols,
                portfolio=portfolio,
                timeframe=timeframe
            )

            day_trades = session_res["trades"]
            for t in day_trades:
                if hasattr(t, "metadata") and isinstance(t.metadata, dict):
                    if "date" not in t.metadata:
                        t.metadata["date"] = d
            all_closed_trades.extend(day_trades)
            full_equity_curve.extend(session_res["equity_curve"])

            m = session_res["metrics"]
            end_cap = session_res["final_equity"]
            ret_pct = round(((end_cap - start_cap) / start_cap) * 100, 2) if start_cap > 0 else 0.0
            summary = {
                "date": d,
                "starting_equity": round(start_cap, 2),
                "ending_equity": round(end_cap, 2),
                "gross_pnl": round(m["gross_pnl"], 2),
                "charges": round(m["total_charges"], 2),
                "net_pnl": round(m["net_pnl"], 2),
                "pnl": round(m["net_pnl"], 2),
                "return_pct": ret_pct,
                "trades": m["total_trades"],
                "trades_count": m["total_trades"],
                "win_rate": round(m["win_rate"], 2)
            }
            daily_summaries.append(summary)
            current_capital = end_cap

            # Yield progress event — dashboard renders a progress bar update
            yield {
                "type": "progress",
                "day": i,
                "total": total,
                "date": d,
                "trades": m["total_trades"],
                "net_pnl": round(m["net_pnl"], 2),
                "equity": round(current_capital, 2),
                "win_rate": m["win_rate"]
            }

        # Final aggregate — same shape as run()
        overall_metrics = calculate_performance_metrics(
            trades=all_closed_trades,
            initial_capital=self.capital,
            equity_curve=full_equity_curve
        )

        yield {
            "type": "complete",
            "result": {
                "strategy": strategy.name,
                "dates_tested": sorted_dates,
                "source_directory": self.source_dir,
                "initial_capital": self.capital,
                "final_equity": round(current_capital, 2),
                "metrics": overall_metrics,
                "daily_breakdown": daily_summaries,
                "trades": all_closed_trades,
                "equity_curve": full_equity_curve
            }
        }
