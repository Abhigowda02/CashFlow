from backend import ledger
from backend.tests.conftest import signed_in_client
from backend.tests.test_ledger_api import payload


def context(**overrides):
    return dict(dict(customer_id='C1', importance='strategic', repeat_customer=True,
                     service_issue='open', disputed_invoice_ids=['I1'], notes='Resolve delivery complaint first'), **overrides)


def test_owner_context_and_ranking_use_outstanding_cash_only(client):
    client.post('/api/import', json=payload())
    original = client.get('/api/collections').json()
    assert len(original['customers']) == 1  # Paid I2 is excluded.
    assert original['customers'][0]['overdue_amount'] == 800
    assert original['customers'][0]['guidance']['sensitivity'] == 'unknown'
    fingerprint = client.get('/api/customers').json()['model']['fingerprint']
    saved = client.post('/api/customer-context', json=context())
    assert saved.status_code == 200, saved.text
    assert ledger.load_business(client.business_id)['customers'][0]['collection_context']['notes'] == context()['notes']
    profiles = client.get('/api/customers').json()
    assert profiles['model']['fingerprint'] == fingerprint  # Context is not an ML feature.
    assert profiles['customers'][0]['collection_context']['importance'] == 'strategic'
    ranking = client.get('/api/collections').json()
    assert ranking['customers'][0]['guidance']['approach'] == 'Resolve issue, then agree payment'
    for key in ['expected_gap_reduction', 'probability_reduction_pp', 'runway_days_gained']:
        assert ranking['customers'][0][key] == original['customers'][0][key]
    assert client.get('/api/business').json()['opening_cash'] == 10000


def test_context_is_tenant_scoped_and_disputes_are_validated(client):
    client.post('/api/import', json=payload())
    other = signed_in_client('other@example.com')
    assert other.post('/api/customer-context', json=context()).status_code == 400
    assert client.post('/api/customer-context', json=context(disputed_invoice_ids=['I2'])).status_code == 400
    assert client.post('/api/customer-context', json=context(importance='invalid')).status_code == 422
    assert client.get('/api/collections?acceleration_days=0').status_code == 422
    assert client.post('/api/customer-context', json=context()).status_code == 200
    assert other.get('/api/collections').json()['customers'] == []
    other.post('/api/import', json=payload())
    other_row = other.get('/api/collections').json()['customers'][0]
    assert other_row['guidance']['sensitivity'] == 'unknown'
    assert other_row['collection_context'] is None
