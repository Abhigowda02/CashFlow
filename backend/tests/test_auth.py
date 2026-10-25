import time
import pytest

from fastapi.testclient import TestClient
from sqlalchemy import select, update

from backend import auth, database as db
from backend.main import app
from backend.tests.conftest import signed_in_client
from backend.tests.test_ledger_api import payload


def test_no_anonymous_business_access():
    client = TestClient(app)
    for path in ['business', 'forecast', 'ledger', 'actions', 'expenses', 'collections', 'customers']:
        assert client.get('/api/'+path).status_code == 401
    assert client.post('/api/import', json=payload()).status_code == 401


def test_onboarding_login_logout_and_cookie_flags():
    client = signed_in_client(onboard=False)
    assert client.get('/api/auth/me').json()['onboarding_required']
    assert client.get('/api/business').status_code == 409
    setup = dict(name='Actual business', as_of='2026-10-24', opening_cash=2000, safety_floor=500)
    assert client.post('/api/onboarding', json=setup).status_code == 200
    assert client.post('/api/onboarding', json=setup).status_code == 409
    business = client.get('/api/business').json()
    assert business['invoices'] == [] and business['opening_cash'] == 2000
    assert business['data_source'] == 'owner'
    cookie = client.cookies.get(auth.COOKIE)
    assert client.post('/api/auth/logout', json={}).status_code == 204
    assert client.get('/api/auth/me').status_code == 401
    # Replaying a revoked cookie must fail.
    client.cookies.set(auth.COOKIE, cookie)
    assert client.get('/api/business').status_code == 401
    client.cookies.clear()
    response = client.post('/api/auth/login', json={'email': 'OWNER@example.com', 'password': 'Cash!7'})
    assert response.status_code == 200
    assert not response.json()['onboarding_required']
    assert 'HttpOnly' in response.headers['set-cookie']
    assert 'SameSite=lax' in response.headers['set-cookie']
    assert response.headers['cache-control'] == 'no-store'


def test_tenant_isolation_even_with_reused_ids():
    alice, bob = signed_in_client('alice@example.com'), signed_in_client('bob@example.com')
    assert alice.business_id != bob.business_id
    assert alice.post('/api/import', json=payload()).status_code == 200
    assert bob.get('/api/ledger').json()['invoices'] == []
    assert bob.get('/api/business?business_id='+alice.business_id).json()['name'] == 'Owner workspace'
    receipt = dict(invoice_id='I1', receipt_id='same-key', amount=100, date='2026-10-24')
    assert bob.post('/api/receipts', json=receipt).status_code == 400
    request = payload()
    request['name'] = 'Bob business'
    request['opening_cash'] = 50
    assert bob.post('/api/import', json=request).status_code == 200
    assert alice.post('/api/receipts', json=receipt).status_code == 200
    assert bob.post('/api/receipts', json=receipt).status_code == 200
    assert alice.get('/api/business').json()['opening_cash'] == 10100
    assert bob.get('/api/business').json()['opening_cash'] == 150
    # Replacing one tenant's workspace must not clear another's receipt log.
    assert bob.post('/api/import', json=request).status_code == 200
    assert alice.post('/api/receipts', json=receipt).status_code == 200
    assert alice.get('/api/business').json()['opening_cash'] == 10100


def test_csrf_and_foreign_origins_are_rejected():
    client = signed_in_client()
    client.headers.pop('X-CSRF-Token')
    assert client.post('/api/import', json=payload()).status_code == 403
    client.headers['X-CSRF-Token'] = client.get('/api/auth/me').json()['csrf_token']
    client.headers['Origin'] = 'https://attacker.example'
    assert client.post('/api/import', json=payload()).status_code == 403
    assert client.post('/api/auth/login', json={'email': 'owner@example.com', 'password': 'Cash!7'}).status_code == 403


def test_session_expiration_and_password_storage():
    client = signed_in_client()
    raw_token = client.cookies.get(auth.COOKIE)
    with db.transaction() as connection:
        user = connection.execute(select(db.users)).mappings().one()
        assert user['password_hash'].startswith('$argon2id$')
        session = connection.execute(select(db.sessions)).mappings().one()
        assert session['token_hash'] != raw_token
        connection.execute(update(db.sessions).values(expires_at=int(time.time())-1))
    assert client.get('/api/auth/me').status_code == 401


def test_wrong_password_duplicate_account_and_throttling():
    client = signed_in_client()
    request = {'email': 'owner@example.com', 'password': 'Cash!7'}
    assert client.post('/api/auth/signup', json=request).status_code == 409
    wrong = dict(request, password='Wrong!7')
    for _ in range(10):
        assert client.post('/api/auth/login', json=wrong).status_code == 401
    assert client.post('/api/auth/login', json=wrong).status_code == 429


def test_secure_cookie_option(monkeypatch):
    monkeypatch.setattr(auth, 'SECURE_COOKIE', True)
    client = TestClient(app, headers={'Origin': 'http://localhost:5173'})
    response = client.post('/api/auth/signup', json={'email': 'secure@example.com', 'password': 'Cash!7'})
    assert response.status_code == 201
    assert 'Secure' in response.headers['set-cookie']


@pytest.mark.parametrize('password', ['abc!', 'NoSpecial7', 'TooLongPass!'])
def test_signup_enforces_password_length_and_special_character(password):
    client = TestClient(app, headers={'Origin': 'http://localhost:5173'})

    response = client.post('/api/auth/signup', json={
        'email': f'invalid-{len(password)}-{password[:2]}@example.com',
        'password': password,
    })

    assert response.status_code == 422


def test_signup_accepts_five_to_ten_character_password_with_special_character():
    client = TestClient(app, headers={'Origin': 'http://localhost:5173'})

    response = client.post('/api/auth/signup', json={
        'email': 'valid-password@example.com',
        'password': 'Cash!7',
    })

    assert response.status_code == 201


def test_existing_long_passwords_remain_usable_for_login():
    client = signed_in_client()
    legacy_password = 'A long legacy password!'
    with db.transaction() as connection:
        user = connection.execute(select(db.users)).mappings().one()
        connection.execute(update(db.users).where(db.users.c.id == user['id']).values(
            password_hash=auth.passwords.hash(legacy_password)))
    client.cookies.clear()

    response = client.post('/api/auth/login', json={
        'email': 'owner@example.com',
        'password': legacy_password,
    })

    assert response.status_code == 200


def test_production_refuses_development_database(monkeypatch):
    monkeypatch.setenv('APP_ENV', 'production')
    with pytest.raises(RuntimeError, match='Production requires DATABASE_URL'):
        with TestClient(app):
            pass
