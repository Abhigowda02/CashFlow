"""Pure forecast-accuracy measures and walk-forward evaluation utilities.

Inputs are invoice/forecast dictionaries and injected model callables; outputs
are JSON-like metric dictionaries.  No application state is read or written.
"""
from __future__ import annotations

from datetime import date
from statistics import mean
from typing import Any, Callable


def payment_date_mae(pairs: list[dict[str, Any]]) -> float | None:
    """Return mean absolute payment-date error in days, or None for no pairs."""
    errors = [abs((date.fromisoformat(row['actual']) - date.fromisoformat(row['predicted'])).days) for row in pairs if row.get('actual') and row.get('predicted')]
    return round(mean(errors), 2) if errors else None


def coverage(actuals: list[str], p10s: list[str], p90s: list[str]) -> float | None:
    """Return fraction of actual ISO dates inside inclusive forecast intervals."""
    triples = zip(actuals, p10s, p90s)
    values = [date.fromisoformat(low) <= date.fromisoformat(actual) <= date.fromisoformat(high) for actual, low, high in triples]
    return round(sum(values) / len(values), 4) if values else None


def alert_hit_rate(pred_probs: list[float], actual_shortage_flags: list[bool], threshold: float = .5) -> dict[str, float]:
    """Return precision, recall and F1 for shortage alert predictions."""
    if len(pred_probs) != len(actual_shortage_flags): raise ValueError('probabilities and flags must have equal length')
    predicted = [value >= threshold for value in pred_probs]
    tp = sum(p and a for p, a in zip(predicted, actual_shortage_flags)); fp = sum(p and not a for p, a in zip(predicted, actual_shortage_flags)); fn = sum(not p and a for p, a in zip(predicted, actual_shortage_flags))
    precision, recall = (tp / (tp + fp) if tp + fp else 0.0), (tp / (tp + fn) if tp + fn else 0.0)
    return {'precision': round(precision, 4), 'recall': round(recall, 4), 'f1': round(2 * precision * recall / (precision + recall), 4) if precision + recall else 0.0}


def empirical_fit(rows: list[dict[str, Any]]) -> dict[str, float]:
    """Fit a simple mean due-date delay baseline for tests and fallback use."""
    delays = [(date.fromisoformat(row['paid_date']) - date.fromisoformat(row['due_date'])).days for row in rows if row.get('paid_date')]
    return {'mean_delay': mean(delays) if delays else 0.0}


def empirical_predict(model: dict[str, float], row: dict[str, Any]) -> dict[str, str]:
    """Predict an 80%-style ±7-day ISO interval around the empirical mean."""
    due = date.fromisoformat(row['due_date']); offset = round(model['mean_delay'])
    mid = due.fromordinal(due.toordinal() + offset)
    return {'predicted': mid.isoformat(), 'p10': mid.fromordinal(mid.toordinal() - 7).isoformat(), 'p90': mid.fromordinal(mid.toordinal() + 7).isoformat()}


def walk_forward(rows: list[dict[str, Any]], cutoffs: list[str], fit_fn: Callable[[list[dict[str, Any]]], Any], predict_fn: Callable[[Any, dict[str, Any]], dict[str, str]]) -> dict[str, Any]:
    """Evaluate injected models using only settlements known before each cutoff."""
    results = []
    for cutoff_text in cutoffs:
        cutoff = date.fromisoformat(cutoff_text)
        train = [row for row in rows if row.get('paid_date') and date.fromisoformat(row['paid_date']) < cutoff]
        evaluate = [row for row in rows if row.get('paid_date') and date.fromisoformat(row['issue_date']) <= cutoff < date.fromisoformat(row['paid_date'])]
        model = fit_fn(train)
        predictions = [dict(actual=row['paid_date'], **predict_fn(model, row)) for row in evaluate]
        results.append({'cutoff': cutoff_text, 'n_train': len(train), 'n_test': len(evaluate), 'mae': payment_date_mae(predictions), 'coverage': coverage([p['actual'] for p in predictions], [p['p10'] for p in predictions], [p['p90'] for p in predictions])})
    usable = [row for row in results if row['mae'] is not None]
    return {'cutoffs': results, 'aggregate': {'mae': round(mean([row['mae'] for row in usable]), 2) if usable else None, 'coverage': round(mean([row['coverage'] for row in usable]), 4) if usable else None, 'n_cutoffs': len(usable)}}


def live_accuracy(forecast_log: list[dict[str, Any]], actual_balances: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Compare logged P50 balances to actual balances after at least fourteen days."""
    actual = {row['date']: int(row['balance']) for row in actual_balances}
    pairs = [(int(row['p50']), actual[row['date']], int(row.get('p10', row['p50'])), int(row.get('p90', row['p50']))) for row in forecast_log if row.get('date') in actual]
    if len(pairs) < 14: return None
    return {'mae': round(mean(abs(predicted - observed) for predicted, observed, _, _ in pairs), 2), 'coverage': round(sum(low <= observed <= high for _, observed, low, high in pairs) / len(pairs), 4), 'n_days': len(pairs)}


def badge_text(backtest: dict[str, Any] | None, live: dict[str, Any] | None) -> str:
    """Return honest UI copy which never misrepresents backtest as live accuracy."""
    aggregate = (backtest or {}).get('aggregate', backtest or {})
    mae, band = aggregate.get('mae'), aggregate.get('coverage')
    if mae is None or band is None: return 'Accuracy is not yet measured. Live accuracy builds after 14 days of use.'
    text = f'Backtested on public data: payments predicted within {round(float(mae))} days on average; the 80% band contained the actual {round(float(band) * 100)}% of the time.'
    return text + (f" Live accuracy: {live['mae']:.0f} INR mean daily error over {live['n_days']} days." if live else ' Live accuracy builds after 14 days of use.')
