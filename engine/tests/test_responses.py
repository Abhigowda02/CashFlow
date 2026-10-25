from engine.datagen import generate_business
from engine.responses import evaluate_response, generate_candidates

def _business(): return generate_business(seed=1)
def test_candidate_costs_are_never_negative():
    assert all(row['cost'] >= 0 for row in generate_candidates(_business()))

def test_candidate_probability_never_worsens():
    assert all(row['shortage_probability_after'] <= row['shortage_probability_before'] for row in generate_candidates(_business()))

def test_candidates_are_deterministic():
    assert generate_candidates(_business()) == generate_candidates(_business())
def test_chase_response_is_paired_and_cost_free():
    business=_business(); invoice=next(i for i in business['invoices'] if i['status']=='open')
    row=evaluate_response(business,None,{'kind':'chase_customer','invoice_id':invoice['id'],'days':15})
    assert row['cost']==0 and row==evaluate_response(business,None,{'kind':'chase_customer','invoice_id':invoice['id'],'days':15})

def test_chase_large_late_invoice_reduces_shortage_probability():
    business=_business(); invoice=max((i for i in business['invoices'] if i['status']=='open'), key=lambda i:i['amount'])
    row=evaluate_response(business,None,{'kind':'chase_customer','invoice_id':invoice['id'],'days':60})
    assert row['shortage_probability_after'] < row['shortage_probability_before']
def test_cost_override_changes_discount_cost():
    business=_business(); invoice=next(i for i in business['invoices'] if i['status']=='open')
    assert evaluate_response(business,None,{'kind':'early_payment_discount','invoice_id':invoice['id']},{'early_discount_pct':5})['cost']==round(invoice['amount']*.05)

def test_non_improving_candidates_are_dropped():
    business=_business(); business['opening_cash']=100_000_000
    assert generate_candidates(business) == []
