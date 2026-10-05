"""
main.py — Primary Entry Point for the Quantitative Testing Engine.

Orchestrates all testing engine subsystems:
1. Environment and configuration verification
2. Hardware acceleration detection (NVIDIA CUDA CuPy / Vectorized NumPy)
3. 56 Institutional strategy catalog verification
4. Starts the interactive Flask dashboard server
5. Automatically opens the dashboard in the shared Chrome profile (C:\\selenium\\ChromeProfile)
"""

import os
import sys
import argparse
import signal
import time
from typing import Optional

# Ensure testing engine root is in sys.path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

# Safe console configuration on Windows
if sys.platform == "win32":
    try:
        if hasattr(sys.stdout, "reconfigure"):
            getattr(sys.stdout, "reconfigure")(encoding="utf-8", errors="replace")
        if hasattr(sys.stderr, "reconfigure"):
            getattr(sys.stderr, "reconfigure")(encoding="utf-8", errors="replace")
    except Exception:
        pass

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from config import (
    DASHBOARD_HOST,
    DASHBOARD_PORT,
    DOWNLOADS_DIR,
    DATA_CACHE_DIR,
    RESULTS_DIR,
    CHROME_PROFILE_DIR,
    CHROME_AUTO_OPEN,
    validate_config
)
from math_engine.hardware import is_gpu_available
from strategies.builtin import BUILTIN_STRATEGIES
from dashboard.server import run_server

console = Console()


def _print_banner(port: int, host: str, no_browser: bool):
    """Render startup dashboard telemetry."""
    gpu_active = is_gpu_available()
    hw_text = "[bold green]NVIDIA CUDA GPU (CuPy)[/bold green]" if gpu_active else "[bold cyan]Vectorized SIMD (NumPy CPU)[/bold cyan]"
    browser_text = "[dim yellow]Disabled (--no-browser)[/dim yellow]" if no_browser else f"[bold green]Shared Profile ({CHROME_PROFILE_DIR})[/bold green]"

    grid = Table.grid(expand=True)
    grid.add_column(justify="left")
    grid.add_row("[bold cyan]Universal Quantitative Testing Engine (AGY 2.0)[/bold cyan]")
    grid.add_row("[dim]Institutional Event-Driven Backtesting, Strategy Catalog & Mass Iteration Terminal[/dim]")
    grid.add_row("")

    info_table = Table(box=None, show_header=False, padding=(0, 2))
    info_table.add_column("Key", style="bold white")
    info_table.add_column("Value", style="dim")

    info_table.add_row("🌐 Dashboard URL", f"[bold underline cyan]http://{host}:{port}[/bold underline cyan]")
    info_table.add_row("💻 Hardware Compute", hw_text)
    info_table.add_row("📊 Strategy Catalog", f"[bold green]{len(BUILTIN_STRATEGIES)} institutional strategies loaded[/bold green]")
    info_table.add_row("🌐 Chrome Browser", browser_text)
    info_table.add_row("📁 Historical Data", f"{DOWNLOADS_DIR}")
    info_table.add_row("⚡ Resampled Cache", f"{DATA_CACHE_DIR}")
    info_table.add_row("💾 Results Store", f"{RESULTS_DIR}")

    console.print(Panel(
        info_table,
        title="[bold green]⚡ TESTING ENGINE INITIALIZING[/bold green]",
        subtitle="[dim]Press Ctrl+C to shut down[/dim]",
        border_style="cyan"
    ))


def _handle_exit(sig, frame):
    console.print("\n[yellow]Shutting down Testing Engine gracefully... Goodbye![/yellow]")
    sys.exit(0)


def main():
    parser = argparse.ArgumentParser(description="Institutional Testing Engine Main Launcher")
    parser.add_argument("--port", type=int, default=DASHBOARD_PORT, help="Port to run dashboard on (default: 5690)")
    parser.add_argument("--host", type=str, default=DASHBOARD_HOST, help="Host to bind to (default: 127.0.0.1)")
    parser.add_argument("--no-browser", action="store_true", help="Do not auto-open shared Chrome profile")
    parser.add_argument("--data-dir", type=str, default=DOWNLOADS_DIR, help="Path to market data / database directory")
    args = parser.parse_args()

    # Register clean shutdown handlers
    signal.signal(signal.SIGINT, _handle_exit)
    signal.signal(signal.SIGTERM, _handle_exit)

    # 1. Validate configuration
    validate_config()

    # 2. Ensure directories exist
    os.makedirs(DATA_CACHE_DIR, exist_ok=True)
    os.makedirs(RESULTS_DIR, exist_ok=True)
    os.makedirs(os.path.join(RESULTS_DIR, "sessions"), exist_ok=True)

    # 3. Print interactive banner
    open_browser = not args.no_browser and CHROME_AUTO_OPEN
    _print_banner(port=args.port, host=args.host, no_browser=not open_browser)

    # 4. Start dashboard server and launch browser
    run_server(port=args.port, host=args.host, open_browser=open_browser)


if __name__ == "__main__":
    main()
