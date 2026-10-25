"""Nominal amounts are never model inputs without an explicit unit policy."""
from copy import deepcopy

import joblib
import numpy as np
import pandas as pd
import pytest

from ml import delay_model, personalization
from ml.data import amount_feature_metadata, build_training_table, load_csv
from ml.delay_model import FEATURE_POLICY_VERSION, fit
from ml.tests.test_pipeline import business
from ml.train import training_table_from_csv


def declared_business():
    data = business()
    data.update(currency='INR', amount_unit_verified=True, amount_semantics='original_invoice_amount',
        currency_provenance='owner_confirmed_INR', source_kind='owner_entered',
        source_provenance='Owner-declared invoice upload; not independently verified',
        observation_date_source='owner_supplied')
    return data


@pytest.mark.parametrize('metadata', [
    {},
    {'currency': 'INR'},
    {'currency': 'INR', 'amount_unit_verified': 'False', 'amount_semantics': 'original_invoice_amount'},
    {'currency': 'INR', 'amount_unit_verified': True, 'amount_semantics': 'outstanding_balance'},
    {'currency': 'UNKNOWN', 'amount_unit_verified': True, 'amount_semantics': 'original_invoice_amount'},
])
def test_unconfirmed_units_or_semantics_exclude_amount(metadata):
    data = business()
    data.update(metadata)
    model = fit(data, use_saved=False)
    assert model.amount_feature_used is False
    assert 'log_amount' not in model.columns
    invoice, customer = data['invoices'][-1], data['customers'][0]
    a = model._distribution(dict(invoice, amount=1), customer)
    b = model._distribution(dict(invoice, amount=10_000_000), customer)
    np.testing.assert_array_equal(a, b)


def test_explicit_single_unit_original_amount_can_be_used():
    model = fit(declared_business(), use_saved=False)
    assert model.amount_feature_used is True
    assert 'log_amount' in model.columns
    assert 'INR' in model.amount_feature_policy
    invoice = dict(business()['invoices'][-1], currency='USD')
    with pytest.raises(ValueError, match='currency differs'):
        model.sample_delay(invoice, business()['customers'][0], np.random.default_rng(1))


def test_mixed_currency_amounts_are_excluded_even_with_confirmation():
    data = declared_business()
    data['invoices'][0]['currency'] = 'USD'
    model = fit(data, use_saved=False)
    assert model.amount_feature_used is False
    assert 'mixed or unknown' in model.amount_feature_policy


def test_canonical_metadata_round_trips_without_trusting_a_currency_label(tmp_path):
    path = tmp_path / 'canonical.csv'
    table = build_training_table(declared_business())
    table.to_csv(path, index=False)
    loaded = load_csv(path)
    assert amount_feature_metadata(loaded)['amount_feature_used'] is True
    assert loaded.currency_provenance.unique().tolist() == ['owner_confirmed_INR']
    assert loaded.source_kind.unique().tolist() == ['owner_entered']
    assert loaded.observation_date_source.unique().tolist() == ['owner_supplied']
    # Old canonical schemas remain readable but cannot authorize the amount feature.
    table.drop(columns=['amount_unit_verified', 'amount_semantics']).to_csv(path, index=False)
    assert amount_feature_metadata(load_csv(path))['amount_feature_used'] is False


def test_invalid_boolean_metadata_is_not_treated_as_truthy(tmp_path):
    table = build_training_table(business())
    table['amount_unit_verified'] = 'unverified'
    path = tmp_path / 'invalid.csv'
    table.to_csv(path, index=False)
    with pytest.raises(ValueError, match='true or false'):
        load_csv(path)


def test_raw_currency_provenance_and_duplicates_survive_canonical_csv(tmp_path):
    raw = pd.DataFrame([
        dict(business_code='X', cust_number='001', doc_id='1', posting_date='1/1/2020',
             due_in_date='20200110', clear_date='1/15/2020', isOpen='0', total_open_amount='100', invoice_currency='USD'),
        dict(business_code='X', cust_number='001', doc_id='2', posting_date='1/12/2020',
             due_in_date='20200120', clear_date=None, isOpen='1', total_open_amount='200', invoice_currency='CAD'),
    ])
    raw = pd.concat([raw, raw.iloc[:1]], ignore_index=True)
    source = tmp_path / 'raw.csv'
    raw.to_csv(source, index=False)
    adapted = training_table_from_csv(source, as_of='2020-01-30')
    assert adapted.currency.tolist() == ['USD', 'CAD']
    assert adapted.amount.tolist() == [100, 200]  # No guessed conversion.
    assert not adapted.amount_unit_verified.any()
    assert adapted.amount_semantics.unique().tolist() == ['unknown']
    canonical = tmp_path / 'canonical.csv'
    adapted.to_csv(canonical, index=False)
    loaded = load_csv(canonical)
    assert loaded.attrs['source_rows'] == 3 and loaded.attrs['duplicates_removed'] == 1
    assert loaded.source_kind.unique().tolist() == ['unverified_export']
    assert loaded.observation_date_source.unique().tolist() == ['explicit_user_snapshot']
    assert 'not verified' in loaded.source_provenance.iloc[0]
    assert amount_feature_metadata(loaded)['amount_feature_used'] is False


def test_legacy_shared_artifact_requires_safe_refit(tmp_path):
    table = build_training_table(business())
    legacy = fit(table, use_saved=False)
    del legacy.feature_policy_version
    path = tmp_path / 'legacy.joblib'
    joblib.dump(legacy, path)
    with pytest.raises(ValueError, match='retrain'):
        fit(artifact_path=path)
    fresh = fit(table, artifact_path=path)
    assert fresh.feature_policy_version == FEATURE_POLICY_VERSION
    assert fresh.amount_feature_used is False
    assert fresh is not legacy


def test_saved_unit_sensitive_model_is_not_used_with_unknown_or_foreign_units(tmp_path):
    model = fit(declared_business(), use_saved=False)
    path = tmp_path / 'inr.joblib'
    joblib.dump(model, path)
    unknown = fit(business(), artifact_path=path)
    assert unknown.amount_feature_used is False
    foreign = declared_business()
    foreign['currency'] = 'USD'
    usd = fit(foreign, artifact_path=path)
    assert usd.amount_currency == 'USD'


def test_business_unit_policy_changes_invalidate_private_artifacts(tmp_path, monkeypatch):
    monkeypatch.setattr(personalization, 'ARTIFACT_ROOT', tmp_path)
    old = business()
    old['currency'] = 'INR'  # A historical currency label is not confirmation.
    untouched = deepcopy(old)
    first = personalization.get_model(old, 'owner')
    second = personalization.get_model(declared_business(), 'owner')
    assert first['status'] == second['status'] == 'ready'
    assert first['amount_feature_used'] is False
    assert second['amount_feature_used'] is True
    assert first['fingerprint'] != second['fingerprint']
    assert second['validation_status'] == 'not_validated_on_representative_real_businesses'
    assert second['source_kind'] == 'owner_entered'
    assert old == untouched
    assert personalization.public_status(second)['amount_feature_used'] is True


def test_private_artifact_with_legacy_feature_policy_is_refitted(tmp_path, monkeypatch):
    monkeypatch.setattr(personalization, 'ARTIFACT_ROOT', tmp_path)
    data = business()
    first = personalization.get_model(data, 'owner')
    artifact = tmp_path / first['scope'] / 'delay_model.joblib'
    saved = joblib.load(artifact)
    del saved['model'].feature_policy_version
    joblib.dump(saved, artifact)
    personalization._cache.clear()
    result = personalization.get_model(data, 'owner')
    assert result['model'].feature_policy_version == FEATURE_POLICY_VERSION
