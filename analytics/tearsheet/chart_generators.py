"""
analytics/tearsheet/chart_generators.py — Chart serialization and client-side Chart.js script generation.
"""

import json
from typing import Any, Dict, List


def extract_chart_data(result: Dict[str, Any]) -> Dict[str, Any]:
    """Extracts and formats series data for equity curve and underwater drawdown."""
    init_cap = result.get("initial_capital", 500000.0)
    metrics = result.get("metrics", {})
    equity_curve = result.get("equity_curve", [])
    drawdown_curve = result.get("drawdown_curve", metrics.get("drawdown_curve", []))
    daily = result.get("daily_breakdown", [])

    ec_labels = [pt.get("timestamp", "") for pt in equity_curve]
    ec_values = [pt.get("equity", init_cap) for pt in equity_curve]

    dd_labels = [pt.get("timestamp", "") for pt in drawdown_curve]
    dd_values = [-abs(pt.get("drawdown_pct", 0.0)) for pt in drawdown_curve]

    daily_labels = [d.get("date", "") for d in daily]
    daily_pnls = [d.get("pnl", 0.0) for d in daily]

    return {
        "ec_labels": ec_labels,
        "ec_values": ec_values,
        "dd_labels": dd_labels,
        "dd_values": dd_values,
        "daily_labels": daily_labels,
        "daily_pnls": daily_pnls,
    }


def render_chart_scripts(chart_data: Dict[str, Any]) -> str:
    """Renders Chart.js initialization script tag."""
    ec_labels = json.dumps(chart_data.get("ec_labels", []))
    ec_values = json.dumps(chart_data.get("ec_values", []))
    dd_labels = json.dumps(chart_data.get("dd_labels", []))
    dd_values = json.dumps(chart_data.get("dd_values", []))

    return f"""
    <script>
        const ecLabels = {ec_labels};
        const ecValues = {ec_values};
        const ddLabels = {dd_labels};
        const ddValues = {dd_values};

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
    """


__all__ = ["extract_chart_data", "render_chart_scripts"]
