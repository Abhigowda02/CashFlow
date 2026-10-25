"""Paired simulations of collection timing, with separate relationship guidance."""
from copy import deepcopy
from datetime import date
from collections import defaultdict

import numpy as np

from .forecast import run_forecast


def relationship_guidance(customer, invoice_ids, oldest_days, paid_delays):
    context = customer.get('collection_context')
    if not context:
        return dict(sensitivity='unknown', approach='Review relationship first',
            reason='Relationship and service context has not been reviewed by the owner.',
            next_action='Check for disputes and service issues before choosing a reminder approach.')
    disputes = set(context.get('disputed_invoice_ids', [])) & set(invoice_ids)
    if context['service_issue'] != 'none' or disputes:
        return dict(sensitivity='high', approach='Resolve issue, then agree payment',
            reason='An unresolved service issue or disputed overdue invoice needs attention.',
            next_action='Have the account owner clarify the issue, confirm the undisputed balance, and agree a payment date. The simulated benefit assumes the issue is resolved.')
    if context['importance'] == 'strategic' or context['repeat_customer']:
        return dict(sensitivity='high' if context['importance'] == 'strategic' else 'medium', approach='Personal account-owner call',
            reason='This is a strategic or repeat customer; preserve continuity while confirming payment.',
            next_action='Use a personal, polite call to confirm invoice acceptance and agree a specific payment date.')
    if len(paid_delays) >= 3 and np.mean(np.asarray(paid_delays) <= 0) >= .8:
        return dict(sensitivity='medium', approach='Courtesy reminder',
            reason='Most observed payments were on time; check for an administrative oversight.',
            next_action='Send a friendly invoice check with the outstanding balance and ask whether anything is blocking payment.')
    if oldest_days >= 30:
        return dict(sensitivity='medium' if context['importance'] == 'important' else 'standard', approach='Firm, professional follow-up',
            reason='The oldest eligible invoice is at least 30 days overdue and no issue is recorded.',
            next_action='Request a written payment commitment. If the customer cannot settle in full, discuss a revised schedule for owner approval.')
    return dict(sensitivity='medium' if context['importance'] == 'important' else 'standard', approach='Friendly payment confirmation',
        reason='No unresolved issue is recorded; a routine follow-up is appropriate.',
        next_action='Confirm that the invoice was received and ask for the expected payment date.')


def _stress(balance, floor):
    below = balance < floor
    first = np.where(below.any(axis=1), below.argmax(axis=1), balance.shape[1])
    return float(below.any(axis=1).mean()), np.maximum(floor-balance.min(axis=1), 0), first


def rank_collections(business, acceleration_days=15, n_sims=500, seed=42, delay_model='empirical'):
    if not 1 <= acceleration_days <= 60:
        raise ValueError('Acceleration must be between 1 and 60 days')
    business = deepcopy(business)
    business['_collection_diagnostics'] = True
    forecast = run_forecast(business, n_sims=n_sims, seed=seed, delay_model=delay_model)
    diagnostics = forecast.pop('_collection_diagnostics')
    balance, records = diagnostics['balance'], diagnostics['invoices']
    floor, as_of = forecast['safety_floor'], date.fromisoformat(business['as_of'])
    base_prob, base_gap, base_first = _stress(balance, floor)
    deadline = (date.fromisoformat(forecast['first_shortage_date'])-as_of).days if forecast['first_shortage_date'] else 30
    groups = defaultdict(list)
    for record in records:
        groups[record['customer_id']].append(record)
    customers = {c['id']: c for c in business['customers']}
    invoices = {i['id']: i for i in business['invoices']}
    result = []
    sample_indices = np.arange(n_sims)
    for cid, group in groups.items():
        # Move the exact same sampled receipts; all unrelated random draws stay fixed.
        changes = np.zeros_like(balance)
        for record in group:
            original = record['pay_days']
            earlier = np.maximum(1, original-acceleration_days)
            earlier = np.minimum(earlier, original)  # Day-zero overrides must never be delayed.
            for days, sign in [(original, -1), (earlier, 1)]:
                inside = (days >= 0) & (days < balance.shape[1])
                np.add.at(changes, (sample_indices[inside], days[inside]), sign*record['amount'])
        cash_change = np.cumsum(changes, axis=1)
        after_prob, after_gap, after_first = _stress(balance+cash_change, floor)
        invoice_ids = [record['invoice_id'] for record in group]
        oldest = max((as_of-date.fromisoformat(invoices[iid]['due_date'])).days for iid in invoice_ids)
        customer = customers.get(cid, dict(id=cid, name=cid))
        history = [i for i in business['invoices'] if i['customer_id'] == cid and i['status'] == 'paid'
                   and i.get('paid_date') and i['paid_date'] <= business['as_of']]
        delays = [(date.fromisoformat(i['paid_date'])-date.fromisoformat(i['due_date'])).days for i in history]
        gap_reduction = float((base_gap-after_gap).mean())
        runway_gain = float((after_first-base_first).mean())
        prob_reduction = base_prob-after_prob
        before_shortage = float(cash_change[:, deadline].mean())
        row = dict(customer_id=cid, customer_name=customer.get('name', cid), invoice_ids=invoice_ids,
            overdue_amount=sum(record['amount'] for record in group), oldest_overdue_days=oldest,
            shortage_probability_after=round(after_prob, 4), probability_reduction_pp=round(prob_reduction*100, 2),
            expected_gap_reduction=round(gap_reduction), runway_days_gained=round(runway_gain, 2),
            cash_advanced_by_deadline=round(before_shortage),
            collection_context=customer.get('collection_context'),
            guidance=relationship_guidance(customer, invoice_ids, oldest, delays))
        # Unrounded metrics rank first; relationship context changes outreach, not financial data.
        key = (-prob_reduction, -gap_reduction, -runway_gain, -before_shortage, -row['overdue_amount'], cid)
        result.append((key, row))
    result.sort(key=lambda entry: entry[0])
    rows = [dict(rank=index+1, **row) for index, (_, row) in enumerate(result)]
    return dict(as_of=business['as_of'], delay_model_used=forecast['meta']['delay_model_used'],
        delay_model_requested=delay_model, n_sims=n_sims, seed=seed, acceleration_days=acceleration_days,
        baseline=dict(shortage_probability=round(base_prob, 4), first_shortage_date=forecast['first_shortage_date'],
                      expected_peak_gap=round(float(base_gap.mean()))),
        comparison_deadline=forecast['dates'][deadline], customers=rows,
        assumption='What-if only: all overdue receipts for one customer arrive up to the selected number of days earlier, no earlier than tomorrow. This is conditional on successful collection or dispute resolution. No additional revenue, outreach costs, discounts, future relationship revenue changes, or collection-success probability are modelled.',
        ranking_method='Shortage probability reduced, then expected peak cash gap reduced, then expected runway gained, then cash advanced by the comparison date. Ties use overdue amount and customer ID.')
