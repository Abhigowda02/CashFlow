"""Canonical training data; source-specific CSV adapters live outside this module."""
from pathlib import Path
import numpy as np
import pandas as pd

FEATURES = ['segment', 'amount', 'issue_month', 'past_delay', 'prior_count']
REQUIRED = ['invoice_id', 'customer_id', 'issue_date', 'due_date', 'duration', 'event', *FEATURES]


def validate_table(table):
    table = table.copy()
    missing = set(REQUIRED) - set(table.columns)
    if missing:
        raise ValueError(f'Missing canonical columns: {sorted(missing)}; adapt the source CSV first')
    for col in ['issue_date', 'due_date']:
        table[col] = pd.to_datetime(table[col], errors='raise')
    for col in ['duration', 'event', 'amount', 'issue_month', 'past_delay', 'prior_count']:
        table[col] = pd.to_numeric(table[col], errors='raise')
        if not np.isfinite(table[col]).all():
            raise ValueError(f'{col} must be finite')
    if not table.event.isin([0, 1]).all():
        raise ValueError('event must be 0 (censored) or 1 (paid)')
    if table.invoice_id.duplicated().any():
        raise ValueError('invoice_id must be unique')
    table['segment'] = table.segment.fillna('unknown').astype(str)
    table['customer_id'] = table.customer_id.astype(str)
    return table


def load_csv(path):
    """Load canonical columns. Raw payment_date.csv requires a separate adapter."""
    return validate_table(pd.read_csv(Path(path), dtype={'customer_id': str, 'invoice_id': str}))


def build_training_table(business):
    if isinstance(business, (str, Path)):
        return load_csv(business)
    as_of = pd.Timestamp(business['as_of'])
    customers = {str(c['id']): c for c in business['customers']}
    invoices = business['invoices']
    histories = {}
    for inv in invoices:
        paid = inv.get('paid_date')
        if inv['status'] == 'paid' and not paid:
            raise ValueError('Paid invoice requires paid_date')
        if inv['status'] == 'paid' and pd.Timestamp(paid) <= as_of:
            histories.setdefault(str(inv['customer_id']), []).append(
                (pd.Timestamp(paid), (pd.Timestamp(paid) - pd.Timestamp(inv['due_date'])).days))
    for cid, values in histories.items():
        values.sort(key=lambda value: value[0])
        histories[cid] = (np.array([v[0].to_datetime64() for v in values]),
                          np.r_[0., np.cumsum([v[1] for v in values])])
    rows = []
    for inv in invoices:
        issue, due = pd.Timestamp(inv['issue_date']), pd.Timestamp(inv['due_date'])
        if issue > as_of:
            raise ValueError('Invoice issue_date is after as_of')
        cid = str(inv['customer_id'])
        dates, sums = histories.get(cid, (np.array([], dtype='datetime64[ns]'), np.array([0.])))
        count = int(np.searchsorted(dates, issue.to_datetime64(), side='left'))
        event = int(inv['status'] == 'paid' and pd.Timestamp(inv['paid_date']) <= as_of)
        end = pd.Timestamp(inv['paid_date']) if event else as_of
        rows.append(dict(invoice_id=inv['id'], customer_id=cid, issue_date=issue,
                         due_date=due, paid_date=inv.get('paid_date') if event else None,
                         as_of=as_of, segment=customers.get(cid, {}).get('segment', 'unknown'),
                         amount=inv['amount'], issue_month=issue.month,
                         past_delay=float(sums[count] / count) if count else 0., prior_count=count,
                         duration=(end-due).days, event=event))
    return validate_table(pd.DataFrame(rows, columns=[*REQUIRED, 'paid_date', 'as_of']))
