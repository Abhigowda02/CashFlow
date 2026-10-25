"""Observed payment profiles and conditional estimates for this tenant only."""
from datetime import date, timedelta
import math
import numpy as np


def model_result(business, business_id, force=False):
    try:
        from ml.personalization import get_model
        return get_model(business, business_id, force=force)
    except ImportError:
        paid = sum(invoice['status'] == 'paid' and bool(invoice.get('paid_date'))
                   and invoice['paid_date'] <= business['as_of'] for invoice in business['invoices'])
        return dict(status='unavailable', message='Install the ML dependencies to enable business-specific models.',
                    model=None, trained_at=None, checked_at=None, fingerprint=None,
                    invoice_count=len(business['invoices']), paid_count=paid, censored_count=len(business['invoices'])-paid)


def status(result):
    return {key: value for key, value in result.items() if key not in ['model', 'scope']}


def profiles(business, business_id, force=False):
    result = model_result(business, business_id, force)
    model = result['model']
    as_of = date.fromisoformat(business['as_of'])
    output = []
    for customer in business['customers']:
        invoices = [invoice for invoice in business['invoices'] if invoice['customer_id'] == customer['id']]
        paid = [invoice for invoice in invoices if invoice['status'] == 'paid' and invoice.get('paid_date')
                and date.fromisoformat(invoice['paid_date']) <= as_of]
        delays = [(date.fromisoformat(invoice['paid_date']) - date.fromisoformat(invoice['due_date'])).days for invoice in paid]
        unpaid = [invoice for invoice in invoices if invoice not in paid]
        outstanding = lambda invoice: max(0, invoice['amount'] - invoice.get('received_amount', 0))
        if model is None:
            basis = 'not_fitted'
        elif model.counts.get(customer['id'], 0) >= 3:
            basis = 'customer_features'
        elif customer.get('segment', 'unknown') in model.segment_models:
            basis = 'segment_fallback'
        else:
            basis = 'business_pool'
        predictions = []
        for invoice in unpaid:
            amount = outstanding(invoice)
            if amount == 0:
                continue
            prediction = dict(invoice_id=invoice['id'], due_date=invoice['due_date'], outstanding=amount,
                              probability_7_days=None, probability_30_days=None, probability_60_days=None,
                              paid_by_70=None, paid_by_90=None, status='not_available')
            if model is not None:
                elapsed = (as_of - date.fromisoformat(invoice['due_date'])).days
                try:
                    probabilities = model.conditional_cdf(invoice, customer, [7, 30, 60], elapsed)
                    quantiles = [model.conditional_quantile(invoice, customer, p, elapsed) for p in [.7, .9]]
                    if not np.isfinite([*probabilities, *quantiles]).all():
                        raise ValueError('Nonfinite estimate')
                    for key, value in zip(['probability_7_days', 'probability_30_days', 'probability_60_days'], probabilities):
                        prediction[key] = float(np.clip(value, 0, 1))
                    for key, value in zip(['paid_by_70', 'paid_by_90'], quantiles):
                        days = max(1, math.ceil(value)-elapsed)
                        prediction[key] = (as_of + timedelta(days=days)).isoformat() if days <= 3650 else None
                    prediction['status'] = 'estimated'
                except (ValueError, ArithmeticError, OverflowError):
                    prediction['status'] = 'unstable_estimate'
            predictions.append(prediction)
        output.append(dict(id=customer['id'], name=customer.get('name', customer['id']),
            segment=customer.get('segment', 'unknown'), invoice_count=len(invoices), paid_count=len(paid),
            collection_context=customer.get('collection_context'),
            unpaid_count=len(predictions), outstanding=sum(row['outstanding'] for row in predictions),
            median_delay=float(np.median(delays)) if delays else None,
            average_delay=float(np.mean(delays)) if delays else None,
            delay_std=float(np.std(delays)) if len(delays) >= 2 else None,
            on_time_share=sum(d <= 0 for d in delays)/len(delays) if delays else None,
            prediction_basis=basis, invoices=sorted(predictions, key=lambda row: row['due_date'])))
    return dict(as_of=business['as_of'], model=status(result),
                customers=sorted(output, key=lambda row: (-row['outstanding'], row['name'])))
