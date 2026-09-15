# Testing Engine (stocks-engine / testing-engine)

High-performance, event-driven backtesting and quantitative strategy simulation terminal designed for Indian equity markets (NSE). Fully isolated from the live execution system, powered 100% by real recorded historical market data archives, and featuring a real-time Bloomberg-style dark glassmorphism dashboard.

---

## Key Features

1. **Strictly Zero Hardcoded/Mock Data**:
   - All quotes, OHLC bars, indicators, trades, and portfolio values are dynamically calculated from real recorded SQLite databases (`equities.db`, `indices.db`, `indicators.db`, `trade.db`, `optionchain_snapshot.db`).

2. **Smart Archive & Folder Ingestion**:
   - Dynamic scanning of any target directory or session folder (e.g. `~/Downloads` or local data folders).
   - Date regex pattern matching (`\d{4}[-_]\d{2}[-_]\d{2}`) filters out non-market files.
   - Automatic session date resolution for arbitrary folders (e.g. `trade/` automatically resolves to `2026_09_01` via database tick timestamps).

3. **High-Speed Vectorized Resampling**:
   - Resamples millions of sub-second market ticks into `1min`, `5min`, and `15min` OHLCV bars without lookahead bias.

4. **Realistic Execution & NSE Statutory Charges**:
   - Models bid-ask spreads, depth slippage, and real statutory taxes (STT, Exchange Turnover Charges, GST, SEBI Turnover, and State Stamp Duty).

5. **Multi-Model Strategy Suite**:
   - **Equity Momentum (v4/v5)**: 7-factor trend confirmation with ATR trailing stops.
   - **VWAP Mean Reversion**: Mean reversion from extreme Bollinger Band deviations (2.0+ std) back to intraday VWAP.
   - **Dual EMA + RSI Momentum Filter**: 9/21 EMA crossover filtered by RSI(14) directional momentum.
   - **NIFTY Options Breakout**: Strike selection (ATM/OTM), premium stop-loss, and ORB opening range breakouts.
   - **AI Decision Replay**: Counterfactual evaluator replaying 2,800+ recorded historical Gemini AI trade signals.

6. **Interactive Real-Data Terminal (Web Dashboard)**:
   - Modern dark Bloomberg glassmorphism UI running on port `5690`.
   - Real-time Cumulative Equity, Daily Net P&L, and Underwater Drawdown charts.
   - Live searchable trade table, CSV exporter, and granular fee inspector modal.

---

## Directory Structure

```
testing-engine/
├── config.py                 # Central configurations (capital, margin, fees, paths)
├── requirements.txt          # Python dependencies
├── cli.py                    # Standalone Command Line Interface
├── README.md                 # Documentation
│
├── data/                     # Archive ingestion, extraction, and data loaders
│   ├── archive_manager.py    # RAR/folder discovery, date extraction, and cache management
│   ├── data_loader.py        # Unified SQLite database query layer
│   ├── ohlc_resampler.py     # High-speed tick-to-OHLC resampler
│   ├── option_chain_loader.py# Option chain replayer & Greeks calculator
│   └── watchlist.json        # NIFTY constituent symbols and security IDs
│
├── indicators/               # Vectorized indicator calculations
│   ├── indicators.py         # EMA, RSI, ATR, VWAP, Bollinger Bands, Camarilla pivots
│   └── scorer.py             # 0-100 multi-factor signal quality scoring engine
│
├── execution/                # Order models and portfolio accounting
│   ├── order.py              # Order, Trade, and Position dataclasses
│   ├── simulator.py          # Fill simulation with slippage and Indian statutory taxes
│   └── portfolio.py          # Portfolio equity, MTM, risk limits, stop loss & square-off
│
├── strategies/               # Strategy algorithms
│   ├── base_strategy.py      # Base strategy lifecycle interface
│   ├── equity_momentum.py    # Equity momentum strategy
│   ├── vwap_reversion.py     # VWAP mean reversion strategy
│   ├── rsi_momentum.py       # Dual EMA + RSI momentum strategy
│   ├── nifty_options.py      # NIFTY index options breakout strategy
│   ├── ai_evaluator.py       # Historical AI recommendation evaluator
│   └── custom_strategy.py    # Boilerplate template for custom algorithms
│
├── engine/                   # Backtesting orchestration
│   ├── backtest_engine.py    # Event-driven backtest loop
│   ├── multi_day_runner.py   # Multi-session runner with dynamic source directories
│   └── optimizer.py          # Grid search parameter optimizer
│
├── analytics/                # Performance analytics and export
│   ├── metrics.py            # Sharpe, Sortino, Calmar, Max Drawdown, Profit Factor
│   └── trade_exporter.py     # CSV, JSON, and SQLite trade log exporters
│
├── dashboard/                # Real-data Web Terminal
│   ├── server.py             # Flask API server (Port 5690)
│   ├── templates/index.html  # Bloomberg dark glassmorphism dashboard UI
│   └── static/               # CSS & JS assets (Chart.js, styling)
│
└── tests/                    # Automated test suite (17 passing tests)
```

---

## Getting Started

### Installation
```bash
git clone https://github.com/solder3t/testing-engine.git
cd testing-engine
pip install -r requirements.txt
```

### Run Tests
```bash
python3 -m pytest tests/ -v
```

### CLI Usage
```bash
# Check archives in any directory
python3 cli.py data status --data-dir ~/Downloads

# Run an Equity Momentum backtest
python3 cli.py run equity --dates 2026_09_02 --symbols RELIANCE,INFY --timeframe 1min

# Run VWAP Reversion backtest
python3 cli.py run vwap --dates 2026_09_02 --symbols RELIANCE,INFY

# Run Options Breakout backtest
python3 cli.py run options --dates 2026_09_11

# Launch the Web Terminal
python3 cli.py dashboard --port 5690
```

### Dashboard
Open `http://localhost:5690` in any web browser.

---

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

