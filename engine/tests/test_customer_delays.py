"""Customer stress changes shift receipts without changing other sampled paths."""
from copy import deepcopy
from datetime import date, timedelta
import sys
from types import ModuleType, SimpleNamespace

import numpy as np
import pytest

from engine.forecast import run_forecast


def business_with_receipts():
    def invoice(identifier, customer, due, amount):
        return dict(id=identifier, customer_id=customer, amount=amount,
                    issue_date=(date.fromisoformat(due)-timedelta(days=30)).isoformat(),
                    due_date=due, status='open', paid_date=None)

    return dict(name='Customer delay regression', as_of='2026-10-25',
        opening_cash=5000, safety_floor=1000,
        customers=[dict(id='C1', name='Selected customer', segment='small'),
                   dict(id='C2', name='Other customer', segment='corporate')],
        invoices=[invoice('I1', 'C1', '2026-01-31', 1000),
                  invoice('I2', 'C2', '2026-01-31', 500),
                  invoice('I3', 'C1', '2026-10-15', 600),
                  invoice('I4', 'C2', '2026-11-05', 700)],
        supplier_bills=[dict(id='B1', supplier='Supplier', amount=500,
                            due_date='2026-11-03', is_msme=False, status='open')],
        obligations=[dict(id='O1', name='Payroll', amount=2000,
                          frequency='monthly', day_of_month=1)],
        sales_plan=dict(monthly_amount=3000, terms_days=15, monthly_noise_pct=20),
        _collection_diagnostics=True)


def configure_sampler(monkeypatch, kind):
    if kind == 'empirical':
        return 'empirical'
    module = ModuleType('ml.delay_model')

    def legacy_sample(invoice, customer, rng, days_overdue):
        # Exercise the engine's clamp for samplers that return dates before as_of.
        return int(rng.integers(0, 30))

    def sample_after(invoice, customer, rng, elapsed):
        return int(elapsed+rng.integers(1, 30))

    def fit(business):
        if kind == 'survival_fallback':
            raise ImportError('Unavailable model')
        if kind == 'survival_after':
            return SimpleNamespace(sample_after=sample_after)
        return SimpleNamespace()

    module.fit, module.sample_delay = fit, legacy_sample
    monkeypatch.setitem(sys.modules, 'ml.delay_model', module)
    return 'survival'


@pytest.mark.parametrize('kind', ['empirical', 'survival_after', 'survival_legacy', 'survival_fallback'])
@pytest.mark.parametrize('extra_days', [20, 180])
def test_only_selected_receipts_shift_by_the_requested_delay(monkeypatch, kind, extra_days):
    model = configure_sampler(monkeypatch, kind)
    business = business_with_receipts()
    scenario = dict(name='Selected customer late', changes=[
        dict(type='delay_customer', customer_id='C1', extra_days=extra_days)])
    original_business, original_scenario = deepcopy(business), deepcopy(scenario)
    baseline = run_forecast(business, n_sims=40, seed=42, delay_model=model)
    changed = run_forecast(business, scenario=scenario, n_sims=40, seed=42, delay_model=model)
    expected_model = 'empirical' if kind in ('empirical', 'survival_fallback') else 'survival'
    assert baseline['meta']['delay_model_used'] == changed['meta']['delay_model_used'] == expected_model

    before, after = baseline['_collection_diagnostics'], changed['_collection_diagnostics']
    records = {record['invoice_id']: record for record in after['invoices']}
    expected_balance = before['balance'].copy()
    for record in before['invoices']:
        selected = record['customer_id'] == 'C1'
        old_days = record['pay_days']
        new_days = old_days+extra_days if selected else old_days
        np.testing.assert_array_equal(records[record['invoice_id']]['pay_days'], new_days)
        if selected:
            for sample, (old, new) in enumerate(zip(old_days, new_days)):
                if old < 90:
                    expected_balance[sample, old:] -= record['amount']
                if new < 90:
                    expected_balance[sample, new:] += record['amount']

    # Includes the untouched customer's future invoice, noisy future sales, and bills.
    np.testing.assert_array_equal(after['balance'], expected_balance)
    assert np.all(after['balance'] <= before['balance'])
    assert business == original_business and scenario == original_scenario


@pytest.mark.parametrize('due_date', ['2026-10-25', '2026-11-01'])
def test_early_payment_history_does_not_absorb_delay_on_an_unpaid_future_invoice(due_date):
    business = business_with_receipts()
    business.update(supplier_bills=[], obligations=[], sales_plan=dict(monthly_amount=0))
    business['invoices'] = [dict(id='unpaid', customer_id='C1', amount=1000,
        issue_date='2026-10-01', due_date=due_date, status='open', paid_date=None)]
    for index in range(3):
        business['invoices'].append(dict(id=f'early-{index}', customer_id='C1', amount=1000,
            issue_date='2026-05-01', due_date='2026-06-15', status='paid', paid_date='2026-06-05'))
    baseline = run_forecast(business, n_sims=40, seed=19)['_collection_diagnostics']['balance']
    scenario = dict(name='Twenty days later', changes=[
        dict(type='delay_customer', customer_id='C1', extra_days=20)])
    actual = run_forecast(business, scenario=scenario, n_sims=40, seed=19)['_collection_diagnostics']['balance']
    receipts = np.diff(baseline, axis=1, prepend=np.full((40, 1), business['opening_cash']))
    shifted = np.zeros_like(receipts)
    shifted[:, 20:] = receipts[:, :-20]
    np.testing.assert_array_equal(actual, business['opening_cash']+shifted.cumsum(axis=1))


@pytest.mark.parametrize('action', ['override', 'accelerate'])
def test_existing_action_priority_is_preserved(action):
    business = business_with_receipts()
    business['invoices'] = business['invoices'][:1]
    original = deepcopy(business)
    if action == 'override':
        business['invoices'][0]['override_pay_day'] = 5
    else:
        business['invoices'][0]['accelerate_days'] = 7
    scenario = dict(name='Customer stress with action', changes=[
        dict(type='delay_customer', customer_id='C1', extra_days=20)])
    sampled_days = run_forecast(original, n_sims=20)['_collection_diagnostics']['invoices'][0]['pay_days']
    actual_days = run_forecast(business, scenario=scenario, n_sims=20)['_collection_diagnostics']['invoices'][0]['pay_days']
    expected = np.full(20, 5) if action == 'override' else np.maximum(1, sampled_days+20-7)
    np.testing.assert_array_equal(actual_days, expected)
