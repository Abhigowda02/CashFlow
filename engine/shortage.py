"""Additive forecast-shortage summaries for scenario comparison JSON."""
from __future__ import annotations

from typing import Any

def analyse(forecast: dict[str, Any]) -> dict[str, Any]:
    """Return deterministic P10/P50 floor metrics from an existing forecast."""
    floor = int(forecast['safety_floor']); p10 = forecast['p10']; p50 = forecast['p50']; dates = forecast['dates']
    p10_index = min(range(len(p10)), key=p10.__getitem__); p50_index = min(range(len(p50)), key=p50.__getitem__)
    below = [value < floor for value in p50]
    return {'first_shortage_date': forecast.get('first_shortage_date'), 'days_until_shortage': next((index for index, value in enumerate(below) if value), None),
        'shortage_probability': forecast['shortage_prob'], 'minimum_p10_balance': p10[p10_index], 'minimum_p10_date': dates[p10_index],
        'minimum_p50_balance': p50[p50_index], 'minimum_p50_date': dates[p50_index],
        'peak_funding_gap': max(0, floor - min(p10)), 'days_below_floor': sum(below)}

def with_delta(summary: dict[str, Any], baseline: dict[str, Any]) -> dict[str, Any]:
    """Add numeric deltas versus a baseline shortage summary."""
    result = dict(summary)
    result['deltas'] = {key: summary[key] - baseline[key] for key in ('shortage_probability','minimum_p10_balance','minimum_p50_balance','peak_funding_gap','days_below_floor')}
    return result
