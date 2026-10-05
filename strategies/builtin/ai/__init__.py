"""
strategies/builtin/ai — AI Backtesting and Decision Evaluation Engines.
"""

from .online_ai import OnlineAIEngine
from .local_ai import LocalAIEngine

__all__ = ["OnlineAIEngine", "LocalAIEngine"]
