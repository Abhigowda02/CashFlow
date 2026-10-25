from copy import deepcopy
import json
from datetime import date, timedelta
import pytest
import numpy as np

from engine.collections import rank_collections
from engine.forecast import run_forecast


def example_business():
    customers = [dict(id='small', name='Small but timely', segment='small'),
                 dict(id='large', name='Large but much later', segment='corporate')]
    invoices = []
    for cid, delay in [('small', 30), ('large', 90)]:
        for i in range(3):
            due = date(2026, 6, 1)+timedelta(days=i)
            invoices.append(dict(id=f'{cid}-paid-{i}', customer_id=cid, amount=1000,
                issue_date='2026-05-01', due_date=due.isoformat(), status='paid',
                paid_date=(due+timedelta(days=delay)).isoformat()))
        invoices.append(dict(id=f'{cid}-open', customer_id=cid, amount=5000 if cid == 'small' else 100000,
            issue_date='2026-09-01', due_date='2026-09-20', status='open', paid_date=None))
    return dict(name='Test', as_of='2026-10-01', opening_cash=0, safety_floor=0, customers=customers,
        invoices=invoices, supplier_bills=[], obligations=[dict(id='pay', name='Payroll', amount=1000,
        frequency='monthly', day_of_month=12)], sales_plan=dict(monthly_amount=0))


def test_cash_impact_can_rank_smaller_customer_first():
    business = example_business()
    original = deepcopy(business)
    ranking = rank_collections(business, n_sims=100)
    assert ranking['customers'][0]['customer_id'] == 'small'
    assert ranking['customers'][0]['probability_reduction_pp'] == 100
    assert ranking['customers'][1]['overdue_amount'] > ranking['customers'][0]['overdue_amount']
    assert business == original
    assert rank_collections(business, n_sims=100) == ranking
    json.dumps(ranking)  # No private arrays or simulation paths reach API responses.
    for row in ranking['customers']:
        assert row['shortage_probability_after'] <= ranking['baseline']['shortage_probability']
        assert row['expected_gap_reduction'] >= 0
        assert row['runway_days_gained'] >= 0


def test_diagnostics_preserve_baseline_draws():
    business = example_business()
    expected = run_forecast(business, n_sims=25)
    captured = run_forecast(dict(business, _collection_diagnostics=True), n_sims=25)
    diagnostics = captured.pop('_collection_diagnostics')
    assert captured == expected
    assert diagnostics['balance'].shape == (25, 90)
    assert len(diagnostics['invoices']) == 2


def test_relationship_changes_approach_without_distorting_cash():
    business = example_business()
    before = rank_collections(business, n_sims=25)
    business['customers'][0]['collection_context'] = dict(importance='strategic', repeat_customer=True,
        service_issue='open', disputed_invoice_ids=['small-open'], notes='Delivery issue')
    after = rank_collections(business, n_sims=25)
    for key in ['customer_id', 'overdue_amount', 'probability_reduction_pp', 'runway_days_gained', 'expected_gap_reduction']:
        assert before['customers'][0][key] == after['customers'][0][key]
    assert before['customers'][0]['guidance']['sensitivity'] == 'unknown'
    assert after['customers'][0]['guidance']['approach'] == 'Resolve issue, then agree payment'


def test_no_overdue_invoices_produces_empty_ranking():
    business = example_business()
    for invoice in business['invoices']:
        if invoice['status'] == 'open':
            invoice['due_date'] = '2026-11-01'
    assert rank_collections(business, n_sims=10)['customers'] == []


@pytest.mark.parametrize('delay_model', ['empirical', 'survival'])
def test_paired_cash_benefits_match_full_forecast_rerun(delay_model):
    business = example_business()
    ranking = rank_collections(business, n_sims=30, delay_model=delay_model)
    base = run_forecast(dict(business, _collection_diagnostics=True), n_sims=30, delay_model=delay_model)
    floor = base['safety_floor']
    base_balance = base['_collection_diagnostics']['balance']
    base_gap = np.maximum(floor-base_balance.min(axis=1), 0)
    for row in ranking['customers']:
        changed = deepcopy(business)
        for invoice in changed['invoices']:
            if invoice['id'] in row['invoice_ids']:
                invoice['accelerate_days'] = 15
        actual = run_forecast(dict(changed, _collection_diagnostics=True), n_sims=30, delay_model=delay_model)
        balances = actual['_collection_diagnostics']['balance']
        actual_prob = float((balances < floor).any(axis=1).mean())
        actual_gap = np.maximum(floor-balances.min(axis=1), 0)
        assert row['shortage_probability_after'] == round(actual_prob, 4)
        assert row['expected_gap_reduction'] == round(float((base_gap-actual_gap).mean()))
