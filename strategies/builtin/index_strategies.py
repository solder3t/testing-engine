"""
index_strategies.py - Backward Compatibility Shim.

All institutional index trading strategies have been modularized into:
`strategies.builtin.index.*`

This module re-exports all strategies so that existing imports:
`from strategies.builtin.index_strategies import ...`
continue to work without modification.
"""

from .index import (
    Orb15MinBreakoutStrategy,
    Orb30MinExpansionStrategy,
    CprPivotReversalStrategy,
    CamarillaPivotBreakoutStrategy,
    TtmSqueezeProStrategy,
    SupertrendMultiTfStrategy,
    EmaRibbonAlignmentStrategy,
    VwapBandPinchStrategy,
    GapFillFadeStrategy,
    NiftyInternalsBreadthStrategy,
    HeikinAshiTrendRiderStrategy,
    FiiDiiCashMomentumStrategy,
    IndiaVixDivergenceStrategy,
)

__all__ = [
    "Orb15MinBreakoutStrategy",
    "Orb30MinExpansionStrategy",
    "CprPivotReversalStrategy",
    "CamarillaPivotBreakoutStrategy",
    "TtmSqueezeProStrategy",
    "SupertrendMultiTfStrategy",
    "EmaRibbonAlignmentStrategy",
    "VwapBandPinchStrategy",
    "GapFillFadeStrategy",
    "NiftyInternalsBreadthStrategy",
    "HeikinAshiTrendRiderStrategy",
    "FiiDiiCashMomentumStrategy",
    "IndiaVixDivergenceStrategy",
]
