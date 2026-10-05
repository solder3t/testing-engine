"""
dashboard/blueprints/system.py — System and browser automation routes.
"""

from flask import Blueprint, jsonify
from config import DASHBOARD_PORT, CHROME_PROFILE_DIR
import dashboard.server as server

system_bp = Blueprint("system_bp", __name__)


@system_bp.route("/api/open_browser", methods=["GET", "POST"])
def api_open_browser():
    r"""Triggers opening of the dashboard in the shared bot Chrome profile (C:\selenium\ChromeProfile)."""
    target_url = f"http://127.0.0.1:{DASHBOARD_PORT}/"
    ok = server.open_dashboard_in_profile(url=target_url, delay=0.0)
    return jsonify({
        "status": "success" if ok else "error",
        "opened": ok,
        "profile": CHROME_PROFILE_DIR,
        "url": target_url
    })


__all__ = ["system_bp"]
