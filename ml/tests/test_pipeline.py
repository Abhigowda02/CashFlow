import numpy as np
import pandas as pd
import pytest
from ml.data import build_training_table
from ml.delay_model import fit
from ml.evaluate import evaluate


def business():
    invoices = []
    for i in range(40):
        issue = pd.Timestamp('2020-01-01') + pd.Timedelta(days=i*10)
        due = issue + pd.Timedelta(days=5)
        delay = [-3, 2, 7, 12, 20][i % 5]
        invoices.append(dict(id=str(i), customer_id='c', amount=100+i*13,
                             issue_date=str(issue.date()), due_date=str(due.date()),
                             paid_date=str((due+pd.Timedelta(days=delay)).date()), status='paid'))
    invoices[-1].update(status='open', paid_date=None)
    return dict(as_of='2021-03-01', customers=[dict(id='c', segment='small')], invoices=invoices)


def test_no_leakage():
    b = business()
    t = build_training_table(b)
    for i, row in t.iterrows():
        past = [x for x in b['invoices'] if x['status'] == 'paid' and x['paid_date'] < str(row.issue_date.date())]
        assert row.prior_count == len(past)
        delays = [(pd.Timestamp(x['paid_date'])-pd.Timestamp(x['due_date'])).days for x in past]
        assert row.past_delay == pytest.approx(np.mean(delays) if delays else 0)
    changed = business()
    changed['invoices'][-2]['paid_date'] = '2021-02-28'
    assert build_training_table(changed).iloc[0].past_delay == t.iloc[0].past_delay


def test_censoring():
    b = business()
    b['invoices'][-1]['paid_date'] = '2020-01-01'  # stale value must not imply payment
    row = build_training_table(b).iloc[-1]
    assert row.event == 0
    assert row.duration == (pd.Timestamp(b['as_of'])-row.due_date).days


def test_sampling():
    b = business()
    model = fit(build_training_table(b), use_saved=False)
    inv, customer = b['invoices'][-1], b['customers'][0]
    a, z = np.random.default_rng(7), np.random.default_rng(7)
    assert [model.sample_delay(inv, customer, a) for _ in range(50)] == [model.sample_delay(inv, customer, z) for _ in range(50)]
    assert min(model.sample_delay(inv, customer, a) for _ in range(500)) >= -model.shift
    assert min(model.sample_delay(inv, customer, a, 30) for _ in range(100)) >= 30
    assert model.cdf(inv, customer, [10, 20, 60]).tolist() == sorted(model.cdf(inv, customer, [10, 20, 60]).tolist())


def test_csv_evaluation(tmp_path, monkeypatch):
    import importlib
    module = importlib.import_module('ml.evaluate')
    captured = []
    original_fit = module.fit
    def capture(table, **kwargs):
        captured.append(table.copy())
        return original_fit(table, **kwargs)
    monkeypatch.setattr(module, 'fit', capture)
    path = tmp_path / 'canonical.csv'
    build_training_table(business()).to_csv(path, index=False)
    result = evaluate(path, tmp_path, source_kind='synthetic')
    assert len(result) == 99
    assert result.fold.nunique() == 3
    assert result.evidence_status.eq('synthetic_pipeline_smoke_only').all()
    assert set(result.metric) == {'mae_paid_days', 'brier_ipcw', 'share_paid_ipcw'}
    assert len(captured) == 3
    assert (tmp_path / 'calibration.png').is_file()
    assert (tmp_path / 'metrics.csv').is_file()
    assert (tmp_path / 'report.json').is_file()
    cutoff = pd.Timestamp(result.train_cutoff.iloc[0])
    training = captured[0]
    assert (training.issue_date < cutoff).all()
    paid = training[training.event == 1]
    assert (paid.due_date + pd.to_timedelta(paid.duration, unit='D') < cutoff).all()
    # At least one training invoice paid only after cutoff was recensored.
    assert (training.event == 0).any()


def test_sparse_and_unseen_customer():
    b = business()
    model = fit(build_training_table(b).iloc[:2], use_saved=False)
    inv = b['invoices'][-1]
    assert np.isfinite(model.sample_delay(inv, {'id': 'new', 'segment': 'unknown'}, np.random.default_rng(4)))


def test_future_payment_is_censored():
    b = business()
    b['invoices'][0]['paid_date'] = '2022-01-01'
    assert build_training_table(b).iloc[0].event == 0


def test_distribution_cache_does_not_change_samples(monkeypatch):
    b = business()
    model = fit(build_training_table(b), use_saved=False)
    invoice, customer = b['invoices'][-1], b['customers'][0]
    calls = []
    compute = model._compute_distribution
    def record(*args):
        calls.append(1)
        return compute(*args)
    monkeypatch.setattr(model, '_compute_distribution', record)
    first = model.sample_delay(invoice, customer, np.random.default_rng(19))
    assert model.sample_delay(invoice, customer, np.random.default_rng(19)) == first
    assert len(calls) == 1
    model.sample_delay(dict(invoice, amount=invoice['amount']+1), customer, np.random.default_rng(19))
    assert len(calls) == 2
