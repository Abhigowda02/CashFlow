"""Tenant-scoped UI-ready forecast endpoint."""
from __future__ import annotations

from datetime import date, datetime, timezone
from fastapi import APIRouter, Depends, HTTPException

from backend import auth, clock, ledger
from backend.modules.forecast_view_builder import build_headline, build_why

router = APIRouter(prefix='/api/forecast', tags=['forecast'])

@router.get('/view')
def view(user: auth.Account = Depends(auth.require_user)):
    """Return a derived forecast view; reads only the signed-in business."""
    business = ledger.load_business(user.business_id)
    if business is None:
        raise HTTPException(409, 'Complete business setup first')
    from engine import run_forecast
    forecast = run_forecast(ledger.forecast_business(business, user.business_id))
    cash_updated = business.get('cash_updated_on') or business.get('as_of')
    stale = clock.is_stale(cash_updated, 3)
    try:
        stale = stale or date.fromisoformat(str(cash_updated).split('T')[0]) < clock.today_ist()
    except (TypeError, ValueError):
        stale = True
    obligations = business.get('obligations', [])
    names = {item['id']: item.get('name', item['id']) for item in business.get('customers', [])}
    invoices = []
    for invoice in business.get('invoices', []):
        if invoice.get('status') != 'open': continue
        invoices.append({'id': invoice['id'], 'customer_id': invoice.get('customer_id'), 'customer_name': names.get(invoice.get('customer_id'), invoice.get('customer_id')), 'amount': invoice['amount'] - invoice.get('received_amount', 0), 'due_date': invoice['due_date'], 'expected_date': invoice['due_date'], 'spread_days': 0})
    warnings = []
    if stale: warnings.append('Your balance is stale. Update it before relying on this estimate.')
    missing_expenses = not obligations
    if missing_expenses: warnings.append('No recurring expenses are recorded; this forecast only shows receipts.')
    return {**forecast, 'headline': build_headline(forecast['shortage_prob'], forecast['first_shortage_date'], max(0, business.get('safety_floor', 0) - forecast['min_balance_p50']), stale, missing_expenses), 'as_of': clock.today_ist().isoformat(), 'cash_last_updated': cash_updated, 'stale': stale, 'why': build_why(invoices, obligations, forecast, clock.today_ist().isoformat()), 'warnings': warnings, 'generated_at': datetime.now(timezone.utc).isoformat(), 'accuracy': None}
