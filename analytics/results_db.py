"""
analytics/results_db.py — Persistent SQLite Storage for Backtest Runs & Optimization.

Maintains persistent records of individual backtests, parameter optimization experiments,
trade logs, and statistical validation metrics with crash resilience.
"""

from datetime import datetime
import json
import os
import sqlite3
from typing import Any, Dict, List, Optional
import uuid

import config


class ResultsDB:
    """Manages SQLite schema and ACID operations for test results."""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or config.RESULTS_DB_PATH
        os.makedirs(os.path.dirname(os.path.abspath(self.db_path)), exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA synchronous = NORMAL;")
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        """Initializes tables and compound indexes."""
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS backtest_runs (
                    run_id              TEXT PRIMARY KEY,
                    created_at          TEXT NOT NULL,
                    strategy_name       TEXT NOT NULL,
                    instrument          TEXT NOT NULL,
                    timeframe           TEXT NOT NULL,
                    start_date          TEXT NOT NULL,
                    end_date            TEXT NOT NULL,
                    initial_capital     REAL NOT NULL,
                    final_equity        REAL NOT NULL,
                    net_pnl             REAL NOT NULL,
                    win_rate            REAL,
                    sharpe_ratio        REAL,
                    sortino_ratio       REAL,
                    max_drawdown_pct    REAL,
                    profit_factor       REAL,
                    total_trades        INTEGER,
                    params_json         TEXT,
                    metrics_json        TEXT,
                    status              TEXT DEFAULT 'COMPLETED'
                );
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_runs_strat ON backtest_runs(strategy_name, created_at);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_runs_inst ON backtest_runs(instrument);")

            conn.execute("""
                CREATE TABLE IF NOT EXISTS trades (
                    trade_id            TEXT PRIMARY KEY,
                    run_id              TEXT NOT NULL,
                    symbol              TEXT NOT NULL,
                    side                TEXT NOT NULL,
                    entry_time          TEXT NOT NULL,
                    entry_price         REAL NOT NULL,
                    exit_time           TEXT NOT NULL,
                    exit_price          REAL NOT NULL,
                    quantity            INTEGER NOT NULL,
                    gross_pnl           REAL NOT NULL,
                    charges             REAL NOT NULL,
                    net_pnl             REAL NOT NULL,
                    exit_reason         TEXT,
                    FOREIGN KEY(run_id) REFERENCES backtest_runs(run_id)
                );
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_trades_run_id ON trades(run_id);")

            conn.execute("""
                CREATE TABLE IF NOT EXISTS grid_experiments (
                    experiment_id       TEXT PRIMARY KEY,
                    created_at          TEXT NOT NULL,
                    strategy_name       TEXT NOT NULL,
                    instruments         TEXT NOT NULL,
                    total_candidates    INTEGER,
                    completed_candidates INTEGER,
                    best_candidate_id   TEXT,
                    config_json         TEXT
                );
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS validation_metrics (
                    run_id              TEXT PRIMARY KEY,
                    pbo_score           REAL,
                    deflated_sharpe     REAL,
                    wfe_score           REAL,
                    mc_var_95           REAL,
                    mc_max_dd_95        REAL,
                    verdict             TEXT,
                    diagnostics_json    TEXT,
                    FOREIGN KEY(run_id) REFERENCES backtest_runs(run_id)
                );
            """)
            conn.commit()

    def save_run(
        self,
        strategy_name: str,
        instrument: str,
        timeframe: str,
        start_date: str,
        end_date: str,
        initial_capital: float,
        final_equity: float,
        metrics: Dict[str, Any],
        params: Optional[Dict[str, Any]] = None,
        run_id: Optional[str] = None
    ) -> str:
        """Saves or updates a backtest run summary."""
        rid = run_id or str(uuid.uuid4())[:8]
        now_str = datetime.now().isoformat()
        params_str = json.dumps(params or {})
        metrics_str = json.dumps(metrics or {})

        net_pnl = metrics.get("net_pnl", final_equity - initial_capital)
        win_rate = metrics.get("win_rate", 0.0)
        sharpe = metrics.get("sharpe_ratio", 0.0)
        sortino = metrics.get("sortino_ratio", 0.0)
        max_dd = metrics.get("max_drawdown_pct", 0.0)
        pf = metrics.get("profit_factor", 0.0)
        total_trades = metrics.get("total_trades", 0)

        with self._get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO backtest_runs (
                    run_id, created_at, strategy_name, instrument, timeframe,
                    start_date, end_date, initial_capital, final_equity, net_pnl,
                    win_rate, sharpe_ratio, sortino_ratio, max_drawdown_pct, profit_factor,
                    total_trades, params_json, metrics_json, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'COMPLETED')
            """, (
                rid, now_str, strategy_name, instrument, timeframe,
                start_date, end_date, initial_capital, final_equity, net_pnl,
                win_rate, sharpe, sortino, max_dd, pf, total_trades,
                params_str, metrics_str
            ))
            conn.commit()
        return rid

    def save_trades(self, run_id: str, trades: List[Dict[str, Any]]) -> None:
        """Inserts batch of executed trades for a run."""
        if not trades:
            return
        rows = []
        for t in trades:
            tid = t.get("trade_id") or str(uuid.uuid4())[:8]
            rows.append((
                tid,
                run_id,
                t.get("symbol", "UNKNOWN"),
                t.get("side", "BUY"),
                str(t.get("entry_time", "")),
                float(t.get("entry_price", 0.0)),
                str(t.get("exit_time", "")),
                float(t.get("exit_price", 0.0)),
                int(t.get("quantity", 0)),
                float(t.get("gross_pnl", 0.0)),
                float(t.get("charges", 0.0)),
                float(t.get("net_pnl", 0.0)),
                str(t.get("exit_reason", ""))
            ))

        with self._get_connection() as conn:
            conn.executemany("""
                INSERT OR REPLACE INTO trades (
                    trade_id, run_id, symbol, side, entry_time, entry_price,
                    exit_time, exit_price, quantity, gross_pnl, charges, net_pnl, exit_reason
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, rows)
            conn.commit()

    def save_validation(
        self,
        run_id: str,
        pbo_score: float,
        deflated_sharpe: float,
        wfe_score: float,
        mc_var_95: float,
        mc_max_dd_95: float,
        verdict: str,
        diagnostics: Optional[Dict[str, Any]] = None
    ) -> None:
        """Saves statistical validation metrics for a run."""
        with self._get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO validation_metrics (
                    run_id, pbo_score, deflated_sharpe, wfe_score,
                    mc_var_95, mc_max_dd_95, verdict, diagnostics_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                run_id, pbo_score, deflated_sharpe, wfe_score,
                mc_var_95, mc_max_dd_95, verdict, json.dumps(diagnostics or {})
            ))
            conn.commit()

    def get_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves run details by run_id."""
        with self._get_connection() as conn:
            cur = conn.execute("SELECT * FROM backtest_runs WHERE run_id = ?", (run_id,))
            row = cur.fetchone()
            if not row:
                return None
            res = dict(row)
            res["params"] = json.loads(res["params_json"] or "{}")
            res["metrics"] = json.loads(res["metrics_json"] or "{}")
            return res

    def list_runs(self, limit: int = 50, strategy: Optional[str] = None) -> List[Dict[str, Any]]:
        """Returns recent backtest runs."""
        query = "SELECT * FROM backtest_runs"
        params = []
        if strategy:
            query += " WHERE strategy_name = ?"
            params.append(strategy)
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        with self._get_connection() as conn:
            rows = conn.execute(query, params).fetchall()
            result = []
            for r in rows:
                d = dict(r)
                d["params"] = json.loads(d["params_json"] or "{}")
                d["metrics"] = json.loads(d["metrics_json"] or "{}")
                result.append(d)
            return result

    # Alias for convenience
    query_runs = list_runs

