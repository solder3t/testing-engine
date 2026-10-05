"""
dashboard/blueprints — Flask Blueprints for modular dashboard server.
"""

from .views import views_bp
from .archives import archives_bp
from .backtest import backtest_bp
from .optimize import optimize_bp
from .strategies import strategies_bp
from .system import system_bp
from .trading_engine import trading_engine_bp

__all__ = [
    "views_bp",
    "archives_bp",
    "backtest_bp",
    "optimize_bp",
    "strategies_bp",
    "system_bp",
    "trading_engine_bp",
]

