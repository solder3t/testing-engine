"""
cli/strategy_loader.py — CLI Strategy instantiation and symbol normalization.
"""

from typing import Tuple, List, Any
from strategies.base_strategy import BaseStrategy
from strategies.ai_evaluator import AiSnapshotStrategy
from engine.param_grids import STRATEGY_REGISTRY

# Base catalog of all available strategies from STRATEGY_REGISTRY
# Include both standard registry keys and hyphenated aliases for CLI convenience
ALL_STRATEGIES: List[str] = list(STRATEGY_REGISTRY.keys())
for _k in list(STRATEGY_REGISTRY.keys()):
    _hyphen_k = _k.replace("_", "-")
    if _hyphen_k not in ALL_STRATEGIES:
        ALL_STRATEGIES.append(_hyphen_k)


def _parse_cli_symbols(args_symbols) -> List[str]:
    """Safely normalizes symbols argument into uppercase list or ['auto'] default."""
    raw = (args_symbols or "").strip()
    if not raw or raw.lower() == "auto":
        return ["auto"]
    return [s.strip().upper() for s in raw.split(",") if s.strip()] or ["auto"]


def _build_strategy(strategy_name: str, args: Any) -> Tuple[BaseStrategy, List[str]]:
    """Instantiates a strategy from CLI arguments using STRATEGY_REGISTRY."""
    cli_symbols = _parse_cli_symbols(getattr(args, "symbols", "auto"))
    strat_lower = strategy_name.lower().strip()
    strat_key = strat_lower.replace("-", "_")
    strat_hyphen = strat_lower.replace("_", "-")

    if strat_key == "ai_replay" or strat_hyphen == "ai-replay":
        conf = getattr(args, "confidence", 0.70)
        return AiSnapshotStrategy(params={"min_confidence": conf}), ["NIFTY"]

    # Lookup in STRATEGY_REGISTRY
    strat_cls = (
        STRATEGY_REGISTRY.get(strat_lower)
        or STRATEGY_REGISTRY.get(strat_key)
        or STRATEGY_REGISTRY.get(strat_hyphen)
    )
    if strat_cls is None:
        raise ValueError(
            f"Unknown strategy '{strategy_name}'.\n"
            f"Available ({len(STRATEGY_REGISTRY)}): {sorted(STRATEGY_REGISTRY.keys())}"
        )

    strat_inst = strat_cls()

    # Determine symbols if auto
    if cli_symbols == ["auto"]:
        if "banknifty" in strat_key:
            return strat_inst, ["BANKNIFTY"]
        elif strat_key in ("options", "short_straddle", "pcr_reversion", "futures_trend", "max_pain", "trading_engine_v4", "trading-engine-v4"):
            return strat_inst, ["NIFTY"]
        elif getattr(strat_inst, "asset_class", None) in ("options", "futures", "index"):
            return strat_inst, ["NIFTY"]

    return strat_inst, cli_symbols


__all__ = ["ALL_STRATEGIES", "_parse_cli_symbols", "_build_strategy"]

