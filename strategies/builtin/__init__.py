"""
Built-in Strategies for Strategy Engine.
Comprehensive catalog of 56 Institutional Trading Strategies spanning:
- Options Trading (12 Strategies)
- Index & Major Benchmarks (13 Strategies)
- Cash Equities (13 Strategies)
- High-Leverage Futures (12 Strategies)
- Legacy & AI Builtins (6 Strategies)
"""

# Legacy & AI Builtins
from .momentum_rsi import MomentumRsiStrategy
from .vwap_reversion import VwapReversionStrategy
from .options_flow import OptionsFlowStrategy
from .fii_flow_momentum import FiiFlowMomentumStrategy
from .vol_regime import VolRegimeStrategy
from .ai_replay import AiReplayStrategy

# Options Suite (12)
from .options_strategies import (
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

# Index Suite (13)
from .index_strategies import (
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

# Equities Suite (13)
from .equity_strategies import (
    MomentumRsiEmaStrategy,
    VwapInstitutionalBounceStrategy,
    ConnorsRsi2PullbackStrategy,
    VolumePriceActionBreakoutStrategy,
    DonchianChannelTurtleStrategy,
    KeltnerChannelMomentumStrategy,
    StochasticRsiCrossoverStrategy,
    MacdHistogramAccelerationStrategy,
    RelativeStrengthAlphaStrategy,
    HullMaDirectionFlipStrategy,
    IchimokuCloudBreakoutStrategy,
    LinearRegressionSlopeStrategy,
    BollingerPercentBReversalStrategy,
)

# Futures Suite (12)
from .futures_strategies import (
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

BUILTIN_STRATEGIES = {
    # Legacy / AI
    "momentum_rsi": MomentumRsiStrategy,
    "vwap_reversion": VwapReversionStrategy,
    "options_flow": OptionsFlowStrategy,
    "fii_flow_momentum": FiiFlowMomentumStrategy,
    "vol_regime": VolRegimeStrategy,
    "ai_replay": AiReplayStrategy,

    # Options Strategies (12)
    "options_flow_momentum": OptionsFlowMomentumStrategy,
    "pcr_extreme_reversal": PcrExtremeReversalStrategy,
    "iv_expansion_breakout": IvExpansionBreakoutStrategy,
    "straddle_premium_decay": StraddlePremiumDecayStrategy,
    "gamma_scalp_momentum": GammaScalpMomentumStrategy,
    "theta_harvest_slope": ThetaHarvestSlopeStrategy,
    "option_buyer_vwap_cross": OptionBuyerVwapCrossStrategy,
    "expiry_pinning_magnet": ExpiryPinningMagnetStrategy,
    "volatility_crush_reversion": VolatilityCrushReversionStrategy,
    "max_pain_convergence": MaxPainConvergenceStrategy,
    "oi_buildup_trend": OiBuildupTrendStrategy,
    "option_breakout_consolidation": OptionBreakoutConsolidationStrategy,

    # Index Strategies (13)
    "orb_15min_breakout": Orb15MinBreakoutStrategy,
    "orb_30min_expansion": Orb30MinExpansionStrategy,
    "cpr_pivot_reversal": CprPivotReversalStrategy,
    "camarilla_pivot_breakout": CamarillaPivotBreakoutStrategy,
    "ttm_squeeze_pro": TtmSqueezeProStrategy,
    "supertrend_multi_tf": SupertrendMultiTfStrategy,
    "ema_ribbon_alignment": EmaRibbonAlignmentStrategy,
    "vwap_band_pinch": VwapBandPinchStrategy,
    "gap_fill_fade": GapFillFadeStrategy,
    "nifty_internals_breadth": NiftyInternalsBreadthStrategy,
    "heikin_ashi_trend_rider": HeikinAshiTrendRiderStrategy,
    "fii_dii_cash_momentum": FiiDiiCashMomentumStrategy,
    "india_vix_divergence": IndiaVixDivergenceStrategy,

    # Equity Strategies (13)
    "equity_momentum_rsi_ema": MomentumRsiEmaStrategy,
    "vwap_institutional_bounce": VwapInstitutionalBounceStrategy,
    "connors_rsi2_pullback": ConnorsRsi2PullbackStrategy,
    "volume_price_action_breakout": VolumePriceActionBreakoutStrategy,
    "donchian_channel_turtle": DonchianChannelTurtleStrategy,
    "keltner_channel_momentum": KeltnerChannelMomentumStrategy,
    "stochastic_rsi_crossover": StochasticRsiCrossoverStrategy,
    "macd_histogram_acceleration": MacdHistogramAccelerationStrategy,
    "relative_strength_alpha": RelativeStrengthAlphaStrategy,
    "hull_ma_direction_flip": HullMaDirectionFlipStrategy,
    "ichimoku_cloud_breakout": IchimokuCloudBreakoutStrategy,
    "linear_regression_slope": LinearRegressionSlopeStrategy,
    "bollinger_percent_b_reversal": BollingerPercentBReversalStrategy,

    # Futures Strategies (12)
    "futures_vsa_climactic": FuturesVolumeSpreadAnalysisStrategy,
    "order_flow_imbalance": OrderFlowImbalanceStrategy,
    "futures_basis_momentum": FuturesBasisArbitrageStrategy,
    "vwap_value_area_poc": VwapValueAreaPocStrategy,
    "atr_volatility_expansion": AtrVolatilityExpansionStrategy,
    "futures_oi_divergence": FuturesOiDivergenceStrategy,
    "parabolic_sar_momentum": ParabolicSarMomentumStrategy,
    "multi_day_breakout": MultiDayBreakoutStrategy,
    "futures_momentum_pinbar": FuturesMomentumPinbarStrategy,
    "choppiness_breakout": ChoppinessBreakoutStrategy,
    "futures_vwap_envelope_reversion": FuturesVwapMeanReversionStrategy,
    "futures_dual_thrust": FuturesDualThrustStrategy,
}

__all__ = [
    # Builtins Dict
    "BUILTIN_STRATEGIES",
    # Legacy / AI
    "MomentumRsiStrategy",
    "VwapReversionStrategy",
    "OptionsFlowStrategy",
    "FiiFlowMomentumStrategy",
    "VolRegimeStrategy",
    "AiReplayStrategy",
    # Options
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
    # Index
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
    # Equities
    "MomentumRsiEmaStrategy",
    "VwapInstitutionalBounceStrategy",
    "ConnorsRsi2PullbackStrategy",
    "VolumePriceActionBreakoutStrategy",
    "DonchianChannelTurtleStrategy",
    "KeltnerChannelMomentumStrategy",
    "StochasticRsiCrossoverStrategy",
    "MacdHistogramAccelerationStrategy",
    "RelativeStrengthAlphaStrategy",
    "HullMaDirectionFlipStrategy",
    "IchimokuCloudBreakoutStrategy",
    "LinearRegressionSlopeStrategy",
    "BollingerPercentBReversalStrategy",
    # Futures
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
