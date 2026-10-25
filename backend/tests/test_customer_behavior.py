from copy import deepcopy
from datetime import date

from backend import ledger
from backend.tests.conftest import signed_in_client
from backend.tests.test_ledger_api import payload
from ml.tests.test_pipeline import business as training_business


def seed(client):
    business = training_business()
    business.update(name='Own business', opening_cash=10000, safety_floor=1000,
                    supplier_bills=[], obligations=[], sales_plan=dict(monthly_amount=0), data_source='imported')
    business['customers'][0]['name'] = 'Own customer'
    ledger.save_business(business, client.business_id)
    return business


def test_cold_start_is_honest_and_censoring_is_preserved(client):
    client.post('/api/import', json=payload())
    response = client.get('/api/customers')
    assert response.status_code == 200, response.text
    data = response.json()
    assert data['model']['status'] == 'insufficient_history'
    assert data['model']['paid_count'] == 1
    assert data['model']['censored_count'] == 1
    partly_paid = next(c for c in data['customers'] if c['id'] == 'C1')
    assert partly_paid['paid_count'] == 0
    assert partly_paid['median_delay'] is None
    assert partly_paid['invoices'][0]['outstanding'] == 800
    assert partly_paid['invoices'][0]['paid_by_70'] is None
    forecast = client.get('/api/forecast?delay_model=survival').json()
    assert forecast['meta']['delay_model_used'] == 'empirical'
    assert forecast['meta']['model_training_source'] == 'this_business'


def test_private_model_is_reused_and_retrained_after_payment(client, monkeypatch):
    from ml import personalization
    fits = []
    original = personalization.DelayModel
    def track(table):
        fits.append(len(table))
        return original(table)
    monkeypatch.setattr(personalization, 'DelayModel', track)
    business = seed(client)
    first = client.get('/api/customers').json()
    assert first['model']['status'] == 'ready', first
    assert fits == [40]
    prediction = first['customers'][0]['invoices'][0]
    assert business['as_of'] < prediction['paid_by_70'] <= prediction['paid_by_90']
    assert 0 <= prediction['probability_7_days'] <= prediction['probability_30_days'] <= prediction['probability_60_days'] <= 1
    assert client.get('/api/customers').json() == first
    # A survival forecast uses the same tenant model, not the global CSV artifact.
    forecast = client.get('/api/forecast?delay_model=survival').json()
    assert forecast['meta']['delay_model_used'] == 'survival'
    assert forecast['meta']['payment_model']['fingerprint'] == first['model']['fingerprint']
    assert fits == [40]
    invoice = business['invoices'][-1]
    receipt = dict(invoice_id=invoice['id'], receipt_id='settled-now', amount=invoice['amount'], date=business['as_of'])
    assert client.post('/api/receipts', json=receipt).status_code == 200
    second = client.get('/api/customers').json()
    assert second['model']['paid_count'] == 40
    assert second['model']['fingerprint'] != first['model']['fingerprint']
    assert fits == [40, 40]
    manual = client.post('/api/customers/retrain', json={})
    assert manual.status_code == 200
    assert fits == [40, 40, 40]


def test_business_isolation_with_same_customer_ids(client):
    first_business = seed(client)
    first = client.get('/api/customers').json()
    other = signed_in_client('other-owner@example.com')
    assert other.get('/api/customers').json()['customers'] == []
    changed = deepcopy(first_business)
    changed['customers'][0]['name'] = 'Other customer'
    changed['invoices'][0]['paid_date'] = '2020-01-20'
    ledger.save_business(changed, other.business_id)
    second = other.get('/api/customers').json()
    assert second['customers'][0]['name'] == 'Other customer'
    assert second['model']['fingerprint'] != first['model']['fingerprint']
    assert client.get('/api/customers').json() == first


def test_new_customer_uses_segment_fallback(client):
    business = seed(client)
    business['customers'].append(dict(id='new', name='New customer', segment='small'))
    business['invoices'].append(dict(id='new-invoice', customer_id='new', amount=500,
        issue_date='2021-02-01', due_date='2021-02-20', status='open', paid_date=None))
    ledger.save_business(business, client.business_id)
    data = client.get('/api/customers').json()
    new = next(c for c in data['customers'] if c['id'] == 'new')
    assert new['prediction_basis'] == 'segment_fallback'
    assert new['paid_count'] == 0
    assert new['median_delay'] is None
    assert new['invoices'][0]['paid_by_70'] is not None
