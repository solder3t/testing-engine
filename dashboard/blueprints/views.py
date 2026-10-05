"""
dashboard/blueprints/views.py — HTML template and tearsheet delivery routes.
"""

import json
import os
from flask import Blueprint, current_app, render_template, request, jsonify, Response

from config import RESULTS_DIR
from analytics.tearsheet import generate_html_tearsheet
import dashboard.server as server

views_bp = Blueprint("views_bp", __name__)


@views_bp.route("/")
def index():
    static_f = current_app.static_folder
    css_path = os.path.join(static_f, "css", "dashboard.css")
    js_path = os.path.join(static_f, "js", "dashboard.js")
    css_v = int(os.path.getmtime(css_path)) if os.path.exists(css_path) else 1
    js_v = int(os.path.getmtime(js_path)) if os.path.exists(js_path) else 1
    return render_template("index.html", css_v=css_v, js_v=js_v)


@views_bp.route("/api/tearsheet", methods=["GET"])
def view_tearsheet():
    """Renders the standalone institutional HTML tearsheet for the latest run."""
    run_data = server.latest_run_result
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


@views_bp.route("/api/export_tearsheet", methods=["GET"])
def export_tearsheet():
    """Downloads the standalone institutional HTML tearsheet."""
    run_data = server.latest_run_result
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
