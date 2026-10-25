import numpy as np
import pytest

from ml.delay_model import fit
from ml.tests.test_pipeline import business


def test_conditional_probability_quantile_consistency():
    data = business()
    model = fit(data, use_saved=False)
    invoice, customer = data['invoices'][-1], data['customers'][0]
    for elapsed in [-30, 0, 40]:
        for probability in [.7, .9]:
            delay = model.conditional_quantile(invoice, customer, probability, elapsed)
            assert delay > elapsed
            actual = model.conditional_cdf(invoice, customer, [delay-elapsed], elapsed)[0]
            assert actual == pytest.approx(probability)
        assert model.conditional_cdf(invoice, customer, [0], elapsed)[0] == 0
        a, b = np.random.default_rng(42), np.random.default_rng(42)
        draws = [model.sample_after(invoice, customer, a, elapsed) for _ in range(30)]
        assert draws == [model.sample_after(invoice, customer, b, elapsed) for _ in range(30)]
        assert min(draws) > elapsed


def test_private_artifact_reloads_without_global_model(tmp_path, monkeypatch):
    from ml import personalization, delay_model
    monkeypatch.setattr(personalization, 'ARTIFACT_ROOT', tmp_path)
    data = business()
    first = personalization.get_model(data, 'owner-one')
    assert first['status'] == 'ready'
    personalization._cache.clear()
    def must_not_refit(table):
        raise AssertionError('Expected saved tenant model')
    monkeypatch.setattr(personalization, 'DelayModel', must_not_refit)
    reloaded = personalization.get_model(data, 'owner-one')
    invoice, customer = data['invoices'][-1], data['customers'][0]
    assert first['model'].sample_delay(invoice, customer, np.random.default_rng(20)) == reloaded['model'].sample_delay(invoice, customer, np.random.default_rng(20))
    # Scope is taken from the authenticated server route; fit must ignore the shared artifact.
    monkeypatch.setattr(delay_model, 'DEFAULT_ARTIFACT', tmp_path / 'invalid-shared.joblib')
    delay_model.DEFAULT_ARTIFACT.write_bytes(b'not a valid pickle')
    assert delay_model.fit(dict(data, _model_scope='owner-one')) is reloaded['model']


def test_model_still_works_without_writable_artifact_store(tmp_path, monkeypatch):
    from ml import personalization
    blocked = tmp_path / 'not-a-directory'
    blocked.write_text('file blocks artifact directory')
    monkeypatch.setattr(personalization, 'ARTIFACT_ROOT', blocked)
    result = personalization.get_model(business(), 'owner')
    assert result['status'] == 'ready'
    assert result['persisted'] is False
