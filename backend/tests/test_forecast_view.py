def test_forecast_view_is_tenant_scoped_and_honest(client, monkeypatch):
    monkeypatch.setenv('APP_FAKE_TODAY', '2026-10-25')
    response = client.get('/api/forecast/view')
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload['stale'] is True
    assert 'balance is old' in payload['headline'].lower()
    assert payload['warnings']
