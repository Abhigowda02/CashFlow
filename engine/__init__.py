"""
engine package
Predictive Cash-Flow Management for Small Businesses (India)
Per contracts/CONTRACT.md
"""

from engine.actions import rank_actions
from engine.datagen import generate_business
from engine.forecast import compare_scenario, format_inr, run_forecast

__all__ = [
    "generate_business",
    "run_forecast",
    "compare_scenario",
    "rank_actions",
    "format_inr",
]
