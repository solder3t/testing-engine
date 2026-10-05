"""
Index strategies suite package.
Modularized into intraday breakout, pivot levels, and macro internals.
"""

from .intraday_breakout import (
    Orb15MinBreakoutStrategy,
    Orb30MinExpansionStrategy,
    CamarillaPivotBreakoutStrategy,
    VwapBandPinchStrategy,
    TtmSqueezeProStrategy,
)
from .pivot_levels import (
    CprPivotReversalStrategy,
    GapFillFadeStrategy,
)
from .macro_internals import (
    SupertrendMultiTfStrategy,
    EmaRibbonAlignmentStrategy,
    NiftyInternalsBreadthStrategy,
    HeikinAshiTrendRiderStrategy,
    FiiDiiCashMomentumStrategy,
    IndiaVixDivergenceStrategy,
)

__all__ = [
    "Orb15MinBreakoutStrategy",
    "Orb30MinExpansionStrategy",
    "CamarillaPivotBreakoutStrategy",
    "VwapBandPinchStrategy",
    "TtmSqueezeProStrategy",
    "CprPivotReversalStrategy",
    "GapFillFadeStrategy",
    "SupertrendMultiTfStrategy",
    "EmaRibbonAlignmentStrategy",
    "NiftyInternalsBreadthStrategy",
    "HeikinAshiTrendRiderStrategy",
    "FiiDiiCashMomentumStrategy",
    "IndiaVixDivergenceStrategy",
]
