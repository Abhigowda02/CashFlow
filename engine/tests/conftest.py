"""
engine/tests/conftest.py
Pytest configuration and custom marker registration.
"""

def pytest_configure(config):
    config.addinivalue_line("markers", "slow: mark test as slow performance test")
