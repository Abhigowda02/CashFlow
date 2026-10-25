from copy import deepcopy
import json

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import select, update

from backend import database as db, demo, ledger
from backend.main import app
from backend.tests.conftest import signed_in_client
from backend.tests.test_ledger_api import payload


def load(client, *, reset=False):
    return client.post('/api/demo', json=dict(confirm=True, reset=reset))


def test_explicit_demo_load_reuses_complete_existing_fixture():
    client = signed_in_client(onboard=False)
    assert client.get('/api/auth/me').json()['onboarding_required'] is True
    response = load(client)
    assert response.status_code == 200, response.text
    assert response.json() == dict(loaded=True, data_source='synthetic_demo', onboarding_required=False)
    assert response.headers['cache-control'] == 'no-store'
    assert client.get('/api/auth/me').json()['onboarding_required'] is False
    business = client.get('/api/business').json()
    fixture = demo.fixture_business()
    assert business == fixture
    assert business['data_source'] == 'synthetic_demo'
    assert business['currency'] == 'INR'
    assert business['opening_cash'] == 100000 and business['safety_floor'] == 50000
    assert len(business['invoices']) == 42 and len(business['customers']) == 6
    assert len(business['obligations']) == 4 and len(business['supplier_bills']) == 2
    assert business['sales_plan']['monthly_amount'] == 300000
    assert all(row['frequency'] == 'monthly' for row in business['obligations'])
    assert sum(0 < row['received_amount'] < row['amount'] for row in business['invoices']) == 2
    assert client.get('/api/forecast').json()['meta']['data_source'] == 'synthetic_demo'
    scenario = client.post('/api/scenario', json=dict(name='Demo stress', changes=[
        dict(type='extra_expense', amount=1000, date=business['as_of'])]))
    assert scenario.status_code == 200, scenario.text
    assert all(row['meta']['data_source'] == 'synthetic_demo' for row in scenario.json().values())


@pytest.mark.parametrize('body', [{}, {'confirm': False}, {'confirm': 'true'}, {'confirm': 1},
    {'confirm': True, 'reset': 'true'}, {'confirm': True, 'business_id': 'another-business'}])
def test_demo_requires_explicit_valid_confirmation(body):
    client = signed_in_client(onboard=False)
    assert client.post('/api/demo', json=body).status_code == 422
    assert client.get('/api/auth/me').json()['onboarding_required'] is True


@pytest.mark.parametrize('kind', ['owner_empty', 'cash_only', 'imported', 'name_spoof'])
@pytest.mark.parametrize('reset', [False, True])
def test_demo_never_overwrites_an_onboarded_non_demo_workspace(kind, reset):
    client = signed_in_client()
    if kind in ('imported', 'name_spoof'):
        request = payload()
        if kind == 'name_spoof':
            request['name'] = 'Demo business (Synthetic)'
        assert client.post('/api/import', json=request).status_code == 200
    elif kind == 'cash_only':
        business = ledger.load_business(client.business_id)
        business['opening_cash'] = 12345
        ledger.save_business(business, client.business_id)
    before = deepcopy(client.get('/api/business').json())
    assert load(client, reset=reset).status_code == 409
    assert client.get('/api/business').json() == before


def test_reset_requires_a_loaded_demo_and_confirmation():
    client = signed_in_client(onboard=False)
    assert load(client, reset=True).status_code == 409
    assert load(client).status_code == 200
    original = client.get('/api/business').json()
    # A repeated generic load cannot discard changes made during the demo.
    assert client.post('/api/receipts', json=dict(invoice_id='DEMO-O-003', receipt_id='demo-receipt',
        amount=1000, date=original['as_of'])).status_code == 200
    assert client.post('/api/scenarios', json=dict(name='Saved demo experiment', changes=[
        dict(type='extra_expense', amount=1000, date=original['as_of'])])).status_code == 201
    modified = client.get('/api/business').json()
    assert modified['opening_cash'] == original['opening_cash']+1000
    assert load(client).status_code == 409
    assert client.get('/api/business').json() == modified
    assert load(client, reset=True).status_code == 200
    assert client.get('/api/business').json() == original
    assert client.get('/api/scenarios').json() == []
    with db.engine().connect() as connection:
        assert not connection.execute(select(db.receipts).where(db.receipts.c.business_id == client.business_id)).all()


def test_demo_actions_are_tenant_scoped():
    demo_client = signed_in_client('demo@example.com', onboard=False)
    owner = signed_in_client('business@example.com')
    assert owner.post('/api/import', json=payload()).status_code == 200
    before = owner.get('/api/business').json()
    assert load(demo_client).status_code == 200
    assert owner.get('/api/business').json() == before
    assert load(demo_client, reset=True).status_code == 200
    assert owner.get('/api/business').json() == before
    assert owner.get('/api/ledger').json()['outstanding'] == 800


def test_importing_owner_data_into_demo_removes_reset_permission():
    client = signed_in_client(onboard=False)
    assert load(client).status_code == 200
    assert client.post('/api/import', json=payload()).status_code == 200
    imported = client.get('/api/business').json()
    assert imported['data_source'] == 'imported'
    assert 'demo_fixture' not in imported
    assert load(client, reset=True).status_code == 409
    assert client.get('/api/business').json() == imported


def test_demo_requires_session_csrf_and_trusted_origin():
    anonymous = TestClient(app, headers={'Origin': 'http://localhost:5173'})
    assert load(anonymous).status_code == 401
    client = signed_in_client(onboard=False)
    csrf = client.headers.pop('X-CSRF-Token')
    assert load(client).status_code == 403
    client.headers['X-CSRF-Token'] = csrf
    client.headers['Origin'] = 'https://attacker.example'
    assert load(client).status_code == 403
    assert client.get('/api/auth/me').json()['onboarding_required'] is True


def test_demo_cannot_replace_dirty_unonboarded_payload():
    client = signed_in_client(onboard=False)
    with db.transaction() as connection:
        connection.execute(update(db.workspaces).where(db.workspaces.c.id == client.business_id)
            .values(payload=json.dumps(dict(opening_cash=12345))))
    assert load(client).status_code == 409
    with db.engine().connect() as connection:
        assert connection.execute(select(db.workspaces.c.payload).where(db.workspaces.c.id == client.business_id)).scalar_one() == json.dumps(dict(opening_cash=12345))


def test_missing_demo_fixture_does_not_onboard_or_mutate_workspace(monkeypatch, tmp_path):
    client = signed_in_client(onboard=False)
    monkeypatch.setattr(demo, 'EXAMPLES', tmp_path)
    response = load(client)
    assert response.status_code == 503
    assert 'unavailable' in response.json()['detail']
    assert client.get('/api/auth/me').json()['onboarding_required'] is True
