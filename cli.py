"""
cli.py — Standalone Command-Line Interface for Testing Engine.
Entry-point forwarding to modularized cli package.
"""

import sys
import os

# Ensure local testing-engine directory is in sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Ensure UTF-8 output on Windows consoles
if sys.platform == "win32":
    try:
        if hasattr(sys.stdout, "reconfigure"):
            getattr(sys.stdout, "reconfigure")(encoding="utf-8", errors="replace")
        if hasattr(sys.stderr, "reconfigure"):
            getattr(sys.stderr, "reconfigure")(encoding="utf-8", errors="replace")
    except Exception:
        pass

from cli.main import main
from cli.strategy_loader import ALL_STRATEGIES, _build_strategy, _parse_cli_symbols

__all__ = [
    "main",
    "ALL_STRATEGIES",
    "_build_strategy",
    "_parse_cli_symbols",
]

if __name__ == "__main__":
    main()
