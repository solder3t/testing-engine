"""
cli/commands/compose_cmd.py — CLI handler for declarative YAML strategy pipelines.
"""

import os
from pathlib import Path
from rich.console import Console

from config import RESULTS_DIR, DOWNLOADS_DIR, DEFAULT_CAPITAL, DEFAULT_RISK_PCT_PER_TRADE
from data.archive_manager import ArchiveManager
from engine.multi_day_runner import MultiDayRunner
from analytics.trade_exporter import TradeExporter
from strategies.composable import YamlStrategyLoader
from .run_cmd import _print_backtest_summary
from .data_cmd import parse_date_range

console = Console()


def handle_compose(args):
    """Executes a backtest for a declarative YAML strategy definition."""
    yaml_file = getattr(args, "file", None)
    if not yaml_file:
        console.print("[red]Error: --file argument is required specifying path to YAML strategy file.[/red]")
        return

    path = Path(yaml_file)
    if not path.is_file():
        console.print(f"[red]Error: YAML strategy file not found: {yaml_file}[/red]")
        return

    try:
        strat = YamlStrategyLoader.load_from_yaml_file(path)
    except Exception as e:
        console.print(f"[red]Failed to parse YAML strategy file: {e}[/red]")
        return

    data_dir = getattr(args, "data_dir", None) or DOWNLOADS_DIR
    mgr = ArchiveManager(downloads_dir=data_dir)
    all_arch = mgr.list_archives(target_dir=data_dir)
    all_dates = [a["date"] for a in all_arch]

    date_arg = getattr(args, "dates", "all")
    if date_arg.lower() == "all":
        target_dates = all_dates
    elif ".." in date_arg:
        parsed = parse_date_range(date_arg)
        target_dates = [d for d in parsed if d in all_dates] if all_dates else parsed
    else:
        target_dates = [d.strip() for d in date_arg.split(",") if d.strip()]

    for d in target_dates:
        mgr.extract_archive(d, target_dir=data_dir)

    symbols_arg = getattr(args, "symbols", "auto")
    if symbols_arg.lower() == "auto":
        configured_symbols = strat.rule_config.get("symbols")
        if configured_symbols:
            symbols = (
                [s.strip() for s in configured_symbols if s.strip()]
                if isinstance(configured_symbols, list)
                else [s.strip() for s in configured_symbols.split(",")]
            )
        else:
            symbols = ["NIFTY", "BANKNIFTY"]
    else:
        symbols = [s.strip() for s in symbols_arg.split(",") if s.strip()]

    timeframe = getattr(args, "timeframe", None) or strat.rule_config.get("timeframe", "1min")
    capital = getattr(args, "capital", None) or strat.rule_config.get("capital", DEFAULT_CAPITAL)
    risk = getattr(args, "risk", None) or strat.rule_config.get("risk", DEFAULT_RISK_PCT_PER_TRADE)

    console.print(f"[bold cyan]Running composed strategy '{strat.name}' from {yaml_file}...[/bold cyan]")
    runner = MultiDayRunner(capital=capital, risk_pct=risk, source_dir=data_dir)
    res = runner.run(dates=target_dates, strategy=strat, symbols=symbols, timeframe=timeframe)

    _print_backtest_summary(res)

    safe_name = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in strat.name)
    out_file = os.path.join(RESULTS_DIR, f"backtest_composed_{safe_name}.json")
    TradeExporter.export_json(res, out_file)
    csv_file = os.path.join(RESULTS_DIR, f"trades_composed_{safe_name}.csv")
    TradeExporter.export_csv(res["trades"], csv_file)
    console.print(f"\n[dim]Results saved to {out_file} and {csv_file}[/dim]")


__all__ = ["handle_compose"]
