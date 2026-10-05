"""
cli/main.py — CLI Parser and Command Dispatcher.
"""

import argparse
import sys

from config import (
    DEFAULT_CAPITAL,
    DEFAULT_RISK_PCT_PER_TRADE,
    DASHBOARD_PORT,
    DOWNLOADS_DIR,
)
from .strategy_loader import ALL_STRATEGIES
from .commands.data_cmd import (
    handle_data_status,
    handle_data_extract,
    handle_data_audit,
    handle_cache_warm,
)
from .commands.run_cmd import handle_run
from .commands.compare_cmd import handle_compare
from .commands.walk_forward_cmd import handle_walk_forward
from .commands.validate_cmd import handle_validate
from .commands.dashboard_cmd import handle_dashboard
from .commands.compose_cmd import handle_compose
from .commands.cockpit_cmd import (
    handle_audit,
    handle_option_chain,
    handle_replay,
    handle_robustness,
    handle_portfolio,
    handle_auto_tune,
)



def main():
    parser = argparse.ArgumentParser(description="Institutional Testing Engine CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # data command
    p_data = subparsers.add_parser("data", help="Archive and data cache management")
    p_data_sub = p_data.add_subparsers(dest="data_action", required=True)
    p_data_status = p_data_sub.add_parser("status", help="List archive files and extraction status")
    p_data_status.add_argument("--data-dir", type=str, default=DOWNLOADS_DIR, help="Path to archive/data directory")
    p_data_status.set_defaults(func=handle_data_status)

    p_data_extract = p_data_sub.add_parser("extract", help="Extract archive databases")
    p_data_extract.add_argument("--dates", type=str, required=True, help="Comma-separated dates")
    p_data_extract.add_argument("--data-dir", type=str, default=DOWNLOADS_DIR, help="Path to archive/data directory")
    p_data_extract.add_argument("--force", action="store_true", help="Force re-extraction")
    p_data_extract.set_defaults(func=handle_data_extract)

    p_data_audit = p_data_sub.add_parser("audit", help="Audit data quality for dates & symbols")
    p_data_audit.add_argument("--dates", type=str, required=True, help="Comma-separated dates")
    p_data_audit.add_argument("--symbols", type=str, default="NIFTY", help="Symbols to audit")
    p_data_audit.add_argument("--data-dir", type=str, default=DOWNLOADS_DIR, help="Data directory")
    p_data_audit.set_defaults(func=handle_data_audit)

    p_data_warm = p_data_sub.add_parser("warm", help="Pre-resample and warm Parquet cache")
    p_data_warm.add_argument("--dates", type=str, required=True, help="Target dates or range (e.g. 2026_09_01..2026_09_11)")
    p_data_warm.add_argument("--timeframes", type=str, default="1min,5min", help="Comma-separated timeframes")
    p_data_warm.add_argument("--symbols", type=str, default="auto", help="Comma-separated symbols or 'auto'")
    p_data_warm.add_argument("--data-dir", type=str, default=DOWNLOADS_DIR, help="Path to archive/data directory")
    p_data_warm.set_defaults(func=handle_cache_warm)

    # cache command
    p_cache = subparsers.add_parser("cache", help="Manage Parquet cache")
    p_cache_sub = p_cache.add_subparsers(dest="cache_action", required=True)
    p_cache_warm = p_cache_sub.add_parser("warm", help="Pre-resample and warm Parquet cache")
    p_cache_warm.add_argument("--dates", type=str, required=True, help="Target dates or range (e.g. 2026_09_01..2026_09_11)")
    p_cache_warm.add_argument("--timeframes", type=str, default="1min,5min", help="Comma-separated timeframes")
    p_cache_warm.add_argument("--symbols", type=str, default="auto", help="Comma-separated symbols or 'auto'")
    p_cache_warm.add_argument("--data-dir", type=str, default=DOWNLOADS_DIR, help="Path to archive/data directory")
    p_cache_warm.set_defaults(func=handle_cache_warm)

    # validate command
    p_val = subparsers.add_parser("validate", help="Run strategy backtest and institutional anti-overfitting audit")
    p_val.add_argument("strategy", choices=ALL_STRATEGIES, help="Strategy to test & validate")
    p_val.add_argument("--dates", type=str, default="all", help="Target dates or 'all'")
    p_val.add_argument("--data-dir", type=str, default=DOWNLOADS_DIR, help="Path to archive/data directory")
    p_val.add_argument("--timeframe", type=str, default="1min", choices=["1min", "5min", "15min"], help="Bar timeframe")
    p_val.add_argument("--symbols", type=str, default="auto", help="Comma-separated symbols or 'auto'")
    p_val.add_argument("--capital", type=float, default=DEFAULT_CAPITAL, help="Initial capital in INR")
    p_val.add_argument("--risk", type=float, default=DEFAULT_RISK_PCT_PER_TRADE, help="Risk pct per trade")
    p_val.add_argument("--parallel", action="store_true", help="Run multi-day backtest in parallel")
    p_val.add_argument("--trials", type=int, default=1, help="Number of trials for Deflated Sharpe adjustment")
    p_val.set_defaults(func=handle_validate)

    # run command
    p_run = subparsers.add_parser("run", help="Run strategy backtests")
    p_run.add_argument("strategy", choices=ALL_STRATEGIES, help="Strategy to test")
    p_run.add_argument("--dates", type=str, default="all", help="Target dates or 'all'")
    p_run.add_argument("--data-dir", type=str, default=DOWNLOADS_DIR, help="Path to archive/data directory")
    p_run.add_argument("--timeframe", type=str, default="1min", choices=["1min", "5min", "15min"], help="Bar timeframe")
    p_run.add_argument("--symbols", type=str, default="auto", help="Comma-separated symbols or 'auto' (default: auto)")
    p_run.add_argument("--capital", type=float, default=DEFAULT_CAPITAL, help="Initial capital in INR")
    p_run.add_argument("--risk", type=float, default=DEFAULT_RISK_PCT_PER_TRADE, help="Risk pct per trade (e.g. 0.01)")
    p_run.add_argument("--confidence", type=float, default=0.70, help="Confidence threshold for AI replay")
    p_run.add_argument("--parallel", action="store_true", help="Run multi-day backtest in parallel")
    p_run.set_defaults(func=handle_run)

    # compare command
    p_cmp = subparsers.add_parser("compare", help="Compare multiple strategies on identical data")
    p_cmp.add_argument("--dates", type=str, default="all", help="Target dates or 'all'")
    p_cmp.add_argument("--strategies", type=str, default="equity,orb,supertrend,camarilla,ema-ribbon,bollinger-b,macd-accel,vwap-reversion,rsi-momentum,options,ai-replay,short-straddle,pcr-reversion,banknifty-options,futures-trend,max-pain", help="Comma-separated strategy keys")
    p_cmp.add_argument("--data-dir", type=str, default=DOWNLOADS_DIR, help="Path to archive/data directory")
    p_cmp.add_argument("--timeframe", type=str, default="1min", help="Bar timeframe")
    p_cmp.add_argument("--symbols", type=str, default="auto", help="Symbols or 'auto'")
    p_cmp.add_argument("--capital", type=float, default=DEFAULT_CAPITAL, help="Capital")
    p_cmp.add_argument("--risk", type=float, default=DEFAULT_RISK_PCT_PER_TRADE, help="Risk pct")
    p_cmp.set_defaults(func=handle_compare)

    # walk-forward command
    p_wf = subparsers.add_parser("walk-forward", help="Run rolling walk-forward optimization")
    p_wf.add_argument("--strategy", choices=ALL_STRATEGIES, default="orb", help="Strategy to optimize")
    p_wf.add_argument("--dates", type=str, default="all", help="Target dates or 'all'")
    p_wf.add_argument("--in-sample", type=int, default=3, help="Number of in-sample training sessions")
    p_wf.add_argument("--out-of-sample", type=int, default=1, help="Number of out-of-sample forward testing sessions")
    p_wf.add_argument("--symbols", type=str, default="auto", help="Symbols or 'auto'")
    p_wf.add_argument("--capital", type=float, default=DEFAULT_CAPITAL, help="Capital")
    p_wf.add_argument("--risk", type=float, default=DEFAULT_RISK_PCT_PER_TRADE, help="Risk pct")
    p_wf.add_argument("--data-dir", type=str, default=DOWNLOADS_DIR, help="Path to archive/data directory")
    p_wf.set_defaults(func=handle_walk_forward)

    # dashboard command
    p_dash = subparsers.add_parser("dashboard", help="Start the interactive web dashboard")
    p_dash.add_argument("--port", type=int, default=DASHBOARD_PORT, help="Port to run web server on")
    p_dash.add_argument("--data-dir", type=str, default=DOWNLOADS_DIR, help="Default directory to scan")
    p_dash.add_argument("--no-browser", action="store_true", help="Do not auto-open browser in shared Chrome profile")
    p_dash.set_defaults(func=handle_dashboard)

    # compose command
    p_comp = subparsers.add_parser("compose", help="Run backtest using a declarative YAML strategy file")
    p_comp.add_argument("--file", type=str, required=True, help="Path to declarative strategy YAML file")
    p_comp.add_argument("--dates", type=str, default="all", help="Target dates or range (e.g. 2026_09_01..2026_09_11)")
    p_comp.add_argument("--symbols", type=str, default="auto", help="Symbols or 'auto'")
    p_comp.add_argument("--timeframe", type=str, default="1min", help="Candle timeframe (e.g. 1min, 5min)")
    p_comp.add_argument("--capital", type=float, default=DEFAULT_CAPITAL, help="Initial capital")
    p_comp.add_argument("--risk", type=float, default=DEFAULT_RISK_PCT_PER_TRADE, help="Risk percentage per trade")
    p_comp.add_argument("--data-dir", type=str, default=DOWNLOADS_DIR, help="Path to archive/data directory")
    p_comp.set_defaults(func=handle_compose)

    # audit command
    p_audit = subparsers.add_parser("audit", help="Run institutional forensic session audit scorecard")
    p_audit.add_argument("--date", type=str, default="2026_09_11", help="Session date to audit")
    p_audit.add_argument("--output", type=str, default=None, help="Optional output path for standalone HTML tearsheet")
    p_audit.set_defaults(func=handle_audit)

    # option-chain command
    p_chain = subparsers.add_parser("option-chain", help="Inspect option chain snapshot & open interest distribution")
    p_chain.add_argument("--date", type=str, default="2026_09_11", help="Session date")
    p_chain.add_argument("--table", type=str, default="CHAIN_NIFTY_2026_09_17", help="Option chain table name")
    p_chain.add_argument("--time", type=str, default="14:30", help="Snapshot target timestamp (HH:MM)")
    p_chain.set_defaults(func=handle_option_chain)

    # replay command
    p_rep = subparsers.add_parser("replay", help="Generate forensic bar-by-bar tape playback data")
    p_rep.add_argument("--date", type=str, default="2026_09_11", help="Session date")
    p_rep.add_argument("--symbol", type=str, default="NIFTY", help="Target symbol or index")
    p_rep.set_defaults(func=handle_replay)

    # robustness command
    p_rob = subparsers.add_parser("robustness", help="Audit statistical robustness, DSR, PSR, and parameter stability")
    p_rob.add_argument("--strategy", type=str, default="trading-engine-v4", help="Strategy to evaluate")
    p_rob.add_argument("--date", type=str, default="2026_09_11", help="Reference session date")
    p_rob.add_argument("--trials", type=int, default=20, help="Number of strategy trials tested")
    p_rob.set_defaults(func=handle_robustness)

    # portfolio command
    p_port = subparsers.add_parser("portfolio", help="Optimize blended multi-strategy portfolio allocation")
    p_port.add_argument("--method", choices=["risk_parity", "equal", "mean_variance"], default="risk_parity", help="Allocation model")
    p_port.add_argument("--capital", type=float, default=500000.0, help="Total allocation capital in INR")
    p_port.set_defaults(func=handle_portfolio)

    # auto-tune command
    p_tune = subparsers.add_parser("auto-tune", help="Diagnose intraday market regime and generate adaptive parameters")
    p_tune.add_argument("--date", type=str, default="2026_09_11", help="Session date to evaluate")
    p_tune.set_defaults(func=handle_auto_tune)

    args = parser.parse_args()
    args.func(args)



__all__ = ["main"]
