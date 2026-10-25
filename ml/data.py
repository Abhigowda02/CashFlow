"""Canonical training data; source-specific CSV adapters live outside this module."""
from pathlib import Path
import re
import numpy as np
import pandas as pd

FEATURES = ['segment', 'amount', 'issue_month', 'past_delay', 'prior_count']
REQUIRED = ['invoice_id', 'customer_id', 'issue_date', 'due_date', 'duration', 'event', *FEATURES]
METADATA_DEFAULTS = {
    'currency': 'UNKNOWN',
    'amount_unit_verified': False,
    'amount_semantics': 'unknown',
    'currency_provenance': 'unspecified',
    'source_kind': 'unknown',
    'source_provenance': 'Original publisher/source not verified',
    'observation_date_source': 'unspecified',
}


def _explicit_bool(value):
    """CSV metadata must contain an explicit boolean, not a truthy string."""
    if pd.isna(value):
        return False
    if value in (True, 1, 'True', 'true', '1'):
        return True
    if value in (False, 0, 'False', 'false', '0', ''):
        return False
    raise ValueError('amount_unit_verified must be true or false')


def amount_feature_metadata(table):
    """Permit nominal amount only with explicit single-unit original-value metadata.

    Unit verification is an explicit data-owner assertion, not independent proof
    of provenance or predictive validity. A currency label alone is insufficient.
    """
    currencies = sorted(set(table.get('currency', pd.Series('UNKNOWN', index=table.index)).astype(str)))
    permitted_currency = (len(currencies) == 1 and re.fullmatch(r'[A-Z]{3}', currencies[0])
                          and currencies[0] not in {'UNK', 'XXX', 'NAN', 'TBD', 'MIX'})
    verified = table.get('amount_unit_verified', pd.Series(False, index=table.index))
    semantics = table.get('amount_semantics', pd.Series('unknown', index=table.index))
    if table.empty or not verified.map(_explicit_bool).all():
        reason = 'Excluded: amount units have not been explicitly confirmed'
    elif not semantics.eq('original_invoice_amount').all():
        reason = 'Excluded: original invoice amount semantics have not been confirmed'
    elif not permitted_currency:
        reason = 'Excluded: mixed or unknown currency units'
    else:
        return dict(amount_feature_used=True,
                    amount_feature_policy=f'Included: explicitly declared original invoice amounts in {currencies[0]}',
                    currencies=currencies)
    return dict(amount_feature_used=False, amount_feature_policy=reason, currencies=currencies)


def _rebuild_history(table, observed_end):
    """Use only settled rows in this file, strictly before each invoice issue.

    This deliberately undercounts omitted external history rather than trusting
    precomputed covariates that might include future outcomes.
    """
    count = np.zeros(len(table), dtype=np.int64)
    average = np.zeros(len(table), dtype=float)
    event = table.event.eq(1).to_numpy()
    paid_dates = observed_end.to_numpy(dtype='datetime64[ns]')
    issue_dates = table.issue_date.to_numpy(dtype='datetime64[ns]')
    delays = table.duration.to_numpy(dtype=float)
    for positions in table.groupby('customer_id', sort=False).indices.values():
        history = positions[event[positions]]
        if not len(history):
            continue
        history = history[np.argsort(paid_dates[history], kind='stable')]
        known = np.searchsorted(paid_dates[history], issue_dates[positions], side='left')
        sums = np.r_[0., delays[history].cumsum()]
        count[positions] = known
        average[positions] = sums[known]/np.maximum(known, 1)
    table['prior_count'], table['past_delay'] = count, average


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
    if table[['issue_date', 'due_date']].isna().any().any():
        raise ValueError('Issue and due dates cannot be missing')
    observed_end = table.due_date + pd.to_timedelta(table.duration, unit='D')
    if 'paid_date' in table:
        paid_date = pd.to_datetime(table.paid_date, errors='raise')
        supplied = table.event.eq(1) & paid_date.notna()
        if ((paid_date[supplied]-observed_end[supplied]).abs() > pd.Timedelta(microseconds=1)).any():
            raise ValueError('Paid date disagrees with due date plus observed duration')
    if 'as_of' in table:
        snapshot = pd.to_datetime(table.as_of, errors='raise')
        if snapshot.isna().any() or (snapshot < table.issue_date).any():
            raise ValueError('Observation date must be present and on/after issue date')
        # Canonical CSV producers cannot bypass the future-payment censoring rule.
        table['event'] = (table.event.eq(1) & observed_end.le(snapshot)).astype(int)
        observed_end = observed_end.where(observed_end.le(snapshot), snapshot)
        table['duration'] = (observed_end-table.due_date).dt.total_seconds()/86400
        table['as_of'] = snapshot
    if (observed_end < table.issue_date).any():
        raise ValueError('Observed payment/censor date precedes invoice issue date')
    if 'paid_date' in table:
        table['paid_date'] = observed_end.where(table.event.eq(1), pd.NaT)
    if table.invoice_id.duplicated().any():
        raise ValueError('invoice_id must be unique')
    table['segment'] = table.segment.fillna('unknown').astype(str)
    table['customer_id'] = table.customer_id.astype(str)
    _rebuild_history(table, observed_end)
    for column, default in METADATA_DEFAULTS.items():
        if column not in table:
            table[column] = default
        elif column != 'amount_unit_verified':
            table[column] = table[column].fillna(default).astype(str).str.strip().replace('', default)
    table['currency'] = table.currency.str.upper()
    table['amount_unit_verified'] = table.amount_unit_verified.map(_explicit_bool).astype(bool)
    for column in ['source_rows', 'duplicates_removed']:
        if column not in table:
            table[column] = pd.Series(pd.NA, index=table.index, dtype='Int64')
        else:
            numeric = pd.to_numeric(table[column], errors='raise')
            if (numeric.dropna() < 0).any() or (numeric.dropna() % 1 != 0).any():
                raise ValueError(f'{column} must be a nonnegative integer')
            table[column] = numeric.astype('Int64')
        values = table[column].dropna().unique()
        if len(values) == 1:
            table.attrs[column] = int(values[0])
    table.attrs.update(amount_feature_metadata(table))
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
        metadata = {column: inv.get(column, business.get(column, default))
                    for column, default in METADATA_DEFAULTS.items()}
        rows.append(dict(invoice_id=inv['id'], customer_id=cid, issue_date=issue,
                         due_date=due, paid_date=inv.get('paid_date') if event else None,
                         as_of=as_of, segment=customers.get(cid, {}).get('segment', 'unknown'),
                         amount=inv['amount'], issue_month=issue.month,
                         past_delay=float(sums[count] / count) if count else 0., prior_count=count,
                         duration=(end-due).days, event=event, **metadata))
    return validate_table(pd.DataFrame(rows, columns=[*REQUIRED, 'paid_date', 'as_of', *METADATA_DEFAULTS]))
