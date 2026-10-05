"""
dashboard/blueprints/archives.py — File system browser and archive extraction endpoints.
"""

import logging
import os
import re
from flask import Blueprint, request, jsonify

from config import DOWNLOADS_DIR
import dashboard.server as server

logger = logging.getLogger("dashboard_archives")
archives_bp = Blueprint("archives_bp", __name__)


@archives_bp.route("/api/browse", methods=["GET"])
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


@archives_bp.route("/api/archives", methods=["GET", "POST"])
def get_archives():
    """
    Returns market archives and extracted session folders from a target directory or specific file.
    """
    target_dir = request.args.get("dir")
    if not target_dir and request.is_json:
        req_json = request.get_json(silent=True) or {}
        target_dir = req_json.get("directory")
    target_dir = target_dir or DOWNLOADS_DIR

    mgr = server.ArchiveManager(downloads_dir=target_dir)
    sources = mgr.list_archives(target_dir=target_dir)
    return jsonify({
        "status": "success",
        "scanned_directory": os.path.expanduser(target_dir),
        "count": len(sources),
        "archives": sources
    })


@archives_bp.route("/api/extract", methods=["POST"])
def extract_archives():
    """Extracts specified archive dates into data cache."""
    data = request.json or {}
    dates = data.get("dates", [])
    target_dir = data.get("directory") or DOWNLOADS_DIR
    if not dates:
        return jsonify({"status": "error", "message": "No dates specified"}), 400

    mgr = server.ArchiveManager(downloads_dir=target_dir)
    results = []
    for d in dates:
        res = mgr.extract_archive(d, force=data.get("force", False), target_dir=target_dir)
        results.append({"date": d, "result": res})

    return jsonify({"status": "success", "extractions": results})
