"""Signed mock-bank webhooks and owner payment-review API."""
from __future__ import annotations
import hashlib, hmac, json, os
from datetime import datetime, timezone
from uuid import uuid4
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy import insert, select, update
from sqlalchemy.exc import IntegrityError
from backend import auth, database as db, ledger
from backend.modules.fraud_gateway import process_payment

router = APIRouter(prefix='/api', tags=['mock-bank'])
SECRET = os.environ.get('BANK_WEBHOOK_SECRET', 'local-mock-bank-secret')

def _now() -> str: return datetime.now(timezone.utc).isoformat()
def _signature(body: bytes) -> str: return hmac.new(SECRET.encode(), body, hashlib.sha256).hexdigest()
def _account(business_id: str) -> str:
    with db.transaction() as conn:
        value = conn.execute(select(db.merchant_accounts.c.account).where(db.merchant_accounts.c.business_id == business_id)).scalar()
        if value: return value
        value = 'mock_' + uuid4().hex
        conn.execute(insert(db.merchant_accounts).values(account=value, business_id=business_id))
        return value

@router.get('/payments/mock-bank-account')
def mock_account(user: auth.Account = Depends(auth.require_user)): return {'merchant_account': _account(user.business_id), 'mode': 'mock'}

@router.post('/webhooks/bank')
async def webhook(request: Request, x_signature: str | None = Header(None)):
    body = await request.body()
    if not hmac.compare_digest(_signature(body), x_signature or ''): raise HTTPException(401, 'Invalid webhook signature')
    try: event = json.loads(body)
    except json.JSONDecodeError as error: raise HTTPException(400, 'Webhook body must be JSON') from error
    required = {'event_id', 'type', 'amount', 'merchant_account'}
    if not required <= set(event) or not isinstance(event['amount'], int) or event['amount'] <= 0: raise HTTPException(400, 'Invalid bank event')
    with db.engine().connect() as conn:
        business_id = conn.execute(select(db.merchant_accounts.c.business_id).where(db.merchant_accounts.c.account == event['merchant_account'])).scalar()
    if not business_id: raise HTTPException(404, 'Unknown merchant account')
    try:
        with db.transaction() as conn:
            conn.execute(insert(db.bank_events).values(business_id=business_id, event_id=event['event_id'], payload=json.dumps(event), created_at=_now()))
    except IntegrityError: return {'result': 'duplicate_event_ignored'}
    if event['type'] == 'debit': return _debit(business_id, event)
    if event['type'] == 'credit': return _credit(business_id, event)
    return {'result': 'ignored_unknown_type'}

def _credit(business_id: str, event: dict) -> dict:
    business = ledger.load_business(business_id); reference = str(event.get('reference', '')).casefold()
    invoice = next((item for item in business['invoices'] if item['id'].casefold() in reference), None)
    payer = str(event.get('counterparty_account', 'unknown'))
    customer = next((c for c in business['customers'] if invoice and c['id'] == invoice['customer_id']), {})
    payment = process_payment({'user_id': payer, 'amount': event['amount'], 'card_number': payer,
        'email': event.get('payer_email', 'unknown@example.com'), 'ip_country': event.get('counterparty_country', 'IN'),
        'billing_country': customer.get('country', 'IN'), 'device_id': 'bank-transfer', 'account_age_hours': event.get('account_age_hours', 1000)})
    fraud, decision = payment['fraud'], payment['fraud']['decision']; status = payment['status']
    payment_id = 'pay_' + uuid4().hex[:12]
    with db.transaction() as conn:
        conn.execute(insert(db.payments).values(business_id=business_id, id=payment_id, event_id=event['event_id'], invoice_id=invoice['id'] if invoice else None, amount=event['amount'], decision=decision, status=status, fraud_score=int(fraud['score']), fraud_reasons=json.dumps(fraud['reasons']), payer_name=event.get('counterparty_name'), created_at=_now(), reviewed_at=None))
    if not invoice: return {'result': 'unmatched_credit', 'payment_id': payment_id, 'fraud': fraud}
    if decision == 'approve' and event['amount'] == invoice['amount'] - invoice.get('received_amount', 0):
        ledger.record_receipt(business, invoice['id'], event['amount'], event.get('date', business['as_of']), event['event_id'], business_id)
        return {'result': 'paid', 'payment_id': payment_id, 'fraud': fraud}
    invoice['status'] = 'pending_review' if decision == 'review' else 'flagged_fraud' if decision == 'block' else 'amount_mismatch'
    ledger.save_workspace_payload(business, business_id)
    return {'result': invoice['status'], 'payment_id': payment_id, 'fraud': fraud}

def _debit(business_id: str, event: dict) -> dict:
    business = ledger.load_business(business_id); obligation = {'id': 'bank_' + event['event_id'], 'name': event.get('counterparty_name', 'Bank debit'), 'amount': event['amount'], 'day_of_month': 1, 'frequency': 'monthly', 'category': 'other', 'status': 'flagged_obligation', 'description': event.get('description', '')}
    business.setdefault('bank_obligations', []).append(obligation); ledger.save_workspace_payload(business, business_id)
    return {'result': 'flagged_obligation', 'obligation': obligation}

@router.get('/admin/payments')
def payment_admin(user: auth.Account = Depends(auth.require_user)):
    with db.engine().connect() as conn: rows = conn.execute(select(db.payments).where(db.payments.c.business_id == user.business_id).order_by(db.payments.c.created_at.desc())).mappings().all()
    return [{**dict(row), 'fraud_reasons': json.loads(row['fraud_reasons'])} for row in rows]

@router.post('/admin/payments/{payment_id}/review/{action}')
def review_payment(payment_id: str, action: str, user: auth.Account = Depends(auth.require_user)):
    if action not in {'approve', 'reject'}: raise HTTPException(400, 'Action must be approve or reject')
    with db.transaction() as conn:
        payment = conn.execute(select(db.payments).where(db.payments.c.business_id == user.business_id, db.payments.c.id == payment_id).with_for_update()).mappings().first()
        if not payment or payment['status'] != 'pending_review': raise HTTPException(404, 'Payment is not pending review')
        event = conn.execute(select(db.bank_events.c.payload).where(db.bank_events.c.business_id == user.business_id, db.bank_events.c.event_id == payment['event_id'])).scalar_one()
        conn.execute(update(db.payments).where(db.payments.c.business_id == user.business_id, db.payments.c.id == payment_id).values(status='succeeded' if action == 'approve' else 'rejected_by_reviewer', reviewed_at=_now()))
    business = ledger.load_business(user.business_id); invoice = next((item for item in business['invoices'] if item['id'] == payment['invoice_id']), None)
    if invoice is None: raise HTTPException(400, 'Matched invoice no longer exists')
    if action == 'approve':
        ledger.record_receipt(business, invoice['id'], payment['amount'], json.loads(event).get('date', business['as_of']), payment['event_id'], user.business_id)
    else:
        invoice['status'] = 'rejected'; ledger.save_workspace_payload(business, user.business_id)
    return {'status': 'paid' if action == 'approve' else 'rejected'}
