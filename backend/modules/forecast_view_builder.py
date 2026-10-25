"""Pure helpers that turn a forecast into concise, honest UI-ready JSON."""
from __future__ import annotations
from datetime import date
from typing import Any

def format_inr(value: int | float) -> str:
    sign = '-' if value < 0 else ''; digits = str(abs(int(round(value))))
    if len(digits) > 3:
        tail, head = digits[-3:], digits[:-3]; groups=[]
        while head: groups.insert(0, head[-2:]); head=head[:-2]
        digits = ','.join(groups + [tail])
    return f'{sign}Rs {digits}'

def compact_inr(value: int | float) -> str:
    amount=abs(float(value)); sign='-' if value < 0 else ''
    if amount >= 10_000_000: return f'{sign}Rs {amount/10_000_000:.1f}Cr'
    if amount >= 100_000: return f'{sign}Rs {amount/100_000:.1f}L'
    return format_inr(value)

def build_headline(shortage_prob: float, first_shortage_date: str | None, shortfall_amount: int, stale: bool, missing_expenses: bool, horizon_days: int=90) -> str:
    """Return an honest forecast headline from scalar forecast inputs."""
    if stale: return 'Your balance is old. Update it before relying on this cash forecast.'
    if missing_expenses: return 'This forecast only shows expected receipts; add expenses for a complete estimate.'
    risk=round(shortage_prob*100)
    if shortage_prob < .1: return f'No cash shortage expected in the next {horizon_days} days ({risk}% risk)'
    when=(lambda parsed: f'{parsed.day} {parsed.strftime("%b")}')(date.fromisoformat(first_shortage_date)) if first_shortage_date else 'within the forecast period'
    return f'Likely short by {compact_inr(abs(shortfall_amount))} around {when} ({risk}% chance)'

def risk_label(prob_late: float) -> str:
    """Classify a late-payment probability without implying certainty."""
    return 'high' if prob_late >= .6 else 'medium' if prob_late >= .3 else 'low'

def build_why(invoice_forecasts: list[dict[str, Any]], obligations: list[dict[str, Any]], forecast: dict[str, Any], today: str, limit: int=5) -> list[dict[str, Any]]:
    """Rank invoice and obligation drivers by INR impact for display."""
    payroll = next((x for x in obligations if 'payroll' in str(x.get('name','')).casefold()), None)
    rows=[]
    for inv in invoice_forecasts:
        amount=int(inv.get('amount',0)); expected=inv.get('expected_date') or inv.get('due_date')
        customer=inv.get('customer_name') or inv.get('customer_id') or 'Customer'
        text=f"{customer}'s {compact_inr(amount)} is expected around {expected}"
        if payroll: text += f", but {payroll.get('name','payroll')} is due {payroll.get('next_due_date', payroll.get('due_date','soon'))}."
        rows.append({'type':'late_invoice','ref':inv.get('id',''),'text':text,'amount':amount,'expected_date':expected,'spread_days':int(inv.get('spread_days',0))})
    for obligation in obligations:
        amount=int(obligation.get('amount',0)); due=obligation.get('next_due_date') or obligation.get('due_date')
        rows.append({'type':'obligation','ref':obligation.get('id',''),'text':f"{obligation.get('name','Expense')} of {compact_inr(amount)} is due {due}.",'amount':amount,'expected_date':due,'spread_days':0})
    return sorted(rows,key=lambda row:row['amount'],reverse=True)[:limit]
