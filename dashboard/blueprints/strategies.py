"""
dashboard/blueprints/strategies.py — Strategy parameter catalog and discovery routes.
"""

from typing import Dict, List, Any
from flask import Blueprint, jsonify, request
from engine.param_grids import STRATEGY_REGISTRY, DEFAULT_PARAM_GRIDS, get_default_param_grid

strategies_bp = Blueprint("strategies_bp", __name__)


def _extract_strategy_meta(key: str, cls: Any) -> Dict[str, Any]:
    """Helper to introspect strategy parameters, metadata, and default grid."""
    param_list = []
    default_grid = {}
    name = key
    description = ""
    category = "TECHNICAL"

    try:
        inst = cls()
        name = getattr(inst, "name", key)
        description = getattr(inst, "description", "")
        category = getattr(inst, "category", "TECHNICAL")

        if hasattr(inst, "parameters") and hasattr(inst.parameters, "parameters") and inst.parameters.parameters:
            param_list = [p.to_dict() for p in inst.parameters.parameters.values()]
    except Exception:
        inst = None

    # If parameters not defined via ParameterSpace, synthesize from DEFAULT_PARAM_GRIDS or inst.params
    if not param_list:
        grid = {}
        try:
            grid = get_default_param_grid(key)
        except Exception:
            grid = DEFAULT_PARAM_GRIDS.get(key, {})

        inst_params = getattr(inst, "params", {}) if inst else {}
        for p_name, vals in grid.items():
            if not isinstance(vals, list) or len(vals) == 0:
                continue
            first_val = vals[0]
            val_type = "int" if isinstance(first_val, int) and not isinstance(first_val, bool) else (
                "float" if isinstance(first_val, float) else (
                    "bool" if isinstance(first_val, bool) else "str"
                )
            )
            def_val = inst_params.get(p_name, vals[len(vals) // 2])
            min_val = min(vals) if val_type in ("int", "float") else None
            max_val = max(vals) if val_type in ("int", "float") else None
            step = 1 if val_type == "int" else (0.1 if val_type == "float" else None)
            param_list.append({
                "name": p_name,
                "type": val_type,
                "default": def_val,
                "min": min_val,
                "max": max_val,
                "step": step,
                "choices": vals if val_type in ("str", "choice") else None,
                "description": f"Strategy parameter {p_name}"
            })

    try:
        default_grid = get_default_param_grid(key)
    except Exception:
        default_grid = DEFAULT_PARAM_GRIDS.get(key, {})

    return {
        "key": key,
        "name": name,
        "description": description,
        "category": category,
        "parameters": param_list,
        "default_grid": default_grid
    }


@strategies_bp.route("/api/strategy_params", methods=["GET"])
def get_strategy_params():
    """Returns default parameter grids and registered strategy keys, or specific strategy details."""
    strat_key = request.args.get("strategy")
    if strat_key:
        cls = STRATEGY_REGISTRY.get(strat_key)
        if cls:
            meta = _extract_strategy_meta(strat_key, cls)
            return jsonify({
                "status": "success",
                "strategy": strat_key,
                "name": meta["name"],
                "description": meta["description"],
                "category": meta["category"],
                "parameters": meta["parameters"],
                "default_grid": meta["default_grid"],
            })
        else:
            return jsonify({
                "status": "error",
                "message": f"Strategy '{strat_key}' not found",
                "default_grid": {"sl_pts": [10.0, 15.0, 20.0], "target_pts": [20.0, 30.0, 40.0]},
                "parameters": []
            }), 404

    return jsonify({
        "status": "success",
        "strategies": list(STRATEGY_REGISTRY.keys()),
        "grids": DEFAULT_PARAM_GRIDS
    })


@strategies_bp.route("/api/strategies/catalog", methods=["GET"])
def api_strategies_catalog():
    """Returns the full institutional strategy catalog with parameter spaces and default grids."""
    from strategies.builtin import BUILTIN_STRATEGIES
    seen_keys = set()
    catalog = []

    # First add all builtin catalog strategies
    for key, cls in BUILTIN_STRATEGIES.items():
        seen_keys.add(key)
        catalog.append(_extract_strategy_meta(key, cls))

    # Next add any other registered strategies (e.g. classic, trading-engine-v4)
    for key, cls in STRATEGY_REGISTRY.items():
        if key not in seen_keys:
            seen_keys.add(key)
            catalog.append(_extract_strategy_meta(key, cls))

    return jsonify({"status": "success", "count": len(catalog), "strategies": catalog})


__all__ = ["strategies_bp"]
