"""
analytics/tearsheet.py — Institutional Performance Tearsheet Generator.

Generates standalone, printable, publication-grade HTML performance tearsheets
with executive summaries, risk ratios, session breakdown matrices, underwater
drawdowns, and embedded responsive charts.
"""

from typing import Dict, Any, List
import datetime
import json


def generate_html_tearsheet(result: Dict[str, Any]) -> str:
    """
    Builds a standalone HTML document representing an institutional quantitative tearsheet.
    """
    strat = result.get("strategy", "Unknown Strategy")
    dates_tested = result.get("dates_tested", [])
    date_range_str = f"{dates_tested[0]} to {dates_tested[-1]}" if len(dates_tested) > 1 else (dates_tested[0] if dates_tested else "N/A")
    session_count = len(dates_tested)
    init_cap = result.get("initial_capital", 500000.0)
    final_eq = result.get("final_equity", init_cap)
    metrics = result.get("metrics", {})
    daily = result.get("daily_breakdown", [])
    equity_curve = result.get("equity_curve", [])
    drawdown_curve = result.get("drawdown_curve", metrics.get("drawdown_curve", []))

    net_pnl = metrics.get("net_pnl", 0.0)
    return_pct = metrics.get("return_pct", 0.0)
    gross_pnl = metrics.get("gross_pnl", 0.0)
    total_charges = metrics.get("total_charges", 0.0)
    sharpe = metrics.get("sharpe_ratio", 0.0)
    sortino = metrics.get("sortino_ratio", 0.0)
    calmar = metrics.get("calmar_ratio", 0.0)
    max_dd_pct = metrics.get("max_drawdown_pct", 0.0)
    max_dd_rs = metrics.get("max_drawdown_rs", 0.0)
    profit_factor = metrics.get("profit_factor", 0.0)
    win_rate = metrics.get("win_rate", 0.0)
    expectancy = metrics.get("expectancy", 0.0)
    total_trades = metrics.get("total_trades", 0)
    wins = metrics.get("wins", 0)
    losses = metrics.get("losses", 0)
    breakeven_count = metrics.get("breakeven_count", 0)
    max_win_streak = metrics.get("max_consecutive_wins", 0)
    max_loss_streak = metrics.get("max_consecutive_losses", 0)
    avg_trade_pnl = metrics.get("avg_trade_pnl", 0.0)
    best_trade = metrics.get("best_trade", 0.0)
    worst_trade = metrics.get("worst_trade", 0.0)
    avg_holding_bars = metrics.get("avg_holding_bars", 0.0)

    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Format JSON data for charts
    ec_labels = [pt.get("timestamp", "") for pt in equity_curve]
    ec_values = [pt.get("equity", init_cap) for pt in equity_curve]

    dd_labels = [pt.get("timestamp", "") for pt in drawdown_curve]
    dd_values = [-abs(pt.get("drawdown_pct", 0.0)) for pt in drawdown_curve]

    daily_labels = [d.get("date", "") for d in daily]
    daily_pnls = [d.get("net_pnl", d.get("pnl", 0.0)) for d in daily]

    # Calculate Top Drawdown Periods
    dd_periods = []
    if drawdown_curve:
        # Sort points by max drawdown depth
        sorted_dd = sorted(drawdown_curve, key=lambda x: x.get("drawdown_pct", 0.0), reverse=True)
        top_dd = sorted_dd[:5]
        for idx, item in enumerate(top_dd):
            if item.get("drawdown_pct", 0.0) > 0:
                dd_periods.append({
                    "rank": idx + 1,
                    "timestamp": item.get("timestamp", ""),
                    "drawdown_pct": item.get("drawdown_pct", 0.0),
                    "drawdown_rs": item.get("drawdown_rs", 0.0)
                })

    pnl_class = "pos" if net_pnl >= 0 else "neg"
    pnl_sign = "+" if net_pnl >= 0 else ""

    # Build Session Rows
    session_rows_html = ""
    for d in daily:
        d_pnl = d.get("net_pnl", d.get("pnl", 0.0))
        d_sign = "+" if d_pnl >= 0 else ""
        d_cls = "pos" if d_pnl >= 0 else "neg"
        d_trades = d.get("trades_count", d.get("trades", 0))
        start_eq = d.get("starting_equity", 0.0)
        end_eq = d.get("ending_equity", 0.0)
        ret_pct = d.get("return_pct", 0.0)
        if ret_pct == 0.0 and start_eq > 0 and d_pnl != 0.0:
            ret_pct = round((d_pnl / start_eq) * 100, 2)
        session_rows_html += f"""
        <tr>
            <td><strong>{d.get('date', '')}</strong></td>
            <td>₹{start_eq:,.2f}</td>
            <td>₹{end_eq:,.2f}</td>
            <td class="{d_cls}">{d_sign}₹{d_pnl:,.2f}</td>
            <td class="{d_cls}">{d_sign}{ret_pct:.2f}%</td>
            <td>{d_trades}</td>
        </tr>
        """

    if not session_rows_html:
        session_rows_html = "<tr><td colspan='6' style='text-align: center; color: #888;'>No session breakdown data available</td></tr>"

    # Build Top Drawdowns Rows
    dd_rows_html = ""
    for item in dd_periods:
        dd_rows_html += f"""
        <tr>
            <td>#{item['rank']}</td>
            <td>{item['timestamp']}</td>
            <td class="neg">-{item['drawdown_pct']:.2f}%</td>
            <td class="neg">-₹{item['drawdown_rs']:,.2f}</td>
        </tr>
        """
    if not dd_rows_html:
        dd_rows_html = "<tr><td colspan='4' style='text-align: center; color: #888;'>No significant drawdown recorded</td></tr>"

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Tearsheet — {strat} — Testing Engine</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600;700&family=Outfit:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        :root {{
            --bg: #0d1117;
            --surface: #161b22;
            --surface-sub: #1f242c;
            --border: #30363d;
            --text-main: #f0f6fc;
            --text-muted: #8b949e;
            --accent-cyan: #00f2fe;
            --green: #2ea043;
            --red: #f85149;
            --yellow: #e3b341;
        }}
        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }}
        body {{
            background: var(--bg);
            color: var(--text-main);
            font-family: 'Outfit', sans-serif;
            padding: 28px;
            font-size: 14px;
            line-height: 1.5;
        }}
        .no-print-bar {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            background: rgba(0, 242, 254, 0.08);
            border: 1px solid rgba(0, 242, 254, 0.25);
            padding: 12px 20px;
            border-radius: 8px;
            margin-bottom: 24px;
        }}
        .btn {{
            background: var(--accent-cyan);
            color: #000;
            border: none;
            padding: 8px 18px;
            border-radius: 6px;
            font-weight: 700;
            cursor: pointer;
            font-family: inherit;
            font-size: 13px;
            transition: opacity 0.2s;
        }}
        .btn:hover {{ opacity: 0.85; }}
        .header-section {{
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            border-bottom: 2px solid var(--border);
            padding-bottom: 18px;
            margin-bottom: 24px;
        }}
        .header-title h1 {{
            font-size: 1.8rem;
            font-weight: 800;
            letter-spacing: -0.5px;
            color: #fff;
        }}
        .header-title p {{
            color: var(--text-muted);
            margin-top: 4px;
            font-size: 0.9rem;
        }}
        .header-meta {{
            text-align: right;
            font-size: 0.82rem;
            color: var(--text-muted);
            font-family: 'JetBrains Mono', monospace;
        }}
        .header-meta strong {{
            color: var(--text-main);
        }}
        .kpi-row {{
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 14px;
            margin-bottom: 24px;
        }}
        .kpi-box {{
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 14px 18px;
        }}
        .kpi-label {{
            font-size: 0.75rem;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            color: var(--text-muted);
            margin-bottom: 6px;
        }}
        .kpi-val {{
            font-size: 1.5rem;
            font-weight: 800;
            font-family: 'JetBrains Mono', monospace;
        }}
        .kpi-sub {{
            font-size: 0.75rem;
            color: var(--text-muted);
            margin-top: 4px;
        }}
        .pos {{ color: var(--green) !important; }}
        .neg {{ color: var(--red) !important; }}
        .grid-2 {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
            margin-bottom: 24px;
        }}
        .table-card {{
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 16px 20px;
        }}
        .table-card h3 {{
            font-size: 1.05rem;
            font-weight: 700;
            margin-bottom: 12px;
            color: #fff;
            border-bottom: 1px solid var(--border);
            padding-bottom: 8px;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 0.85rem;
        }}
        th, td {{
            padding: 8px 10px;
            text-align: left;
            border-bottom: 1px solid rgba(255,255,255,0.06);
        }}
        th {{
            color: var(--text-muted);
            font-weight: 600;
            font-size: 0.75rem;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        td {{
            font-family: 'JetBrains Mono', monospace;
        }}
        .chart-card {{
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 16px 20px;
            margin-bottom: 24px;
        }}
        .chart-card h3 {{
            font-size: 1.05rem;
            font-weight: 700;
            margin-bottom: 14px;
            color: #fff;
        }}
        .chart-wrap {{
            height: 260px;
            position: relative;
        }}
        .footer-note {{
            margin-top: 30px;
            border-top: 1px solid var(--border);
            padding-top: 14px;
            text-align: center;
            font-size: 0.75rem;
            color: var(--text-muted);
        }}

        @media print {{
            body {{
                background: #ffffff !important;
                color: #111111 !important;
                padding: 10px !important;
                font-size: 11px !important;
            }}
            .no-print-bar {{ display: none !important; }}
            .kpi-box, .table-card, .chart-card {{
                background: #ffffff !important;
                border: 1px solid #d0d7de !important;
                color: #111111 !important;
                page-break-inside: avoid;
            }}
            .header-section {{
                border-bottom: 2px solid #111 !important;
            }}
            .header-title h1 {{ color: #000 !important; font-size: 1.5rem !important; }}
            .header-title p, .header-meta {{ color: #444 !important; }}
            th {{ color: #555 !important; border-bottom: 1px solid #ccc !important; }}
            td {{ border-bottom: 1px solid #eee !important; color: #111 !important; }}
            .table-card h3, .chart-card h3 {{ color: #000 !important; border-bottom: 1px solid #ccc !important; }}
            .pos {{ color: #008800 !important; }}
            .neg {{ color: #cc0000 !important; }}
            .chart-wrap {{ height: 200px !important; }}
        }}
    </style>
</head>
<body>

    <!-- Non-printable top action bar -->
    <div class="no-print-bar">
        <div>
            <span style="font-weight: 700; color: var(--accent-cyan);">⚡ TESTING ENGINE</span>
            <span style="color: var(--text-muted); margin-left: 8px;">— Institutional Performance Tearsheet</span>
        </div>
        <div style="display: flex; gap: 10px;">
            <button class="btn" onclick="window.print()">🖨️ Print / Save as PDF</button>
            <button class="btn" style="background: rgba(255,255,255,0.15); color: #fff;" onclick="window.close()">Close</button>
        </div>
    </div>

    <!-- Header Section -->
    <div class="header-section">
        <div class="header-title">
            <h1>{strat.upper()}</h1>
            <p>Strategy Performance Tearsheet & Risk Profile</p>
        </div>
        <div class="header-meta">
            <div>Dates Tested: <strong>{date_range_str} ({session_count} session{'s' if session_count != 1 else ''})</strong></div>
            <div>Initial Capital: <strong>₹{init_cap:,.2f}</strong></div>
            <div>Final Portfolio Equity: <strong>₹{final_eq:,.2f}</strong></div>
            <div>Generated: <strong>{now_str}</strong></div>
        </div>
    </div>

    <!-- Top KPI Grid -->
    <div class="kpi-row">
        <div class="kpi-box">
            <div class="kpi-label">Net Realized P&L</div>
            <div class="kpi-val {pnl_class}">{pnl_sign}₹{net_pnl:,.2f}</div>
            <div class="kpi-sub">{pnl_sign}{return_pct:.2f}% on capital</div>
        </div>
        <div class="kpi-box">
            <div class="kpi-label">Sharpe / Sortino</div>
            <div class="kpi-val">{sharpe:.2f}</div>
            <div class="kpi-sub">Sortino: {sortino:.2f} (ann. &radic;252)</div>
        </div>
        <div class="kpi-box">
            <div class="kpi-label">Max Drawdown</div>
            <div class="kpi-val neg">-{max_dd_pct:.2f}%</div>
            <div class="kpi-sub">-₹{max_dd_rs:,.2f} peak-to-trough</div>
        </div>
        <div class="kpi-box">
            <div class="kpi-label">Win Rate / Profit Factor</div>
            <div class="kpi-val">{win_rate:.1f}%</div>
            <div class="kpi-sub">PF: {profit_factor:.2f} ({wins}W / {losses}L / {breakeven_count}BE)</div>
        </div>
    </div>

    <!-- Equity Curve Chart -->
    <div class="chart-card">
        <h3>Cumulative Portfolio Equity (₹)</h3>
        <div class="chart-wrap">
            <canvas id="equityChartCanvas"></canvas>
        </div>
    </div>

    <!-- Drawdown Chart -->
    <div class="chart-card">
        <h3>Underwater Drawdown Profile (%)</h3>
        <div class="chart-wrap">
            <canvas id="drawdownChartCanvas"></canvas>
        </div>
    </div>

    <!-- 2 Column Tables: Key Performance & Risk Stats -->
    <div class="grid-2">
        <div class="table-card">
            <h3>Key Performance & Risk Ratios</h3>
            <table>
                <tbody>
                    <tr><td>Gross Realized P&L</td><td style="text-align: right;">₹{gross_pnl:,.2f}</td></tr>
                    <tr><td>Total Statutory Charges & Taxes</td><td style="text-align: right; color: var(--yellow);">₹{total_charges:,.2f}</td></tr>
                    <tr><td>Net Realized P&L</td><td style="text-align: right;" class="{pnl_class}">{pnl_sign}₹{net_pnl:,.2f}</td></tr>
                    <tr><td>Cumulative Return</td><td style="text-align: right;" class="{pnl_class}">{pnl_sign}{return_pct:.2f}%</td></tr>
                    <tr><td>Annualized Sharpe Ratio</td><td style="text-align: right;">{sharpe:.2f}</td></tr>
                    <tr><td>Annualized Sortino Ratio</td><td style="text-align: right;">{sortino:.2f}</td></tr>
                    <tr><td>Calmar Ratio</td><td style="text-align: right;">{calmar:.2f}</td></tr>
                    <tr><td>Max Drawdown (%)</td><td style="text-align: right;" class="neg">-{max_dd_pct:.2f}%</td></tr>
                    <tr><td>Max Drawdown (₹)</td><td style="text-align: right;" class="neg">-₹{max_dd_rs:,.2f}</td></tr>
                </tbody>
            </table>
        </div>

        <div class="table-card">
            <h3>Trade Distribution & Efficiency</h3>
            <table>
                <tbody>
                    <tr><td>Total Trades Executed</td><td style="text-align: right;">{total_trades}</td></tr>
                    <tr><td>Win Rate (%)</td><td style="text-align: right;">{win_rate:.2f}%</td></tr>
                    <tr><td>Profit Factor</td><td style="text-align: right;">{profit_factor:.2f}</td></tr>
                    <tr><td>Mathematical Expectancy / Trade</td><td style="text-align: right;">₹{expectancy:,.2f}</td></tr>
                    <tr><td>Average Trade P&L</td><td style="text-align: right;">₹{avg_trade_pnl:,.2f}</td></tr>
                    <tr><td>Best Single Trade</td><td style="text-align: right;" class="pos">+₹{best_trade:,.2f}</td></tr>
                    <tr><td>Worst Single Trade</td><td style="text-align: right;" class="neg">₹{worst_trade:,.2f}</td></tr>
                    <tr><td>Max Consecutive Wins</td><td style="text-align: right;" class="pos">{max_win_streak}</td></tr>
                    <tr><td>Max Consecutive Losses</td><td style="text-align: right;" class="neg">{max_loss_streak}</td></tr>
                    <tr><td>Average Holding Period (Bars)</td><td style="text-align: right;">{avg_holding_bars:.1f}</td></tr>
                </tbody>
            </table>
        </div>
    </div>

    <!-- Daily Breakdown Table -->
    <div class="table-card" style="margin-bottom: 24px;">
        <h3>Session-by-Session Performance Breakdown</h3>
        <table>
            <thead>
                <tr>
                    <th>Date</th>
                    <th>Starting Equity</th>
                    <th>Ending Equity</th>
                    <th>Session Net P&L</th>
                    <th>Return %</th>
                    <th>Trades</th>
                </tr>
            </thead>
            <tbody>
                {session_rows_html}
            </tbody>
        </table>
    </div>

    <!-- Top Drawdown Periods -->
    <div class="table-card" style="margin-bottom: 24px;">
        <h3>Top Drawdown Periods</h3>
        <table>
            <thead>
                <tr>
                    <th>Rank</th>
                    <th>Timestamp</th>
                    <th>Drawdown Depth %</th>
                    <th>Drawdown Depth ₹</th>
                </tr>
            </thead>
            <tbody>
                {dd_rows_html}
            </tbody>
        </table>
    </div>

    <div class="footer-note">
        ⚡ TESTING ENGINE • Quantitative Research & Strategy Backtesting Engine • Generated automatically from live market recordings.
    </div>

    <script>
        const ecLabels = {json.dumps(ec_labels)};
        const ecValues = {json.dumps(ec_values)};
        const ddLabels = {json.dumps(dd_labels)};
        const ddValues = {json.dumps(dd_values)};

        // Render Equity Chart
        const ctxEc = document.getElementById('equityChartCanvas').getContext('2d');
        new Chart(ctxEc, {{
            type: 'line',
            data: {{
                labels: ecLabels,
                datasets: [{{
                    label: 'Portfolio Equity (₹)',
                    data: ecValues,
                    borderColor: '#00f2fe',
                    backgroundColor: 'rgba(0, 242, 254, 0.08)',
                    borderWidth: 2,
                    fill: true,
                    tension: 0.1,
                    pointRadius: 0
                }}]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                plugins: {{
                    legend: {{ display: false }}
                }},
                scales: {{
                    x: {{ display: false }},
                    y: {{
                        grid: {{ color: 'rgba(255,255,255,0.06)' }},
                        ticks: {{
                            color: '#8b949e',
                            callback: v => '₹' + v.toLocaleString()
                        }}
                    }}
                }}
            }}
        }});

        // Render Drawdown Chart
        const ctxDd = document.getElementById('drawdownChartCanvas').getContext('2d');
        new Chart(ctxDd, {{
            type: 'line',
            data: {{
                labels: ddLabels,
                datasets: [{{
                    label: 'Underwater Drawdown (%)',
                    data: ddValues,
                    borderColor: '#f85149',
                    backgroundColor: 'rgba(248, 81, 73, 0.15)',
                    borderWidth: 1.5,
                    fill: true,
                    tension: 0.1,
                    pointRadius: 0
                }}]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                plugins: {{
                    legend: {{ display: false }}
                }},
                scales: {{
                    x: {{ display: false }},
                    y: {{
                        grid: {{ color: 'rgba(255,255,255,0.06)' }},
                        ticks: {{
                            color: '#8b949e',
                            callback: v => v.toFixed(1) + '%'
                        }}
                    }}
                }}
            }}
        }});
    </script>
</body>
</html>
"""
    return html
