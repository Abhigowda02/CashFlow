"""Compatibility entrypoint for CashFlow's local mock fraud gateway."""
from backend.modules.fraud_gateway import check_fraud, process_payment

__all__ = ['check_fraud', 'process_payment']
