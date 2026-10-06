"""
dashboard/blueprints/backtest.py — Backtest execution and streaming routes.
"""

import json
import logging
import os
import traceback
from typing import Any, Dict
from flask import Blueprint, request, jsonify, send_file, Response

from config import DEFAULT_CAPITAL, DEFAULT_RISK_PCT_PER_TRADE, DOWNLOADS_DIR, RESULTS_DIR
from analytics.trade_exporter import TradeExporter
from engine.multi_day_runner import MultiDayRunner
from engine.param_grids import STRATEGY_REGISTRY

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

import dashboard.server as server

logger = logging.getLogger("dashboard_backtest")
backtest_bp = Blueprint("backtest_bp", __name__)


def resolve_server_symbols(sym_in) -> list:
    """Safely normalizes symbols payload into clean uppercase list or ['auto'] default."""
    if sym_in is None or sym_in == ["auto"] or sym_in == "auto" or sym_in == [] or sym_in == "":
        return ["auto"]
    if isinstance(sym_in, str):
        cleaned = [s.strip().upper() for s in sym_in.split(",") if s.strip()]
        return ["auto"] if (not cleaned or cleaned == ["AUTO"]) else cleaned
    if isinstance(sym_in, list):
        cleaned = [str(s).strip().upper() for s in sym_in if str(s).strip()]
        return ["auto"] if (not cleaned or cleaned == ["AUTO"]) else cleaned
    return ["auto"]


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
            "lot_size": int(data.get("lot_size", 25)),
            "strike_mode": str(data.get("strike_mode", "ATM")),
            "expiry_mode": str(data.get("expiry_mode", "CURRENT_WEEKLY")),
            "instrument_type": str(data.get("instrument_type", "OPTION_CE")),
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
            "expiry_mode": str(data.get("expiry_mode", "CURRENT_WEEKLY")),
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
            "strike_mode": str(data.get("strike_mode", "ATM")),
            "expiry_mode": str(data.get("expiry_mode", "CURRENT_WEEKLY")),
        }
        return PcrReversionStrategy(params=strat_params), ["NIFTY"]

    elif strategy_name == "banknifty-options":
        strat_params = {
            "orb_window_minutes": int(data.get("orb_window_minutes", 15)),
            "sl_points": float(data.get("sl_points", 30.0)),
            "target_multiplier": float(data.get("target_multiplier", 2.0)),
            "lot_size": int(data.get("lot_size", 15)),
            "strike_step": float(data.get("strike_step", 100.0)),
            "strike_mode": str(data.get("strike_mode", "ATM")),
            "expiry_mode": str(data.get("expiry_mode", "CURRENT_WEEKLY")),
            "instrument_type": str(data.get("instrument_type", "OPTION_CE")),
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
            "instrument_type": str(data.get("instrument_type", "FUTURES")),
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
            "strike_mode": str(data.get("strike_mode", "ATM")),
            "expiry_mode": str(data.get("expiry_mode", "CURRENT_WEEKLY")),
        }
        return MaxPainConvergenceStrategy(params=strat_params), ["NIFTY"]

    elif strategy_name in ("trading-engine-v4", "trading_engine_v4"):
        from strategies.trading_engine_v4 import TradingEngineV4Strategy
        strat_symbols = symbols if symbols != ["auto"] else ["NIFTY"]
        return TradingEngineV4Strategy(params=data), strat_symbols

    else:
        norm_name = strategy_name.replace("-", "_")
        dash_name = strategy_name.replace("_", "-")
        cls = (
            STRATEGY_REGISTRY.get(strategy_name)
            or STRATEGY_REGISTRY.get(norm_name)
            or STRATEGY_REGISTRY.get(dash_name)
        )
        if cls:
            try:
                return cls(params=data), symbols
            except TypeError:
                inst = cls()
                if hasattr(inst, "current_params"):
                    inst.current_params.update(data)
                return inst, symbols
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


@backtest_bp.route("/api/run", methods=["POST"])
def run_backtest():
    """Executes a real backtest using MultiDayRunner on selectable directories."""
    data = request.json or {}

    source_dir = data.get("directory") or DOWNLOADS_DIR
    mgr = server.ArchiveManager(downloads_dir=source_dir)

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
        portfolio_config = {
            "sizing_mode": data.get("sizing_mode", "risk_based"),
            "fixed_lots": int(data.get("fixed_lots", 1)),
            "lot_multiplier": float(data.get("lot_multiplier", 1.0)),
            "custom_lot_size": int(data.get("custom_lot_size")) if data.get("custom_lot_size") else None,
            "fixed_qty": int(data.get("fixed_qty", 0)),
            "capital_pct": float(data.get("capital_pct", 0.10)),
        }
        for d in selected_dates:
            mgr.extract_archive(d, target_dir=source_dir)

        runner = MultiDayRunner(capital=capital, risk_pct=risk_pct, source_dir=source_dir, portfolio_config=portfolio_config)
        strat, strat_symbols = server.create_strategy_instance(strategy_name, data, symbols)
        res = runner.run(dates=selected_dates, strategy=strat, symbols=strat_symbols, timeframe=timeframe)
        serializable_res = server.serialize_run_result(res, source_dir)

        out_json = os.path.join(RESULTS_DIR, "latest_backtest.json")
        with open(out_json, "w") as f:
            json.dump(serializable_res, f, indent=2)

        out_csv = os.path.join(RESULTS_DIR, "latest_trades.csv")
        TradeExporter.export_csv(res["trades"], out_csv)

        server.latest_run_result = serializable_res
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


@backtest_bp.route("/api/run/stream", methods=["POST"])
def run_backtest_stream():
    """Executes a real backtest and streams live session progress events via SSE."""
    data = request.json or {}

    source_dir = data.get("directory") or DOWNLOADS_DIR
    mgr = server.ArchiveManager(downloads_dir=source_dir)

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
    symbols = server.resolve_server_symbols(data.get("symbols"))

    portfolio_config = {
        "sizing_mode": data.get("sizing_mode", "risk_based"),
        "fixed_lots": int(data.get("fixed_lots", 1)),
        "lot_multiplier": float(data.get("lot_multiplier", 1.0)),
        "custom_lot_size": int(data.get("custom_lot_size")) if data.get("custom_lot_size") else None,
        "fixed_qty": int(data.get("fixed_qty", 0)),
        "capital_pct": float(data.get("capital_pct", 0.10)),
    }

    def event_stream():
        try:
            for d in selected_dates:
                mgr.extract_archive(d, target_dir=source_dir)

            runner = MultiDayRunner(capital=capital, risk_pct=risk_pct, source_dir=source_dir, portfolio_config=portfolio_config)
            strat, strat_symbols = server.create_strategy_instance(strategy_name, data, symbols)

            for event in runner.stream(dates=selected_dates, strategy=strat, symbols=strat_symbols, timeframe=timeframe):
                if event.get("type") == "complete":
                    res = event.get("result")
                    if isinstance(res, dict):
                        serializable_res = server.serialize_run_result(res, source_dir)

                        out_json = os.path.join(RESULTS_DIR, "latest_backtest.json")
                        with open(out_json, "w") as f:
                            json.dump(serializable_res, f, indent=2)

                        trades_list = res.get("trades")
                        if isinstance(trades_list, list):
                            out_csv = os.path.join(RESULTS_DIR, "latest_trades.csv")
                            TradeExporter.export_csv(trades_list, out_csv)

                        server.latest_run_result = serializable_res
                        event["result"] = serializable_res

                yield f"data: {json.dumps(event)}\n\n"
        except Exception as e:
            logger.error(f"Stream error: {e}\n{traceback.format_exc()}")
    return Response(event_stream(), mimetype="text/event-stream")


@backtest_bp.route("/api/compare", methods=["POST"])
@backtest_bp.route("/api/compare_models", methods=["POST"])
def api_compare_models():
    """Executes multiple strategies across selected sessions in parallel."""
    data = request.json or {}
    source_dir = data.get("directory") or DOWNLOADS_DIR
    mgr = server.ArchiveManager(downloads_dir=source_dir)

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
    symbols = server.resolve_server_symbols(data.get("symbols"))

    portfolio_config = {
        "sizing_mode": data.get("sizing_mode", "risk_based"),
        "fixed_lots": int(data.get("fixed_lots", 1)),
        "lot_multiplier": float(data.get("lot_multiplier", 1.0)),
        "custom_lot_size": int(data.get("custom_lot_size")) if data.get("custom_lot_size") else None,
        "fixed_qty": int(data.get("fixed_qty", 0)),
        "capital_pct": float(data.get("capital_pct", 0.10)),
    }

    for d in selected_dates:
        mgr.extract_archive(d, target_dir=source_dir)

    comparison_results = []
    for s_name in strat_list:
        try:
            strat, strat_symbols = server.create_strategy_instance(s_name, data, symbols)
            runner = MultiDayRunner(
                capital=capital,
                risk_pct=risk_pct,
                source_dir=source_dir,
                compound_capital=False,
                parallel=True,
                portfolio_config=portfolio_config
            )
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


@backtest_bp.route("/api/results", methods=["GET"])
def get_latest_results():
    """Returns the results of the latest backtest run."""
    if not server.latest_run_result:
        latest_file = os.path.join(RESULTS_DIR, "latest_backtest.json")
        if os.path.exists(latest_file):
            with open(latest_file) as f:
                return jsonify({"status": "success", "result": json.load(f)})
        return jsonify({"status": "empty", "message": "No backtest has been executed yet."})

    return jsonify({"status": "success", "result": server.latest_run_result})


@backtest_bp.route("/api/export_csv", methods=["GET"])
def export_csv():
    """Downloads the CSV of trades from the latest backtest."""
    csv_path = os.path.join(RESULTS_DIR, "latest_trades.csv")
    if os.path.exists(csv_path):
        return send_file(csv_path, mimetype="text/csv", as_attachment=True, download_name="backtest_trades.csv")
    return jsonify({"status": "error", "message": "No trades to export"}), 404


__all__ = [
    "backtest_bp",
    "resolve_server_symbols",
    "create_strategy_instance",
    "serialize_run_result",
]
