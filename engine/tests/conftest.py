"""
engine/tests/conftest.py
Pytest configuration and custom marker registration.
"""

import pytest

@pytest.fixture(autouse=True)
def pin_today(monkeypatch):
    monkeypatch.setenv('APP_ENV', 'test')
    monkeypatch.setenv('APP_FAKE_TODAY', '2026-10-24')

def pytest_configure(config):
    config.addinivalue_line("markers", "slow: mark test as slow performance test")
