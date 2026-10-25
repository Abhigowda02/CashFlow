"""Shared database schema: SQLite for development, PostgreSQL for deployment."""
from contextlib import contextmanager
from functools import lru_cache
import os
from pathlib import Path

from sqlalchemy import (BigInteger, Boolean, Column, ForeignKey, Integer, MetaData, String,
                        Table, Text, create_engine, event)

LOCAL_DB = Path(__file__).resolve().parent / '.local' / 'saas.sqlite3'
DATABASE_URL = os.environ.get('DATABASE_URL', f'sqlite:///{LOCAL_DB.as_posix()}')
metadata = MetaData()
workspaces = Table('business_workspaces', metadata,
    Column('id', String(36), primary_key=True), Column('payload', Text, nullable=False),
    Column('onboarded', Boolean, nullable=False, default=False))
users = Table('account_users', metadata,
    Column('id', String(36), primary_key=True), Column('email', String(254), unique=True, nullable=False),
    Column('password_hash', Text, nullable=False),
    Column('business_id', ForeignKey('business_workspaces.id'), nullable=False))
sessions = Table('account_sessions', metadata,
    Column('token_hash', String(64), primary_key=True), Column('user_id', ForeignKey('account_users.id'), nullable=False),
    Column('csrf_token', String(64), nullable=False), Column('expires_at', Integer, nullable=False))
receipts = Table('business_receipts', metadata,
    Column('business_id', ForeignKey('business_workspaces.id'), primary_key=True),
    Column('id', String(100), primary_key=True), Column('invoice_id', String(200), nullable=False),
    Column('amount', BigInteger, nullable=False), Column('date', String(10), nullable=False))
scenarios = Table('business_scenarios', metadata,
    Column('business_id', ForeignKey('business_workspaces.id'), primary_key=True),
    Column('id', String(36), primary_key=True), Column('name', String(120), nullable=False),
    Column('changes', Text, nullable=False), Column('created_at', String(40), nullable=False),
    Column('updated_at', String(40), nullable=False))
limits = Table('auth_rate_limits', metadata,
    Column('key', String(64), primary_key=True), Column('count', Integer, nullable=False),
    Column('expires_at', Integer, nullable=False))
@lru_cache(maxsize=8)
def _engine(url):
    if url.startswith('sqlite:'):
        if url == f'sqlite:///{LOCAL_DB.as_posix()}':
            LOCAL_DB.parent.mkdir(parents=True, exist_ok=True)
        engine = create_engine(url, connect_args={'check_same_thread': False, 'timeout': 20})
        @event.listens_for(engine, 'connect')
        def configure_sqlite(connection, _):
            connection.execute('PRAGMA foreign_keys=ON')
    else:
        engine = create_engine(url, pool_pre_ping=True)
    metadata.create_all(engine)
    return engine


def engine():
    return _engine(DATABASE_URL)


@contextmanager
def transaction():
    with engine().connect() as connection:
        if connection.dialect.name == 'sqlite':
            connection.exec_driver_sql('BEGIN IMMEDIATE')
        else:
            connection.begin()
        try:
            yield connection
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
