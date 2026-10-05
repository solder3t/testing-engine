"""
dashboard/blueprints/strategies.py — Strategy parameter catalog and discovery routes.
"""

from flask import Blueprint, jsonify
from engine.param_grids import STRATEGY_REGISTRY, DEFAULT_PARAM_GRIDS

strategies_bp = Blueprint("strategies_bp", __name__)


@strategies_bp.route("/api/strategy_params", methods=["GET"])
def get_strategy_params():
    """Returns default parameter grids and registered strategy keys."""
    return jsonify({
        "status": "success",
        "strategies": list(STRATEGY_REGISTRY.keys()),
        "grids": DEFAULT_PARAM_GRIDS
    })


@strategies_bp.route("/api/strategies/catalog", methods=["GET"])
def api_strategies_catalog():
    """Returns the full 56-strategy institutional catalog with parameter spaces."""
    from strategies.builtin import BUILTIN_STRATEGIES
    catalog = []
    for key, cls in BUILTIN_STRATEGIES.items():
        try:
            inst = cls()
            param_list = [p.to_dict() for p in inst.parameters.parameters.values()] if hasattr(inst, "parameters") else []
            catalog.append({
                "key": key,
                "name": getattr(inst, "name", key),
                "description": getattr(inst, "description", ""),
                "category": getattr(inst, "category", "TECHNICAL"),
                "parameters": param_list
            })
        except Exception:
            catalog.append({
                "key": key,
                "name": key,
                "description": "",
                "category": "TECHNICAL",
                "parameters": []
            })
    return jsonify({"status": "success", "count": len(catalog), "strategies": catalog})


__all__ = ["strategies_bp"]
