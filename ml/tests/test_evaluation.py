"""Forward validation and hand-checkable censored metric regressions."""
import hashlib
import importlib
import json
import subprocess
import sys

import numpy as np
import pandas as pd
import pytest

from ml.data import build_training_table
from ml.evaluate import (CensoringKM, _outcomes, cluster_interval, evaluate,
                         forward_splits, ipcw_contributions)
from ml.tests.test_pipeline import business


class RecordingModel:
    shift = 0
    amount_feature_used = False
    amount_feature_policy = 'test_amounts_excluded'

    def __init__(self, invoices):
        self.invoices = invoices

    def conditional_cdf(self, invoice, customer, future_days, elapsed):
        np.testing.assert_allclose(np.asarray(future_days)+elapsed, [10, 20, 30, 45, 60])
        assert elapsed == (invoice['issue_date']-invoice['due_date']).total_seconds()/86400
        self.invoices.append(dict(invoice))
        return np.array([.15, .3, .45, .65, .8])

    def conditional_quantile(self, invoice, customer, probability, elapsed):
        assert probability == .5
        return elapsed+20*np.log(2)


@pytest.fixture
def canonical(tmp_path):
    table = build_training_table(business())
    table['source_kind'] = 'synthetic'
    table['source_provenance'] = 'Fictional deterministic test fixture, no real business observations'
    table['observation_date_source'] = 'explicit_synthetic_snapshot'
    path = tmp_path/'canonical.csv'
    table.to_csv(path, index=False)
    return path, table


@pytest.fixture
def recording_fit(monkeypatch):
    module = importlib.import_module('ml.evaluate')
    training, invoices = [], []
    def replacement(table, **kwargs):
        assert kwargs == {'use_saved': False}
        assert '_observed_end' not in table
        training.append(table.copy())
        return RecordingModel(invoices)
    monkeypatch.setattr(module, 'fit', replacement)
    return training, invoices


def test_reverse_km_censoring_and_daily_ties():
    curve = CensoringKM([5, 5, 10], [1, 0, 1])
    # Payment at day 5 leaves the risk set before the tied censoring event.
    np.testing.assert_allclose(curve.probability([0, 5, 9, 10]), [1, .5, .5, .5])


def test_ipcw_matches_uncensored_brier_and_does_not_label_censor_as_paid():
    curve = CensoringKM([1, 5, 30], [1, 1, 1])
    loss, actual, support = ipcw_contributions(curve, [5, 20, 8], [1, 0, 0], [.8, .2, .5], 10)
    # An unknown outcome contributes zero, but remains in the denominator of three.
    np.testing.assert_allclose(loss, [.04, .04, 0])
    np.testing.assert_allclose(actual, [1, 0, 0])
    assert support['n'] == 3 and support['known_n'] == 2 and support['censored_by_n'] == 1
    assert loss.mean() == pytest.approx(.08/3)


def test_ipcw_uses_training_censoring_distribution_and_full_test_denominator():
    curve = CensoringKM([5, 12, 30], [0, 1, 1])
    loss, actual, support = ipcw_contributions(curve, [3, 20, 8], [1, 0, 0], [.8, .2, .5], 10)
    np.testing.assert_allclose(loss, [.04, .06, 0])
    np.testing.assert_allclose(actual, [1, 0, 0])
    assert support['censor_survival'] == pytest.approx(2/3)
    assert support['max_weight'] == pytest.approx(1.5)


def test_unsupported_followup_positivity_and_unknown_outcomes_are_unavailable():
    loss, actual, support = ipcw_contributions(CensoringKM([1, 5], [1, 1]), [4], [1], [.5], 10)
    assert loss is actual is None and support['status'] == 'unsupported_training_followup'
    almost_all_censored = CensoringKM([5]*19+[30], [0]*19+[1])
    loss, actual, support = ipcw_contributions(almost_all_censored, [20], [1], [.5], 10)
    assert loss is actual is None and support['status'] == 'unsupported_censoring_positivity'
    loss, actual, support = ipcw_contributions(CensoringKM([1, 30], [1, 1]), [5], [0], [.5], 10)
    assert loss is actual is None and support['status'] == 'unavailable_no_known_test_outcomes'


def test_censoring_metric_handles_early_payment_negative_offsets():
    curve = CensoringKM([-5, -2, 20], [1, 0, 1])
    loss, actual, support = ipcw_contributions(curve, [-4, 30], [1, 0], [.8, .2], 10)
    np.testing.assert_allclose(loss, [.04, .08])
    np.testing.assert_allclose(actual, [1, 0])
    assert support['status'] == 'ok'


def test_cluster_intervals_are_deterministic_and_small_samples_are_explicit():
    values = np.arange(40, dtype=float)/40
    customers = np.repeat(['a', 'b', 'c', 'd', 'e'], 8)
    first = cluster_interval(values, customers, bootstrap=200, seed=10)
    assert first == cluster_interval(values, customers, bootstrap=200, seed=10)
    assert first[0] < values.mean() < first[1]
    small = cluster_interval([1., 2.], ['a', 'b'])
    assert np.isnan(small[0]) and small[2] == 'unavailable_small_sample'
    disabled = cluster_interval(values, customers, bootstrap=0)
    assert np.isnan(disabled[0]) and disabled[2] == 'unavailable_insufficient_bootstrap_replicates'


def test_forward_folds_are_disjoint_and_keep_tied_issue_dates_together(canonical):
    _, table = canonical
    table = _outcomes(table).sort_values('issue_date')
    table.loc[table.index[21], 'issue_date'] = table.issue_date.iloc[20]
    observed_test_ids = set()
    splits = list(forward_splits(table, folds=3))
    assert len(splits) == 3
    previous_size = 0
    for _, origin, train, test in splits:
        assert len(train) > previous_size
        assert (train.issue_date < origin).all() and (test.issue_date >= origin).all()
        ids = set(test.invoice_id)
        assert not observed_test_ids.intersection(ids)
        observed_test_ids.update(ids)
        assert not set(train.issue_date).intersection(test.issue_date)
        previous_size = len(train)


def test_each_origin_recensors_and_rebuilds_all_history_features(canonical, recording_fit, tmp_path):
    path, original = canonical
    poisoned = original.copy()
    poisoned['past_delay'], poisoned['prior_count'], poisoned['issue_month'] = 999999, 999999, 99
    poisoned.to_csv(path, index=False)
    training, invoices = recording_fit
    result = evaluate(path, tmp_path/'evidence', source_kind='synthetic')
    assert len(training) == 3 and result.fold.nunique() == 3
    source_end = original.due_date+pd.to_timedelta(original.duration, unit='D')
    for fitted, (_, origin, _, test) in zip(training, forward_splits(original.sort_values('issue_date'), 3)):
        assert (fitted.issue_date < origin).all()
        end = fitted.due_date+pd.to_timedelta(fitted.duration, unit='D')
        assert (end[fitted.event == 1] < origin).all()
        assert (end <= origin).all()
        for row in fitted.itertuples():
            known = original[(original.customer_id == row.customer_id) & (original.event == 1) &
                (source_end < min(row.issue_date, origin)) & (original.issue_date < origin)]
            assert row.prior_count == len(known)
            assert row.past_delay == pytest.approx(known.duration.mean() if len(known) else 0)
            assert row.issue_month == row.issue_date.month
        test_ids = set(test.invoice_id)
        scored = [invoice for invoice in invoices if invoice['invoice_id'] in test_ids]
        known = original[(original.event == 1) & (source_end < origin) & (original.issue_date < origin)]
        assert all(invoice['prior_count'] == len(known) for invoice in scored)
        assert all(invoice['past_delay'] == pytest.approx(known.duration.mean()) for invoice in scored)
    assert (training[0].event == 0).any()


def test_test_outcomes_cannot_change_fitted_features_or_prediction_inputs(canonical, recording_fit, tmp_path):
    path, table = canonical
    training, invoices = recording_fit
    evaluate(path, tmp_path/'first', folds=1, source_kind='synthetic')
    first_training = training[0].copy()
    first_features = [(row['invoice_id'], row['past_delay'], row['prior_count']) for row in invoices]
    origin = list(forward_splits(table, 1))[0][1]
    table.loc[table.issue_date >= origin, 'duration'] = 1000
    changed_payments = (table.issue_date >= origin) & table.event.eq(1)
    table.loc[changed_payments, 'paid_date'] = table.loc[changed_payments, 'due_date']+pd.Timedelta(days=1000)
    table.loc[table.issue_date >= origin, 'past_delay'] = -99999
    table.to_csv(path, index=False)
    training.clear()
    invoices.clear()
    evaluate(path, tmp_path/'second', folds=1, source_kind='synthetic')
    pd.testing.assert_frame_equal(training[0], first_training)
    assert [(row['invoice_id'], row['past_delay'], row['prior_count']) for row in invoices] == first_features


def test_source_snapshot_recensors_future_payments(canonical):
    _, table = canonical
    table.loc[0, 'duration'] = 10000
    result = _outcomes(table)
    assert result.loc[0, 'event'] == 0
    assert result.loc[0, '_observed_end'] == pd.Timestamp(table.loc[0, 'as_of'])
    assert pd.isna(result.loc[0, 'paid_date'])


def test_predictions_and_baselines_cannot_pay_before_invoice_issue(canonical, tmp_path, monkeypatch):
    from ml.delay_model import DelayModel
    path, table = canonical
    # Long historical terms permit early payments, but the held-out short terms
    # cannot inherit a customer median date before the new invoice even exists.
    training = np.arange(len(table)) < 28
    table['due_date'] = table.issue_date+pd.to_timedelta(np.where(training, 30, 5), unit='D')
    table['duration'] = np.where(training, -20., 0.)
    table['paid_date'] = table.due_date+pd.to_timedelta(table.duration, unit='D')
    table.loc[table.event == 0, 'duration'] = (pd.Timestamp('2021-03-01')-table.loc[table.event == 0, 'due_date']).dt.days
    table.loc[table.event == 0, 'paid_date'] = pd.NaT
    table.to_csv(path, index=False)
    model = object.__new__(DelayModel)
    model.shift = 20
    model._distribution = lambda invoice, customer: (10., 1.)
    module = importlib.import_module('ml.evaluate')
    monkeypatch.setattr(module, 'fit', lambda *args, **kwargs: model)
    result = evaluate(path, tmp_path/'conditional', folds=1, source_kind='synthetic')
    # Exponential shifted by -20 has unconditional median -13.07, before issue
    # at delay -5. Its conditional median must instead be -5+10*log(2).
    survival_mae = result[(result.model == 'survival') & (result.metric == 'mae_paid_days')].predicted.iloc[0]
    assert survival_mae == pytest.approx(-5+10*np.log(2))
    median_mae = result[(result.model == 'customer_median') & (result.metric == 'mae_paid_days')].predicted.iloc[0]
    assert median_mae == 5  # Historical -20 is clamped to the issue boundary -5.
    probability = result[(result.model == 'survival') & (result.metric == 'share_paid_ipcw') & (result.offset_days == 10)].predicted.iloc[0]
    assert probability == pytest.approx(1-np.exp(-15/10))


def test_report_records_provenance_counts_support_and_smoke_labels(canonical, recording_fit, tmp_path):
    path, _ = canonical
    destination = tmp_path/'evidence'
    result = evaluate(path, destination, source_kind='synthetic', seed=19)
    assert len(result) == 99  # Three models * (MAE + five Brier + five share rows) * three folds.
    assert set(result.model) == {'naive', 'customer_median', 'survival'}
    assert set(result.metric) == {'mae_paid_days', 'brier_ipcw', 'share_paid_ipcw'}
    assert result.evidence_status.eq('synthetic_pipeline_smoke_only').all()
    assert result.validation_status.eq('not_validated_on_representative_real_businesses').all()
    unsupported = result[(result.metric == 'brier_ipcw') & result.status.str.startswith('unsupported')]
    assert len(unsupported) and unsupported.predicted.isna().all()
    assert result[result.metric == 'mae_paid_days'].status.eq('selection_biased_paid_only').all()
    report = json.loads((destination/'report.json').read_text())
    assert report['completed_folds'] == 3 and report['seed'] == 19
    assert report['source']['sha256'] == hashlib.sha256(path.read_bytes()).hexdigest()
    assert report['source']['source_provenance'] == ['Fictional deterministic test fixture, no real business observations']
    assert report['source']['observation_date_start'] == report['source']['observation_date_end'] == '2021-03-01'
    assert report['source']['observed_paid']+report['source']['censored'] == report['source']['invoice_rows']
    assert report['folds'][0]['amount_feature_used'] is False
    assert report['folds'][0]['test_start'] <= report['folds'][0]['test_end']
    assert report['folds'][0]['train_paid']+report['folds'][0]['train_censored'] == report['folds'][0]['train_n']
    assert (destination/'calibration.png').is_file() and (destination/'metrics.csv').is_file()


def test_synthetic_metadata_cannot_be_relabelled_unverified(canonical, tmp_path):
    path, _ = canonical
    with pytest.raises(ValueError, match='Synthetic metadata'):
        evaluate(path, tmp_path/'evidence', source_kind='unverified')


def test_small_or_failed_folds_are_reported_not_presented_as_success(canonical, recording_fit, tmp_path, monkeypatch):
    path, table = canonical
    table.iloc[:8].to_csv(path, index=False)
    result = evaluate(path, tmp_path/'small', source_kind='synthetic')
    assert result.metric.eq('fold_status').all()
    assert json.loads((tmp_path/'small'/'report.json').read_text())['completed_folds'] == 0
    table.to_csv(path, index=False)
    module = importlib.import_module('ml.evaluate')
    def failure(*args, **kwargs):
        raise ValueError('Synthetic test fit failure')
    monkeypatch.setattr(module, 'fit', failure)
    failed = evaluate(path, tmp_path/'failure', source_kind='synthetic')
    assert failed.status.eq('fit_failed').all()
    assert json.loads((tmp_path/'failure'/'report.json').read_text())['completed_folds'] == 0


@pytest.mark.parametrize('folds', [0, 11])
def test_invalid_split_count_rejected(canonical, tmp_path, folds):
    with pytest.raises(ValueError, match='folds'):
        evaluate(canonical[0], tmp_path, folds=folds)


def test_cli_returns_failure_when_all_folds_are_skipped(canonical, tmp_path):
    path, table = canonical
    table.iloc[:8].to_csv(path, index=False)
    destination = tmp_path/'cli-skipped'
    completed = subprocess.run([sys.executable, '-m', 'ml.evaluate', str(path), '--source-kind', 'synthetic',
        '--output', str(destination)], capture_output=True, text=True, check=False)
    assert completed.returncode == 2
    assert 'No forward fold completed' in completed.stderr
    assert json.loads((destination/'report.json').read_text())['completed_folds'] == 0
    assert (destination/'metrics.csv').is_file()
