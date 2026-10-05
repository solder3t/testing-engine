"""
dashboard/blueprints/optimize.py — Parameter optimization, walk-forward, mass iteration, and validation endpoints.
"""

import json
import logging
import traceback
from flask import Blueprint, request, jsonify, Response

from config import DEFAULT_CAPITAL, DEFAULT_RISK_PCT_PER_TRADE, DOWNLOADS_DIR
from data.data_loader import DataLoader
from data.quality_auditor import DataQualityAuditor
from analytics.matrix_analyzer import MatrixAnalyzer
from analytics.session_store import SessionStore
from analytics.validation_report import CandidateValidator
from engine.multi_day_runner import MultiDayRunner
from engine.param_grids import get_strategy_class, get_default_param_grid
from engine.mass_optimizer import MassOptimizer

import dashboard.server as server

logger = logging.getLogger("dashboard_optimize")
optimize_bp = Blueprint("optimize_bp", __name__)

mass_optimizer = MassOptimizer()
session_store = SessionStore()


@optimize_bp.route("/api/walk_forward", methods=["POST"])
def run_walk_forward_api():
    """Executes rolling Walk-Forward Optimization across market sessions."""
    data = request.json or {}
    strategy_name = data.get("strategy", "orb")
    source_dir = data.get("directory") or DOWNLOADS_DIR
    mgr = server.ArchiveManager(downloads_dir=source_dir)

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
    symbols = server.resolve_server_symbols(data.get("symbols"))

    try:
        strat_cls = get_strategy_class(strategy_name)
        param_grid = data.get("param_grid") or get_default_param_grid(strategy_name)

        for d in selected_dates:
            mgr.extract_archive(d, target_dir=source_dir)

        runner = MultiDayRunner(capital=capital, risk_pct=risk_pct, source_dir=source_dir, compound_capital=False)
        wfo = server.WalkForwardOptimizer(runner=runner, in_sample_len=in_sample, out_of_sample_len=out_of_sample)
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


@optimize_bp.route("/api/optimize", methods=["POST"])
def run_optimize_api():
    """Performs grid-search parameter optimization across historical market recordings."""
    data = request.json or {}
    strategy_name = data.get("strategy", "orb")
    source_dir = data.get("directory") or DOWNLOADS_DIR
    mgr = server.ArchiveManager(downloads_dir=source_dir)

    selected_dates = data.get("dates", [])
    if not selected_dates:
        all_sources = mgr.list_archives(target_dir=source_dir)
        selected_dates = [a["date"] for a in all_sources]

    if not selected_dates:
        return jsonify({"status": "error", "message": "No dates available for optimization"}), 400

    rank_by = data.get("rank_by", "sharpe_ratio")
    capital = float(data.get("capital", DEFAULT_CAPITAL))
    risk_pct = float(data.get("risk_pct", DEFAULT_RISK_PCT_PER_TRADE))
    symbols = server.resolve_server_symbols(data.get("symbols"))

    try:
        strat_cls = get_strategy_class(strategy_name)
        param_grid = data.get("param_grid") or get_default_param_grid(strategy_name)

        for d in selected_dates:
            mgr.extract_archive(d, target_dir=source_dir)

        runner = MultiDayRunner(capital=capital, risk_pct=risk_pct, source_dir=source_dir, compound_capital=False, parallel=True)
        optimizer = server.StrategyOptimizer(runner=runner)
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


@optimize_bp.route("/api/validate", methods=["POST"])
def run_validation():
    """Executes backtest and computes comprehensive institutional validation metrics."""
    try:
        data = request.json or {}
        strategy_name = data.get("strategy", "orb")
        selected_dates = data.get("dates", [])
        capital = float(data.get("capital", DEFAULT_CAPITAL))
        risk_pct = float(data.get("risk_pct", DEFAULT_RISK_PCT_PER_TRADE))
        source_dir = data.get("directory") or DOWNLOADS_DIR

        symbols_input = data.get("symbols", ["auto"])
        resolved_syms = server.resolve_server_symbols(symbols_input)

        strat_cls = get_strategy_class(strategy_name)
        if not strat_cls:
            return jsonify({"status": "error", "message": f"Strategy '{strategy_name}' not found"}), 400

        strategy, symbols = server.create_strategy_instance(strategy_name, data, resolved_syms)

        mgr = server.ArchiveManager(downloads_dir=source_dir)
        for d in selected_dates:
            mgr.extract_archive(d, target_dir=source_dir)

        runner = MultiDayRunner(capital=capital, risk_pct=risk_pct, source_dir=source_dir, compound_capital=False)
        run_res = runner.run(strategy=strategy, dates=selected_dates, symbols=symbols)

        validator = CandidateValidator()
        report = validator.validate(run_res)

        return jsonify({
            "status": "success",
            "report": report
        })
    except Exception as e:
        logger.error(f"Validation failure: {e}\n{traceback.format_exc()}")
        return jsonify({
            "status": "error",
            "message": f"{type(e).__name__}: {str(e)}",
            "details": traceback.format_exc()
        }), 500


@optimize_bp.route("/api/data_audit", methods=["GET", "POST"])
def run_data_audit():
    """Runs data quality audit for given dates and symbols."""
    try:
        data = (request.get_json(silent=True) if request.is_json else None) or request.args.to_dict() or {}
        dates = data.get("dates", [])
        if isinstance(dates, str):
            dates = [d.strip() for d in dates.split(",") if d.strip()]
        symbols = data.get("symbols", ["NIFTY"])
        if isinstance(symbols, str):
            symbols = [s.strip() for s in symbols.split(",") if s.strip()]
        data_dir = data.get("directory") or DOWNLOADS_DIR

        dl = DataLoader(source_dir=data_dir)
        results = []
        for d in dates:
            for s in symbols:
                df = dl.get_bars(d, s)
                report = DataQualityAuditor.audit(df, s, d)
                results.append(report.to_dict())
        return jsonify({"status": "success", "results": results})
    except Exception as e:
        logger.error(f"Data audit failure: {e}\n{traceback.format_exc()}")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


@optimize_bp.route("/api/mass_optimize", methods=["POST"])
def api_mass_optimize():
    """Submits a mass iteration parameter sweep job."""
    spec = request.get_json() or {}
    job = mass_optimizer.submit_job(spec)
    return jsonify({
        "status": "submitted",
        "job_id": job.job_id,
        "total_runs": job.total,
        "status_info": job.to_status_dict()
    })


@optimize_bp.route("/api/mass_optimize/stream/<job_id>", methods=["GET"])
def api_mass_optimize_stream(job_id: str):
    """Server-Sent Events (SSE) live progress stream for a running mass iteration job."""
    job = mass_optimizer.get_job(job_id)
    if not job:
        return jsonify({"status": "error", "message": "Job not found"}), 404

    def event_stream():
        while True:
            try:
                event = job.progress_queue.get(timeout=2.0)
                yield f"data: {json.dumps(event, default=str)}\n\n"
                if event.get("type") in ("done", "error"):
                    break
            except Exception:
                if job.status in ("DONE", "ERROR", "CANCELLED"):
                    yield f"data: {json.dumps({'type': job.status.lower(), 'job_id': job_id}, default=str)}\n\n"
                    break
                yield f": heartbeat\n\n"

    return Response(event_stream(), mimetype="text/event-stream")


@optimize_bp.route("/api/mass_optimize/status/<job_id>", methods=["GET"])
def api_mass_optimize_status(job_id: str):
    """Returns current status and execution metrics for a job."""
    job = mass_optimizer.get_job(job_id)
    if not job:
        return jsonify({"status": "error", "message": "Job not found"}), 404
    return jsonify({
        "status": "success",
        "job": job.to_status_dict(),
        "has_results": job.results is not None
    })


@optimize_bp.route("/api/mass_optimize/results/<job_id>", methods=["GET"])
def api_mass_optimize_results(job_id: str):
    """Returns completed results dictionary for a job."""
    job = mass_optimizer.get_job(job_id)
    if not job or not job.results:
        return jsonify({"status": "error", "message": "Results not ready or job not found"}), 404
    return jsonify({
        "status": "success",
        "results": job.results
    })


@optimize_bp.route("/api/mass_optimize/cancel/<job_id>", methods=["POST"])
def api_mass_optimize_cancel(job_id: str):
    """Cancels a running mass iteration job."""
    ok = mass_optimizer.cancel_job(job_id)
    return jsonify({"status": "success" if ok else "error", "cancelled": ok})


@optimize_bp.route("/api/sessions", methods=["GET"])
def api_list_sessions():
    """Lists saved experiment sessions from disk."""
    return jsonify({"status": "success", "sessions": session_store.list_sessions()})


@optimize_bp.route("/api/sessions/<session_id>", methods=["GET"])
def api_get_session(session_id: str):
    """Loads a specific saved session payload."""
    session = session_store.get_session(session_id)
    if not session:
        return jsonify({"status": "error", "message": "Session not found"}), 404
    return jsonify({"status": "success", "session": session})


@optimize_bp.route("/api/sessions/save", methods=["POST"])
def api_save_session():
    """Saves a completed job or custom result payload as a session."""
    data = request.get_json() or {}
    job_id = data.get("job_id")
    job = mass_optimizer.get_job(job_id) if job_id else None
    results = job.results if job else data.get("results")
    spec = data.get("spec", {})
    name = data.get("name")
    if not results:
        return jsonify({"status": "error", "message": "No results to save"}), 400
    s_id = session_store.save_session(results, spec, name=name)
    return jsonify({"status": "success", "session_id": s_id})


@optimize_bp.route("/api/analysis/<session_id>", methods=["GET"])
def api_session_analysis(session_id: str):
    """Calculates multi-dimensional matrix analytics for a saved session."""
    session = session_store.get_session(session_id)
    if not session or not session.get("results"):
        return jsonify({"status": "error", "message": "Session or results not found"}), 404
    param1 = request.args.get("param1")
    param2 = request.args.get("param2")
    results_list = session["results"].get("ranked_results", session["results"].get("all_results", []))
    analysis = MatrixAnalyzer.full_analysis(results_list, param1=param1, param2=param2)
    return jsonify({"status": "success", "analysis": analysis})


__all__ = ["optimize_bp", "mass_optimizer", "session_store"]
