"""
cli/commands/validate_cmd.py — CLI Handlers for institutional anti-overfitting validation.
"""

from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from config import DOWNLOADS_DIR
from data.archive_manager import ArchiveManager
from engine.multi_day_runner import MultiDayRunner
from analytics.validation_report import CandidateValidator
from ..strategy_loader import _build_strategy

console = Console()


def handle_validate(args):
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
    console.print(f"Running backtest & institutional validation for [bold cyan]{strat.name}[/bold cyan]...")
    res = runner.run(dates=target_dates, strategy=strat, symbols=symbols, timeframe=timeframe)

    trades_list = []
    for t in res.get("trades", []):
        trades_list.append({
            "symbol": t.symbol,
            "net_pnl": t.net_pnl,
            "entry_time": t.entry_time,
            "metadata": t.metadata
        })

    val_report = CandidateValidator.evaluate_candidate(
        strategy_name=strat.name,
        initial_capital=res["initial_capital"],
        final_equity=res["final_equity"],
        metrics=res["metrics"],
        trades=trades_list,
        equity_curve=res.get("equity_curve", []),
        n_trials=getattr(args, "trials", 1)
    )

    verdict = val_report["verdict"]
    v_col = "bold green" if verdict == "PASS" else ("bold yellow" if verdict == "MARGINAL" else "bold red")
    score = val_report["score_pct"]
    dsr = val_report["deflated_sharpe"]
    mc = val_report["monte_carlo"]

    val_panel = Panel.fit(
        f"Strategy: [bold cyan]{strat.name}[/bold cyan] | Score: [bold]{score}%[/bold] | Verdict: [{v_col}]{verdict}[/{v_col}]\n"
        f"Deflated Sharpe: {dsr.get('deflated_sharpe_stat', 0.0):.2f} (p-value: {dsr.get('p_value', 1.0):.4f}) | Status: {dsr.get('verdict', 'N/A')}\n"
        f"Monte Carlo VaR 95%: ₹{mc.get('var_95_inr', 0.0):,.2f} | 95% Worst DD: {mc.get('max_drawdown_95_pct', 0.0):.2f}% | Win Prob: {mc.get('prob_profitable', 0.0):.1f}%",
        title="🛡️ Quantitative Validation Tear-Sheet"
    )
    console.print(val_panel)

    h_table = Table(title="Institutional Hurdle Checklist")
    h_table.add_column("Hurdle Criterion", style="white")
    h_table.add_column("Status", justify="center")
    for h_name, passed in val_report["hurdles"].items():
        status_text = "[green]✔ PASS[/green]" if passed else "[red]✘ FAIL[/red]"
        h_table.add_row(h_name.replace("_", " ").title(), status_text)
    console.print(h_table)


__all__ = ["handle_validate"]
