"""Mock fraud scoring for bank-payment events.

Input is a plain payment dictionary using integer INR; output contains score,
decision and reasons. It neither persists data nor charges a real payment method.
"""
from __future__ import annotations
from typing import Any


def check_fraud(payment: dict[str, Any]) -> dict[str, Any]:
    """Return ``score``, ``decision`` and human-readable ``reasons`` for a payment."""
    score, reasons = 0, []
    amount = int(payment['amount'])
    if amount >= 500_000:
        score += 30; reasons.append('High-value payment')
    if payment.get('ip_country', 'IN') != payment.get('billing_country', 'IN'):
        score += 25; reasons.append('Payer country differs from billing country')
    if payment.get('account_age_hours', 1000) < 24 and amount > 20_000:
        score += 25; reasons.append('New account with a large payment')
    email = str(payment.get('email', '')).casefold()
    if email.split('@')[-1] in {'mailinator.com', 'tempmail.com', '10minutemail.com'}:
        score += 25; reasons.append('Disposable email domain')
    if payment.get('ip_country') in {'KP', 'IR', 'SY'}:
        score += 30; reasons.append('High-risk payer country')
    decision = 'block' if score >= 60 else 'review' if score >= 30 else 'approve'
    return {'score': score, 'decision': decision, 'reasons': reasons or ['No risk signals']}


def process_payment(payment: dict[str, Any]) -> dict[str, Any]:
    """Run the mock fraud decision; no real gateway is contacted."""
    fraud = check_fraud(payment)
    return {'status': 'succeeded' if fraud['decision'] == 'approve' else 'pending_review' if fraud['decision'] == 'review' else 'blocked_fraud', 'fraud': fraud}
