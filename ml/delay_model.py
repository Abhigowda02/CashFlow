"""Weibull AFT with a censored segment-only fallback for sparse customers."""
import numpy as np
import pandas as pd
import joblib
from pathlib import Path
from lifelines import WeibullAFTFitter
from .data import build_training_table, validate_table

_active = None
DEFAULT_ARTIFACT = Path(__file__).resolve().parent / 'artifacts' / 'delay_model.joblib'


class DelayModel:
    def __init__(self, table):
        self.table = validate_table(table)
        if self.table.empty or not self.table.event.any():
            raise ValueError('Training requires at least one observed payment')
        self.shift = max(1., 1. - float(self.table.duration.min()))
        self.counts = self.table.groupby('customer_id').size().to_dict()
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
        x['log_amount'] = np.log1p(table.amount.clip(lower=0))
        x['issue_month'] = table.issue_month
        x['past_delay'] = table.past_delay
        x['prior_count'] = table.prior_count
        for segment in self.segments[1:]:
            x['segment_' + segment] = (table.segment == segment).astype(float)
        return x

    def _distribution(self, invoice, customer):
        cid = str(customer.get('id', invoice.get('customer_id', '')))
        segment = customer.get('segment', invoice.get('segment', 'unknown'))
        issue = pd.Timestamp(invoice['issue_date'])
        past = self.table[(self.table.customer_id == cid) & (self.table.event == 1)]
        if 'paid_date' in past:
            past = past[pd.to_datetime(past.paid_date) < issue]
        else:
            past = past[past.due_date + pd.to_timedelta(past.duration, unit='D') < issue]
        row = pd.DataFrame([dict(segment=segment, amount=invoice['amount'], issue_month=issue.month,
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
        return scale, shape

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


def fit(table=None, *, use_saved=True, artifact_path=None):
    """Load the persisted model when present; otherwise fit the supplied data.

    Pass use_saved=False for training or held-out evaluation to avoid loading
    a model trained on a different observation window.
    """
    global _active
    path = Path(artifact_path) if artifact_path is not None else DEFAULT_ARTIFACT
    if use_saved and path.is_file():
        model = joblib.load(path)
        if not isinstance(model, DelayModel):
            raise ValueError(f'Invalid delay model artifact: {path}')
        _active = model
        return model
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
