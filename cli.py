"""
cli.py — Standalone Command-Line Interface for Testing Engine.

Usage:
    python cli.py data status
    python cli.py data extract --dates 2026_09_02,2026_09_08
    python cli.py run equity --dates 2026_09_02 --symbols RELIANCE,HDFCBANK
    python cli.py run options --dates 2026_09_11
    python cli.py run ai-replay --dates all --confidence 0.70
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
from data.option_chain_loader import OptionChainLoader
from strategies.equity_momentum import EquityMomentumStrategy
from strategies.nifty_options import NiftyOptionsStrategy
from strategies.ai_evaluator import AiSnapshotStrategy
from engine.multi_day_runner import MultiDayRunner
from analytics.trade_exporter import TradeExporter

console = Console()


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

    summary_panel = Panel.fit(
        f"[bold cyan]{strat}[/bold cyan] | Dates: [yellow]{dates}[/yellow]\n"
        f"Initial Capital: ₹{result['initial_capital']:,.2f}  →  Final Equity: [{fin_col}]₹{result['final_equity']:,.2f}[/{fin_col}]\n"
        f"Net P&L: [{pnl_col}]₹{m['net_pnl']:,.2f} ({m['return_pct']:+.2f}%)[/{pnl_col}] | Charges: ₹{m['total_charges']:,.2f}\n"
        f"Trades: {m['total_trades']} | Win Rate: {m['win_rate']}% | Profit Factor: {m['profit_factor']} | Sharpe: {m['sharpe_ratio']} | Max DD: {m['max_drawdown_pct']}%",
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
                t.side.value,
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

    # Ensure archives are extracted
    for d in target_dates:
        mgr.extract_archive(d, target_dir=data_dir)

    timeframe = getattr(args, "timeframe", "1min")
    runner = MultiDayRunner(capital=args.capital, risk_pct=args.risk, source_dir=data_dir)

    if args.strategy == "equity":
        symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()] if args.symbols else ["RELIANCE", "HDFCBANK", "INFY"]
        strat = EquityMomentumStrategy()
        res = runner.run(dates=target_dates, strategy=strat, symbols=symbols, timeframe=timeframe)
    elif args.strategy == "options":
        strat = NiftyOptionsStrategy()
        res = runner.run(dates=target_dates, strategy=strat, symbols=["NIFTY"], timeframe=timeframe)
    elif args.strategy == "ai-replay":
        strat = AiSnapshotStrategy(params={"min_confidence": args.confidence})
        res = runner.run(dates=target_dates, strategy=strat, symbols=["NIFTY"], timeframe=timeframe)
    else:
        console.print(f"[red]Unknown strategy: {args.strategy}[/red]")
        return

    _print_backtest_summary(res)

    # Save results
    out_file = os.path.join(RESULTS_DIR, f"backtest_{args.strategy}_{'_'.join(target_dates[:2])}.json")
    TradeExporter.export_json(res, out_file)
    csv_file = os.path.join(RESULTS_DIR, f"trades_{args.strategy}.csv")
    TradeExporter.export_csv(res["trades"], csv_file)
    console.print(f"\n[dim]Detailed results saved to {out_file} and {csv_file}[/dim]")


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
    p_data_status.add_argument("--data-dir", type=str, default=DOWNLOADS_DIR, help="Path to archive/data directory (default: ~/Downloads)")
    p_data_status.set_defaults(func=handle_data_status)

    p_data_extract = p_data_sub.add_parser("extract", help="Extract archive databases")
    p_data_extract.add_argument("--dates", type=str, required=True, help="Comma-separated dates, e.g. 2026_09_02,2026_09_08")
    p_data_extract.add_argument("--data-dir", type=str, default=DOWNLOADS_DIR, help="Path to archive/data directory (default: ~/Downloads)")
    p_data_extract.add_argument("--force", action="store_true", help="Force re-extraction")
    p_data_extract.set_defaults(func=handle_data_extract)

    # run command
    p_run = subparsers.add_parser("run", help="Run strategy backtests")
    p_run.add_argument("strategy", choices=["equity", "options", "ai-replay"], help="Strategy to test")
    p_run.add_argument("--dates", type=str, default="all", help="Target dates or 'all'")
    p_run.add_argument("--data-dir", type=str, default=DOWNLOADS_DIR, help="Path to archive/data directory (default: ~/Downloads)")
    p_run.add_argument("--timeframe", type=str, default="1min", choices=["1min", "5min", "15min"], help="Bar timeframe (default: 1min)")
    p_run.add_argument("--symbols", type=str, default="", help="Comma-separated symbols for equity strategy")
    p_run.add_argument("--capital", type=float, default=DEFAULT_CAPITAL, help="Initial capital in INR")
    p_run.add_argument("--risk", type=float, default=DEFAULT_RISK_PCT_PER_TRADE, help="Risk pct per trade (e.g. 0.01)")
    p_run.add_argument("--confidence", type=float, default=0.70, help="Confidence threshold for AI replay")
    p_run.set_defaults(func=handle_run)

    # dashboard command
    p_dash = subparsers.add_parser("dashboard", help="Start the interactive web dashboard")
    p_dash.add_argument("--port", type=int, default=DASHBOARD_PORT, help="Port to run web server on")
    p_dash.add_argument("--data-dir", type=str, default=DOWNLOADS_DIR, help="Default directory to scan")
    p_dash.set_defaults(func=handle_dashboard)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
