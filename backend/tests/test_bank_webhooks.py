import base64, hashlib, hmac, json
import pandas as pd

from backend.tests.conftest import signed_in_client


def _import(client):
    raw = pd.DataFrame([{'invoice_id': 'INV-1', 'customer_id': 'C1', 'customer_name': 'Customer', 'segment': 'small', 'amount': 1000, 'issue_date': '2026-10-01', 'due_date': '2026-10-20', 'status': 'open', 'received_amount': 0, 'paid_date': '', 'currency': 'INR'}]).to_csv(index=False).encode()
    response = client.post('/api/import', json={'filename': 'invoices.csv', 'content_base64': base64.b64encode(raw).decode(), 'name': 'Test', 'as_of': '2026-10-24', 'opening_cash': 0, 'safety_floor': 0})
    assert response.status_code == 200, response.text


def _webhook(client, event):
    body = json.dumps(event).encode()
    signature = hmac.new(b'local-mock-bank-secret', body, hashlib.sha256).hexdigest()
    return client.post('/api/webhooks/bank', content=body, headers={'X-Signature': signature})


def test_signed_credit_is_idempotent_and_stores_fraud_result():
    client = signed_in_client(); _import(client)
    account = client.get('/api/payments/mock-bank-account').json()['merchant_account']
    event = {'event_id': 'bank-1', 'type': 'credit', 'amount': 1000, 'merchant_account': account, 'reference': 'Payment INV-1', 'counterparty_account': 'payer-1', 'counterparty_name': 'Payer', 'counterparty_country': 'IN'}
    assert _webhook(client, event).json()['result'] == 'paid'
    assert _webhook(client, event).json()['result'] == 'duplicate_event_ignored'
    payments = client.get('/api/admin/payments').json()
    assert payments[0]['decision'] == 'approve' and payments[0]['fraud_reasons'] == ['No risk signals']
    assert client.get('/api/ledger').json()['invoices'][0]['ledger_status'] == 'received'


def test_review_credit_does_not_settle_invoice():
    client = signed_in_client(); _import(client)
    account = client.get('/api/payments/mock-bank-account').json()['merchant_account']
    event = {'event_id': 'bank-2', 'type': 'credit', 'amount': 1000, 'merchant_account': account, 'reference': 'INV-1', 'counterparty_account': 'payer-2', 'counterparty_country': 'IR'}
    assert _webhook(client, event).json()['result'] == 'pending_review'
    assert client.get('/api/ledger').json()['invoices'][0]['ledger_status'] != 'received'
