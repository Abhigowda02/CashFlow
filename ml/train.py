"""Train and persist a model: python -m ml.train --csv data/payment_date.csv."""
import argparse
import os
from pathlib import Path
import tempfile

import joblib
import pandas as pd

from .data import REQUIRED, build_training_table, load_csv, validate_table
from .delay_model import DEFAULT_ARTIFACT, fit


def training_table_from_csv(path, as_of=None):
    """Accept canonical data or adapt the payment_date.csv export.

    The export has no snapshot date or customer segments. Infer the snapshot
    from observed posting/payment dates unless supplied; segment is unknown.
    """
    raw = pd.read_csv(path, dtype=str)
    if set(REQUIRED).issubset(raw.columns):
        if as_of is not None:
            raise ValueError('--as-of is only supported for raw payment-date exports')
        return load_csv(path)
    required = {'business_code', 'cust_number', 'doc_id', 'posting_date',
                'due_in_date', 'clear_date', 'isOpen', 'total_open_amount'}
    missing = required - set(raw.columns)
    if missing:
        raise ValueError(f'Unrecognized CSV schema; missing payment-date columns: {sorted(missing)}')
    source_rows = len(raw)
    raw = raw.drop_duplicates().copy()
    identity = ['business_code', 'doc_id']
    if raw[identity + ['cust_number']].isna().any().any():
        raise ValueError('Missing business, document, or customer identifiers')
    if raw.duplicated(identity).any():
        raise ValueError('Conflicting rows for the same business_code/doc_id')
    issue = pd.to_datetime(raw.posting_date, format='mixed', errors='raise').dt.normalize()
    due = pd.to_datetime(raw.due_in_date, format='%Y%m%d', errors='raise')
    paid = pd.to_datetime(raw.clear_date, format='mixed', errors='raise').dt.normalize()
    if issue.isna().any() or due.isna().any():
        raise ValueError('Missing issue or due dates')
    if not raw.isOpen.isin(['0', '1']).all():
        raise ValueError('isOpen must be 0 or 1')
    closed = raw.isOpen == '0'
    if paid[closed].isna().any():
        raise ValueError('Closed invoice is missing clear_date')
    if (paid[closed] < issue[closed]).any():
        raise ValueError('Payment precedes issue date')
    snapshot = (pd.Timestamp(as_of).normalize() if as_of is not None
                else max(issue.max(), paid[closed].max()))
    if pd.isna(snapshot):
        raise ValueError('Cannot infer observation date; supply --as-of')
    if (issue > snapshot).any():
        raise ValueError('--as-of precedes an invoice issue date')
    customer_ids = raw.business_code + ':' + raw.cust_number
    customers = [{'id': cid, 'segment': 'unknown'} for cid in customer_ids.unique()]
    amounts = pd.to_numeric(raw.total_open_amount, errors='raise')
    invoices = []
    for index, row in raw.iterrows():
        invoices.append(dict(id=f'{row.business_code}:{row.doc_id}', customer_id=customer_ids.loc[index],
                             amount=amounts.loc[index], issue_date=issue.loc[index], due_date=due.loc[index],
                             currency=row.get('invoice_currency') if pd.notna(row.get('invoice_currency')) else 'UNKNOWN',
                             status='paid' if closed.loc[index] else 'open',
                             paid_date=paid.loc[index] if closed.loc[index] else None))
    table = build_training_table(dict(as_of=snapshot, customers=customers, invoices=invoices,
        amount_unit_verified=False, amount_semantics='unknown', currency_provenance='unverified_export_labels',
        source_kind='unverified_export',
        source_provenance='Original publisher and total_open_amount semantics are not verified',
        observation_date_source='explicit_user_snapshot' if as_of is not None else 'inferred_latest_observed'))
    table['source_rows'] = source_rows
    table['duplicates_removed'] = source_rows-len(raw)
    return validate_table(table)


def train(csv_path, as_of=None, artifact_path=DEFAULT_ARTIFACT):
    table = training_table_from_csv(csv_path, as_of)
    model = fit(table, use_saved=False)
    target = Path(artifact_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    # Replace only after serialization succeeds, preserving any existing model.
    descriptor, temporary = tempfile.mkstemp(prefix='delay_model-', suffix='.tmp', dir=target.parent)
    os.close(descriptor)
    try:
        joblib.dump(model, temporary, compress=3)
        os.replace(temporary, target)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    paid = int(table.event.sum())
    print(f'Trained on {len(table):,} invoices: {paid:,} paid, {len(table)-paid:,} censored; '
          f'{table.customer_id.nunique():,} customers.')
    if 'as_of' in table:
        print(f'Observation date: {pd.Timestamp(table.as_of.max()).date()}; '
              f'duplicates removed: {table.attrs.get("duplicates_removed", 0):,}.')
    print(f'Amount feature: {model.amount_feature_policy}.')
    print('Currency labels: ' + ', '.join(sorted(table.currency.unique())) + '; no currency conversion performed.')
    print('Validation: not yet validated on representative real businesses.')
    print(f'Early-payment shift: {model.shift:g} days. Saved: {target}')
    return model


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--csv', required=True, type=Path)
    parser.add_argument('--as-of', help='Observation date (YYYY-MM-DD); otherwise inferred for raw exports')
    args = parser.parse_args()
    try:
        train(args.csv, args.as_of)
    except (ValueError, OSError) as error:
        parser.exit(2, f'Training failed: {error}\n')


if __name__ == '__main__':
    main()
