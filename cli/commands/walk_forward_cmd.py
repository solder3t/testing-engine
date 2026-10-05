"""
cli/commands/walk_forward_cmd.py — CLI Handlers for rolling walk-forward optimization.
"""

from rich.console import Console
from rich.table import Table

from config import DOWNLOADS_DIR
from data.archive_manager import ArchiveManager
from engine.multi_day_runner import MultiDayRunner
from engine.walk_forward import WalkForwardOptimizer
from strategies.equity_momentum import EquityMomentumStrategy
from strategies.nifty_options import NiftyOptionsStrategy
from strategies.orb_breakout import OrbBreakoutStrategy
from strategies.supertrend_trend import SupertrendTrendStrategy
from strategies.camarilla_breakout import CamarillaBreakoutStrategy
from strategies.ema_ribbon import EmaRibbonStrategy
from ..strategy_loader import _parse_cli_symbols

console = Console()


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
    symbols = _parse_cli_symbols(args.symbols)

    runner = MultiDayRunner(capital=args.capital, risk_pct=args.risk, source_dir=data_dir, compound_capital=False)
    wfo = WalkForwardOptimizer(runner=runner, in_sample_len=args.in_sample, out_of_sample_len=args.out_of_sample)

    console.print(f"Executing Walk-Forward Optimization for [bold cyan]{args.strategy}[/bold cyan] across {len(target_dates)} sessions...")
    res = wfo.run_walk_forward(strategy_class=strat_cls, param_grid=param_grid, dates=target_dates, symbols=symbols)

    wfe = res["walk_forward_efficiency"]
    robust_str = "[bold green]ROBUST (WFE >= 0.50)[/bold green]" if res["is_robust"] else "[bold red]OVERFIT (WFE < 0.50)[/bold red]"
    console.print(f"\nWalk-Forward Efficiency Ratio: [bold cyan]{wfe:.2f}[/bold cyan] — Status: {robust_str}")

    psi = res.get("parameter_stability_index", {})
    if psi:
        psi_score = psi.get("overall_psi", 0.0)
        psi_stable = psi.get("is_stable", True)
        psi_str = "[bold green]STABLE (PSI < 0.25)[/bold green]" if psi_stable else "[bold red]UNSTABLE (PSI >= 0.25)[/bold red]"
        console.print(f"Parameter Stability Index (PSI): [bold cyan]{psi_score:.4f}[/bold cyan] — Status: {psi_str}")

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


__all__ = ["handle_walk_forward"]
