"""
cli — Modular Command Line Interface for Institutional Testing Engine.
"""

from .main import main
from .strategy_loader import ALL_STRATEGIES, _build_strategy, _parse_cli_symbols

__all__ = [
    "main",
    "ALL_STRATEGIES",
    "_build_strategy",
    "_parse_cli_symbols",
]
