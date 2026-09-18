"""
engine/backtest_engine.py — Event-Driven Single-Session Backtest Engine.
"""

from typing import List, Dict, Any, Optional
import pandas as pd
import logging

from config import DEFAULT_CAPITAL, DEFAULT_RISK_PCT_PER_TRADE, WATCHLIST_PATH
from execution.portfolio import Portfolio
from execution.simulator import ExecutionSimulator
from execution.order import InstrumentType
from strategies.base_strategy import BaseStrategy
from data.data_loader import DataLoader
from data.option_chain_loader import OptionChainLoader
from analytics.metrics import calculate_performance_metrics

logger = logging.getLogger("backtest_engine")


class BacktestEngine:
    """Executes synchronized bar-by-bar backtests with strict no-lookahead bias."""

    def __init__(
        self,
        data_loader: Optional[DataLoader] = None,
        simulator: Optional[ExecutionSimulator] = None,
        option_loader: Optional[OptionChainLoader] = None,
        capital: float = DEFAULT_CAPITAL,
        risk_pct: float = DEFAULT_RISK_PCT_PER_TRADE,
        source_dir: Optional[str] = None
    ):
        import os
        self.source_dir = os.path.expanduser(source_dir) if source_dir else None
        self.data_loader = data_loader or DataLoader(source_dir=self.source_dir)
        self.simulator = simulator or ExecutionSimulator()
        self.option_loader = option_loader or OptionChainLoader(source_dir=self.source_dir)
        self.capital = capital
        self.risk_pct = risk_pct

    def run_session(
        self,
        date_str: str,
        strategy: BaseStrategy,
        symbols: Optional[List[str]] = None,
        portfolio: Optional[Portfolio] = None,
        timeframe: str = "1min"
    ) -> Dict[str, Any]:
        """
        Runs a complete backtest session for a specific trading date.
        """
        # Load circuit limits for the session
        circuit_limits = self.data_loader.get_circuit_limits(date_str)
        port = portfolio or Portfolio(
            initial_capital=self.capital,
            risk_pct_per_trade=self.risk_pct,
            simulator=self.simulator,
            circuit_limits=circuit_limits
        )
        if not getattr(port, "circuit_limits", None) and circuit_limits:
            port.circuit_limits = circuit_limits

        # 1. Resolve symbols to test
        # 'auto' mode: discover all available equities from equity_master for this date
        auto_discover = (
            (symbols is None)
            or (symbols == ["auto"])
            or (symbols == [])
            or (len(symbols) == 1 and str(symbols[0]).strip().lower() == "auto")
        )

        # 2. Load instrument OHLC data
        ohlc_map: Dict[str, pd.DataFrame] = {}
        symbol_meta: Dict[str, Dict] = {}

        # If testing options / indices, include NIFTY and BANKNIFTY indices
        df_nifty = self.data_loader.get_index_ohlc(date_str, "NIFTY", timeframe=timeframe)
        if not df_nifty.empty:
            ohlc_map["NIFTY"] = df_nifty
            symbol_meta["NIFTY"] = {"security_id": 13, "sector": "Index"}

        df_banknifty = self.data_loader.get_index_ohlc(date_str, "BANKNIFTY", timeframe=timeframe)
        if not df_banknifty.empty:
            ohlc_map["BANKNIFTY"] = df_banknifty
            symbol_meta["BANKNIFTY"] = {"security_id": 25, "sector": "Index"}

        # Load VIX for volatility filter
        df_vix = self.data_loader.get_index_ohlc(date_str, "INDIA_VIX", timeframe=timeframe)
        vix_series = {}
        vix_available = not df_vix.empty
        if vix_available:
            for _, r in df_vix.iterrows():
                vix_series[str(r["timestamp"])] = float(r["close"])
        else:
            logger.warning(
                f"[{date_str}] INDIA_VIX data not found — VIX filter will use fallback 15.0. "
                "Strategies relying on vix_available=False should gate their VIX logic."
            )

        # Load Equities
        # First check equity_master for security_ids
        df_master = self.data_loader.get_equity_master(date_str)
        master_lookup = {}
        if not df_master.empty:
            for _, r in df_master.iterrows():
                master_lookup[str(r["symbol"])] = {
                    "security_id": int(r["security_id"]),
                    "sector": str(r.get("sector") or "Other")
                }

        if auto_discover and master_lookup:
            # Universe mode: use all symbols present in equity_master (capped at 20 to avoid perf issues)
            # Sort by security_id for determinism; user can pass explicit list to override
            target_symbols = sorted(master_lookup.keys())[:20]
            logger.info(f"[{date_str}] Auto-discovered {len(target_symbols)} symbols from equity_master")
        else:
            filtered_syms = [str(s).strip().upper() for s in (symbols or []) if str(s).strip().lower() != "auto"]
            target_symbols = filtered_syms or ["RELIANCE", "HDFCBANK", "INFY", "ICICIBANK", "TCS"]

        for sym in target_symbols:
            meta = master_lookup.get(sym, {"security_id": 0, "sector": "Other"})
            sid = meta["security_id"]
            df_sym = self.data_loader.get_equity_ohlc(date_str, security_id=sid, symbol=sym, timeframe=timeframe)
            if not df_sym.empty and len(df_sym) >= 20:
                ohlc_map[sym] = df_sym
                symbol_meta[sym] = meta

        if not ohlc_map:
            return {
                "date": date_str,
                "strategy": strategy.name,
                "error": f"No data found for requested symbols on {date_str}",
                "metrics": calculate_performance_metrics([], port.initial_capital),
                "trades": [],
                "equity_curve": []
            }

        # 3. Synchronize all timestamps
        all_timestamps = set()
        for df in ohlc_map.values():
            all_timestamps.update(df["timestamp"].astype(str).tolist())
        timeline = sorted(list(all_timestamps))

        # Index data by timestamp for O(1) bar streaming (vectorized records)
        bar_stream: Dict[str, Dict[str, Dict]] = {ts: {} for ts in timeline}
        for sym, df in ohlc_map.items():
            sid = symbol_meta[sym]["security_id"]
            sec = symbol_meta[sym]["sector"]
            records = df.to_dict("records")
            for r in records:
                ts = str(r["timestamp"])
                bar_stream[ts][sym] = {
                    "open": float(r["open"]),
                    "high": float(r["high"]),
                    "low": float(r["low"]),
                    "close": float(r["close"]),
                    "volume": float(r["volume"]),
                    "vwap": float(r["vwap"]),
                    "bid_ask_spread": float(r.get("bid_ask_spread", 0.0) or 0.0),
                    "depth_imbalance": float(r.get("depth_imbalance", 0.0) or 0.0),
                    "security_id": sid,
                    "sector": sec
                }

        # 4. Initialize strategy session
        context = {
            "date": date_str,
            "ohlc_data": ohlc_map,
            "metadata": symbol_meta,
            "current_vix": 15.0,
            "vix_available": vix_available,   # False → VIX is the 15.0 fallback, gate your VIX logic
            "data_loader": self.data_loader,
            "option_loader": self.option_loader,
            "source_dir": self.source_dir
        }
        strategy.on_session_start(date_str, port, context)

        # 5. Chronological bar-by-bar execution loop
        for ts in timeline:
            quotes = bar_stream[ts]
            if not quotes:
                continue

            context["current_vix"] = vix_series.get(ts, 15.0)

            # Enrich quotes with open option positions from option chain snapshots
            for trade in port.open_trades:
                if trade.instrument_type in (InstrumentType.OPTION_CE, InstrumentType.OPTION_PE):
                    strike = trade.metadata.get("strike")
                    opt_type = "ce" if trade.instrument_type == InstrumentType.OPTION_CE else "pe"
                    underlying = trade.metadata.get("underlying", "NIFTY")
                    chain_df = self.option_loader.get_nearest_chain(date_str, ts, underlying=underlying)
                    if chain_df is not None and not chain_df.empty and strike:
                        stk_row = chain_df[chain_df["strike_price"] == strike]
                        if not stk_row.empty:
                            r = stk_row.iloc[0]
                            opt_ltp = float(r.get(f"{opt_type}_ltp") or 0.0)
                            opt_bid = float(r.get(f"{opt_type}_bid") or opt_ltp)
                            opt_ask = float(r.get(f"{opt_type}_ask") or opt_ltp)
                            if opt_ltp > 0:
                                quotes[trade.symbol] = {
                                    "open": opt_ltp, "high": opt_ltp, "low": opt_ltp, "close": opt_ltp,
                                    "ltp": opt_ltp, "bid_ask_spread": max(0.0, opt_ask - opt_bid)
                                }
                elif trade.instrument_type == InstrumentType.FUTURES:
                    underlying = trade.metadata.get("underlying", "NIFTY")
                    uq = quotes.get(underlying) or quotes.get(f"{underlying} 50")
                    if uq and trade.symbol not in quotes:
                        quotes[trade.symbol] = dict(uq)

            # A. Update existing open positions against current bar (SL, Target, Trailing SL, EOD)
            port.update_open_trades(ts, quotes)

            # B. Strategy evaluates current bar and emits entry setups
            signals = strategy.on_bar(ts, quotes, port, context)

            # C. Open new trades for valid signals
            for sig in signals:
                sym = sig["symbol"]
                side = sig["side"]
                price = sig["price"]
                sl = sig["sl"]
                target = sig["target"]
                score = sig.get("score", 70)
                sec_id = sig.get("security_id", 0)
                inst_type = sig.get("instrument_type")
                meta = sig.get("metadata", {})
                q_sym = quotes.get(sym, {})
                spread = q_sym.get("bid_ask_spread", 0.0)
                bar_high = q_sym.get("high", price)
                bar_low = q_sym.get("low", price)
                bar_range_pct = ((bar_high - bar_low) / price) if price > 0 else 0.0

                lot_size = sig.get("lot_size")
                if not lot_size:
                    lot_size = 25 if "OPTION" in str(inst_type) else 1

                qty = port.calculate_position_size(
                    entry_price=price,
                    stop_loss=sl,
                    score=score,
                    lot_size=lot_size,
                    instrument_type=inst_type,
                    underlying=meta.get("underlying", sym)
                )

                port.open_trade(
                    symbol=sym,
                    security_id=sec_id,
                    side=side,
                    price=price,
                    qty=qty,
                    sl=sl,
                    target=target,
                    entry_time=ts,
                    instrument_type=inst_type,
                    metadata=meta,
                    bid_ask_spread=spread,
                    bar_range_pct=bar_range_pct
                )

            # D. Record equity point
            port.record_equity_point(ts, quotes)

        # 6. End session
        strategy.on_session_end(date_str, port, context)

        # Compute summary metrics
        metrics = calculate_performance_metrics(
            trades=port.closed_trades,
            initial_capital=port.initial_capital,
            equity_curve=port.equity_curve
        )

        return {
            "date": date_str,
            "strategy": strategy.name,
            "initial_capital": port.initial_capital,
            "final_equity": port.capital,
            "metrics": metrics,
            "trades": port.closed_trades,
            "equity_curve": port.equity_curve
        }
