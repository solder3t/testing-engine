"""
cli/commands/compare_cmd.py — CLI Handlers for multi-strategy benchmarking.
"""

from rich.console import Console
from rich.table import Table

from config import DOWNLOADS_DIR
from data.archive_manager import ArchiveManager
from engine.multi_day_runner import MultiDayRunner
from ..strategy_loader import _build_strategy

console = Console()


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


__all__ = ["handle_compare"]
