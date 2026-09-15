"""
engine/param_grids.py — Central Strategy Parameter Grid Registry.

Provides default parameter grids and presets for grid search optimization
and Walk-Forward Optimization across all 11 trading strategies.
"""

from typing import Dict, List, Any, Type
from strategies.base_strategy import BaseStrategy
from strategies.equity_momentum import EquityMomentumStrategy
from strategies.orb_breakout import OrbBreakoutStrategy
from strategies.supertrend_trend import SupertrendTrendStrategy
from strategies.camarilla_breakout import CamarillaBreakoutStrategy
from strategies.ema_ribbon import EmaRibbonStrategy
from strategies.bollinger_percent_b import BollingerPercentBStrategy
from strategies.macd_acceleration import MacdAccelerationStrategy
from strategies.vwap_reversion import VwapReversionStrategy
from strategies.rsi_momentum import RsiMomentumStrategy
from strategies.nifty_options import NiftyOptionsStrategy
from strategies.ai_evaluator import AiSnapshotStrategy

# Strategy class mapping
STRATEGY_REGISTRY: Dict[str, Type[BaseStrategy]] = {
    "equity": EquityMomentumStrategy,
    "orb": OrbBreakoutStrategy,
    "supertrend": SupertrendTrendStrategy,
    "camarilla": CamarillaBreakoutStrategy,
    "ema-ribbon": EmaRibbonStrategy,
    "bollinger-b": BollingerPercentBStrategy,
    "macd-accel": MacdAccelerationStrategy,
    "vwap-reversion": VwapReversionStrategy,
    "rsi-momentum": RsiMomentumStrategy,
    "options": NiftyOptionsStrategy,
    "ai-replay": AiSnapshotStrategy,
}

# Sensible default parameter grids for grid search & walk-forward analysis
DEFAULT_PARAM_GRIDS: Dict[str, Dict[str, List[Any]]] = {
    "orb": {
        "opening_minutes": [10, 15, 20],
        "risk_reward": [1.5, 2.0, 2.5],
        "breakout_atr_mult": [0.5, 1.0],
    },
    "equity": {
        "min_score": [50, 55, 60],
        "atr_sl_mult": [1.2, 1.5, 1.8],
        "atr_tgt_mult": [2.5, 3.0],
    },
    "supertrend": {
        "atr_period": [7, 10, 14],
        "multiplier": [2.5, 3.0, 3.5],
        "risk_reward": [1.5, 2.0],
    },
    "camarilla": {
        "risk_reward": [1.5, 2.0, 2.5],
        "sl_buffer_pts": [3.0, 5.0, 7.0],
    },
    "ema-ribbon": {
        "fast_ema": [7, 9],
        "med_ema": [15, 21],
        "sl_pts": [10.0, 15.0],
        "target_pts": [25.0, 35.0],
    },
    "bollinger-b": {
        "period": [15, 20],
        "std_dev": [1.8, 2.0, 2.2],
        "oversold_b": [0.05, 0.10],
        "overbought_b": [0.90, 0.95],
    },
    "macd-accel": {
        "fast_period": [8, 12],
        "slow_period": [21, 26],
        "sl_pts": [10.0, 15.0],
        "target_pts": [25.0, 35.0],
    },
    "vwap-reversion": {
        "bb_period": [15, 20],
        "bb_std": [1.8, 2.0, 2.5],
        "sl_pts": [10.0, 15.0],
        "target_pts": [20.0, 30.0],
    },
    "rsi-momentum": {
        "rsi_period": [10, 14],
        "rsi_long_cutoff": [55.0, 60.0, 65.0],
        "fast_ema": [9, 13],
        "slow_ema": [21, 34],
    },
    "options": {
        "sl_points": [10.0, 12.0, 15.0],
        "target_multiplier": [1.5, 1.8, 2.0],
    },
    "ai-replay": {
        "min_confidence": [0.60, 0.70, 0.80],
    },
}


def get_strategy_class(strategy_name: str) -> Type[BaseStrategy]:
    """Returns the strategy class for a given strategy key."""
    if strategy_name not in STRATEGY_REGISTRY:
        raise ValueError(f"Unknown strategy: '{strategy_name}'. Supported: {list(STRATEGY_REGISTRY.keys())}")
    return STRATEGY_REGISTRY[strategy_name]


def get_default_param_grid(strategy_name: str) -> Dict[str, List[Any]]:
    """Returns the default parameter grid for a strategy."""
    if strategy_name not in DEFAULT_PARAM_GRIDS:
        raise ValueError(f"No default parameter grid registered for '{strategy_name}'")
    return {k: list(v) for k, v in DEFAULT_PARAM_GRIDS[strategy_name].items()}
