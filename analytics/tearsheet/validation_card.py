"""
analytics/tearsheet/validation_card.py — Statistical Validation Report Cards.
Injects WFO consistency, Monte Carlo VaR, CSCV PBO, DSR, and hurdle verification into HTML tearsheets.
"""

from typing import Any, Dict, Optional


def render_validation_audit_card(validation_data: Optional[Dict[str, Any]] = None) -> str:
    """
    Renders an institutional HTML card displaying the 4-hurdle statistical validation
    and an overall GO / NO-GO verdict banner.
    """
    if not validation_data:
        return ""

    hurdles = validation_data.get("hurdles")
    if not hurdles:
        # Fallback to standard metrics card if raw dict provided without hurdle structure
        pbo = validation_data.get("pbo", 0.0)
        wfo_eff = validation_data.get("wfo_efficiency", validation_data.get("wfe", 0.0))
        var_95 = validation_data.get("var_95", 0.0)
        cvar_95 = validation_data.get("cvar_95", 0.0)
        is_deflated = validation_data.get("deflated_sharpe_passed", True)

        status_badge = '<span style="color: #2ea043; font-weight: bold;">PASSED</span>' if is_deflated else '<span style="color: #f85149; font-weight: bold;">OVERFIT WARNING</span>'

        return f"""
        <!-- Statistical Validation Card -->
        <div class="table-card" style="margin-bottom: 24px; border-left: 4px solid var(--accent-cyan);">
            <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid var(--border); padding-bottom: 8px; margin-bottom: 12px;">
                <h3 style="margin: 0; border: none; padding: 0;">Institutional Statistical Validation Suite</h3>
                <div>{status_badge}</div>
            </div>
            <table>
                <tbody>
                    <tr>
                        <td>Probability of Backtest Overfitting (CSCV PBO)</td>
                        <td style="text-align: right;">{pbo:.1%}</td>
                        <td>Walk-Forward Efficiency Ratio (WFO)</td>
                        <td style="text-align: right;">{wfo_eff:.2f}</td>
                    </tr>
                    <tr>
                        <td>Monte Carlo 95% Historical VaR</td>
                        <td style="text-align: right; color: var(--red);">-₹{var_95:,.2f}</td>
                        <td>Conditional VaR (95% Expected Shortfall)</td>
                        <td style="text-align: right; color: var(--red);">-₹{cvar_95:,.2f}</td>
                    </tr>
                </tbody>
            </table>
        </div>
        """

    verdict = validation_data.get("verdict", "NO-GO")
    banner_color = "#2ea043" if verdict == "GO" else "#f85149"
    banner_bg = "rgba(46, 160, 67, 0.15)" if verdict == "GO" else "rgba(248, 81, 73, 0.15)"

    rows_html = ""
    for k, h in hurdles.items():
        icon = "✅ PASS" if h.get("passed") else "❌ FAIL"
        color = "#2ea043" if h.get("passed") else "#f85149"
        val = h.get("value", 0.0)
        val_str = f"{val:.1%}" if "pbo" in k else (f"{val:.2f}" if isinstance(val, float) else str(val))
        rows_html += f"""
        <tr>
            <td style="padding: 10px 14px; font-weight: 500;">{h.get('name', k)}</td>
            <td style="padding: 10px 14px; text-align: right; font-family: monospace;">{val_str}</td>
            <td style="padding: 10px 14px; text-align: center; color: var(--text-dim);">{h.get('hurdle', '')}</td>
            <td style="padding: 10px 14px; text-align: center; font-weight: bold; color: {color};">{icon}</td>
        </tr>
        """

    return f"""
    <!-- Institutional Validation Audit Card -->
    <div class="table-card" style="margin-top: 30px; margin-bottom: 30px; border: 1px solid var(--border); border-radius: 8px; overflow: hidden;">
        <div style="background: {banner_bg}; border-bottom: 2px solid {banner_color}; padding: 14px 20px; display: flex; justify-content: space-between; align-items: center;">
            <div style="font-size: 16px; font-weight: 700; letter-spacing: 0.5px;">INSTITUTIONAL VALIDATION AUDIT</div>
            <div style="background: {banner_color}; color: #fff; padding: 4px 14px; border-radius: 20px; font-weight: 800; font-size: 14px;">
                VERDICT: {verdict}
            </div>
        </div>
        <table style="width: 100%; border-collapse: collapse;">
            <thead>
                <tr style="background: var(--surface); color: var(--text-dim); font-size: 12px; text-transform: uppercase;">
                    <th style="padding: 8px 14px; text-align: left;">Audit Hurdle Metric</th>
                    <th style="padding: 8px 14px; text-align: right;">Observed Value</th>
                    <th style="padding: 8px 14px; text-align: center;">Required Threshold</th>
                    <th style="padding: 8px 14px; text-align: center;">Status</th>
                </tr>
            </thead>
            <tbody>
                {rows_html}
            </tbody>
        </table>
    </div>
    """


render_validation_card = render_validation_audit_card

__all__ = ["render_validation_card", "render_validation_audit_card"]
