"""
cli/commands/run_cmd.py — CLI Handlers for backtest execution and metric reporting.
"""

import os
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from config import RESULTS_DIR, DOWNLOADS_DIR
from data.archive_manager import ArchiveManager
from engine.multi_day_runner import MultiDayRunner
from analytics.trade_exporter import TradeExporter
from ..strategy_loader import _build_strategy

console = Console()


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


__all__ = ["handle_run", "_print_backtest_summary"]
