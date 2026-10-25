from copy import deepcopy
from datetime import datetime
from types import SimpleNamespace

from fastapi.testclient import TestClient
import pytest

from backend import ledger, main
from backend.main import app
from backend.tests.conftest import signed_in_client
from backend.tests.test_ledger_api import payload


@pytest.fixture
def imported(client):
    assert client.post('/api/import', json=payload()).status_code == 200
    return client


def expense(amount=100, date='2026-10-24'):
    return dict(type='extra_expense', amount=amount, date=date)


def definition(changes=None, name='Cash buffer plan'):
    return dict(name=name, changes=[expense()] if changes is None else changes)


def plan_settings(monthly_sales=1000, supplier_bills=None):
    bills = [dict(id='B1', supplier='Supplier', amount=500, due_date='2026-11-01', status='open')]
    return dict(obligations=[], supplier_bills=bills if supplier_bills is None else supplier_bills,
                monthly_sales=monthly_sales, terms_days=30, monthly_noise_pct=0)


@pytest.fixture
def planned(imported):
    assert imported.post('/api/plan', json=plan_settings()).status_code == 200
    return imported


def test_library_round_trip_stores_only_definitions(client, monkeypatch):
    def no_forecast():
        raise AssertionError('Saving or listing definitions must not run a forecast')
    monkeypatch.setattr(main, 'load_engine', no_forecast)
    assert client.post('/api/plan', json=plan_settings()).status_code == 200
    original = client.get('/api/business').json()
    assert client.get('/api/scenarios').json() == []
    request = definition([expense(), dict(type='sales_change', pct=-20),
                          dict(type='supplier_terms', extra_days=15)], name='  Winter plan  ')
    response = client.post('/api/scenarios', json=request)
    assert response.status_code == 201, response.text
    saved = response.json()
    assert set(saved) == {'id', 'name', 'changes', 'created_at', 'updated_at'}
    assert saved['name'] == 'Winter plan'
    assert saved['changes'] == request['changes']
    assert datetime.fromisoformat(saved['created_at']).tzinfo is not None
    assert saved['created_at'] == saved['updated_at']
    assert response.headers['cache-control'] == 'no-store'
    assert client.get('/api/scenarios').json() == [saved]
    assert client.get('/api/business').json() == original

    # A fresh authenticated client reads the database, without relying on browser state.
    reloaded = TestClient(app, headers={'Origin': 'http://localhost:5173'})
    response = reloaded.post('/api/auth/login', json={
        'email': 'owner@example.com', 'password': 'Cash!7'})
    assert response.status_code == 200
    assert reloaded.get('/api/scenarios').json() == [saved]
    deleted = client.delete('/api/scenarios/' + saved['id'])
    assert deleted.status_code == 204 and deleted.content == b''
    assert reloaded.get('/api/scenarios').json() == []
    assert client.delete('/api/scenarios/' + saved['id']).status_code == 404


def test_saved_scenarios_and_customer_selection_are_tenant_scoped(imported):
    alice = imported
    request = definition([dict(type='delay_customer', customer_id='C1', extra_days=30)])
    saved = alice.post('/api/scenarios', json=request).json()
    bob = signed_in_client('bob@example.com')
    assert bob.get('/api/scenarios?business_id=' + alice.business_id).json() == []
    assert bob.post('/api/scenarios', json=request).status_code == 422
    assert bob.delete('/api/scenarios/' + saved['id']).status_code == 404
    assert alice.get('/api/scenarios').json() == [saved]
    # Identical customer IDs in separate workspaces do not grant scenario access.
    assert bob.post('/api/import', json=payload()).status_code == 200
    other = bob.post('/api/scenarios', json=request)
    assert other.status_code == 201
    assert other.json()['id'] != saved['id']
    assert len(bob.get('/api/scenarios').json()) == 1
    assert alice.delete('/api/scenarios/' + other.json()['id']).status_code == 404


def test_library_requires_authentication_and_csrf(client):
    anonymous = TestClient(app)
    assert anonymous.get('/api/scenarios').status_code == 401
    assert anonymous.post('/api/scenarios', json=definition()).status_code == 401
    assert anonymous.delete('/api/scenarios/missing').status_code == 401
    saved = client.post('/api/scenarios', json=definition()).json()
    csrf = client.headers.pop('X-CSRF-Token')
    assert client.post('/api/scenarios', json=definition()).status_code == 403
    assert client.delete('/api/scenarios/' + saved['id']).status_code == 403
    client.headers['X-CSRF-Token'] = csrf
    client.headers['Origin'] = 'https://attacker.example'
    assert client.post('/api/scenarios', json=definition()).status_code == 403
    assert client.delete('/api/scenarios/' + saved['id']).status_code == 403
    assert client.get('/api/scenarios').json() == [saved]


@pytest.mark.parametrize('changes', [
    [dict(type='delay_customer', extra_days=30)],
    [dict(type='delay_customer', customer_id='missing', extra_days=30)],
    [dict(type='delay_customer', customer_id='C2', extra_days=30)],
    [dict(type='delay_customer', customer_id='C1', extra_days=0)],
    [dict(type='delay_customer', customer_id='C1', extra_days=181)],
    [dict(type='delay_customer', customer_id='C1', extra_days=1.5)],
    [dict(type='delay_customer', customer_id='C1', extra_days=True)],
    [dict(type='delay_customer', customer_id='C1', extra_days=30),
     dict(type='delay_customer', customer_id='C1', extra_days=15)],
    [dict(type='sales_change')],
    [dict(type='sales_change', pct=-101)],
    [dict(type='sales_change', pct=101)],
    [dict(type='sales_change', pct=0)],
    [dict(type='sales_change', pct='10')],
    [dict(type='sales_change', pct=True)],
    [dict(type='sales_change', pct=10), dict(type='sales_change', pct=20)],
    [dict(type='supplier_terms')],
    [dict(type='supplier_terms', extra_days=0)],
    [dict(type='supplier_terms', extra_days=181)],
    [dict(type='supplier_terms', extra_days='15')],
    [dict(type='supplier_terms', extra_days=10), dict(type='supplier_terms', extra_days=20)],
    [dict(type='extra_expense', date='2026-10-24')],
    [dict(type='extra_expense', amount=100)],
    [expense(amount=0)],
    [expense(amount=-1)],
    [expense(amount=100.5)],
    [expense(amount='100')],
    [expense(amount=True)],
    [expense(amount=9_007_199_254_740_992)],
    [expense(amount=10 ** 400)],
    [expense(date='2026-02-30')],
    [expense(date='20261024')],
    [expense(date='2026-10-23')],
    [expense(date='2027-01-22')],
    [expense(date=1792800000)],
    [dict(type='unsupported')],
    [dict(type='sales_change', pct=10, customer_id='C1')],
    [expense()] * 21,
])
def test_invalid_definitions_rejected_before_save_or_compare(planned, monkeypatch, changes):
    def no_forecast():
        raise AssertionError('Invalid assumptions must be rejected before forecasting')
    monkeypatch.setattr(main, 'load_engine', no_forecast)
    for path in ['/api/scenarios', '/api/scenario']:
        response = planned.post(path, json=definition(changes))
        assert response.status_code == 422, response.text
    assert planned.get('/api/scenarios').json() == []


@pytest.mark.parametrize('name', ['', '   ', 'x' * 121])
def test_names_validated_for_saved_and_compared_scenarios(client, name):
    for path in ['/api/scenarios', '/api/scenario']:
        assert client.post(path, json=definition(name=name)).status_code == 422


def test_no_invoices_and_fully_received_open_invoice_are_not_eligible(imported):
    business = ledger.load_business(imported.business_id)
    business['customers'].append(dict(id='C3', name='No invoices', segment='small'))
    business['invoices'][0]['received_amount'] = business['invoices'][0]['amount']
    ledger.save_business(business, imported.business_id)
    for customer_id in ['C1', 'C3']:
        request = definition([dict(type='delay_customer', customer_id=customer_id, extra_days=30)])
        assert imported.post('/api/scenarios', json=request).status_code == 422
        assert imported.post('/api/scenario', json=request).status_code == 422


def test_bounds_and_multiple_expenses_are_valid(planned):
    for pct, days in [(-100, 1), (100, 180)]:
        request = definition([
            dict(type='delay_customer', customer_id='C1', extra_days=days),
            dict(type='sales_change', pct=pct),
            dict(type='supplier_terms', extra_days=days),
            expense(date='2026-10-24'), expense(date='2027-01-21'),
        ], name='x' * 120)
        response = planned.post('/api/scenarios', json=request)
        assert response.status_code == 201, response.text
        assert response.json()['changes'] == request['changes']
    assert planned.post('/api/scenarios', json=definition([expense()] * 20)).status_code == 201


def test_largest_safe_integer_expense_can_be_saved_and_compared(client):
    amount = 9_007_199_254_740_991
    request = definition([expense(amount=amount)])
    response = client.post('/api/scenarios', json=request)
    assert response.status_code == 201, response.text
    assert response.json()['changes'][0]['amount'] == amount
    comparison = client.post('/api/scenario', json=request)
    assert comparison.status_code == 200, comparison.text
    assert comparison.json()['scenario']['p50'][0] == -amount


@pytest.mark.parametrize('changes, settings', [
    ([dict(type='sales_change', pct=10)], plan_settings(monthly_sales=0)),
    ([dict(type='supplier_terms', extra_days=15)], plan_settings(supplier_bills=[])),
    ([dict(type='supplier_terms', extra_days=15)], plan_settings(supplier_bills=[
        dict(id='B1', supplier='Paid supplier', amount=500, due_date='2026-11-01', status='paid')])),
])
def test_sales_and_supplier_changes_require_current_exposure(client, monkeypatch, changes, settings):
    assert client.post('/api/plan', json=settings).status_code == 200
    def no_forecast():
        raise AssertionError('Changes without underlying sales or bills must be rejected before forecasting')
    monkeypatch.setattr(main, 'load_engine', no_forecast)
    for path in ['/api/scenarios', '/api/scenario']:
        response = client.post(path, json=definition(changes))
        assert response.status_code == 422, response.text
    assert client.get('/api/scenarios').json() == []


@pytest.mark.parametrize('changes, settings', [
    ([dict(type='sales_change', pct=-20)], plan_settings(monthly_sales=0)),
    ([dict(type='supplier_terms', extra_days=15)], plan_settings(supplier_bills=[])),
    ([dict(type='supplier_terms', extra_days=15)], plan_settings(supplier_bills=[
        dict(id='B1', supplier='Paid supplier', amount=500, due_date='2026-11-01', status='paid')])),
])
def test_saved_sales_and_supplier_assumptions_are_revalidated(planned, monkeypatch, changes, settings):
    request = definition(changes)
    response = planned.post('/api/scenarios', json=request)
    assert response.status_code == 201, response.text
    saved = response.json()
    assert planned.post('/api/scenario', json=request).status_code == 200
    assert planned.post('/api/plan', json=settings).status_code == 200
    def no_forecast():
        raise AssertionError('Stale sales or supplier assumptions must be rejected before forecasting')
    monkeypatch.setattr(main, 'load_engine', no_forecast)
    assert planned.post('/api/scenario', json=request).status_code == 422
    assert planned.get('/api/scenarios').json() == [saved]


def test_empty_changes_compare_baseline_but_cannot_be_saved(client):
    request = definition([])
    response = client.post('/api/scenario', json=request)
    assert response.status_code == 200, response.text
    assert response.json()['baseline'] == response.json()['scenario']
    assert client.post('/api/scenarios', json=request).status_code == 422


def test_comparison_recalculates_saved_assumptions_against_current_business(imported):
    saved = imported.post('/api/scenarios', json=definition()).json()
    request = {key: saved[key] for key in ['name', 'changes']}
    before = imported.post('/api/scenario', json=request)
    assert before.status_code == 200
    first = before.json()
    assert first['baseline']['p50'][0] - first['scenario']['p50'][0] == 100
    # Cash received after saving must be reflected when the definition is compared again.
    assert imported.post('/api/receipts', json=dict(
        invoice_id='I1', receipt_id='later-receipt', amount=800, date='2026-10-24')).status_code == 200
    after = imported.post('/api/scenario', json=request)
    assert after.status_code == 200
    second = after.json()
    assert second['baseline']['p50'][0] == 10800
    assert second['scenario']['p50'][0] == 10700
    assert imported.get('/api/scenarios').json() == [saved]


def test_customer_delay_affects_only_selected_outstanding_exposure(imported):
    business = ledger.load_business(imported.business_id)
    business['invoices'][0]['due_date'] = '2026-11-01'
    business['invoices'].append(dict(id='I3', customer_id='C2', amount=500, received_amount=0,
        issue_date='2026-10-01', due_date='2026-11-01', status='open', paid_date=None))
    ledger.save_business(business, imported.business_id)
    original = imported.get('/api/business').json()
    for customer_id, expected_remaining_cash in [('C1', 10500), ('C2', 10800)]:
        request = definition([dict(type='delay_customer', customer_id=customer_id, extra_days=180)])
        assert imported.post('/api/scenarios', json=request).status_code == 201
        response = imported.post('/api/scenario', json=request)
        assert response.status_code == 200, response.text
        comparison = response.json()
        # The selected customer's receipts fall beyond 90 days. Other receipts remain.
        assert comparison['baseline']['p50'][-1] == 11300
        assert comparison['scenario']['p50'][-1] == expected_remaining_cash
        assert imported.get('/api/business').json() == original


@pytest.mark.parametrize('delay_model', ['empirical', 'survival'])
def test_very_overdue_customer_delay_excludes_only_selected_residual_balance(imported, monkeypatch, delay_model):
    business = ledger.load_business(imported.business_id)
    business['invoices'][0].update(issue_date='2024-12-01', due_date='2025-01-01')
    business['invoices'].append(dict(id='I3', customer_id='C2', amount=500, received_amount=0,
        issue_date='2026-08-01', due_date='2026-08-15', status='open', paid_date=None))
    ledger.save_business(business, imported.business_id)
    original_business = imported.get('/api/business').json()
    original_ledger = imported.get('/api/ledger').json()

    if delay_model == 'survival':
        from ml import delay_model as payment_model
        # Force a historical estimate so the survival branch must clamp before delaying.
        monkeypatch.setattr(payment_model, 'fit', lambda _: SimpleNamespace(sample_after=lambda *args: 0))

    request = definition([dict(type='delay_customer', customer_id='C1', extra_days=180)])
    saved_response = imported.post('/api/scenarios', json=request)
    assert saved_response.status_code == 201, saved_response.text
    saved = saved_response.json()
    response = imported.post('/api/scenario?delay_model=' + delay_model, json=request)
    assert response.status_code == 200, response.text
    comparison = response.json()
    assert set(comparison) == {'baseline', 'scenario'}
    assert '_collection_diagnostics' not in response.text
    assert 'pay_days' not in response.text
    for forecast in comparison.values():
        assert forecast['meta']['delay_model_used'] == delay_model
        assert forecast['p50'][0] == 10000
    for percentile in ['p10', 'p50', 'p90']:
        # Already received INR 200 stays in cash; only the remaining INR 800 is delayed.
        assert comparison['baseline'][percentile][-1] == 11300
        assert comparison['scenario'][percentile][-1] == 10500
        assert comparison['baseline'][percentile][-1] - comparison['scenario'][percentile][-1] == 800
    assert imported.get('/api/business').json() == original_business
    assert imported.get('/api/ledger').json() == original_ledger
    assert imported.get('/api/scenarios').json() == [saved]


def test_saved_customer_delay_is_revalidated_after_receipt(imported):
    request = definition([dict(type='delay_customer', customer_id='C1', extra_days=15)])
    saved = imported.post('/api/scenarios', json=request).json()
    assert imported.post('/api/receipts', json=dict(
        invoice_id='I1', receipt_id='settled', amount=800, date='2026-10-24')).status_code == 200
    assert imported.post('/api/scenario', json=request).status_code == 422
    assert imported.get('/api/scenarios').json() == [saved]


def test_saved_expense_date_is_revalidated_after_business_date_changes(client):
    request = definition()
    saved = client.post('/api/scenarios', json=request).json()
    assert client.post('/api/plan', json=dict(as_of='2026-10-25', obligations=[], supplier_bills=[],
        monthly_sales=0, terms_days=30, monthly_noise_pct=0)).status_code == 200
    assert client.post('/api/scenario', json=request).status_code == 422
    assert client.get('/api/scenarios').json() == [saved]


def test_forecast_payloads_and_caller_business_ids_cannot_be_saved(client):
    for unexpected in [{'baseline': {}}, {'business_id': 'another-business'}, {'id': 'caller-chosen-id'}]:
        request = deepcopy(definition())
        request.update(unexpected)
        assert client.post('/api/scenarios', json=request).status_code == 422
