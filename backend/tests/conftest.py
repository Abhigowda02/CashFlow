from fastapi.testclient import TestClient
import pytest
from backend import database
from backend.main import app


@pytest.fixture(autouse=True)
def isolated_database(tmp_path, monkeypatch):
    monkeypatch.setenv('APP_ENV', 'test')
    monkeypatch.setenv('APP_FAKE_TODAY', '2026-10-24')
    monkeypatch.setattr(database, 'DATABASE_URL', f'sqlite:///{(tmp_path / "saas.sqlite3").as_posix()}')
    from ml import personalization
    monkeypatch.setattr(personalization, 'ARTIFACT_ROOT', tmp_path / 'models')


def signed_in_client(email='owner@example.com', onboard=True):
    client = TestClient(app, headers={'Origin': 'http://localhost:5173'})
    response = client.post('/api/auth/signup', json={'email': email, 'password': 'Cash!7'})
    assert response.status_code == 201, response.text
    client.headers['X-CSRF-Token'] = response.json()['csrf_token']
    client.business_id = response.json()['business_id']
    if onboard:
        response = client.post('/api/onboarding', json={
            'name': 'Owner workspace', 'as_of': '2026-10-24', 'opening_cash': 0, 'safety_floor': 0})
        assert response.status_code == 200, response.text
    return client


@pytest.fixture
def client():
    return signed_in_client()
