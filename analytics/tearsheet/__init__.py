"""
analytics.tearsheet — Institutional Performance Tearsheet Generator.
"""

from .builder import generate_html_tearsheet, render_tearsheet
from .chart_generators import extract_chart_data, render_chart_scripts
from .validation_card import render_validation_card

__all__ = [
    "generate_html_tearsheet",
    "render_tearsheet",
    "extract_chart_data",
    "render_chart_scripts",
    "render_validation_card",
]
