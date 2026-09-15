"""
cli.py — Standalone Command-Line Interface for Testing Engine.

Usage:
    python cli.py data status
    python cli.py data extract --dates 2026_09_02,2026_09_08
    python cli.py run orb --dates 2026_09_11 --symbols auto
    python cli.py run options --dates 2026_09_11
    python cli.py compare --dates 2026_09_11 --strategies orb,supertrend,camarilla
    python cli.py walk-forward --dates 2026_09_02,2026_09_08,2026_09_09,2026_09_10,2026_09_11 --strategy orb
    python cli.py dashboard --port 5690
"""

import sys
import os
import argparse
import json
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

# Ensure local testing-engine directory is in sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import (
    DEFAULT_CAPITAL,
    DEFAULT_RISK_PCT_PER_TRADE,
    DASHBOARD_PORT,
    RESULTS_DIR,
    DOWNLOADS_DIR
)
from data.archive_manager import ArchiveManager
from data.data_loader import DataLoader
from strategies.equity_momentum import EquityMomentumStrategy
from strategies.nifty_options import NiftyOptionsStrategy
from strategies.ai_evaluator import AiSnapshotStrategy
from strategies.vwap_reversion import VwapReversionStrategy
from strategies.rsi_momentum import RsiMomentumStrategy
from strategies.orb_breakout import OrbBreakoutStrategy
from strategies.supertrend_trend import SupertrendTrendStrategy
from strategies.camarilla_breakout import CamarillaBreakoutStrategy
from strategies.ema_ribbon import EmaRibbonStrategy
from strategies.bollinger_percent_b import BollingerPercentBStrategy
from strategies.macd_acceleration import MacdAccelerationStrategy
from strategies.short_straddle import ShortStraddleStrategy
from strategies.pcr_reversion import PcrReversionStrategy
from strategies.banknifty_options import BankNiftyOptionsStrategy
from strategies.futures_trend import FuturesTrendStrategy
from strategies.max_pain import MaxPainConvergenceStrategy
from engine.multi_day_runner import MultiDayRunner
from engine.walk_forward import WalkForwardOptimizer
from analytics.trade_exporter import TradeExporter

console = Console()

ALL_STRATEGIES = [
    "equity", "orb", "supertrend", "camarilla", "ema-ribbon",
    "bollinger-b", "macd-accel", "vwap-reversion", "rsi-momentum",
    "options", "ai-replay", "short-straddle", "pcr-reversion",
    "banknifty-options", "futures-trend", "max-pain"
]


def _build_strategy(strategy_name: str, args):
    """Instantiates a strategy from CLI arguments."""
    if strategy_name == "equity":
        return EquityMomentumStrategy(), (
            ["auto"] if getattr(args, "symbols", "") == "auto" else
            [s.strip().upper() for s in getattr(args, "symbols", "").split(",") if s.strip()] or ["RELIANCE", "HDFCBANK", "INFY"]
        )
    elif strategy_name == "orb":
        return OrbBreakoutStrategy(), (
            ["auto"] if getattr(args, "symbols", "") == "auto" else
            [s.strip().upper() for s in getattr(args, "symbols", "").split(",") if s.strip()] or ["RELIANCE", "HDFCBANK", "INFY"]
        )
    elif strategy_name == "supertrend":
        return SupertrendTrendStrategy(), (
            ["auto"] if getattr(args, "symbols", "") == "auto" else
            [s.strip().upper() for s in getattr(args, "symbols", "").split(",") if s.strip()] or ["RELIANCE", "HDFCBANK", "INFY"]
        )
    elif strategy_name == "camarilla":
        return CamarillaBreakoutStrategy(), (
            ["auto"] if getattr(args, "symbols", "") == "auto" else
            [s.strip().upper() for s in getattr(args, "symbols", "").split(",") if s.strip()] or ["RELIANCE", "HDFCBANK", "INFY"]
        )
    elif strategy_name == "ema-ribbon":
        return EmaRibbonStrategy(), (
            ["auto"] if getattr(args, "symbols", "") == "auto" else
            [s.strip().upper() for s in getattr(args, "symbols", "").split(",") if s.strip()] or ["RELIANCE", "HDFCBANK", "INFY"]
        )
    elif strategy_name == "bollinger-b":
        return BollingerPercentBStrategy(), (
            ["auto"] if getattr(args, "symbols", "") == "auto" else
            [s.strip().upper() for s in getattr(args, "symbols", "").split(",") if s.strip()] or ["RELIANCE", "HDFCBANK", "INFY"]
        )
    elif strategy_name == "macd-accel":
        return MacdAccelerationStrategy(), (
            ["auto"] if getattr(args, "symbols", "") == "auto" else
            [s.strip().upper() for s in getattr(args, "symbols", "").split(",") if s.strip()] or ["RELIANCE", "HDFCBANK", "INFY"]
        )
    elif strategy_name == "vwap-reversion":
        return VwapReversionStrategy(), (
            ["auto"] if getattr(args, "symbols", "") == "auto" else
            [s.strip().upper() for s in getattr(args, "symbols", "").split(",") if s.strip()] or ["RELIANCE", "HDFCBANK", "INFY"]
        )
    elif strategy_name == "rsi-momentum":
        return RsiMomentumStrategy(), (
            ["auto"] if getattr(args, "symbols", "") == "auto" else
            [s.strip().upper() for s in getattr(args, "symbols", "").split(",") if s.strip()] or ["RELIANCE", "HDFCBANK", "INFY"]
        )
    elif strategy_name == "options":
        return NiftyOptionsStrategy(), ["NIFTY"]
    elif strategy_name == "ai-replay":
        conf = getattr(args, "confidence", 0.70)
        return AiSnapshotStrategy(params={"min_confidence": conf}), ["NIFTY"]
    elif strategy_name == "short-straddle":
        return ShortStraddleStrategy(), ["NIFTY"]
    elif strategy_name == "pcr-reversion":
        return PcrReversionStrategy(), ["NIFTY"]
    elif strategy_name == "banknifty-options":
        return BankNiftyOptionsStrategy(), ["BANKNIFTY"]
    elif strategy_name == "futures-trend":
        return FuturesTrendStrategy(), ["NIFTY"]
    elif strategy_name == "max-pain":
        return MaxPainConvergenceStrategy(), ["NIFTY"]
    else:
        raise ValueError(f"Unknown strategy: {strategy_name}")


def handle_data_status(args):
    data_dir = getattr(args, "data_dir", None) or DOWNLOADS_DIR
    mgr = ArchiveManager(downloads_dir=data_dir)
    archives = mgr.list_archives(target_dir=data_dir)

    table = Table(title=f"📦 Market Recording Archives & Sessions ({data_dir})")
    table.add_column("Date", style="cyan bold")
    table.add_column("Source Name", style="white")
    table.add_column("Type", style="yellow")
    table.add_column("Size (MB)", justify="right")
    table.add_column("Extraction Status", style="magenta")
    table.add_column("Extracted Files", style="green")

    for a in archives:
        status_str = "✅ Extracted" if a.get("is_extracted") else "⏳ Compressed"
        src_type = "📁 Folder" if a.get("type") == "folder" else "📦 RAR"
        files_str = ", ".join(a.get("extracted_files", [])[:4]) if a.get("extracted_files") else "-"
        if len(a.get("extracted_files", [])) > 4:
            files_str += f" (+{len(a['extracted_files'])-4} more)"
        table.add_row(a["date"], a["filename"], src_type, f"{a.get('size_mb', 0):.1f}", status_str, files_str)

    console.print(table)


def handle_data_extract(args):
    data_dir = getattr(args, "data_dir", None) or DOWNLOADS_DIR
    mgr = ArchiveManager(downloads_dir=data_dir)
    dates = [d.strip() for d in args.dates.split(",") if d.strip()]
    console.print(f"Extracting standard databases for: {', '.join(dates)} from {data_dir}...")

    for d in dates:
        res = mgr.extract_archive(d, force=args.force, target_dir=data_dir)
        if res.get("success"):
            console.print(f"  [green]✔ {d}:[/green] {res['message']}")
        else:
            console.print(f"  [red]✘ {d}:[/red] {res.get('error')}")


def _print_backtest_summary(result: dict):
    m = result["metrics"]
    strat = result["strategy"]
    dates = ", ".join(result["dates_tested"])

    fin_col = "green" if result['final_equity'] >= result['initial_capital'] else "red"
    pnl_col = "green" if m['net_pnl'] >= 0 else "red"

    wins = m.get("wins", 0)
    losses = m.get("losses", 0)
    be = m.get("breakeven_count", 0)
    calmar = m.get("calmar_ratio", 0.0)
    mx_wins = m.get("max_consecutive_wins", 0)
    mx_loss = m.get("max_consecutive_losses", 0)

    summary_panel = Panel.fit(
        f"[bold cyan]{strat}[/bold cyan] | Dates: [yellow]{dates}[/yellow]\n"
        f"Initial Capital: ₹{result['initial_capital']:,.2f}  →  Final Equity: [{fin_col}]₹{result['final_equity']:,.2f}[/{fin_col}]\n"
        f"Net P&L: [{pnl_col}]₹{m['net_pnl']:,.2f} ({m['return_pct']:+.2f}%)[/{pnl_col}] | Charges: ₹{m['total_charges']:,.2f}\n"
        f"Trades: {m['total_trades']} ({wins}W / {losses}L / {be}BE) | Win Rate: {m['win_rate']:.1f}% | Profit Factor: {m['profit_factor']:.2f}\n"
        f"Sharpe: {m['sharpe_ratio']:.2f} | Sortino: {m['sortino_ratio']:.2f} | Calmar: {calmar:.2f} | Max DD: {m['max_drawdown_pct']:.2f}%\n"
        f"Streaks: Best {mx_wins} wins | Worst {mx_loss} losses",
        title="📊 Backtest Performance Summary"
    )
    console.print(summary_panel)

    # Daily breakdown table
    if len(result["daily_breakdown"]) > 0:
        d_table = Table(title="Daily Session Breakdown")
        d_table.add_column("Session Date", style="cyan")
        d_table.add_column("Trades", justify="right")
        d_table.add_column("Win Rate", justify="right")
        d_table.add_column("Gross PnL", justify="right")
        d_table.add_column("Charges", justify="right")
        d_table.add_column("Net PnL", justify="right")
        d_table.add_column("Ending Capital", justify="right")

        for d in result["daily_breakdown"]:
            pnl_color = "green" if d["net_pnl"] >= 0 else "red"
            d_table.add_row(
                d["date"],
                str(d["trades_count"]),
                f"{d['win_rate']:.1f}%",
                f"₹{d['gross_pnl']:,.2f}",
                f"₹{d['charges']:,.2f}",
                f"[{pnl_color}]₹{d['net_pnl']:,.2f}[/{pnl_color}]",
                f"₹{d['ending_equity']:,.2f}"
            )
        console.print(d_table)

    # Sample trades table
    trades = result.get("trades", [])
    if trades:
        t_table = Table(title=f"Sample Trades ({len(trades)} total)")
        t_table.add_column("Time", style="dim")
        t_table.add_column("Symbol", style="bold")
        t_table.add_column("Side")
        t_table.add_column("Qty", justify="right")
        t_table.add_column("Entry", justify="right")
        t_table.add_column("Exit", justify="right")
        t_table.add_column("Net P&L", justify="right")
        t_table.add_column("Reason")

        for t in trades[:10]:
            pnl_col = "green" if t.net_pnl >= 0 else "red"
            t_table.add_row(
                t.entry_time.split(" ")[-1] if " " in t.entry_time else t.entry_time,
                t.symbol,
                t.side.value if hasattr(t.side, "value") else str(t.side),
                str(t.qty),
                f"₹{t.entry_price:,.2f}",
                f"₹{t.exit_price:,.2f}" if t.exit_price else "-",
                f"[{pnl_col}]₹{t.net_pnl:+,.2f}[/{pnl_col}]",
                t.exit_reason or "-"
            )
        console.print(t_table)


def handle_run(args):
    data_dir = getattr(args, "data_dir", None) or DOWNLOADS_DIR
    mgr = ArchiveManager(downloads_dir=data_dir)
    all_arch = mgr.list_archives(target_dir=data_dir)
    all_dates = [a["date"] for a in all_arch]

    if args.dates.lower() == "all":
        target_dates = all_dates
    else:
        target_dates = [d.strip() for d in args.dates.split(",") if d.strip()]

    for d in target_dates:
        mgr.extract_archive(d, target_dir=data_dir)

    timeframe = getattr(args, "timeframe", "1min")
    runner = MultiDayRunner(capital=args.capital, risk_pct=args.risk, source_dir=data_dir, parallel=args.parallel)

    strat, symbols = _build_strategy(args.strategy, args)
    res = runner.run(dates=target_dates, strategy=strat, symbols=symbols, timeframe=timeframe)

    _print_backtest_summary(res)

    out_file = os.path.join(RESULTS_DIR, f"backtest_{args.strategy}_{'_'.join(target_dates[:2])}.json")
    TradeExporter.export_json(res, out_file)
    csv_file = os.path.join(RESULTS_DIR, f"trades_{args.strategy}.csv")
    TradeExporter.export_csv(res["trades"], csv_file)
    console.print(f"\n[dim]Detailed results saved to {out_file} and {csv_file}[/dim]")


def handle_compare(args):
    data_dir = getattr(args, "data_dir", None) or DOWNLOADS_DIR
    mgr = ArchiveManager(downloads_dir=data_dir)
    all_arch = mgr.list_archives(target_dir=data_dir)
    all_dates = [a["date"] for a in all_arch]

    if args.dates.lower() == "all":
        target_dates = all_dates
    else:
        target_dates = [d.strip() for d in args.dates.split(",") if d.strip()]

    for d in target_dates:
        mgr.extract_archive(d, target_dir=data_dir)

    strat_names = [s.strip() for s in args.strategies.split(",") if s.strip()]
    console.print(f"Benchmarking [bold cyan]{len(strat_names)} strategies[/bold cyan] across [yellow]{len(target_dates)} session(s)[/yellow]...")

    runner = MultiDayRunner(capital=args.capital, risk_pct=args.risk, source_dir=data_dir, compound_capital=False, parallel=True)

    c_table = Table(title="⚖️ Multi-Strategy Performance Benchmark")
    c_table.add_column("Strategy", style="bold cyan")
    c_table.add_column("Trades", justify="right")
    c_table.add_column("Win Rate", justify="right")
    c_table.add_column("Profit Factor", justify="right")
    c_table.add_column("Sharpe", justify="right")
    c_table.add_column("Calmar", justify="right")
    c_table.add_column("Max DD %", justify="right", style="red")
    c_table.add_column("Net P&L (₹)", justify="right")
    c_table.add_column("Return %", justify="right")

    for s_name in strat_names:
        try:
            strat, symbols = _build_strategy(s_name, args)
            res = runner.run(dates=target_dates, strategy=strat, symbols=symbols, timeframe=args.timeframe)
            m = res["metrics"]
            pnl_col = "green" if m["net_pnl"] >= 0 else "red"
            c_table.add_row(
                strat.name,
                str(m["total_trades"]),
                f"{m['win_rate']:.1f}%",
                f"{m['profit_factor']:.2f}",
                f"{m['sharpe_ratio']:.2f}",
                f"{m.get('calmar_ratio', 0.0):.2f}",
                f"{m['max_drawdown_pct']:.2f}%",
                f"[{pnl_col}]₹{m['net_pnl']:,.2f}[/{pnl_col}]",
                f"[{pnl_col}]{m['return_pct']:+.2f}%[/{pnl_col}]"
            )
        except Exception as e:
            c_table.add_row(s_name, "-", "-", "-", "-", "-", "-", f"[red]Error: {e}[/red]", "-")

    console.print(c_table)


def handle_walk_forward(args):
    data_dir = getattr(args, "data_dir", None) or DOWNLOADS_DIR
    mgr = ArchiveManager(downloads_dir=data_dir)
    all_arch = mgr.list_archives(target_dir=data_dir)
    all_dates = [a["date"] for a in all_arch]

    if args.dates.lower() == "all":
        target_dates = all_dates
    else:
        target_dates = [d.strip() for d in args.dates.split(",") if d.strip()]

    if len(target_dates) < (args.in_sample + args.out_of_sample):
        console.print(f"[red]Need at least {args.in_sample + args.out_of_sample} dates, got {len(target_dates)}[/red]")
        return

    for d in target_dates:
        mgr.extract_archive(d, target_dir=data_dir)

    strat_map = {
        "orb": (OrbBreakoutStrategy, {"opening_minutes": [10, 15, 20], "risk_reward": [1.5, 2.0]}),
        "supertrend": (SupertrendTrendStrategy, {"multiplier": [2.5, 3.0], "atr_period": [10, 14]}),
        "camarilla": (CamarillaBreakoutStrategy, {"risk_reward": [1.5, 2.0, 2.5]}),
        "ema-ribbon": (EmaRibbonStrategy, {"sl_pts": [10.0, 15.0], "target_pts": [25.0, 30.0]}),
        "options": (NiftyOptionsStrategy, {"sl_points": [10.0, 12.0], "target_multiplier": [1.5, 1.8]}),
        "equity": (EquityMomentumStrategy, {"min_score": [50, 55, 60]}),
    }

    if args.strategy not in strat_map:
        console.print(f"[red]Walk-forward optimization not pre-configured for {args.strategy}. Choose: {list(strat_map.keys())}[/red]")
        return

    strat_cls, param_grid = strat_map[args.strategy]
    symbols = ["auto"] if args.symbols == "auto" else ([s.strip().upper() for s in args.symbols.split(",") if s.strip()] or None)

    runner = MultiDayRunner(capital=args.capital, risk_pct=args.risk, source_dir=data_dir, compound_capital=False)
    wfo = WalkForwardOptimizer(runner=runner, in_sample_len=args.in_sample, out_of_sample_len=args.out_of_sample)

    console.print(f"Executing Walk-Forward Optimization for [bold cyan]{args.strategy}[/bold cyan] across {len(target_dates)} sessions...")
    res = wfo.run_walk_forward(strategy_class=strat_cls, param_grid=param_grid, dates=target_dates, symbols=symbols)

    wfe = res["walk_forward_efficiency"]
    robust_str = "[bold green]ROBUST (WFE >= 0.50)[/bold green]" if res["is_robust"] else "[bold red]OVERFIT (WFE < 0.50)[/bold red]"
    console.print(f"\nWalk-Forward Efficiency Ratio: [bold cyan]{wfe:.2f}[/bold cyan] — Status: {robust_str}")

    w_table = Table(title="Rolling Walk-Forward Windows")
    w_table.add_column("Window", justify="right")
    w_table.add_column("In-Sample Dates", style="yellow")
    w_table.add_column("Best Params", style="magenta")
    w_table.add_column("IS Sharpe", justify="right")
    w_table.add_column("Out-of-Sample Date", style="cyan")
    w_table.add_column("OOS Net P&L (₹)", justify="right")
    w_table.add_column("OOS Sharpe", justify="right")

    for w in res["windows"]:
        is_m = w["in_sample_metrics"]
        oos_m = w["out_of_sample_metrics"]
        pnl_col = "green" if oos_m["net_pnl"] >= 0 else "red"
        w_table.add_row(
            str(w["window"]),
            ", ".join(w["in_sample_dates"]),
            str(w["best_params"]),
            f"{is_m['sharpe_ratio']:.2f}",
            ", ".join(w["out_of_sample_dates"]),
            f"[{pnl_col}]₹{oos_m['net_pnl']:,.2f}[/{pnl_col}]",
            f"{oos_m['sharpe_ratio']:.2f}"
        )

    console.print(w_table)


def handle_dashboard(args):
    from dashboard.server import run_server
    data_dir = getattr(args, "data_dir", None) or DOWNLOADS_DIR
    console.print(f"[bold green]Starting Testing Engine Dashboard on port {args.port} (default source: {data_dir})...[/bold green]")
    run_server(port=args.port)


def main():
    parser = argparse.ArgumentParser(description="⚡ Testing Engine CLI")
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

    # run command
    p_run = subparsers.add_parser("run", help="Run strategy backtests")
    p_run.add_argument("strategy", choices=ALL_STRATEGIES, help="Strategy to test")
    p_run.add_argument("--dates", type=str, default="all", help="Target dates or 'all'")
    p_run.add_argument("--data-dir", type=str, default=DOWNLOADS_DIR, help="Path to archive/data directory")
    p_run.add_argument("--timeframe", type=str, default="1min", choices=["1min", "5min", "15min"], help="Bar timeframe")
    p_run.add_argument("--symbols", type=str, default="", help="Comma-separated symbols or 'auto'")
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
    p_dash.set_defaults(func=handle_dashboard)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
