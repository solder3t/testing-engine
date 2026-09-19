"""
engine/param_grids.py — Central Strategy Parameter Grid Registry.

Provides default parameter grids and presets for grid search optimization
and Walk-Forward Optimization across all 16 trading strategies.
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
from strategies.short_straddle import ShortStraddleStrategy
from strategies.pcr_reversion import PcrReversionStrategy
from strategies.banknifty_options import BankNiftyOptionsStrategy
from strategies.futures_trend import FuturesTrendStrategy
from strategies.max_pain import MaxPainConvergenceStrategy
from strategies.trading_engine_v4 import TradingEngineV4Strategy

# Strategy class mapping (17 strategies)
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
    "short-straddle": ShortStraddleStrategy,
    "pcr-reversion": PcrReversionStrategy,
    "banknifty-options": BankNiftyOptionsStrategy,
    "futures-trend": FuturesTrendStrategy,
    "max-pain": MaxPainConvergenceStrategy,
    "trading-engine-v4": TradingEngineV4Strategy,
    "trading_engine_v4": TradingEngineV4Strategy,
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
    "short-straddle": {
        "sl_pct": [0.20, 0.25, 0.30],
        "target_pct": [0.50, 0.60, 0.70],
    },
    "pcr-reversion": {
        "pcr_oversold": [0.65, 0.70, 0.75],
        "pcr_overbought": [1.30, 1.35, 1.40],
        "sl_pct": [0.20, 0.25, 0.30],
    },
    "banknifty-options": {
        "sl_points": [25.0, 30.0, 35.0],
        "target_multiplier": [1.8, 2.0, 2.5],
    },
    "futures-trend": {
        "fast_ema": [7, 9],
        "mid_ema": [15, 21],
        "atr_multiplier": [1.2, 1.5, 2.0],
        "risk_reward": [1.5, 2.0],
    },
    "max-pain": {
        "min_displacement": [30.0, 40.0, 50.0],
        "sl_pct": [0.25, 0.30],
        "target_pct": [0.40, 0.50],
    },
    "trading-engine-v4": {
        "min_signal_score": [60, 65, 70],
        "vix_halt_threshold": [22.0, 24.0, 26.0],
        "adx_trend_level": [20.0, 25.0],
        "use_cpr": [True, False],
        "use_htf_15m": [True, False],
        "use_adx_regime": [True, False],
        "use_vix_filter": [True, False],
    },
    "trading_engine_v4": {
        "min_signal_score": [60, 65, 70],
        "vix_halt_threshold": [22.0, 24.0, 26.0],
        "adx_trend_level": [20.0, 25.0],
        "use_cpr": [True, False],
        "use_htf_15m": [True, False],
        "use_adx_regime": [True, False],
        "use_vix_filter": [True, False],
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
