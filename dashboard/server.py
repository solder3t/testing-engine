"""
dashboard/server.py — Independent Flask API Server for Testing Engine.

Serves the interactive real-data testing dashboard on port 5690.
Strictly zero hardcoded data: all responses come from live engine calculations.
Refactored into Flask Blueprints with preserved top-level API compatibility.
"""

import logging
import os
import sys
import threading
from typing import Any, Dict, Optional
from flask import Flask
from flask_cors import CORS

# Ensure testing-engine is on sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from config import (
    DASHBOARD_HOST,
    DASHBOARD_PORT,
    CHROME_PROFILE_DIR,
    CHROME_AUTO_OPEN,
)
from dashboard.browser_launcher import open_dashboard_in_profile
from data.archive_manager import ArchiveManager
from engine.walk_forward import WalkForwardOptimizer
from engine.optimizer import StrategyOptimizer
from engine.mass_optimizer import MassOptimizer, HyperJob

# Import blueprint helpers to maintain root re-exports
from .blueprints.backtest import (
    resolve_server_symbols,
    create_strategy_instance,
    serialize_run_result,
)
from .blueprints import (
    views_bp,
    archives_bp,
    backtest_bp,
    optimize_bp,
    strategies_bp,
    system_bp,
    trading_engine_bp,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("dashboard_server")

# Global state for latest backtest run
latest_run_result: Dict[str, Any] = {}


def create_app() -> Flask:
    """Application factory for dashboard web server."""
    application = Flask(
        __name__,
        template_folder=os.path.join(os.path.dirname(__file__), "templates"),
        static_folder=os.path.join(os.path.dirname(__file__), "static")
    )
    CORS(application)

    # Register modular Blueprints
    application.register_blueprint(views_bp)
    application.register_blueprint(archives_bp)
    application.register_blueprint(backtest_bp)
    application.register_blueprint(optimize_bp)
    application.register_blueprint(strategies_bp)
    application.register_blueprint(system_bp)
    application.register_blueprint(trading_engine_bp)

    return application



app = create_app()


def run_server(port: int = DASHBOARD_PORT, host: str = DASHBOARD_HOST, open_browser: Optional[bool] = None):
    """Starts the dashboard web server and optionally launches Chrome."""
    if open_browser is None:
        open_browser = CHROME_AUTO_OPEN

    logger.info(f"Starting Testing Engine Dashboard at http://{host}:{port}")

    if open_browser:
        target_url = f"http://127.0.0.1:{port}/"
        logger.info(f"[Dashboard] Scheduling browser auto-open in shared Chrome profile ({CHROME_PROFILE_DIR})...")
        t = threading.Thread(
            target=open_dashboard_in_profile,
            kwargs={"url": target_url, "delay": 1.2},
            name="DashboardChromeOpener",
            daemon=True
        )
        t.start()

    app.run(host=host, port=port, debug=False)


if __name__ == "__main__":
    run_server()


__all__ = [
    "app",
    "create_app",
    "run_server",
    "latest_run_result",
    "resolve_server_symbols",
    "create_strategy_instance",
    "serialize_run_result",
    "open_dashboard_in_profile",
    "ArchiveManager",
    "WalkForwardOptimizer",
    "StrategyOptimizer",
    "MassOptimizer",
    "HyperJob",
]
