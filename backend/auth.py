"""Password accounts and revocable, opaque server-side sessions."""
from dataclasses import dataclass
import hashlib
import os
import re
import secrets
import time
from uuid import uuid4

from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, InvalidHashError
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import case, delete, insert, select, update
from sqlalchemy.dialects.postgresql import insert as postgres_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.exc import IntegrityError

from . import database as db

COOKIE = 'cashflow_session'
SESSION_SECONDS = 7 * 24 * 60 * 60
SECURE_COOKIE = os.environ.get('COOKIE_SECURE', '').lower() == 'true'
ALLOWED_ORIGINS = [value.strip() for value in os.environ.get(
    'ALLOWED_ORIGINS', 'http://localhost:5173,http://127.0.0.1:5173').split(',') if value.strip()]
passwords = PasswordHasher()
_dummy_hash = passwords.hash('timing-placeholder-not-a-valid-account-password')
router = APIRouter(prefix='/api/auth', tags=['accounts'])


@dataclass(frozen=True)
class Account:
    id: str
    email: str
    business_id: str
    csrf_token: str
    token_hash: str
    onboarding_required: bool


class Credentials(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=128)


class SignupCredentials(Credentials):
    password: str = Field(min_length=5, max_length=10)

    @field_validator('password')
    @classmethod
    def require_special_character(cls, value):
        if not re.search(r'[^A-Za-z0-9]', value):
            raise ValueError('Password must include at least one special character')
        return value


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def normalize_email(value):
    value = value.strip().casefold()
    if len(value) > 254 or not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', value):
        raise HTTPException(422, 'Enter a valid email address')
    return value


def origin_check(request):
    if request.headers.get('origin') not in ALLOWED_ORIGINS:
        raise HTTPException(403, 'Request origin is not allowed')


def rate_limit(key, maximum, seconds):
    key, now = digest(key), int(time.time())
    with db.transaction() as connection:
        dialect_insert = sqlite_insert if connection.dialect.name == 'sqlite' else postgres_insert
        expired = db.limits.c.expires_at <= now
        statement = dialect_insert(db.limits).values(key=key, count=1, expires_at=now+seconds)
        statement = statement.on_conflict_do_update(index_elements=[db.limits.c.key], set_={
            'count': case((expired, 1), else_=db.limits.c.count+1),
            'expires_at': case((expired, now+seconds), else_=db.limits.c.expires_at),
        }).returning(db.limits.c.count, db.limits.c.expires_at)
        count, expires_at = connection.execute(statement).one()
        if count > maximum:
            raise HTTPException(429, 'Too many attempts. Please try again later.', headers={'Retry-After': str(expires_at-now)})


def require_user(request: Request):
    token = request.cookies.get(COOKIE)
    if not token:
        raise HTTPException(401, 'Sign in to continue')
    with db.engine().connect() as connection:
        row = connection.execute(select(db.users.c.id, db.users.c.email, db.users.c.business_id,
            db.sessions.c.csrf_token, db.sessions.c.token_hash, db.workspaces.c.onboarded)
            .select_from(db.sessions.join(db.users).join(db.workspaces))
            .where(db.sessions.c.token_hash == digest(token), db.sessions.c.expires_at > int(time.time()))).mappings().first()
    if row is None:
        raise HTTPException(401, 'Your session expired. Sign in again.')
    if request.method not in ['GET', 'HEAD', 'OPTIONS']:
        origin_check(request)
        if not secrets.compare_digest(request.headers.get('x-csrf-token', ''), row['csrf_token']):
            raise HTTPException(403, 'Refresh the page and try again')
    return Account(row['id'], row['email'], row['business_id'], row['csrf_token'],
                   row['token_hash'], not row['onboarded'])


def session_response(connection, user, response):
    token, csrf, now = secrets.token_urlsafe(32), secrets.token_hex(32), int(time.time())
    connection.execute(delete(db.sessions).where(db.sessions.c.expires_at <= now))
    connection.execute(insert(db.sessions).values(token_hash=digest(token), user_id=user['id'],
                                                csrf_token=csrf, expires_at=now+SESSION_SECONDS))
    response.set_cookie(COOKIE, token, httponly=True, secure=SECURE_COOKIE,
                        samesite='lax', path='/api', max_age=SESSION_SECONDS)
    workspace = connection.execute(select(db.workspaces.c.onboarded).where(db.workspaces.c.id == user['business_id'])).scalar_one()
    return dict(email=user['email'], business_id=user['business_id'], csrf_token=csrf, onboarding_required=not workspace)


@router.post('/signup', status_code=201)
def signup(payload: SignupCredentials, request: Request, response: Response):
    origin_check(request)
    rate_limit('signup:'+request.client.host, 10, 3600)
    email, password_hash = normalize_email(payload.email), passwords.hash(payload.password)
    bid, uid = str(uuid4()), str(uuid4())
    try:
        with db.transaction() as connection:
            connection.execute(insert(db.workspaces).values(id=bid, payload='{}', onboarded=False))
            user = dict(id=uid, email=email, password_hash=password_hash, business_id=bid)
            connection.execute(insert(db.users).values(**user))
            return session_response(connection, user, response)
    except IntegrityError as error:
        raise HTTPException(409, 'Unable to create this account. Try signing in instead.') from error


@router.post('/login')
def login(payload: Credentials, request: Request, response: Response):
    origin_check(request)
    email = normalize_email(payload.email)
    rate_limit('login-ip:'+request.client.host, 40, 900)
    rate_limit('login-email:'+email, 10, 900)
    with db.engine().connect() as connection:
        user = connection.execute(select(db.users).where(db.users.c.email == email)).mappings().first()
    try:
        valid = passwords.verify(user['password_hash'] if user else _dummy_hash, payload.password)
    except (VerificationError, InvalidHashError):
        valid = False
    if not user or not valid:
        raise HTTPException(401, 'Email or password is incorrect')
    with db.transaction() as connection:
        connection.execute(delete(db.limits).where(db.limits.c.key == digest('login-email:'+email)))
        if passwords.check_needs_rehash(user['password_hash']):
            connection.execute(update(db.users).where(db.users.c.id == user['id']).values(password_hash=passwords.hash(payload.password)))
        return session_response(connection, user, response)


@router.get('/me')
def me(user: Account = Depends(require_user)):
    return dict(email=user.email, business_id=user.business_id, csrf_token=user.csrf_token,
                onboarding_required=user.onboarding_required)


@router.post('/logout', status_code=204)
def logout(response: Response, user: Account = Depends(require_user)):
    with db.transaction() as connection:
        connection.execute(delete(db.sessions).where(db.sessions.c.token_hash == user.token_hash))
    response.delete_cookie(COOKIE, path='/api', secure=SECURE_COOKIE, httponly=True, samesite='lax')
