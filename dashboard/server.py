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
from flask import Flask, render_template, request, jsonify, send_file, Response
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
from strategies.orb_breakout import OrbBreakoutStrategy
from strategies.supertrend_trend import SupertrendTrendStrategy
from strategies.camarilla_breakout import CamarillaBreakoutStrategy
from strategies.ema_ribbon import EmaRibbonStrategy
from strategies.bollinger_percent_b import BollingerPercentBStrategy
from strategies.macd_acceleration import MacdAccelerationStrategy
from strategies.short_straddle import ShortStraddleStrategy
from strategies.pcr_reversion import PcrReversionStrategy
from strategies.banknifty_options import BankNiftyOptionsStrategy
from strategies.futures_trend import FuturesTrendStrategy
from strategies.max_pain import MaxPainConvergenceStrategy
from engine.multi_day_runner import MultiDayRunner
from engine.optimizer import StrategyOptimizer
from engine.walk_forward import WalkForwardOptimizer
from engine.param_grids import STRATEGY_REGISTRY, DEFAULT_PARAM_GRIDS, get_strategy_class, get_default_param_grid
from analytics.trade_exporter import TradeExporter
from analytics.tearsheet import generate_html_tearsheet

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("dashboard_server")

app = Flask(
    __name__,
    template_folder=os.path.join(os.path.dirname(__file__), "templates"),
    static_folder=os.path.join(os.path.dirname(__file__), "static")
)
CORS(app)

latest_run_result: Dict[str, Any] = {}


def create_strategy_instance(strategy_name: str, data: dict, symbols: list):
    """Instantiates a strategy by name with extracted parameters and resolved symbols."""
    if strategy_name == "equity":
        strat_params = {
            "min_score": int(data.get("min_score", 55)),
            "atr_sl_mult": float(data.get("atr_sl_mult", 1.5)),
            "atr_tgt_mult": float(data.get("atr_tgt_mult", 3.0)),
        }
        return EquityMomentumStrategy(params=strat_params), symbols

    elif strategy_name == "vwap-reversion":
        strat_params = {
            "bb_period": int(data.get("bb_period", 20)),
            "bb_std": float(data.get("bb_std", 2.0)),
            "sl_pts": float(data.get("sl_pts", 15.0)),
            "target_pts": float(data.get("target_pts", 30.0)),
        }
        return VwapReversionStrategy(params=strat_params), symbols

    elif strategy_name == "rsi-momentum":
        strat_params = {
            "fast_ema": int(data.get("fast_ema", 9)),
            "slow_ema": int(data.get("slow_ema", 21)),
            "rsi_period": int(data.get("rsi_period", 14)),
            "rsi_long_cutoff": float(data.get("rsi_long_cutoff", 60.0)),
        }
        return RsiMomentumStrategy(params=strat_params), symbols

    elif strategy_name == "orb":
        strat_params = {
            "opening_minutes": int(data.get("opening_minutes", 15)),
            "risk_reward": float(data.get("risk_reward", 2.0)),
            "breakout_atr_mult": float(data.get("breakout_atr_mult", 0.5)),
        }
        return OrbBreakoutStrategy(params=strat_params), symbols

    elif strategy_name == "supertrend":
        strat_params = {
            "atr_period": int(data.get("atr_period", 10)),
            "multiplier": float(data.get("multiplier", 3.0)),
            "ema_filter": int(data.get("ema_filter", 50)),
            "risk_reward": float(data.get("risk_reward", 2.0)),
        }
        return SupertrendTrendStrategy(params=strat_params), symbols

    elif strategy_name == "camarilla":
        strat_params = {
            "risk_reward": float(data.get("risk_reward", 2.0)),
            "sl_buffer_pts": float(data.get("sl_buffer_pts", 5.0)),
        }
        return CamarillaBreakoutStrategy(params=strat_params), symbols

    elif strategy_name == "ema-ribbon":
        strat_params = {
            "fast_ema": int(data.get("fast_ema", 9)),
            "med_ema": int(data.get("med_ema", 21)),
            "slow_ema": int(data.get("slow_ema", 50)),
            "sl_pts": float(data.get("sl_pts", 15.0)),
            "target_pts": float(data.get("target_pts", 30.0)),
        }
        return EmaRibbonStrategy(params=strat_params), symbols

    elif strategy_name == "bollinger-b":
        strat_params = {
            "period": int(data.get("bb_period", 20)),
            "std_dev": float(data.get("bb_std", 2.0)),
            "oversold_b": float(data.get("oversold_b", 0.05)),
            "overbought_b": float(data.get("overbought_b", 0.95)),
            "sl_pts": float(data.get("sl_pts", 15.0)),
            "target_pts": float(data.get("target_pts", 30.0)),
        }
        return BollingerPercentBStrategy(params=strat_params), symbols

    elif strategy_name == "macd-accel":
        strat_params = {
            "fast_period": int(data.get("fast_period", 12)),
            "slow_period": int(data.get("slow_period", 26)),
            "signal_period": int(data.get("signal_period", 9)),
            "sl_pts": float(data.get("sl_pts", 15.0)),
            "target_pts": float(data.get("target_pts", 35.0)),
        }
        return MacdAccelerationStrategy(params=strat_params), symbols

    elif strategy_name == "options":
        strat_params = {
            "sl_points": float(data.get("sl_points", 12.0)),
            "target_multiplier": float(data.get("target_multiplier", 1.8)),
            "lot_size": int(data.get("lot_size", 25))
        }
        return NiftyOptionsStrategy(params=strat_params), ["NIFTY"]

    elif strategy_name == "ai-replay":
        strat_params = {
            "min_confidence": float(data.get("confidence", 0.70))
        }
        return AiSnapshotStrategy(params=strat_params), ["NIFTY"]

    elif strategy_name == "short-straddle":
        strat_params = {
            "entry_time": str(data.get("entry_time", "09:20")),
            "sl_pct": float(data.get("sl_pct", 0.25)),
            "target_pct": float(data.get("target_pct", 0.60)),
            "lot_size": int(data.get("lot_size", 25)),
            "strike_step": float(data.get("strike_step", 50.0)),
            "otm_strikes": int(data.get("otm_strikes", 0)),
        }
        return ShortStraddleStrategy(params=strat_params), ["NIFTY"]

    elif strategy_name == "pcr-reversion":
        strat_params = {
            "pcr_oversold": float(data.get("pcr_oversold", 0.70)),
            "pcr_overbought": float(data.get("pcr_overbought", 1.35)),
            "sl_pct": float(data.get("sl_pct", 0.25)),
            "target_pct": float(data.get("target_pct", 0.50)),
            "lot_size": int(data.get("lot_size", 25)),
            "strike_step": float(data.get("strike_step", 50.0)),
        }
        return PcrReversionStrategy(params=strat_params), ["NIFTY"]

    elif strategy_name == "banknifty-options":
        strat_params = {
            "orb_window_minutes": int(data.get("orb_window_minutes", 15)),
            "sl_points": float(data.get("sl_points", 30.0)),
            "target_multiplier": float(data.get("target_multiplier", 2.0)),
            "lot_size": int(data.get("lot_size", 15)),
            "strike_step": float(data.get("strike_step", 100.0)),
        }
        return BankNiftyOptionsStrategy(params=strat_params), ["BANKNIFTY"]

    elif strategy_name == "futures-trend":
        strat_params = {
            "fast_ema": int(data.get("fast_ema", 9)),
            "mid_ema": int(data.get("mid_ema", 21)),
            "slow_ema": int(data.get("slow_ema", 50)),
            "atr_multiplier": float(data.get("atr_multiplier", 1.5)),
            "risk_reward": float(data.get("risk_reward", 2.0)),
            "lot_size": int(data.get("lot_size", 25)),
        }
        return FuturesTrendStrategy(params=strat_params), ["NIFTY"]

    elif strategy_name == "max-pain":
        strat_params = {
            "entry_start_time": str(data.get("entry_start_time", "11:30")),
            "entry_end_time": str(data.get("entry_end_time", "14:15")),
            "min_displacement": float(data.get("min_displacement", 40.0)),
            "sl_pct": float(data.get("sl_pct", 0.30)),
            "target_pct": float(data.get("target_pct", 0.50)),
            "lot_size": int(data.get("lot_size", 25)),
            "strike_step": float(data.get("strike_step", 50.0)),
        }
        return MaxPainConvergenceStrategy(params=strat_params), ["NIFTY"]

    else:
        raise ValueError(f"Unknown strategy: {strategy_name}")


def serialize_run_result(res: dict, source_dir: str) -> dict:
    """Converts Trade objects to serializable dicts and formats run output."""
    trades_df = TradeExporter.to_dataframe(res["trades"])
    trades_list = trades_df.to_dict(orient="records") if not trades_df.empty else []
    return {
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
        strat, strat_symbols = create_strategy_instance(strategy_name, data, symbols)
        res = runner.run(dates=selected_dates, strategy=strat, symbols=strat_symbols, timeframe=timeframe)
        serializable_res = serialize_run_result(res, source_dir)

        # Save clean serializable JSON & CSV to disk
        out_json = os.path.join(RESULTS_DIR, "latest_backtest.json")
        with open(out_json, "w") as f:
            json.dump(serializable_res, f, indent=2)

        out_csv = os.path.join(RESULTS_DIR, "latest_trades.csv")
        TradeExporter.export_csv(res["trades"], out_csv)

        latest_run_result = serializable_res
        return jsonify({
            "status": "success",
            "result": serializable_res,
            "metrics": serializable_res["metrics"],
            "trades": serializable_res["trades"]
        })
    except Exception as e:
        logger.error(f"Backtest execution failure: {e}\n{traceback.format_exc()}")
        return jsonify({
            "status": "error",
            "message": f"{type(e).__name__}: {str(e)}",
            "details": traceback.format_exc()
        }), 500


@app.route("/api/run/stream", methods=["POST"])
def run_backtest_stream():
    """
    Executes a real backtest and streams live session progress events via SSE (text/event-stream).
    Zero mock data: runs real simulation session-by-session.
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

    def event_stream():
        global latest_run_result
        try:
            for d in selected_dates:
                mgr.extract_archive(d, target_dir=source_dir)

            runner = MultiDayRunner(capital=capital, risk_pct=risk_pct, source_dir=source_dir)
            strat, strat_symbols = create_strategy_instance(strategy_name, data, symbols)

            for event in runner.stream(dates=selected_dates, strategy=strat, symbols=strat_symbols, timeframe=timeframe):
                if event.get("type") == "complete":
                    res = event["result"]
                    serializable_res = serialize_run_result(res, source_dir)

                    out_json = os.path.join(RESULTS_DIR, "latest_backtest.json")
                    with open(out_json, "w") as f:
                        json.dump(serializable_res, f, indent=2)

                    out_csv = os.path.join(RESULTS_DIR, "latest_trades.csv")
                    TradeExporter.export_csv(res["trades"], out_csv)

                    latest_run_result = serializable_res
                    event["result"] = serializable_res

                yield f"data: {json.dumps(event)}\n\n"
        except Exception as e:
            logger.error(f"Stream error: {e}\n{traceback.format_exc()}")
            err_event = {"type": "error", "message": f"{type(e).__name__}: {str(e)}"}
            yield f"data: {json.dumps(err_event)}\n\n"

    return Response(event_stream(), mimetype="text/event-stream")


@app.route("/api/compare", methods=["POST"])
def compare_strategies():
    """
    Executes multiple strategies across the same dates and returns comparative metrics
    and equity curves for side-by-side evaluation.
    """
    data = request.json or {}
    source_dir = data.get("directory") or DOWNLOADS_DIR
    mgr = ArchiveManager(downloads_dir=source_dir)

    selected_dates = data.get("dates", [])
    if not selected_dates:
        all_sources = mgr.list_archives(target_dir=source_dir)
        selected_dates = [a["date"] for a in all_sources]

    if not selected_dates:
        return jsonify({"status": "error", "message": "No archive dates found to test"}), 400

    strat_list = data.get("strategies", [
        "equity", "orb", "supertrend", "camarilla", "ema-ribbon", "bollinger-b",
        "macd-accel", "vwap-reversion", "rsi-momentum", "options", "ai-replay",
        "short-straddle", "pcr-reversion", "banknifty-options", "futures-trend", "max-pain"
    ])
    capital = float(data.get("capital", DEFAULT_CAPITAL))
    risk_pct = float(data.get("risk_pct", DEFAULT_RISK_PCT_PER_TRADE))
    timeframe = data.get("timeframe", "1min")
    symbols = data.get("symbols", ["RELIANCE", "HDFCBANK", "INFY"])

    for d in selected_dates:
        mgr.extract_archive(d, target_dir=source_dir)

    comparison_results = []
    for s_name in strat_list:
        try:
            strat, strat_symbols = create_strategy_instance(s_name, data, symbols)
            runner = MultiDayRunner(capital=capital, risk_pct=risk_pct, source_dir=source_dir, compound_capital=False, parallel=True)
            res = runner.run(dates=selected_dates, strategy=strat, symbols=strat_symbols, timeframe=timeframe)
            m = res["metrics"]
            comparison_results.append({
                "strategy_key": s_name,
                "strategy_name": strat.name,
                "metrics": {
                    "total_trades": m["total_trades"],
                    "wins": m["wins"],
                    "losses": m["losses"],
                    "breakeven_count": m["breakeven_count"],
                    "win_rate": m["win_rate"],
                    "gross_pnl": m["gross_pnl"],
                    "total_charges": m["total_charges"],
                    "net_pnl": m["net_pnl"],
                    "return_pct": m["return_pct"],
                    "profit_factor": m["profit_factor"],
                    "expectancy": m["expectancy"],
                    "sharpe_ratio": m["sharpe_ratio"],
                    "sortino_ratio": m["sortino_ratio"],
                    "calmar_ratio": m["calmar_ratio"],
                    "max_drawdown_pct": m["max_drawdown_pct"],
                    "max_consecutive_wins": m["max_consecutive_wins"],
                    "max_consecutive_losses": m["max_consecutive_losses"]
                },
                "equity_curve": res["equity_curve"]
            })
        except Exception as e:
            logger.warning(f"Error comparing strategy {s_name}: {e}")
            comparison_results.append({
                "strategy_key": s_name,
                "error": str(e)
            })

    return jsonify({
        "status": "success",
        "dates_tested": selected_dates,
        "comparison": comparison_results
    })


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


@app.route("/api/strategy_params", methods=["GET"])
def get_strategy_params():
    """Returns default parameter grids and registered strategy keys."""
    return jsonify({
        "status": "success",
        "strategies": list(STRATEGY_REGISTRY.keys()),
        "grids": DEFAULT_PARAM_GRIDS
    })


@app.route("/api/walk_forward", methods=["POST"])
def run_walk_forward_api():
    """
    Executes rolling Walk-Forward Optimization across market sessions.
    Evaluates In-Sample parameter tuning and Out-Of-Sample forward testing efficiency.
    """
    data = request.json or {}
    strategy_name = data.get("strategy", "orb")
    source_dir = data.get("directory") or DOWNLOADS_DIR
    mgr = ArchiveManager(downloads_dir=source_dir)

    selected_dates = data.get("dates", [])
    if not selected_dates:
        all_sources = mgr.list_archives(target_dir=source_dir)
        selected_dates = [a["date"] for a in all_sources]

    in_sample = int(data.get("in_sample", 3))
    out_of_sample = int(data.get("out_of_sample", 1))
    total_needed = in_sample + out_of_sample

    if len(selected_dates) < total_needed:
        return jsonify({
            "status": "error",
            "message": f"Walk-Forward requires at least {total_needed} dates (in_sample={in_sample}, out_of_sample={out_of_sample}), got {len(selected_dates)}"
        }), 400

    rank_by = data.get("rank_by", "sharpe_ratio")
    capital = float(data.get("capital", DEFAULT_CAPITAL))
    risk_pct = float(data.get("risk_pct", DEFAULT_RISK_PCT_PER_TRADE))
    sym_in = data.get("symbols", ["RELIANCE", "HDFCBANK", "INFY"])
    symbols = ["auto"] if (isinstance(sym_in, str) and sym_in.lower() == "auto") else (sym_in if isinstance(sym_in, list) else None)

    try:
        strat_cls = get_strategy_class(strategy_name)
        param_grid = data.get("param_grid") or get_default_param_grid(strategy_name)

        for d in selected_dates:
            mgr.extract_archive(d, target_dir=source_dir)

        runner = MultiDayRunner(capital=capital, risk_pct=risk_pct, source_dir=source_dir, compound_capital=False)
        wfo = WalkForwardOptimizer(runner=runner, in_sample_len=in_sample, out_of_sample_len=out_of_sample)
        res = wfo.run_walk_forward(
            strategy_class=strat_cls,
            param_grid=param_grid,
            dates=selected_dates,
            symbols=symbols,
            rank_by=rank_by
        )

        return jsonify({
            "status": "success",
            "strategy": strategy_name,
            "walk_forward_efficiency": res["walk_forward_efficiency"],
            "is_robust": res["is_robust"],
            "total_windows": res["total_windows"],
            "windows": res["windows"],
            "overall_oos_metrics": res["overall_oos_metrics"]
        })
    except Exception as e:
        logger.error(f"Walk-forward optimization failure: {e}\n{traceback.format_exc()}")
        return jsonify({
            "status": "error",
            "message": f"{type(e).__name__}: {str(e)}",
            "details": traceback.format_exc()
        }), 500


@app.route("/api/optimize", methods=["POST"])
def run_optimize_api():
    """
    Performs grid-search parameter optimization across historical market recordings.
    Ranks parameter combinations by chosen metric (Sharpe, P&L, Profit Factor, Win Rate).
    """
    data = request.json or {}
    strategy_name = data.get("strategy", "orb")
    source_dir = data.get("directory") or DOWNLOADS_DIR
    mgr = ArchiveManager(downloads_dir=source_dir)

    selected_dates = data.get("dates", [])
    if not selected_dates:
        all_sources = mgr.list_archives(target_dir=source_dir)
        selected_dates = [a["date"] for a in all_sources]

    if not selected_dates:
        return jsonify({"status": "error", "message": "No dates available for optimization"}), 400

    rank_by = data.get("rank_by", "sharpe_ratio")
    capital = float(data.get("capital", DEFAULT_CAPITAL))
    risk_pct = float(data.get("risk_pct", DEFAULT_RISK_PCT_PER_TRADE))
    sym_in = data.get("symbols", ["RELIANCE", "HDFCBANK", "INFY"])
    symbols = ["auto"] if (isinstance(sym_in, str) and sym_in.lower() == "auto") else (sym_in if isinstance(sym_in, list) else None)

    try:
        strat_cls = get_strategy_class(strategy_name)
        param_grid = data.get("param_grid") or get_default_param_grid(strategy_name)

        for d in selected_dates:
            mgr.extract_archive(d, target_dir=source_dir)

        runner = MultiDayRunner(capital=capital, risk_pct=risk_pct, source_dir=source_dir, compound_capital=False, parallel=True)
        optimizer = StrategyOptimizer(runner=runner)
        ranked = optimizer.optimize(
            strategy_class=strat_cls,
            param_grid=param_grid,
            dates=selected_dates,
            symbols=symbols,
            rank_by=rank_by
        )

        return jsonify({
            "status": "success",
            "strategy": strategy_name,
            "rank_by": rank_by,
            "total_combinations": len(ranked),
            "best_params": ranked[0]["params"] if ranked else {},
            "ranked_results": ranked[:50]
        })
    except Exception as e:
        logger.error(f"Parameter optimization failure: {e}\n{traceback.format_exc()}")
        return jsonify({
            "status": "error",
            "message": f"{type(e).__name__}: {str(e)}",
            "details": traceback.format_exc()
        }), 500


@app.route("/api/tearsheet", methods=["GET"])
def view_tearsheet():
    """Renders the standalone institutional HTML tearsheet for the latest run."""
    run_data = latest_run_result
    if not run_data:
        latest_file = os.path.join(RESULTS_DIR, "latest_backtest.json")
        if os.path.exists(latest_file):
            with open(latest_file) as f:
                run_data = json.load(f)

    if not run_data:
        return """<!DOCTYPE html><html><body style="background:#0d1117;color:#fff;font-family:sans-serif;padding:40px;text-align:center;">
        <h2>No backtest results found</h2>
        <p style="color:#8b949e;">Please run a backtest first from the Testing Engine Console.</p>
        </body></html>""", 404

    html = generate_html_tearsheet(run_data)
    return Response(html, mimetype="text/html")


@app.route("/api/export_tearsheet", methods=["GET"])
def export_tearsheet():
    """Downloads the standalone institutional HTML tearsheet."""
    run_data = latest_run_result
    if not run_data:
        latest_file = os.path.join(RESULTS_DIR, "latest_backtest.json")
        if os.path.exists(latest_file):
            with open(latest_file) as f:
                run_data = json.load(f)

    if not run_data:
        return jsonify({"status": "error", "message": "No backtest results to export"}), 404

    html = generate_html_tearsheet(run_data)
    strat = run_data.get("strategy", "strategy").lower().replace(" ", "_")
    return Response(
        html,
        mimetype="text/html",
        headers={"Content-Disposition": f"attachment; filename=tearsheet_{strat}.html"}
    )


def run_server(port: int = DASHBOARD_PORT, host: str = DASHBOARD_HOST):
    logger.info(f"Starting Testing Engine Dashboard at http://{host}:{port}")
    app.run(host=host, port=port, debug=False)


if __name__ == "__main__":
    run_server()
