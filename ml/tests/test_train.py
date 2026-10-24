import numpy as np
import pandas as pd
import pytest

from ml import delay_model
from ml.data import build_training_table
from ml.tests.test_pipeline import business
from ml.train import train, training_table_from_csv


def test_train_and_load(tmp_path, monkeypatch):
    csv = tmp_path / 'canonical.csv'
    build_training_table(business()).to_csv(csv, index=False)
    artifact = tmp_path / 'delay_model.joblib'
    trained = train(csv, artifact_path=artifact)
    monkeypatch.setattr(delay_model, 'DEFAULT_ARTIFACT', artifact)
    # No table: loading must not attempt to train.
    loaded = delay_model.fit()
    assert loaded.shift == trained.shift
    inv, customer = business()['invoices'][-1], business()['customers'][0]
    assert loaded.sample_delay(inv, customer, np.random.default_rng(11)) == trained.sample_delay(
        inv, customer, np.random.default_rng(11))
    # The module-level sampler is set too.
    assert delay_model.sample_delay(inv, customer, np.random.default_rng(11)) == loaded.sample_delay(
        inv, customer, np.random.default_rng(11))
    smaller = build_training_table(business()).iloc[:20]
    assert len(delay_model.fit(smaller, use_saved=False).table) == 20


def test_raw_adapter(tmp_path):
    raw = pd.DataFrame([
        dict(business_code='X', cust_number='001', doc_id='1', posting_date='1/1/2020',
             due_in_date='20200110', clear_date='1/15/2020 0:00', isOpen='0', total_open_amount='100'),
        dict(business_code='X', cust_number='001', doc_id='2', posting_date='1/12/2020',
             due_in_date='20200120', clear_date=None, isOpen='1', total_open_amount='200'),
        dict(business_code='X', cust_number='001', doc_id='3', posting_date='1/16/2020',
             due_in_date='20200125', clear_date=None, isOpen='1', total_open_amount='300'),
    ])
    raw = pd.concat([raw, raw.iloc[:1]], ignore_index=True)
    path = tmp_path / 'raw.csv'
    raw.to_csv(path, index=False)
    table = training_table_from_csv(path, '2020-01-30')
    assert len(table) == 3
    assert table.event.tolist() == [1, 0, 0]
    assert table.prior_count.tolist() == [0, 0, 1]
    assert table.past_delay.tolist() == [0, 0, 5]
    assert table.duration.tolist() == [5, 10, 5]
    assert table.customer_id.tolist() == ['X:001'] * 3
    assert table.attrs['duplicates_removed'] == 1
    inferred = training_table_from_csv(path)
    assert inferred.as_of.max() == pd.Timestamp('2020-01-16')
    # Paid after the observation date is censored even when the source is closed.
    raw.loc[raw.doc_id == '1', 'clear_date'] = '2/1/2020 0:00'
    raw.to_csv(path, index=False)
    limited = training_table_from_csv(path, '2020-01-16')
    assert limited.event.tolist() == [0, 0, 0]


def test_no_artifact_or_training_data(tmp_path):
    with pytest.raises(ValueError, match='Supply training data'):
        delay_model.fit(artifact_path=tmp_path / 'missing.joblib')
