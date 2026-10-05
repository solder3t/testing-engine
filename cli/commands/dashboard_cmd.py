"""
cli/commands/dashboard_cmd.py — CLI Handlers for launching interactive dashboard server.
"""

from rich.console import Console
from config import DOWNLOADS_DIR, DASHBOARD_PORT

console = Console()


def handle_dashboard(args):
    from dashboard.server import run_server
    data_dir = getattr(args, "data_dir", None) or DOWNLOADS_DIR
    no_browser = getattr(args, "no_browser", False)
    console.print(f"[bold green]Starting Testing Engine Dashboard on port {args.port} (default source: {data_dir})...[/bold green]")
    run_server(port=args.port, open_browser=not no_browser)


__all__ = ["handle_dashboard"]
