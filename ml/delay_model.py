"""Weibull AFT with a censored segment-only fallback for sparse customers."""
import numpy as np
import pandas as pd
import joblib
from pathlib import Path
from collections import OrderedDict
from lifelines import WeibullAFTFitter
from .data import amount_feature_metadata, build_training_table, validate_table

_active = None
DEFAULT_ARTIFACT = Path(__file__).resolve().parent / 'artifacts' / 'delay_model.joblib'
FEATURE_POLICY_VERSION = 2


class DelayModel:
    def __init__(self, table):
        self.table = validate_table(table)
        self.feature_policy_version = FEATURE_POLICY_VERSION
        policy = amount_feature_metadata(self.table)
        self.amount_feature_used = policy['amount_feature_used']
        self.amount_feature_policy = policy['amount_feature_policy']
        self.amount_currency = policy['currencies'][0] if self.amount_feature_used else None
        if self.table.empty or not self.table.event.any():
            raise ValueError('Training requires at least one observed payment')
        self.shift = max(1., 1. - float(self.table.duration.min()))
        self.counts = self.table[self.table.event == 1].groupby('customer_id').size().to_dict()
        self.segments = sorted(self.table.segment.unique())
        self.segment_models = {}
        for segment, group in self.table.groupby('segment'):
            if group.event.any():
                # An intercept-only censored fit: its Weibull mean is the segment average.
                frame = pd.DataFrame({'T': group.duration + self.shift, 'E': group.event})
                self.segment_models[segment] = WeibullAFTFitter(penalizer=.1).fit(frame, 'T', 'E')
        self.global_model = WeibullAFTFitter(penalizer=.1).fit(
            pd.DataFrame({'T': self.table.duration + self.shift, 'E': self.table.event}), 'T', 'E')
        x = self._encode(self.table)
        self.columns = [col for col in x if x[col].nunique() > 1]
        x = x[self.columns].copy()
        x['T'], x['E'] = self.table.duration + self.shift, self.table.event
        self.aft = (WeibullAFTFitter(penalizer=.1).fit(x, 'T', 'E')
                    if len(self.table) >= 3 else self.global_model)

    def _encode(self, table):
        x = pd.DataFrame(index=table.index)
        if self.amount_feature_used:
            x['log_amount'] = np.log1p(table.amount.clip(lower=0))
        x['issue_month'] = table.issue_month
        x['past_delay'] = table.past_delay
        x['prior_count'] = table.prior_count
        for segment in self.segments[1:]:
            x['segment_' + segment] = (table.segment == segment).astype(float)
        return x

    def _distribution(self, invoice, customer):
        # A forecast samples each invoice hundreds of times. Only the random
        # draw changes; compute its parameters once. Bound memory for long runs.
        supplied_currency = invoice.get('currency')
        if self.amount_feature_used and supplied_currency and str(supplied_currency).upper() != self.amount_currency:
            raise ValueError('Invoice currency differs from the model amount units')
        key = (str(customer.get('id', invoice.get('customer_id', ''))),
               customer.get('segment', invoice.get('segment', 'unknown')),
               str(invoice['issue_date']), float(invoice.get('model_amount', invoice['amount'])),
               invoice.get('past_delay'), invoice.get('prior_count'))
        if not hasattr(self, '_parameter_cache'):
            self._parameter_cache = OrderedDict()
        cached = self._parameter_cache.get(key)
        if cached is not None:
            return cached
        result = self._compute_distribution(invoice, customer)
        self._parameter_cache[key] = result
        if len(self._parameter_cache) > 4096:
            self._parameter_cache.popitem(last=False)
        return result

    def _compute_distribution(self, invoice, customer):
        cid = str(customer.get('id', invoice.get('customer_id', '')))
        segment = customer.get('segment', invoice.get('segment', 'unknown'))
        issue = pd.Timestamp(invoice['issue_date'])
        past = self.table[(self.table.customer_id == cid) & (self.table.event == 1)]
        if 'paid_date' in past:
            past = past[pd.to_datetime(past.paid_date) < issue]
        else:
            past = past[past.due_date + pd.to_timedelta(past.duration, unit='D') < issue]
        row = pd.DataFrame([dict(segment=segment, amount=invoice.get('model_amount', invoice['amount']), issue_month=issue.month,
                                 past_delay=invoice.get('past_delay', past.duration.mean() if len(past) else 0.),
                                 prior_count=invoice.get('prior_count', len(past)))])
        if self.counts.get(cid, 0) < 3:
            model = self.segment_models.get(segment, self.global_model)
            x = pd.DataFrame(index=[0])
        else:
            model, x = self.aft, self._encode(row)[self.columns]
        # lifelines percentile gives lambda at survival probability exp(-1).
        scale = float(model.predict_percentile(x, p=np.exp(-1)).iloc[0])
        shape = float(np.exp(model.params_.loc[('rho_', 'Intercept')]))
        if not np.isfinite([scale, shape]).all() or min(scale, shape) <= 0:
            raise ValueError('Invalid fitted payment distribution')
        return scale, shape

    def conditional_quantile(self, invoice, customer, probability, elapsed_days):
        """Delay quantile given no payment by elapsed_days relative to due date."""
        if not 0 < probability < 1:
            raise ValueError('probability must be between zero and one')
        scale, shape = self._distribution(invoice, customer)
        hazard = (max(elapsed_days + self.shift, 0.) / scale) ** shape
        return scale * (hazard - np.log1p(-probability)) ** (1. / shape) - self.shift

    def conditional_cdf(self, invoice, customer, future_days, elapsed_days):
        scale, shape = self._distribution(invoice, customer)
        start = max(elapsed_days + self.shift, 0.)
        end = np.maximum(elapsed_days + np.asarray(future_days) + self.shift, start)
        return -np.expm1(-np.maximum((end / scale) ** shape - (start / scale) ** shape, 0.))

    def cdf(self, invoice, customer, offsets):
        scale, shape = self._distribution(invoice, customer)
        t = np.maximum(np.asarray(offsets, dtype=float) + self.shift, 0.)
        return -np.expm1(-np.power(t / scale, shape))

    def sample_delay(self, invoice, customer, rng, days_overdue=0):
        scale, shape = self._distribution(invoice, customer)
        # Zero means unconditional (including early payments); positive means still unpaid.
        lower = days_overdue + self.shift if days_overdue > 0 else 0.
        hazard = (max(lower, 0.) / scale) ** shape
        t = scale * (hazard + rng.exponential()) ** (1. / shape)
        return max(int(np.ceil(-self.shift)), int(days_overdue) if days_overdue > 0 else int(np.ceil(-self.shift)),
                   int(np.ceil(t - self.shift)))

    def sample_after(self, invoice, customer, rng, elapsed_days):
        """Sample given still unpaid at as_of, including invoices not yet due."""
        scale, shape = self._distribution(invoice, customer)
        hazard = (max(elapsed_days + self.shift, 0.) / scale) ** shape
        delay = scale * (hazard + rng.exponential()) ** (1. / shape) - self.shift
        return max(int(np.floor(elapsed_days))+1, int(np.ceil(-self.shift)), int(np.ceil(delay)))


def fit(table=None, *, use_saved=True, artifact_path=None):
    """Load the persisted model when present; otherwise fit the supplied data.

    Pass use_saved=False for training or held-out evaluation to avoid loading
    a model trained on a different observation window.
    """
    global _active
    if isinstance(table, dict) and table.get('_model_scope'):
        from .personalization import get_model
        result = get_model(table, table['_model_scope'])
        if result['model'] is None:
            raise ValueError(result['message'])
        _active = result['model']
        return _active
    path = Path(artifact_path) if artifact_path is not None else DEFAULT_ARTIFACT
    if use_saved and path.is_file():
        model = joblib.load(path)
        if not isinstance(model, DelayModel):
            raise ValueError(f'Invalid delay model artifact: {path}')
        compatible = getattr(model, 'feature_policy_version', None) == FEATURE_POLICY_VERSION
        if compatible and model.amount_feature_used and table is not None:
            if not isinstance(table, pd.DataFrame):
                table = build_training_table(table)
            else:
                table = validate_table(table)
            requested_policy = amount_feature_metadata(table)
            compatible = (requested_policy['amount_feature_used'] and
                          requested_policy['currencies'] == [model.amount_currency])
        if compatible:
            _active = model
            return model
        if table is None:
            raise ValueError('Saved model predates the safe amount-feature policy; retrain with python -m ml.train --csv PATH')
        # Do not silently reuse a legacy artifact trained on unknown/mixed units.
    if table is None:
        raise ValueError('Supply training data or run python -m ml.train --csv PATH first')
    if not isinstance(table, pd.DataFrame):
        table = build_training_table(table)
    model = DelayModel(table)
    _active = model
    return model


def sample_delay(invoice, customer, rng, days_overdue=0):
    if _active is None:
        raise RuntimeError('Call fit first')
    return _active.sample_delay(invoice, customer, rng, days_overdue)
