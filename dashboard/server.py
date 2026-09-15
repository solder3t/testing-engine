"""
dashboard/server.py — Independent Flask API Server for Testing Engine.

Serves the interactive real-data testing dashboard on port 5690.
Strictly zero hardcoded data: all responses come from live engine calculations.
Supports dynamic directory selection for archive and folder scanning.
"""

import os
import sys
import json
import re
import logging
import traceback
from typing import Dict, Any, Optional
from flask import Flask, render_template, request, jsonify, send_file
from flask_cors import CORS

# Ensure testing-engine is on sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from config import (
    DASHBOARD_HOST,
    DASHBOARD_PORT,
    DEFAULT_CAPITAL,
    DEFAULT_RISK_PCT_PER_TRADE,
    DOWNLOADS_DIR,
    RESULTS_DIR
)
from data.archive_manager import ArchiveManager
from strategies.equity_momentum import EquityMomentumStrategy
from strategies.nifty_options import NiftyOptionsStrategy
from strategies.ai_evaluator import AiSnapshotStrategy
from strategies.vwap_reversion import VwapReversionStrategy
from strategies.rsi_momentum import RsiMomentumStrategy
from engine.multi_day_runner import MultiDayRunner
from analytics.trade_exporter import TradeExporter

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("dashboard_server")

app = Flask(
    __name__,
    template_folder=os.path.join(os.path.dirname(__file__), "templates"),
    static_folder=os.path.join(os.path.dirname(__file__), "static")
)
CORS(app)

latest_run_result: Dict[str, Any] = {}


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/browse", methods=["GET"])
def browse_directory():
    """
    Filesystem explorer endpoint for dashboard file/folder selector dialog.
    Allows users to navigate directories, inspect folders, and select .rar archives,
    session folders, or market database files.
    """
    raw_path = request.args.get("path") or DOWNLOADS_DIR
    target_path = os.path.abspath(os.path.expanduser(raw_path))

    if not os.path.exists(target_path):
        target_path = os.path.abspath(os.path.expanduser(DOWNLOADS_DIR))
        if not os.path.exists(target_path):
            target_path = os.path.abspath(os.path.expanduser("~"))

    # If target is a file, explore its parent folder but note the file
    if os.path.isfile(target_path):
        current_dir = os.path.dirname(target_path)
        selected_file = os.path.basename(target_path)
    else:
        current_dir = target_path
        selected_file = None

    parent_dir = os.path.dirname(current_dir) if current_dir != "/" else None

    items = []
    try:
        entries = sorted(os.listdir(current_dir))
        # 1. Directories first
        for entry in entries:
            if entry.startswith(".") and entry not in [".", ".."]:
                continue
            full_p = os.path.join(current_dir, entry)
            if os.path.isdir(full_p):
                has_dbs = any(os.path.exists(os.path.join(full_p, db)) for db in ["equities.db", "indices.db", "trade.db"])
                date_m = re.search(r"(\d{4}[-_]\d{2}[-_]\d{2})", entry)
                items.append({
                    "name": entry,
                    "path": full_p,
                    "type": "folder",
                    "is_session": has_dbs,
                    "session_date": date_m.group(1).replace("-", "_") if date_m else None,
                    "is_selected": (entry == selected_file)
                })

        # 2. Files second (.rar, .zip, .db, others)
        for entry in entries:
            if entry.startswith("."):
                continue
            full_p = os.path.join(current_dir, entry)
            if os.path.isfile(full_p):
                ext = os.path.splitext(entry)[1].lower()
                is_rar = ext in [".rar", ".zip"]
                is_db = ext in [".db"]
                date_match = re.search(r"(\d{4}[-_]\d{2}[-_]\d{2})", entry)
                size_mb = round(os.path.getsize(full_p) / (1024 * 1024), 1)
                items.append({
                    "name": entry,
                    "path": full_p,
                    "type": "archive" if is_rar else ("database" if is_db else "file"),
                    "is_market_archive": bool(is_rar and date_match),
                    "is_db": is_db,
                    "session_date": date_match.group(1).replace("-", "_") if date_match else None,
                    "size_mb": size_mb,
                    "is_selected": (entry == selected_file)
                })
    except Exception as e:
        logger.warning(f"Error browsing {current_dir}: {e}")
        return jsonify({"status": "error", "message": str(e)}), 400

    return jsonify({
        "status": "success",
        "current_path": current_dir,
        "parent_path": parent_dir,
        "selected_target": target_path,
        "items": items
    })


@app.route("/api/archives", methods=["GET", "POST"])
def get_archives():
    """
    Returns market archives and extracted session folders from a target directory or specific file.
    Accepts ?dir=/path/to/folder or POST json {"directory": "/path/to/folder"}.
    Defaults to DOWNLOADS_DIR (~/Downloads).
    """
    target_dir = request.args.get("dir")
    if not target_dir and request.is_json:
        target_dir = request.json.get("directory")
    target_dir = target_dir or DOWNLOADS_DIR

    mgr = ArchiveManager(downloads_dir=target_dir)
    sources = mgr.list_archives(target_dir=target_dir)
    return jsonify({
        "status": "success",
        "scanned_directory": os.path.expanduser(target_dir),
        "count": len(sources),
        "archives": sources
    })


@app.route("/api/extract", methods=["POST"])
def extract_archives():
    """Extracts specified archive dates into data cache."""
    data = request.json or {}
    dates = data.get("dates", [])
    target_dir = data.get("directory") or DOWNLOADS_DIR
    if not dates:
        return jsonify({"status": "error", "message": "No dates specified"}), 400

    mgr = ArchiveManager(downloads_dir=target_dir)
    results = []
    for d in dates:
        res = mgr.extract_archive(d, force=data.get("force", False), target_dir=target_dir)
        results.append({"date": d, "result": res})

    return jsonify({"status": "success", "extractions": results})


@app.route("/api/run", methods=["POST"])
def run_backtest():
    """
    Executes a real backtest using MultiDayRunner on selectable directories.
    Zero mock data: all results are computed dynamically from actual SQLite databases.
    """
    global latest_run_result
    data = request.json or {}

    source_dir = data.get("directory") or DOWNLOADS_DIR
    mgr = ArchiveManager(downloads_dir=source_dir)

    selected_dates = data.get("dates", [])
    if not selected_dates:
        all_sources = mgr.list_archives(target_dir=source_dir)
        selected_dates = [a["date"] for a in all_sources]

    if not selected_dates:
        return jsonify({"status": "error", "message": "No archive dates or folders found to test"}), 400

    strategy_name = data.get("strategy", "equity")
    capital = float(data.get("capital", DEFAULT_CAPITAL))
    risk_pct = float(data.get("risk_pct", DEFAULT_RISK_PCT_PER_TRADE))
    timeframe = data.get("timeframe", "1min")
    symbols = data.get("symbols", ["RELIANCE", "HDFCBANK", "INFY"])

    try:
        # Ensure target dates are extracted if needed
        for d in selected_dates:
            mgr.extract_archive(d, target_dir=source_dir)

        runner = MultiDayRunner(capital=capital, risk_pct=risk_pct, source_dir=source_dir)

        if strategy_name == "equity":
            strat_params = {
                "min_score": int(data.get("min_score", 55)),
                "atr_sl_mult": float(data.get("atr_sl_mult", 1.5)),
                "atr_tgt_mult": float(data.get("atr_tgt_mult", 3.0)),
            }
            strat = EquityMomentumStrategy(params=strat_params)
            res = runner.run(dates=selected_dates, strategy=strat, symbols=symbols, timeframe=timeframe)

        elif strategy_name == "vwap-reversion":
            strat_params = {
                "bb_period": int(data.get("bb_period", 20)),
                "bb_std": float(data.get("bb_std", 2.0)),
                "sl_pts": float(data.get("sl_pts", 15.0)),
                "target_pts": float(data.get("target_pts", 30.0)),
            }
            strat = VwapReversionStrategy(params=strat_params)
            res = runner.run(dates=selected_dates, strategy=strat, symbols=symbols, timeframe=timeframe)

        elif strategy_name == "rsi-momentum":
            strat_params = {
                "fast_ema": int(data.get("fast_ema", 9)),
                "slow_ema": int(data.get("slow_ema", 21)),
                "rsi_period": int(data.get("rsi_period", 14)),
                "rsi_long_cutoff": float(data.get("rsi_long_cutoff", 60.0)),
            }
            strat = RsiMomentumStrategy(params=strat_params)
            res = runner.run(dates=selected_dates, strategy=strat, symbols=symbols, timeframe=timeframe)

        elif strategy_name == "options":
            strat_params = {
                "sl_points": float(data.get("sl_points", 12.0)),
                "target_multiplier": float(data.get("target_multiplier", 1.8)),
                "lot_size": int(data.get("lot_size", 25))
            }
            strat = NiftyOptionsStrategy(params=strat_params)
            res = runner.run(dates=selected_dates, strategy=strat, symbols=["NIFTY"], timeframe=timeframe)

        elif strategy_name == "ai-replay":
            strat_params = {
                "min_confidence": float(data.get("confidence", 0.70))
            }
            strat = AiSnapshotStrategy(params=strat_params)
            res = runner.run(dates=selected_dates, strategy=strat, symbols=["NIFTY"], timeframe=timeframe)

        else:
            return jsonify({"status": "error", "message": f"Unknown strategy: {strategy_name}"}), 400

        # Save to disk
        out_json = os.path.join(RESULTS_DIR, "latest_backtest.json")
        TradeExporter.export_json(res, out_json)
        out_csv = os.path.join(RESULTS_DIR, "latest_trades.csv")
        TradeExporter.export_csv(res["trades"], out_csv)

        # Convert Trade objects to serializable dicts
        trades_df = TradeExporter.to_dataframe(res["trades"])
        trades_list = trades_df.to_dict(orient="records") if not trades_df.empty else []

        serializable_res = {
            "strategy": res["strategy"],
            "dates_tested": res["dates_tested"],
            "source_directory": os.path.expanduser(source_dir),
            "initial_capital": res["initial_capital"],
            "final_equity": res["final_equity"],
            "metrics": res["metrics"],
            "daily_breakdown": res["daily_breakdown"],
            "equity_curve": res["equity_curve"],
            "drawdown_curve": res["metrics"].get("drawdown_curve", []),
            "trades": trades_list
        }

        latest_run_result = serializable_res
        return jsonify({"status": "success", "result": serializable_res})
    except Exception as e:
        logger.error(f"Backtest execution failure: {e}\n{traceback.format_exc()}")
        return jsonify({
            "status": "error",
            "message": f"{type(e).__name__}: {str(e)}",
            "details": traceback.format_exc()
        }), 500


@app.route("/api/results", methods=["GET"])
def get_latest_results():
    """Returns the results of the latest backtest run."""
    if not latest_run_result:
        latest_file = os.path.join(RESULTS_DIR, "latest_backtest.json")
        if os.path.exists(latest_file):
            with open(latest_file) as f:
                return jsonify({"status": "success", "result": json.load(f)})
        return jsonify({"status": "empty", "message": "No backtest has been executed yet."})

    return jsonify({"status": "success", "result": latest_run_result})


@app.route("/api/export_csv", methods=["GET"])
def export_csv():
    """Downloads the CSV of trades from the latest backtest."""
    csv_path = os.path.join(RESULTS_DIR, "latest_trades.csv")
    if os.path.exists(csv_path):
        return send_file(csv_path, as_attachment=True, download_name="backtest_trades.csv")
    return jsonify({"status": "error", "message": "No trades to export"}), 404


def run_server(port: int = DASHBOARD_PORT, host: str = DASHBOARD_HOST):
    logger.info(f"Starting Testing Engine Dashboard at http://{host}:{port}")
    app.run(host=host, port=port, debug=False)


if __name__ == "__main__":
    run_server()
