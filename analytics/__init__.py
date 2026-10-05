"""
analytics package — Quantitative performance metrics, validation suite, and reporting.
"""

from .metrics import calculate_performance_metrics
from .results_db import ResultsDB
from .tearsheet import generate_html_tearsheet
from .trade_exporter import TradeExporter
from .validation import ValidationSuite
from .validation_report import CandidateValidator
from .matrix_analyzer import MatrixAnalyzer

# Trading Engine Integration & Analytical Cockpit
from .ai_decision_analyzer import AIDecisionAnalyzer
from .auto_tuner import AutoTuningEngine
from .config_sync import ConfigSyncEngine
from .factor_attribution import FactorAttributionEngine
from .monte_carlo import MonteCarloSimulator
from .multi_leg_options import BlackScholesCalculator, MultiLegOptionEngine
from .option_chain_analyzer import OptionChainAnalyzer
from .portfolio_allocator import PortfolioAllocator
from .reconciliation import ReconciliationEngine
from .robustness import RobustnessEngine
from .session_auditor import SessionAuditor
from .trade_replay import TradeReplayEngine

__all__ = [
    "calculate_performance_metrics",
    "ResultsDB",
    "generate_html_tearsheet",
    "TradeExporter",
    "ValidationSuite",
    "CandidateValidator",
    "MatrixAnalyzer",
    "AIDecisionAnalyzer",
    "AutoTuningEngine",
    "ConfigSyncEngine",
    "FactorAttributionEngine",
    "MonteCarloSimulator",
    "BlackScholesCalculator",
    "MultiLegOptionEngine",
    "OptionChainAnalyzer",
    "PortfolioAllocator",
    "ReconciliationEngine",
    "RobustnessEngine",
    "SessionAuditor",
    "TradeReplayEngine",
]
