"""
cli/commands/data_cmd.py — CLI Handlers for archive extraction, status, and data audit.
"""

from rich.console import Console
from rich.table import Table

from config import DOWNLOADS_DIR
from data.archive_manager import ArchiveManager
from data.data_loader import DataLoader
from data.quality_auditor import DataQualityAuditor
from ..strategy_loader import _parse_cli_symbols

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


def handle_data_audit(args):
    data_dir = getattr(args, "data_dir", None) or DOWNLOADS_DIR
    dl = DataLoader(source_dir=data_dir)
    target_dates = [d.strip() for d in args.dates.split(",") if d.strip()]
    symbols = _parse_cli_symbols(args.symbols)

    a_table = Table(title=f"🩺 Historical Data Quality Audit ({len(target_dates)} dates)")
    a_table.add_column("Date", style="cyan")
    a_table.add_column("Symbol", style="bold")
    a_table.add_column("Bars", justify="right")
    a_table.add_column("Missing", justify="right")
    a_table.add_column("Health Score", justify="right")
    a_table.add_column("Status", justify="center")
    a_table.add_column("Issues", style="dim")

    for d in target_dates:
        for s in symbols:
            df = dl.get_bars(d, s)
            report = DataQualityAuditor.audit(df, s, d)
            col = "green" if report.status == "EXCELLENT" else ("yellow" if report.status == "ACCEPTABLE" else "red")
            issues_str = "; ".join(report.issues[:2]) if report.issues else "Clean"
            a_table.add_row(
                d, s, str(report.total_bars), str(report.missing_bars),
                f"{report.health_score:.1f}%", f"[{col}]{report.status}[/{col}]", issues_str
            )
    console.print(a_table)


def parse_date_range(raw_dates: str) -> list:
    """Parses date string supporting comma-separated and range syntax (e.g. 2026_09_01..2026_09_11)."""
    from datetime import datetime, timedelta
    raw = (raw_dates or "").strip()
    if not raw:
        return []
    if ".." in raw:
        parts = raw.split("..", 1)
        start_str = parts[0].strip().replace("-", "_")
        end_str = parts[1].strip().replace("-", "_")
        start_d = datetime.strptime(start_str, "%Y_%m_%d")
        end_d = datetime.strptime(end_str, "%Y_%m_%d")
        dates = []
        cur = start_d
        while cur <= end_d:
            dates.append(cur.strftime("%Y_%m_%d"))
            cur += timedelta(days=1)
        return dates
    return [d.strip().replace("-", "_") for d in raw.split(",") if d.strip()]


def handle_cache_warm(args):
    """Pre-resamples tick tables for specified dates/timeframes and writes Snappy Parquet."""
    from data.parquet_cache import ParquetDataCache
    data_dir = getattr(args, "data_dir", None) or DOWNLOADS_DIR
    dates = parse_date_range(getattr(args, "dates", ""))
    if not dates:
        console.print("[red]No dates specified for cache warming.[/red]")
        return

    timeframes = [tf.strip() for tf in getattr(args, "timeframes", "1min,5min").split(",") if tf.strip()]
    symbols_arg = getattr(args, "symbols", None)
    symbols = _parse_cli_symbols(symbols_arg) if symbols_arg and symbols_arg != "auto" else None

    console.print(f"[cyan]Warming Parquet cache for {len(dates)} dates across timeframes {timeframes}...[/cyan]")
    cache = ParquetDataCache()
    res = cache.warm_batch(dates=dates, symbols=symbols, timeframes=timeframes, source_dir=data_dir)
    console.print(f"[green]✔ Warmed {res['files_written']} files in {res['elapsed_ms']}ms[/green]")


__all__ = ["handle_data_status", "handle_data_extract", "handle_data_audit", "handle_cache_warm", "parse_date_range"]
