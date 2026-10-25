"""Canonical files keep the same observation boundary as business adapters."""
import pandas as pd
import pytest

from ml.data import build_training_table, load_csv, validate_table
from ml.tests.test_pipeline import business


def test_canonical_future_payment_is_censored_at_explicit_snapshot(tmp_path):
    table = build_training_table(business())
    first = table.index[0]
    future = pd.Timestamp('2022-01-01')
    table.loc[first, 'paid_date'] = future
    table.loc[first, 'duration'] = (future-table.loc[first, 'due_date']).days
    path = tmp_path / 'future.csv'
    table.to_csv(path, index=False)
    loaded = load_csv(path)
    assert loaded.loc[first, 'event'] == 0
    assert pd.isna(loaded.loc[first, 'paid_date'])
    assert loaded.loc[first, 'duration'] == (loaded.loc[first, 'as_of']-loaded.loc[first, 'due_date']).days


def test_canonical_stale_paid_date_does_not_turn_censoring_into_payment():
    table = build_training_table(business())
    last = table.index[-1]
    table.loc[last, 'paid_date'] = pd.Timestamp('2020-01-01')
    loaded = validate_table(table)
    assert loaded.loc[last, 'event'] == 0 and pd.isna(loaded.loc[last, 'paid_date'])


def test_canonical_inconsistent_payment_metadata_is_rejected():
    table = build_training_table(business())
    table.loc[table.index[0], 'paid_date'] = pd.Timestamp('2022-01-01')
    with pytest.raises(ValueError, match='disagrees'):
        validate_table(table)


def test_canonical_issue_after_snapshot_is_rejected():
    table = build_training_table(business())
    table.loc[table.index[-1], 'as_of'] = pd.Timestamp('2020-01-01')
    with pytest.raises(ValueError, match='on/after issue'):
        validate_table(table)


def test_recensoring_does_not_extend_an_earlier_training_origin():
    table = build_training_table(business())
    origin = pd.Timestamp('2020-03-01')
    subset = table[table.issue_date < origin].copy()
    end = subset.due_date+pd.to_timedelta(subset.duration, unit='D')
    subset['event'] = (subset.event.eq(1) & end.lt(origin)).astype(int)
    end = end.where(end.lt(origin), origin)
    subset['duration'] = (end-subset.due_date).dt.days
    subset['paid_date'] = end.where(subset.event.eq(1), pd.NaT)
    loaded = validate_table(subset)
    assert (loaded.due_date+pd.to_timedelta(loaded.duration, unit='D') <= origin).all()


def test_canonical_supplied_history_is_rebuilt_after_future_payment_is_censored():
    table = build_training_table(business())
    future = pd.Timestamp('2022-01-01')
    first = table.index[0]
    table.loc[first, 'paid_date'] = future
    table.loc[first, 'duration'] = (future-table.loc[first, 'due_date']).days
    table['prior_count'] = 999
    table['past_delay'] = 99999
    loaded = validate_table(table)
    assert loaded.loc[first, 'event'] == 0
    assert loaded.iloc[0].prior_count == 0
    assert loaded.iloc[0].past_delay == 0
    assert loaded.iloc[1].prior_count == 0  # The original first payment is now unknown.
    assert loaded.iloc[1].past_delay == 0
    for _, row in loaded.iterrows():
        prior = loaded[(loaded.customer_id == row.customer_id) & loaded.event.eq(1) &
                       (loaded.due_date+pd.to_timedelta(loaded.duration, unit='D') < row.issue_date)]
        assert row.prior_count == len(prior)
        assert row.past_delay == pytest.approx(prior.duration.mean() if len(prior) else 0)


def test_canonical_subset_uses_only_available_in_file_history():
    table = build_training_table(business()).iloc[10:20].copy()
    loaded = validate_table(table)
    assert loaded.iloc[0].prior_count == 0
    assert loaded.iloc[0].past_delay == 0
