"""Forward-in-time, censor-aware evidence: python -m ml.evaluate CANONICAL.csv."""
import argparse
import hashlib
from importlib.metadata import version
import json
from pathlib import Path
import platform

import numpy as np
import pandas as pd

from .data import load_csv
from .delay_model import fit

OFFSETS = [10, 20, 30, 45, 60]
VALIDATION_STATUS = 'not_validated_on_representative_real_businesses'
MIN_CENSOR_SURVIVAL = .05
LIMITATIONS = [
    'Synthetic data is a pipeline smoke test, never evidence of predictive accuracy.',
    'No dataset here establishes validation on representative real businesses.',
    'IPCW assumes independent censoring and a censoring distribution transferable from training to test; administrative or informative censoring can violate this.',
    'Unsupported horizons and censor-survival probabilities at or below 0.05 are unavailable, not zero-error results. We do not clip large weights.',
    'Paid-only MAE excludes unknown settlement times and is selection biased; it is secondary.',
    'Bootstrap intervals condition on the fitted model and training censoring estimate; they do not include fitting uncertainty, temporal dependence or censoring-model error.',
    'IPCW observed-share estimates and their intervals can exceed one in finite samples; they are not silently clipped.',
    'The exercise predicts invoice final-settlement delay at issue using history frozen at each origin; it does not validate cash-shortage probabilities or collection actions.',
]


def _outcomes(table):
    """Reconstruct observed end dates, respecting an available source snapshot."""
    table = table.copy()
    end = table.due_date+pd.to_timedelta(table.duration, unit='D')
    if 'as_of' in table:
        snapshot = pd.to_datetime(table.as_of, errors='raise')
        if snapshot.isna().any() or (snapshot < table.issue_date).any():
            raise ValueError('Every source observation date must be on/after issue_date')
        table['event'] = ((table.event == 1) & (end <= snapshot)).astype(int)
        end = end.where(end <= snapshot, snapshot)
    if (end < table.issue_date).any():
        raise ValueError('An observed payment/censoring date precedes invoice issue')
    table['duration'] = (end-table.due_date).dt.total_seconds()/86400
    table['_observed_end'] = end
    table['issue_month'] = table.issue_date.dt.month
    if 'paid_date' in table:
        table['paid_date'] = end.where(table.event == 1, pd.NaT)
    return table


def forward_splits(table, folds=3):
    """Expand training history; keep tied issue dates together and tests disjoint."""
    if not 1 <= folds <= 10:
        raise ValueError('folds must be between 1 and 10')
    if len(table) < 4:
        raise ValueError('Need at least four invoices for time evaluation')
    initial = .7 if folds == 1 else .5
    positions = np.linspace(initial, 1., folds+1)[:-1]
    origins = sorted({table.issue_date.iloc[min(int(len(table)*fraction), len(table)-1)] for fraction in positions})
    for number, origin in enumerate(origins, start=1):
        stop = origins[number] if number < len(origins) else None
        training = table[table.issue_date < origin].copy()
        testing = table[table.issue_date >= origin].copy()
        if stop is not None:
            testing = testing[testing.issue_date < stop].copy()
        yield number, origin, training, testing


def frozen_features(rows, observed_training, origin):
    """Ignore supplied history features; use payments known before min(issue, origin)."""
    rows = rows.copy()
    counts, averages = np.zeros(len(rows), dtype=int), np.zeros(len(rows), dtype=float)
    histories = {}
    for customer, paid in observed_training[observed_training.event == 1].groupby('customer_id'):
        paid = paid.sort_values('_observed_end', kind='stable')
        histories[customer] = (paid['_observed_end'].to_numpy(dtype='datetime64[ns]'),
                               np.r_[0., paid.duration.to_numpy(dtype=float).cumsum()])
    limits = np.minimum(rows.issue_date.to_numpy(dtype='datetime64[ns]'), origin.to_datetime64())
    for customer, indices in rows.groupby('customer_id', sort=False).indices.items():
        if customer not in histories:
            continue
        times, sums = histories[customer]
        previous = np.searchsorted(times, limits[indices], side='left')
        counts[indices] = previous
        averages[indices] = sums[previous]/np.maximum(previous, 1)
    rows['prior_count'], rows['past_delay'] = counts, averages
    rows['issue_month'] = rows.issue_date.dt.month
    return rows


class CensoringKM:
    """Training-only reverse Kaplan-Meier; event-before-censor ordering for ties."""
    def __init__(self, durations, events):
        durations, events = np.asarray(durations, dtype=float), np.asarray(events, dtype=bool)
        self.times, inverse, totals = np.unique(durations, return_inverse=True, return_counts=True)
        payments = np.bincount(inverse, weights=events, minlength=len(self.times))
        censored = totals-payments
        risk = len(durations)-np.r_[0, totals[:-1].cumsum()]-payments
        factors = 1-np.divide(censored, risk, out=np.zeros_like(payments), where=risk > 0)
        self.survival = np.cumprod(factors)
        self.max_followup = float(durations.max())

    def probability(self, times):
        indices = np.searchsorted(self.times, np.asarray(times, dtype=float), side='right')-1
        return np.where(indices >= 0, self.survival[np.maximum(indices, 0)], 1.)


def ipcw_contributions(censoring, durations, events, probabilities, horizon):
    """Unnormalised Graf IPCW contributions, averaged over the full test cohort."""
    durations, events = np.asarray(durations), np.asarray(events, dtype=bool)
    probabilities = np.asarray(probabilities, dtype=float)
    event_by = events & (durations <= horizon)
    beyond = durations > horizon
    g_horizon = float(censoring.probability(horizon))
    details = dict(n=len(durations), known_n=int((event_by | beyond).sum()),
        event_by_n=int(event_by.sum()), observed_beyond_n=int(beyond.sum()),
        censored_by_n=int((~events & ~beyond).sum()), censor_survival=g_horizon,
        train_max_followup=censoring.max_followup)
    if horizon >= censoring.max_followup:
        return None, None, dict(details, status='unsupported_training_followup')
    if g_horizon <= MIN_CENSOR_SURVIVAL+1e-12:
        return None, None, dict(details, status='unsupported_censoring_positivity')
    if details['known_n'] == 0:
        return None, None, dict(details, status='unavailable_no_known_test_outcomes')
    weights = np.zeros(len(durations), dtype=float)
    weights[event_by] = 1/censoring.probability(durations[event_by])
    weights[beyond] = 1/g_horizon
    losses = weights*np.where(event_by, (1-probabilities)**2, probabilities**2)
    outcome = weights*event_by
    details.update(status='ok', max_weight=float(weights.max(initial=0)),
        effective_n=float(weights.sum()**2/np.square(weights).sum()) if weights.any() else 0.)
    return losses, outcome, details


def cluster_interval(values, customers, *, bootstrap=200, seed=42):
    """Pointwise 95% cluster bootstrap, conditional on model/KM; no fake small-n CI."""
    values, customers = np.asarray(values, dtype=float), np.asarray(customers)
    groups, inverse = np.unique(customers, return_inverse=True)
    if len(values) < 20 or len(groups) < 5:
        return np.nan, np.nan, 'unavailable_small_sample'
    if bootstrap < 100:
        return np.nan, np.nan, 'unavailable_insufficient_bootstrap_replicates'
    counts = np.bincount(inverse, minlength=len(groups))
    sums = np.bincount(inverse, weights=values, minlength=len(groups))
    selected = np.random.default_rng(seed).integers(0, len(groups), size=(bootstrap, len(groups)))
    estimates = sums[selected].sum(axis=1)/counts[selected].sum(axis=1)
    lower, upper = np.quantile(estimates, [.025, .975])
    return float(lower), float(upper), 'conditional_customer_cluster_bootstrap_95pct'


def _source_details(path, table, source_kind):
    kinds = sorted(table.source_kind.astype(str).unique()) if 'source_kind' in table else ['unknown']
    synthetic = any('synthetic' in kind.lower() for kind in kinds)
    if synthetic and source_kind == 'unverified':
        raise ValueError('Synthetic metadata must remain explicitly synthetic')
    kind = 'synthetic' if source_kind == 'synthetic' or synthetic else 'unverified'
    details = dict(path=str(path), sha256=hashlib.sha256(Path(path).read_bytes()).hexdigest(),
        source_kind=kind, input_source_kinds=kinds,
        evidence_status='synthetic_pipeline_smoke_only' if kind == 'synthetic' else VALIDATION_STATUS,
        invoice_rows=len(table), customer_count=int(table.customer_id.nunique()),
        observed_paid=int(table.event.sum()), censored=int(table.event.eq(0).sum()),
        issue_date_start=table.issue_date.min().date().isoformat(),
        issue_date_end=table.issue_date.max().date().isoformat())
    if 'as_of' in table:
        snapshot = pd.to_datetime(table.as_of)
        details.update(observation_date_start=snapshot.min().date().isoformat(),
                       observation_date_end=snapshot.max().date().isoformat())
    for field in ['source_provenance', 'observation_date_source', 'currency', 'currency_provenance',
                  'amount_unit_verified', 'amount_semantics', 'source_rows', 'duplicates_removed']:
        details[field] = sorted(table[field].dropna().astype(str).unique().tolist()) if field in table else ['unspecified']
    return details


def evaluate(path, output=None, *, folds=3, source_kind=None, bootstrap=200, seed=42):
    """Evaluate frozen-origin predictions; outputs are evidence descriptions, not claims."""
    if source_kind not in (None, 'synthetic', 'unverified'):
        raise ValueError('source_kind must be synthetic or unverified')
    if bootstrap < 0:
        raise ValueError('bootstrap must be nonnegative')
    table = _outcomes(load_csv(path)).sort_values('issue_date', kind='stable')
    source = _source_details(path, table, source_kind)
    records, fold_reports = [], []
    for fold, origin, train, test in forward_splits(table, folds):
        # The model cannot see a settlement on or after the forecast origin.
        train['event'] = ((train.event == 1) & (train['_observed_end'] < origin)).astype(int)
        train['_observed_end'] = train['_observed_end'].where(train['_observed_end'] < origin, origin)
        train['duration'] = (train['_observed_end']-train.due_date).dt.total_seconds()/86400
        if 'paid_date' in train:
            train['paid_date'] = train['_observed_end'].where(train.event == 1, pd.NaT)
        train = frozen_features(train, train, origin)
        test = frozen_features(test, train, origin)
        train_paid, test_paid = int(train.event.sum()), int(test.event.sum())
        context = dict(fold=fold, train_cutoff=origin.date().isoformat(), train_n=len(train), test_n=len(test),
            train_paid=train_paid, train_censored=len(train)-train_paid, test_paid=test_paid,
            train_start=train.issue_date.min().date().isoformat() if len(train) else None,
            train_end=train.issue_date.max().date().isoformat() if len(train) else None,
            test_censored=len(test)-test_paid, test_start=test.issue_date.min().date().isoformat() if len(test) else None,
            test_end=test.issue_date.max().date().isoformat() if len(test) else None,
            source=source['path'], source_sha256=source['sha256'], evidence_status=source['evidence_status'],
            validation_status=VALIDATION_STATUS)
        report = dict(context)
        fold_reports.append(report)
        reason = 'insufficient_training_rows' if len(train) < 10 else 'insufficient_test_rows' if len(test) < 3 else 'insufficient_observed_training_payments' if train_paid < 3 else None
        if reason:
            report['status'] = reason
            records.append(dict(context, model='all', metric='fold_status', status=reason, n=len(test)))
            continue
        # Drop internal outcome helper so its post-issue date cannot be used as a feature.
        training = train.drop(columns=['_observed_end'])
        try:
            model = fit(training, use_saved=False)
        except (ValueError, ArithmeticError, RuntimeError) as error:
            report.update(status='fit_failed', error=f'{type(error).__name__}: {str(error)[:240]}')
            records.append(dict(context, model='survival', metric='fold_status', status='fit_failed', n=len(test)))
            continue
        report.update(status='completed', amount_feature_used=bool(getattr(model, 'amount_feature_used', False)),
                      amount_feature_policy=getattr(model, 'amount_feature_policy', 'unspecified'))
        paid = train[train.event == 1]
        medians = paid.groupby('customer_id').duration.median()
        elapsed_at_issue = (test.issue_date-test.due_date).dt.total_seconds().to_numpy()/86400
        customer_baseline = np.maximum(test.customer_id.map(medians).fillna(float(paid.duration.median())).to_numpy(), elapsed_at_issue)
        probabilities, predictions = [], []
        for _, row in test.iterrows():
            invoice, customer = row.drop(labels=['_observed_end']).to_dict(), {'id': row.customer_id, 'segment': row.segment}
            elapsed = (row.issue_date-row.due_date).total_seconds()/86400
            # Payment cannot occur before issue: condition every model on that
            # same invoice-availability boundary, rather than evaluating an
            # unconditional shifted distribution with pre-issue probability mass.
            probabilities.append(model.conditional_cdf(invoice, customer, np.asarray(OFFSETS)-elapsed, elapsed))
            predictions.append(model.conditional_quantile(invoice, customer, .5, elapsed))
        probabilities = np.asarray(probabilities, dtype=float)
        if not np.isfinite(probabilities).all() or ((probabilities < 0) | (probabilities > 1)).any():
            raise ValueError(f'Fold {fold} produced invalid payment probabilities')
        forecasts = {'naive': np.maximum(np.zeros(len(test)), elapsed_at_issue), 'customer_median': customer_baseline,
                     'survival': np.asarray(predictions)}
        events, durations, customers = test.event.to_numpy(dtype=bool), test.duration.to_numpy(), test.customer_id.to_numpy()
        censoring = CensoringKM(train.duration, train.event)
        for name, prediction in forecasts.items():
            absolute = np.abs(prediction[events]-durations[events])
            lower, upper, interval = cluster_interval(absolute, customers[events], bootstrap=bootstrap, seed=seed+fold)
            records.append(dict(context, model=name, metric='mae_paid_days', offset_days=np.nan,
                predicted=float(absolute.mean()) if len(absolute) else np.nan, actual=np.nan, n=test_paid,
                status='selection_biased_paid_only' if test_paid else 'unavailable_no_observed_test_payments',
                ci_low=lower, ci_high=upper, ci_target='paid_only_mae', interval_status=interval))
            for column, horizon in enumerate(OFFSETS):
                probability = probabilities[:, column] if name == 'survival' else (prediction <= horizon).astype(float)
                losses, actual, support = ipcw_contributions(censoring, durations, events, probability, horizon)
                common = dict(context, **support, model=name, offset_days=horizon,
                              training_customer_clusters=int(train.customer_id.nunique()), test_customer_clusters=int(test.customer_id.nunique()))
                if losses is None:
                    records.extend([
                        dict(common, metric='brier_ipcw', predicted=np.nan, actual=np.nan, interval_status='unavailable_metric_support'),
                        dict(common, metric='share_paid_ipcw', predicted=float(probability.mean()), actual=np.nan,
                             interval_status='unavailable_metric_support'),
                    ])
                    continue
                lower, upper, interval = cluster_interval(losses, customers, bootstrap=bootstrap, seed=seed+fold)
                records.append(dict(common, metric='brier_ipcw', predicted=float(losses.mean()), actual=np.nan,
                    ci_low=lower, ci_high=upper, ci_target='brier_ipcw', interval_status=interval))
                lower, upper, interval = cluster_interval(actual, customers, bootstrap=bootstrap, seed=seed+fold)
                records.append(dict(common, metric='share_paid_ipcw', predicted=float(probability.mean()), actual=float(actual.mean()),
                    ci_low=lower, ci_high=upper, ci_target='actual_share_ipcw', interval_status=interval))
    result = pd.DataFrame(records)
    result.attrs['completed_folds'] = sum(item['status'] == 'completed' for item in fold_reports)
    destination = Path(output) if output else Path(__file__).parent/'results'
    destination.mkdir(parents=True, exist_ok=True)
    result.to_csv(destination/'metrics.csv', index=False)
    _calibration_plot(result, source, destination/'calibration.png')
    report = dict(source=source, validation_status=VALIDATION_STATUS, requested_folds=folds,
        emitted_folds=len(fold_reports), completed_folds=result.attrs['completed_folds'],
        folds=fold_reports, offsets_days=OFFSETS, bootstrap_replicates=bootstrap, seed=seed,
        censoring_method='training_reverse_KM_event_before_censor_ties', min_censor_survival=MIN_CENSOR_SURVIVAL,
        limitations=LIMITATIONS, outputs=['metrics.csv', 'calibration.png', 'report.json'],
        environment=dict(python=platform.python_version(), numpy=np.__version__, pandas=pd.__version__, lifelines=version('lifelines')))
    (destination/'report.json').write_text(json.dumps(report, indent=2, allow_nan=False)+'\n', encoding='utf-8')
    return result


def _calibration_plot(result, source, path):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    completed = sorted(result.loc[result.metric == 'share_paid_ipcw', 'fold'].unique())
    figure, axes = plt.subplots(1, max(1, len(completed)), figsize=(5*max(1, len(completed)), 4.5), squeeze=False)
    for axis, fold in zip(axes.ravel(), completed):
        data = result[(result.fold == fold) & (result.metric == 'share_paid_ipcw') & (result.status == 'ok')]
        for name, subset in data.groupby('model', sort=False):
            axis.plot(subset.offset_days, subset.predicted, marker='o', label=name)
        observed = data[data.model == 'naive']
        if not observed.empty:
            axis.plot(observed.offset_days, observed.actual, 'k--o', label='observed (IPCW estimate)')
            interval = observed.dropna(subset=['ci_low', 'ci_high'])
            if not interval.empty:
                axis.fill_between(interval.offset_days, interval.ci_low, interval.ci_high, color='grey', alpha=.15)
            axis.legend(fontsize=8)
        else:
            axis.text(.5, .5, 'No supported calibration horizons', transform=axis.transAxes, ha='center', wrap=True)
        axis.set(xlabel='Days after due date', ylabel='Share paid', title=f'Forward fold {fold}')
        axis.set_ylim(bottom=min(-.02, axis.get_ylim()[0]), top=max(1.02, axis.get_ylim()[1]))
    if not completed:
        axes[0, 0].text(.5, .5, 'No completed folds; see report.json', ha='center', va='center')
    label = 'Synthetic pipeline smoke only' if source['source_kind'] == 'synthetic' else 'Not validated on representative real businesses'
    figure.suptitle(label, fontsize=11)
    figure.text(.5, .015, 'Unsupported horizons omitted. IPCW assumptions and conditional CI limits: see report.json.', ha='center', fontsize=8)
    figure.tight_layout(rect=[0, .045, 1, .94])
    figure.savefig(path)
    plt.close(figure)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('csv_path')
    parser.add_argument('--output')
    parser.add_argument('--folds', type=int, default=3)
    parser.add_argument('--source-kind', choices=['synthetic', 'unverified'])
    parser.add_argument('--bootstrap', type=int, default=200)
    parser.add_argument('--seed', type=int, default=42)
    arguments = parser.parse_args()
    try:
        results = evaluate(arguments.csv_path, arguments.output, folds=arguments.folds,
                           source_kind=arguments.source_kind, bootstrap=arguments.bootstrap, seed=arguments.seed)
    except (ValueError, OSError) as error:
        parser.exit(2, f'Evaluation failed: {error}\n')
    print(results.to_string(index=False))
    print('Not yet validated on representative real businesses. See report.json for evidence limits.')
    if results.attrs['completed_folds'] == 0:
        parser.exit(2, 'No forward fold completed. Metrics and report.json were written with explicit failure/skip statuses.\n')
