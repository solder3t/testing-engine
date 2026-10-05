"""
options_strategies.py - Backward Compatibility Shim.

All institutional options trading strategies have been modularized into:
`strategies.builtin.options.*`

This module re-exports all strategies so that existing imports:
`from strategies.builtin.options_strategies import ...`
continue to work without modification.
"""

from .options import (
    OptionsFlowMomentumStrategy,
    PcrExtremeReversalStrategy,
    IvExpansionBreakoutStrategy,
    StraddlePremiumDecayStrategy,
    GammaScalpMomentumStrategy,
    ThetaHarvestSlopeStrategy,
    OptionBuyerVwapCrossStrategy,
    ExpiryPinningMagnetStrategy,
    VolatilityCrushReversionStrategy,
    MaxPainConvergenceStrategy,
    OiBuildupTrendStrategy,
    OptionBreakoutConsolidationStrategy,
)

__all__ = [
    "OptionsFlowMomentumStrategy",
    "PcrExtremeReversalStrategy",
    "IvExpansionBreakoutStrategy",
    "StraddlePremiumDecayStrategy",
    "GammaScalpMomentumStrategy",
    "ThetaHarvestSlopeStrategy",
    "OptionBuyerVwapCrossStrategy",
    "ExpiryPinningMagnetStrategy",
    "VolatilityCrushReversionStrategy",
    "MaxPainConvergenceStrategy",
    "OiBuildupTrendStrategy",
    "OptionBreakoutConsolidationStrategy",
]
