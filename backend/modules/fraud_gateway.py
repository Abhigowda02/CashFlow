"""Adapter for the supplied local fraud mock.

Input/output are plain dictionaries. Persistence remains in the tenant-scoped
payment tables; this adapter only calls the supplied fraud decision/gateway.
"""
from __future__ import annotations
from typing import Any
from fraud_system import check_fraud as _check_fraud, process_payment as _process_payment


def check_fraud(payment: dict[str, Any]) -> dict[str, Any]:
    """Delegate to the supplied ``fraud_system.check_fraud``."""
    return _check_fraud(payment)


def process_payment(payment: dict[str, Any]) -> dict[str, Any]:
    """Run the mock fraud decision; no real gateway is contacted."""
    return _process_payment(payment)
