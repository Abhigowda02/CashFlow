"""Private per-business fits. No mixing with the shared offline training artifact."""
from collections import OrderedDict
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import tempfile
from pickle import UnpicklingError
from threading import RLock
import warnings

import joblib

from .data import METADATA_DEFAULTS, amount_feature_metadata, build_training_table
from .delay_model import DelayModel, FEATURE_POLICY_VERSION

ARTIFACT_ROOT = Path(os.environ.get('PAYMENT_MODEL_DIR', Path(__file__).resolve().parent / 'artifacts' / 'businesses'))
MIN_PAID = 10
MIN_INVOICES = 20
MODEL_VERSION = 2
_cache = OrderedDict()
_cache_lock = RLock()
_locks = [RLock() for _ in range(32)]


def training_snapshot(business):
    snapshot = dict(as_of=business['as_of'], customers=[
        {'id': c['id'], 'segment': c.get('segment', 'unknown')} for c in business['customers']], invoices=[])
    snapshot.update({column: business.get(column, default) for column, default in METADATA_DEFAULTS.items()})
    for invoice in business['invoices']:
        row = dict(id=invoice['id'], customer_id=invoice['customer_id'],
            amount=invoice.get('model_amount', invoice['amount']), issue_date=invoice['issue_date'],
            due_date=invoice['due_date'], status=invoice['status'], paid_date=invoice.get('paid_date'))
        row.update({column: invoice[column] for column in METADATA_DEFAULTS if column in invoice})
        snapshot['invoices'].append(row)
    snapshot['customers'].sort(key=lambda row: row['id'])
    snapshot['invoices'].sort(key=lambda row: row['id'])
    return snapshot


def get_model(business, business_id, force=False):
    scope = hashlib.sha256(str(business_id).encode()).hexdigest()
    snapshot = training_snapshot(business)
    fingerprint = hashlib.sha256(json.dumps([MODEL_VERSION, snapshot], sort_keys=True).encode()).hexdigest()
    # Include the store root so tests and different local stores never reuse a fit.
    key = (str(ARTIFACT_ROOT.resolve()), scope)
    path = ARTIFACT_ROOT / scope / 'delay_model.joblib'
    with _locks[int(scope[:8], 16) % len(_locks)]:
        with _cache_lock:
            cached = _cache.get(key)
        if not force and cached and cached['fingerprint'] == fingerprint:
            return cached
        if not force and path.is_file():
            try:
                saved = joblib.load(path)
                compatible = saved['model'] is None or getattr(saved['model'], 'feature_policy_version', None) == FEATURE_POLICY_VERSION
                if saved['fingerprint'] == fingerprint and saved['scope'] == scope and compatible:
                    _remember(key, saved)
                    return saved
            except (OSError, ValueError, KeyError, EOFError, ImportError, AttributeError, TypeError, UnpicklingError):
                pass  # Refit a missing/incompatible local artifact from this tenant only.
        table = build_training_table(snapshot)
        paid = int(table.event.sum())
        amount_policy = amount_feature_metadata(table)
        result = dict(scope=scope, fingerprint=fingerprint, invoice_count=len(table), paid_count=paid,
                      censored_count=len(table)-paid, model=None, trained_at=None,
                      checked_at=datetime.now(timezone.utc).isoformat(), status='insufficient_history',
                      amount_feature_used=False, amount_feature_policy=amount_policy['amount_feature_policy'],
                      currencies=amount_policy['currencies'], source_kind=snapshot['source_kind'],
                      source_provenance=snapshot['source_provenance'],
                      validation_status='not_validated_on_representative_real_businesses',
                      message=f'Need at least {MIN_INVOICES} invoices and {MIN_PAID} observed payments for a business model.')
        if len(table) >= MIN_INVOICES and paid >= MIN_PAID:
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter('ignore')
                    model = DelayModel(table)
                result.update(model=model, status='ready', message='Fitted to this business only; predictive accuracy is not yet validated.',
                              amount_feature_used=model.amount_feature_used,
                              trained_at=datetime.now(timezone.utc).isoformat())
            except (ValueError, ArithmeticError, RuntimeError):
                result.update(status='fit_failed', message='The model could not be fitted reliably. Historical-delay forecasts remain available.')
        temp = None
        result['persisted'] = True
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            descriptor, temp = tempfile.mkstemp(dir=path.parent, suffix='.tmp')
            os.close(descriptor)
            joblib.dump(result, temp, compress=3)
            os.replace(temp, path)
        except OSError:
            result['persisted'] = False  # Read-only deployments can safely refit after restart.
        finally:
            if temp is not None and os.path.exists(temp):
                try:
                    os.unlink(temp)
                except OSError:
                    pass
        _remember(key, result)
        return result


def _remember(key, result):
    with _cache_lock:
        _cache[key] = result
        _cache.move_to_end(key)
        while len(_cache) > 32:
            _cache.popitem(last=False)


def public_status(result):
    return {key: result[key] for key in ['status', 'message', 'fingerprint', 'invoice_count',
            'paid_count', 'censored_count', 'trained_at', 'checked_at', 'amount_feature_used',
            'amount_feature_policy', 'currencies', 'source_kind', 'source_provenance', 'validation_status']}
