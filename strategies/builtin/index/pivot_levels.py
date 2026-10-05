from typing import Dict, Any, Optional, List

try:
    from ...base_strategy import BaseStrategy, Signal
    from ...parameter_space import Parameter
except (ImportError, ValueError):
    from strategies.base_strategy import BaseStrategy, Signal
    from strategies.parameter_space import Parameter

from math_engine import MathEngine


class CprPivotReversalStrategy(BaseStrategy):
    """Central Pivot Range (CPR: Pivot, TC, BC) bounce and breakout system."""
    def __init__(self):
        super().__init__(
            name="CPR Pivot Reversal",
            description="Trades bounces and breakouts from Central Pivot Range (Pivot, Top Central, Bottom Central).",
            category="INDEX"
        )
        self.math = MathEngine(use_gpu=False)

    def _setup_parameters(self) -> None:
        self.parameters.add(Parameter("stop_loss_pts", "float", 20.0, 10.0, 50.0, 5.0, "Stop loss points"))
        self.parameters.add(Parameter("target_pts", "float", 45.0, 20.0, 100.0, 5.0, "Target points"))

    def on_candle(self, candle: Dict[str, Any], history: List[Dict[str, Any]], context: Optional[Dict[str, Any]] = None) -> Optional[Signal]:
        if len(history) < 15:
            return None

        c_close = float(candle.get("close", 0))
        p_close = float(history[-1].get("close", 0))

        pd_h = float((context or {}).get("prev_day_high", c_close * 1.005) or c_close * 1.005)
        pd_l = float((context or {}).get("prev_day_low", c_close * 0.995) or c_close * 0.995)
        pd_c = float((context or {}).get("prev_day_close", c_close) or c_close)

        pivot = (pd_h + pd_l + pd_c) / 3.0
        bc = (pd_h + pd_l) / 2.0
        tc = (pivot - bc) + pivot

        cpr_top = max(tc, bc)
        cpr_bottom = min(tc, bc)

        if p_close <= cpr_top and c_close > cpr_top:
            return Signal("ENTER", "CALL", "CE", stop_loss=self.current_params["stop_loss_pts"], target=self.current_params["target_pts"], confidence=0.81, reasoning="CPR Top Bullish Rejection")
        elif p_close >= cpr_bottom and c_close < cpr_bottom:
            return Signal("ENTER", "PUT", "PE", stop_loss=self.current_params["stop_loss_pts"], target=self.current_params["target_pts"], confidence=0.81, reasoning="CPR Bottom Bearish Breakdown")
        return None


class GapFillFadeStrategy(BaseStrategy):
    """Morning opening gap fill & fade reversal."""
    def __init__(self):
        super().__init__(
            name="Gap Fill Fade",
            description="Fades large opening gap-ups or gap-downs expecting full intraday fill back to prior close.",
            category="INDEX"
        )

    def _setup_parameters(self) -> None:
        self.parameters.add(Parameter("min_gap_pts", "float", 40.0, 20.0, 100.0, 10.0, "Minimum opening gap points"))
        self.parameters.add(Parameter("stop_loss_pts", "float", 25.0, 10.0, 60.0, 5.0, "Stop loss points"))
        self.parameters.add(Parameter("target_pts", "float", 40.0, 20.0, 90.0, 5.0, "Target points"))

    def on_candle(self, candle: Dict[str, Any], history: List[Dict[str, Any]], context: Optional[Dict[str, Any]] = None) -> Optional[Signal]:
        idx = (context or {}).get("candle_index", len(history))
        if idx == 2 and len(history) >= 2:
            open_c = float(history[0].get("open", 0))
            prev_close = float((context or {}).get("prev_day_close", open_c) or open_c)
            gap = open_c - prev_close

            if gap >= self.current_params["min_gap_pts"]:
                return Signal("ENTER", "PUT", "PE", stop_loss=self.current_params["stop_loss_pts"], target=min(gap, self.current_params["target_pts"]), confidence=0.80, reasoning="Gap Up Reversal Fade")
            elif gap <= -self.current_params["min_gap_pts"]:
                return Signal("ENTER", "CALL", "CE", stop_loss=self.current_params["stop_loss_pts"], target=min(abs(gap), self.current_params["target_pts"]), confidence=0.80, reasoning="Gap Down Reversal Fade")
        return None
