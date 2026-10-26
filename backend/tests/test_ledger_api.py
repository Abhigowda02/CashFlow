import base64
import io

from fastapi.testclient import TestClient
import pandas as pd
import pytest

from backend import ledger
from backend.main import app, current_business


def payload(extension='csv'):
    rows = pd.DataFrame([
        dict(invoice_id='I1', customer_id='C1', customer_name='Customer A', segment='small',
             amount=1000, issue_date='2026-09-01', due_date='2026-10-01', status='open', received_amount=200, paid_date='', currency='INR'),
        dict(invoice_id='I2', customer_id='C2', customer_name='Customer B', segment='corporate',
             amount=500, issue_date='2026-08-01', due_date='2026-08-15', status='paid', received_amount=500, paid_date='2026-09-01', currency='INR')])
    if extension == 'xlsx':
        out = io.BytesIO()
        rows.to_excel(out, index=False)
        content = out.getvalue()
    else:
        content = rows.to_csv(index=False).encode()
    return dict(filename=f'invoices.{extension}', content_base64=base64.b64encode(content).decode(),
                name='Test business', as_of='2026-10-24', opening_cash=10000, safety_floor=1000)


@pytest.mark.parametrize('extension', ['csv', 'xlsx'])
def test_import_and_persistence(client, extension):
    response = client.post('/api/import', json=payload(extension))
    assert response.status_code == 200, response.text
    business = client.get('/api/business').json()
    assert business['data_source'] == 'imported'
    assert business['opening_cash'] == 10000  # Historical receipts are already included.
    assert ledger.load_business(client.business_id)['name'] == 'Test business'
    summary = client.get('/api/ledger').json()
    assert summary['outstanding'] == 800
    assert summary['received'] == 700
    assert summary['receivable_aging']['0–30'] == 800
    assert summary['invoices'][0]['ledger_status'] == 'partly paid'
    assert ledger.forecast_business(business)['invoices'][0]['amount'] == 800
    assert business['invoices'][0]['amount'] == 1000
    assert summary['concentration'][0]['share'] == 1


def test_import_accepts_common_export_headers_and_contact_fields(client):
    rows = pd.DataFrame([dict(**{'Invoice No': 'V-1', 'Party Name': 'Vendor Customer', 'Invoice Date': '2026-09-01',
                                  'Due Date': '2026-10-01', 'Invoice Amount': 1000, 'Email Address': 'vendor@example.com',
                                  'Mobile Number': '+919876543210'})])
    raw = rows.to_csv(index=False).encode()
    response = client.post('/api/import', json=dict(filename='export.csv', content_base64=base64.b64encode(raw).decode(),
        name='Test business', as_of='2026-10-24', opening_cash=0, safety_floor=0, declared_currency='INR'))
    assert response.status_code == 200, response.text
    customer = ledger.load_business(client.business_id)['customers'][0]
    assert customer['email'] == 'vendor@example.com' and customer['phone'] == '+919876543210'


def test_receipts_are_idempotent_and_update_cash(client):
    assert client.post('/api/import', json=payload()).status_code == 200
    receipt = dict(invoice_id='I1', receipt_id='unique-payment', amount=300, date='2026-10-24')
    first = client.post('/api/receipts', json=receipt)
    assert first.status_code == 200, first.text
    assert first.json()['outstanding'] == 500
    assert client.post('/api/receipts', json=receipt).status_code == 200
    assert current_business(client.business_id)['opening_cash'] == 10300
    assert client.post('/api/receipts', json=dict(receipt, amount=301)).status_code == 400
    assert client.post('/api/receipts', json=dict(receipt, receipt_id='overpay', amount=501)).status_code == 400
    last = client.post('/api/receipts', json=dict(receipt, receipt_id='final', amount=500))
    assert last.status_code == 200
    assert last.json()['invoices'][0]['ledger_status'] == 'received'
    assert current_business(client.business_id)['opening_cash'] == 10800
    assert current_business(client.business_id)['invoices'][0]['paid_date'] == '2026-10-24'
    # Settled invoices must not be forecast again.
    forecast = client.get('/api/forecast').json()
    assert forecast['p50'] == [10800] * 90


def test_invalid_import_does_not_replace_workspace(client):
    client.post('/api/import', json=payload())
    invalid = payload()
    invalid['content_base64'] = base64.b64encode(b'wrong,columns\n1,2\n').decode()
    assert client.post('/api/import', json=invalid).status_code == 400
    assert current_business(client.business_id)['name'] == 'Test business'
    bad = payload()
    bad['opening_cash'] = -10
    assert client.post('/api/import', json=bad).status_code == 422


def test_model_selection_and_real_fallback(client, monkeypatch):
    client.post('/api/import', json=payload())
    response = client.get('/api/forecast?delay_model=empirical')
    assert response.status_code == 200
    assert response.json()['meta']['data_source'] == 'imported'
    assert response.json()['meta']['delay_model_used'] == 'empirical'
    assert client.get('/api/forecast?delay_model=invalid').status_code == 422
    from ml import delay_model
    def unavailable(*args, **kwargs):
        raise ValueError('Unavailable model')
    monkeypatch.setattr(delay_model, 'fit', unavailable)
    response = client.get('/api/forecast?delay_model=survival')
    assert response.json()['meta']['delay_model_requested'] == 'survival'
    assert response.json()['meta']['delay_model_used'] == 'empirical'
    scenario = client.post('/api/scenario?delay_model=survival', json={
        'name': 'Expense', 'changes': [{'type': 'extra_expense', 'amount': 100, 'date': '2026-10-24'}]})
    assert scenario.status_code == 200
    assert scenario.json()['scenario']['p50'][0] == scenario.json()['baseline']['p50'][0] - 100


def test_foreign_currency_is_not_silently_converted(client):
    request = payload()
    csv = base64.b64decode(request['content_base64']).decode().replace('INR', 'USD')
    request['content_base64'] = base64.b64encode(csv.encode()).decode()
    response = client.post('/api/import', json=request)
    assert response.status_code == 400
    assert ledger.load_business(client.business_id)['invoices'] == []


def test_plan_survives_reload_and_preserves_receipts(client):
    client.post('/api/import', json=payload())
    receipt = dict(invoice_id='I1', receipt_id='one', amount=800, date='2026-10-24')
    client.post('/api/receipts', json=receipt)
    plan = dict(as_of='2026-10-24', obligations=[dict(id='rent', name='Rent', amount=100, day_of_month=31)],
                supplier_bills=[], monthly_sales=0, terms_days=0, monthly_noise_pct=0)
    assert client.post('/api/plan', json=plan).status_code == 200
    assert ledger.load_business(client.business_id)['obligations'][0]['name'] == 'Rent'
    assert ledger.load_business(client.business_id)['sales_plan']['terms_days'] == 0
    assert client.post('/api/receipts', json=receipt).status_code == 200
    assert current_business(client.business_id)['opening_cash'] == 10800
    # Monthly day 31 must also trigger on November 30.
    forecast = client.get('/api/forecast').json()
    november_30 = forecast['dates'].index('2026-11-30')
    assert forecast['p50'][november_30 - 1] - forecast['p50'][november_30] == 100
    assert client.post('/api/plan', json=dict(plan, as_of='2026-09-01')).status_code == 400


def test_invalid_plan_is_atomic(client):
    client.post('/api/import', json=payload())
    bill = dict(id='b', supplier='Supplier', amount=500, due_date='2026-11-01')
    plan = dict(obligations=[], supplier_bills=[bill, bill], monthly_sales=0, terms_days=30, monthly_noise_pct=0)
    assert client.post('/api/plan', json=plan).status_code == 400
    assert current_business(client.business_id)['supplier_bills'] == []
