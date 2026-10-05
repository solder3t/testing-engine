"""
futures_strategies.py - Backward Compatibility Shim.

All institutional futures trading strategies have been modularized into:
`strategies.builtin.futures.*`

This module re-exports all strategies so that existing imports:
`from strategies.builtin.futures_strategies import ...`
continue to work without modification.
"""

from .futures import (
    FuturesVolumeSpreadAnalysisStrategy,
    OrderFlowImbalanceStrategy,
    FuturesBasisArbitrageStrategy,
    VwapValueAreaPocStrategy,
    AtrVolatilityExpansionStrategy,
    FuturesOiDivergenceStrategy,
    ParabolicSarMomentumStrategy,
    MultiDayBreakoutStrategy,
    FuturesMomentumPinbarStrategy,
    ChoppinessBreakoutStrategy,
    FuturesVwapMeanReversionStrategy,
    FuturesDualThrustStrategy,
)

__all__ = [
    "FuturesVolumeSpreadAnalysisStrategy",
    "OrderFlowImbalanceStrategy",
    "FuturesBasisArbitrageStrategy",
    "VwapValueAreaPocStrategy",
    "AtrVolatilityExpansionStrategy",
    "FuturesOiDivergenceStrategy",
    "ParabolicSarMomentumStrategy",
    "MultiDayBreakoutStrategy",
    "FuturesMomentumPinbarStrategy",
    "ChoppinessBreakoutStrategy",
    "FuturesVwapMeanReversionStrategy",
    "FuturesDualThrustStrategy",
]
