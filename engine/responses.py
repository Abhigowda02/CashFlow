"""Pure, deterministic response what-if simulations built on the forecast engine."""
from __future__ import annotations
from copy import deepcopy
from datetime import date
from typing import Any
from .forecast import run_forecast
from .shortage import analyse

DEFAULT_RESPONSE_COSTS = {'overdraft_rate_pct_per_year': 14.0, 'overdraft_limit': 200000,
    'early_discount_pct': 2.0, 'early_discount_window_days': 20,
    'invoice_discounting_fee_pct_per_year': 12.0, 'discounting_advance_pct': 80.0,
    'target_shortage_probability': .10}

def _costs(costs: dict[str, Any] | None) -> dict[str, Any]:
    result = dict(DEFAULT_RESPONSE_COSTS); result.update(costs or {})
    if any(float(value) < 0 for value in result.values()): raise ValueError('Response costs cannot be negative')
    return result

def _apply(business: dict, response: dict, costs: dict) -> tuple[dict, int, int, list[str]]:
    changed=deepcopy(business); kind=response['kind']; warnings=[]; cost=0; moved=0
    if kind == 'chase_customer':
        for invoice in changed['invoices']:
            if invoice['id']==response['invoice_id']:
                invoice['accelerate_days']=int(response.get('days',15)); moved=int(invoice['amount'])
                break
    elif kind == 'early_payment_discount':
        for invoice in changed['invoices']:
            if invoice['id']==response['invoice_id']:
                pct=float(costs['early_discount_pct'])/100; cost=round(invoice['amount']*pct); moved=invoice['amount']-cost
                invoice['accelerate_days']=int(costs['early_discount_window_days']); invoice['amount_multiplier']=1-pct; warnings.append(f'Discount annualised cost assumption: {cost} INR')
                break
    elif kind == 'overdraft_or_credit_line':
        amount=min(int(response.get('amount', costs['overdraft_limit'])), int(costs['overdraft_limit'])); days=int(response.get('days',30)); cost=round(amount*float(costs['overdraft_rate_pct_per_year'])/100*days/365); moved=amount
        changed['opening_cash']=int(changed.get('opening_cash',0))+amount
    else: raise ValueError('Unsupported response')
    return changed, max(0,cost), max(0,moved), warnings

def evaluate_response(business: dict, scenario: dict | None, response: dict, costs: dict | None=None, *, seed: int=42, n_sims: int=500) -> dict:
    """Evaluate one response with identical forecast seed/draw order as baseline."""
    merged=_costs(costs); before=run_forecast(deepcopy(business),scenario=scenario,n_sims=n_sims,seed=seed); changed,cost,moved,warnings=_apply(business,response,merged); after=run_forecast(changed,scenario=scenario,n_sims=n_sims,seed=seed); base=analyse(before); outcome=analyse(after); closed=max(0,base['peak_funding_gap']-outcome['peak_funding_gap'])
    return {'id':response.get('id',response['kind']+'-'+response.get('invoice_id','default')),'kind':response['kind'],'title':response.get('title',response['kind'].replace('_',' ').title()),'cost':cost,'cash_moved_or_saved':moved,'shortage_probability_before':base['shortage_probability'],'shortage_probability_after':outcome['shortage_probability'],'first_shortage_date_after':outcome['first_shortage_date'],'min_balance_after':outcome['minimum_p50_balance'],'funding_gap_after':outcome['peak_funding_gap'],'gap_closed':closed,'cost_per_rupee_of_gap_closed':(round(cost/closed,4) if cost and closed else None),'warnings':warnings}

def generate_candidates(business: dict, scenario: dict | None=None, costs: dict | None=None) -> list[dict]:
    """Generate relevant deterministic responses and drop non-improving options."""
    as_of=date.fromisoformat(business['as_of']); opens=[i for i in business.get('invoices',[]) if i.get('status')=='open']; relevant=sorted([i for i in opens if date.fromisoformat(i['due_date'])<=as_of or i['amount']>=max([x['amount'] for x in opens] or [0])],key=lambda x:-x['amount'])[:2]
    responses=[]
    for invoice in relevant:
        responses.extend([{'kind':'chase_customer','invoice_id':invoice['id'],'days':15},{'kind':'early_payment_discount','invoice_id':invoice['id']}])
    responses.append({'kind':'overdraft_or_credit_line'})
    rows=[evaluate_response(business,scenario,row,costs) for row in responses]
    return sorted([row for row in rows if row['shortage_probability_after']<=row['shortage_probability_before'] and (row['gap_closed']>0 or row['shortage_probability_after']<row['shortage_probability_before'])],key=lambda row:(-(row['gap_closed']/max(1,row['cost'])),row['cost'],row['id']))
