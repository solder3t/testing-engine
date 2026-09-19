"""
analytics/session_auditor.py — Automated Daily Session Audit and Tearsheet Generator.

Performs institutional auditing of a live/paper trading session:
1. Reconciles live order execution against theoretical backtest signals (slippage, latency, efficiency).
2. Audits Gemini AI decision precision, recall, and capital preservation.
3. Evaluates Strategy v4 factor contributions.
4. Generates an executive health scorecard with automated anomaly flags.
5. Outputs rich terminal tables and standalone executive HTML reports.
"""

from datetime import datetime
from typing import Dict, List, Any, Optional
from data.data_loader import DataLoader
from analytics.reconciliation import ReconciliationEngine
from analytics.ai_decision_analyzer import AIDecisionAnalyzer
from analytics.factor_attribution import FactorAttributionEngine


class SessionAuditor:
    """Consolidated session auditor and tearsheet generator."""

    def __init__(self, data_loader: Optional[DataLoader] = None):
        self.data_loader = data_loader or DataLoader()

    def audit_session(self, date_str: str, include_ablation: bool = False) -> Dict[str, Any]:
        """
        Execute comprehensive audit for a specific trading date.
        
        Args:
            date_str: Date in format YYYY_MM_DD.
            include_ablation: Whether to run full 8-pass factor ablation (takes ~30s). Default False.
            
        Returns:
            Dict containing session scorecard, reconciliation, AI metrics, and flags.
        """
        clean_date = date_str.replace("-", "_")

        # 1. Reconciliation Audit
        recon_engine = ReconciliationEngine(data_loader=self.data_loader)
        recon_result = recon_engine.run_reconciliation(date_str=clean_date)
        recon_summary = recon_result.get("summary", {})

        # 2. AI Decision Audit
        ai_analyzer = AIDecisionAnalyzer(data_loader=self.data_loader)
        ai_result = ai_analyzer.analyze_session(date_str=clean_date)
        ai_matrix = ai_result.get("counterfactual_matrix", {})

        # 3. Factor & Strategy Attribution
        factor_engine = FactorAttributionEngine(data_loader=self.data_loader)
        if include_ablation:
            factor_result = factor_engine.run_ablation(date_strings=[clean_date])
        else:
            factor_result = {"status": "skipped", "factors": []}

        # 4. Compute Anomaly Flags & Session Health Rating
        flags: List[Dict[str, str]] = []
        eff_score = recon_summary.get("execution_efficiency_score", 100.0)
        avg_slippage = recon_summary.get("avg_entry_slippage_pct", 0.0)
        avg_latency = recon_summary.get("avg_latency_seconds", 0.0)
        ai_prec = ai_matrix.get("precision", 100.0)
        total_live = recon_summary.get("total_live_trades", 0)

        if total_live > 0 and avg_slippage > 3.0:
            flags.append({
                "severity": "WARNING",
                "code": "HIGH_ENTRY_SLIPPAGE",
                "message": f"Average entry slippage was {avg_slippage:.2f}% (exceeds 3.0% threshold)."
            })
        elif total_live > 0 and avg_slippage > 1.5:
            flags.append({
                "severity": "INFO",
                "code": "MODERATE_ENTRY_SLIPPAGE",
                "message": f"Average entry slippage was {avg_slippage:.2f}%."
            })

        if abs(avg_latency) > 90.0:
            flags.append({
                "severity": "WARNING",
                "code": "SIGNAL_LATENCY_DELAY",
                "message": f"Execution latency averaged {avg_latency:.1f}s relative to strategy signal."
            })

        if ai_matrix.get("signals_filtered", 0) > 0:
            saved_capital = ai_matrix.get("true_negatives", 0)
            flags.append({
                "severity": "SUCCESS",
                "code": "CAPITAL_PRESERVATION_ACTIVE",
                "message": f"Gemini AI filtered {ai_matrix.get('signals_filtered', 0)} market states, successfully preventing drawdown in {saved_capital} instances."
            })

        # Overall Session Scorecard
        score = 100.0
        if avg_slippage > 2.0:
            score -= 15.0
        if abs(avg_latency) > 60.0:
            score -= 15.0
        if ai_prec < 60.0:
            score -= 15.0

        if score >= 90:
            grade = "A+ (Institutional Optimal)"
            status_color = "#00f5a0"
        elif score >= 75:
            grade = "A (Clean Execution)"
            status_color = "#00f2fe"
        elif score >= 60:
            grade = "B (Acceptable Drift)"
            status_color = "#fadb14"
        else:
            grade = "C (Degraded Performance)"
            status_color = "#ff4d4f"

        audit_data = {
            "date": clean_date,
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "health_score": round(max(0.0, score), 1),
            "grade": grade,
            "status_color": status_color,
            "flags": flags,
            "reconciliation": recon_result,
            "ai_analytics": ai_result,
            "factor_attribution": factor_result
        }
        return audit_data

    def generate_html_report(self, audit_data: Dict[str, Any]) -> str:
        """Render a publication-quality standalone HTML executive tearsheet report."""
        date = audit_data.get("date", "Unknown")
        score = audit_data.get("health_score", 0.0)
        grade = audit_data.get("grade", "N/A")
        recon = audit_data.get("reconciliation", {}).get("summary", {})
        ai = audit_data.get("ai_analytics", {})
        ai_mat = ai.get("counterfactual_matrix", {})
        flags = audit_data.get("flags", [])
        matched_pairs = audit_data.get("reconciliation", {}).get("matched_pairs", [])

        flags_html = "".join([
            f"""<div style="padding: 10px 14px; margin-bottom: 8px; border-radius: 6px; 
                 background: {'rgba(255,77,79,0.1)' if f['severity']=='WARNING' else ('rgba(0,245,160,0.1)' if f['severity']=='SUCCESS' else 'rgba(0,242,254,0.1)')};
                 border-left: 4px solid {'#ff4d4f' if f['severity']=='WARNING' else ('#00f5a0' if f['severity']=='SUCCESS' else '#00f2fe')};
                 font-size: 0.85rem; color: #fff;">
                <strong>[{f['severity']}] {f['code']}</strong>: {f['message']}
            </div>""" for f in flags
        ]) if flags else '<div style="color: #a0aec0; font-size: 0.85rem;">No anomaly flags triggered. Session execution was aligned.</div>'

        pairs_rows = "".join([
            f"""<tr>
                <td style="font-weight: 600;">{p.get('symbol') or p.get('live_trade', {}).get('symbol') or p.get('sim_trade', {}).get('symbol', 'N/A')}</td>
                <td style="font-family: monospace;">{p.get('live_trade', {}).get('entry_time', '')}</td>
                <td style="font-family: monospace;">₹{p.get('live_trade', {}).get('entry_price', 0):.2f}</td>
                <td style="font-family: monospace;">₹{(p.get('sim_trade') or p.get('simulated_trade', {})).get('entry_price', 0):.2f}</td>
                <td style="font-family: monospace; color: {'#ff4d4f' if p.get('entry_slippage_rs', 0) > 2 else '#00f5a0'};">₹{p.get('entry_slippage_rs', 0):.2f} ({p.get('entry_slippage_pct', 0):.1f}%)</td>
                <td style="font-family: monospace;">{p.get('latency_seconds', 0):.1f}s</td>
                <td style="font-family: monospace; font-weight: 700; color: {'#00f5a0' if p.get('live_trade', {}).get('net_pnl', 0) >= 0 else '#ff4d4f'};">₹{p.get('live_trade', {}).get('net_pnl', 0):.2f}</td>
                <td style="font-family: monospace; font-weight: 700; color: {'#00f5a0' if (p.get('sim_trade') or p.get('simulated_trade', {})).get('net_pnl', 0) >= 0 else '#ff4d4f'};">₹{(p.get('sim_trade') or p.get('simulated_trade', {})).get('net_pnl', 0):.2f}</td>
                <td style="font-family: monospace; font-weight: 700; color: #00f2fe;">{p.get('execution_efficiency', 0):.1f}%</td>
            </tr>""" for p in matched_pairs
        ]) if matched_pairs else '<tr><td colspan="9" style="text-align: center; color: #a0aec0; padding: 14px;">No matched pairs.</td></tr>'

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Session Audit Report: {date} — Testing Engine</title>
  <style>
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      background: #0d1117;
      color: #c9d1d9;
      margin: 0;
      padding: 30px;
    }}
    .container {{
      max-width: 1080px;
      margin: 0 auto;
    }}
    .header {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      border-bottom: 1px solid rgba(255,255,255,0.1);
      padding-bottom: 20px;
      margin-bottom: 24px;
    }}
    .kpi-grid {{
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 14px;
      margin-bottom: 24px;
    }}
    .kpi-card {{
      background: rgba(22,27,34,0.8);
      border: 1px solid rgba(255,255,255,0.08);
      border-radius: 8px;
      padding: 16px;
    }}
    .kpi-label {{
      font-size: 0.75rem;
      color: #8b949e;
      text-transform: uppercase;
      letter-spacing: 0.05em;
    }}
    .kpi-val {{
      font-size: 1.5rem;
      font-weight: 700;
      color: #fff;
      margin: 6px 0 2px;
    }}
    .card {{
      background: rgba(22,27,34,0.8);
      border: 1px solid rgba(255,255,255,0.08);
      border-radius: 8px;
      padding: 18px;
      margin-bottom: 24px;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 0.82rem;
    }}
    th {{
      text-align: left;
      padding: 8px 10px;
      color: #8b949e;
      border-bottom: 1px solid rgba(255,255,255,0.1);
    }}
    td {{
      padding: 10px;
      border-bottom: 1px solid rgba(255,255,255,0.05);
    }}
    .btn-print {{
      background: #00f2fe;
      color: #000;
      border: none;
      padding: 8px 16px;
      border-radius: 6px;
      font-weight: 700;
      cursor: pointer;
    }}
    @media print {{
      .btn-print {{ display: none; }}
      body {{ background: #fff; color: #000; }}
      .card, .kpi-card {{ background: #fff; border: 1px solid #ccc; color: #000; }}
      .kpi-val {{ color: #000; }}
    }}
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <div>
        <h1 style="margin: 0; color: #fff; font-size: 1.6rem;">⚡ Session Audit Report: {date}</h1>
        <p style="margin: 4px 0 0; color: #8b949e; font-size: 0.85rem;">Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} by Antigravity Testing Engine</p>
      </div>
      <div style="display: flex; gap: 12px; align-items: center;">
        <span style="font-size: 1.1rem; font-weight: 700; color: {audit_data.get('status_color', '#00f2fe')};">
          {grade} ({score}/100)
        </span>
        <button class="btn-print" onclick="window.print()">Print / Export PDF</button>
      </div>
    </div>

    <!-- KPI Grid -->
    <div class="kpi-grid">
      <div class="kpi-card">
        <div class="kpi-label">Execution Efficiency</div>
        <div class="kpi-val" style="color: #00f2fe;">{recon.get('execution_efficiency_score', 0):.1f}%</div>
        <div style="font-size: 0.75rem; color: #8b949e;">Slippage & latency quality</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">Avg Entry Slippage</div>
        <div class="kpi-val">₹{recon.get('avg_entry_slippage_rs', 0):.2f}</div>
        <div style="font-size: 0.75rem; color: #8b949e;">{recon.get('avg_entry_slippage_pct', 0):.2f}% premium drag</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">AI Decision Precision</div>
        <div class="kpi-val" style="color: #00f5a0;">{ai_mat.get('precision', 0):.1f}%</div>
        <div style="font-size: 0.75rem; color: #8b949e;">Accuracy: {ai_mat.get('accuracy', 0):.1f}%</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">Net P&L Realized</div>
        <div class="kpi-val" style="color: {'#00f5a0' if recon.get('live_total_pnl', 0) >= 0 else '#ff4d4f'};">
          ₹{recon.get('live_total_pnl', 0):.2f}
        </div>
        <div style="font-size: 0.75rem; color: #8b949e;">Sim P&L: ₹{recon.get('sim_total_pnl', 0):.2f}</div>
      </div>
    </div>

    <!-- Anomaly & Execution Flags -->
    <div class="card">
      <h3 style="margin-top: 0; color: #fff;">Diagnostic Flags & Observations</h3>
      {flags_html}
    </div>

    <!-- Matched Trades Table -->
    <div class="card">
      <h3 style="margin-top: 0; color: #fff;">Live vs Theoretical Order Reconciliation</h3>
      <table>
        <thead>
          <tr>
            <th>Symbol</th>
            <th>Live Time</th>
            <th>Live ₹</th>
            <th>Sim ₹</th>
            <th>Slippage</th>
            <th>Latency</th>
            <th>Live Net P&L</th>
            <th>Sim Net P&L</th>
            <th>Efficiency</th>
          </tr>
        </thead>
        <tbody>
          {pairs_rows}
        </tbody>
      </table>
    </div>

  </div>
</body>
</html>
"""
