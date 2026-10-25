"""Pure payment-model adjustments.

All functions accept JSON-like dictionaries/lists and injected RNG/samplers and
return JSON-like values.  They neither persist data nor import application code.
"""
from __future__ import annotations

import calendar
import math
from datetime import date, timedelta
from statistics import mean, pstdev
from typing import Any, Callable


def _stats(row: dict[str, Any]) -> tuple[float, float, float, int]:
    count = int(row.get("n", row.get("count", 0)) or 0)
    return (float(row.get("mean_delay", 0)), float(row.get("std_delay", 0)), float(row.get("on_time_rate", 0)), count)


def shrinkage_blend(customer_stats: dict[str, Any], segment_stats: dict[str, Any], business_stats: dict[str, Any], k: int = 5) -> dict[str, float]:
    """Blend delay statistics customer→segment→business with n/(n+k) weights."""
    if k < 0:
        raise ValueError("k must be non-negative")
    b_mean, b_std, b_rate, _ = _stats(business_stats)
    s_mean, s_std, s_rate, s_n = _stats(segment_stats)
    s_weight = s_n / (s_n + k) if s_n + k else 1.0
    segment = tuple(s_weight * value + (1 - s_weight) * base for value, base in zip((s_mean, s_std, s_rate), (b_mean, b_std, b_rate)))
    c_mean, c_std, c_rate, c_n = _stats(customer_stats)
    weight = c_n / (c_n + k) if c_n + k else 0.0
    blended = tuple(weight * value + (1 - weight) * base for value, base in zip((c_mean, c_std, c_rate), segment))
    return {"mean_delay": blended[0], "std_delay": blended[1], "on_time_rate": blended[2], "shrinkage_weight": weight}


def invoice_features(invoice: dict[str, Any], customer_history: list[dict[str, Any]], today: str) -> dict[str, Any]:
    """Return deterministic numeric/categorical features for one invoice proposal."""
    due = date.fromisoformat(invoice["due_date"])
    issue = date.fromisoformat(invoice.get("issue_date", invoice["due_date"]))
    delays = [float(item["delay"]) for item in customer_history if item.get("delay") is not None]
    recent, previous = delays[-3:], delays[-6:-3]
    trend = (mean(recent) - mean(previous)) if recent and previous else 0.0
    return {"log_amount": math.log1p(max(0, int(invoice.get("amount", 0)))), "terms_days": max(0, (due - issue).days),
        "month_end": due.day >= calendar.monthrange(due.year, due.month)[1] - 4, "delay_trend": trend,
        "late_count": sum(delay > 0 for delay in delays), "dispute": bool(invoice.get("dispute", False))}


def common_shock_sigma(monthly_mean_delays_by_customer: dict[str, list[float]]) -> float:
    """Estimate shared delay variation; return conservative 0.15 if not estimable."""
    series = [values for values in monthly_mean_delays_by_customer.values() if len(values) >= 3]
    if len(series) < 2:
        return 0.15
    length = min(map(len, series))
    correlations: list[float] = []
    for left_index, left in enumerate(series):
        for right in series[left_index + 1:]:
            a, b = left[-length:], right[-length:]
            sa, sb = pstdev(a), pstdev(b)
            if sa and sb:
                correlations.append(sum((x - mean(a)) * (y - mean(b)) for x, y in zip(a, b)) / (length * sa * sb))
    if not correlations:
        return 0.15
    return round(max(0.01, min(1.0, pstdev([mean(values[-length:]) for values in series]) / max(1.0, abs(mean([v for values in series for v in values[-length:]]))) * (1 + max(0, mean(correlations))))), 4)


def draw_shock(rng: Any, sigma: float) -> float:
    """Draw a median-one lognormal multiplier using a numpy- or random-like RNG."""
    if sigma < 0: raise ValueError("sigma must be non-negative")
    if hasattr(rng, "lognormal"): return float(rng.lognormal(mean=0, sigma=sigma))
    return math.exp(rng.gauss(0, sigma))


def promise_adjusted_date(rng: Any, promised_date: str, p_keep: float, fallback_sampler: Callable[[], str | date]) -> str:
    """Sample a payment date near a promise or after it on a missed promise."""
    promised = date.fromisoformat(promised_date)
    random_value = float(rng.random())
    if random_value < max(0, min(1, p_keep)):
        offset = int(rng.integers(-3, 4)) if hasattr(rng, "integers") else rng.randint(-3, 3)
        return (promised + timedelta(days=offset)).isoformat()
    sampled = fallback_sampler()
    fallback = date.fromisoformat(sampled) if isinstance(sampled, str) else sampled
    return max(fallback, promised + timedelta(days=1)).isoformat()


def keep_rate_shrunk(kept: int, total: int, prior: float = 0.6, k: int = 3) -> float:
    """Return a beta-prior-smoothed promise keeping rate."""
    if total < 0 or kept < 0 or kept > total or not 0 <= prior <= 1 or k < 0: raise ValueError("invalid promise counts or prior")
    return (kept + prior * k) / (total + k) if total + k else prior


def run_rate_sales(invoices: list[dict[str, Any]], today: str, months: int = 6) -> dict[str, Any]:
    """Return trimmed mean monthly invoiced sales for the recent completed months."""
    if months < 3: raise ValueError("months must be at least 3")
    anchor = date.fromisoformat(today).replace(day=1)
    buckets: dict[tuple[int, int], int] = {}
    for invoice in invoices:
        try: issued = date.fromisoformat(invoice["issue_date"])
        except (KeyError, TypeError, ValueError): continue
        month_age = (anchor.year - issued.year) * 12 + anchor.month - issued.month
        if 1 <= month_age <= months:
            buckets[(issued.year, issued.month)] = buckets.get((issued.year, issued.month), 0) + int(invoice.get("amount", 0))
    values = list(buckets.values())
    if len(values) < 3: return {"monthly_amount": None, "months_used": len(values), "method": "insufficient_history"}
    values.sort()
    trimmed = values[1:-1] if len(values) >= 5 else values
    return {"monthly_amount": int(round(mean(trimmed))), "months_used": len(values), "method": "trimmed_mean_invoiced"}
