"""Frozen contract layer schemas for CashFlow.

Do not edit shared/ except by deliberate team decision; run shared/validate.py
after every backend or UI-contract change.
"""

from __future__ import annotations

from typing import Any, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field


class ContractBaseModel(BaseModel):
    """Base model enforcing contract conventions."""
    model_config = ConfigDict(extra="ignore", populate_by_name=True)


class Invoice(ContractBaseModel):
    """Invoice record for receivables."""
    id: str
    customer_id: str
    amount: int
    issue_date: str
    due_date: str
    status: Literal["open", "paid", "disputed", "cancelled"] = "open"
    paid_date: Optional[str] = None
    customer_name: Optional[str] = None
    description: Optional[str] = None


class Customer(ContractBaseModel):
    """Customer profile and payment terms."""
    id: str
    name: str
    segment: Optional[Literal["government", "corporate", "small"]] = None
    payment_terms_days: Optional[int] = 30
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    gstin: Optional[str] = None
    notes: Optional[str] = None


class Transaction(ContractBaseModel):
    """Bank or statement transaction with deduplication hash."""
    id: str
    date: str
    amount: int
    direction: Literal["credit", "debit"]
    description: str
    balance: Optional[int] = None
    source: Literal["statement", "sms", "aa", "manual", "synthetic"]
    dedupe_hash: str


class ProposedObligation(ContractBaseModel):
    """Obligation proposed from recurring transaction pattern detection."""
    id: str
    name: str
    amount: int
    frequency: Literal["monthly", "weekly", "quarterly", "yearly"] = "monthly"
    day_of_month: Optional[int] = 1
    category: Optional[Literal["payroll", "rent", "emi", "tax", "utility", "vendor", "other"]] = "other"
    confidence: float = 0.90
    detected_from_transaction_ids: list[str] = Field(default_factory=list)
    status: Literal["pending", "approved", "rejected"] = "pending"


class ProposedMatch(ContractBaseModel):
    """Match proposed between bank transactions and invoices or bills."""
    id: str
    transaction_id: str
    invoice_id: Optional[str] = None
    bill_id: Optional[str] = None
    confidence: float = 0.90
    match_type: Literal["invoice_receipt", "supplier_payment", "obligation", "other"] = "invoice_receipt"
    notes: Optional[str] = None
    status: Literal["pending", "confirmed", "rejected"] = "pending"


class WhyItem(ContractBaseModel):
    """Explanation item contributing to the forecast trajectory."""
    type: Literal["late_invoice", "obligation", "supplier_bill", "sales_inflow", "other"]
    ref: str
    text: str
    amount: int
    expected_date: str
    spread_days: int


class ForecastAccuracy(ContractBaseModel):
    """Historical backtest evaluation metrics."""
    mape: Optional[float] = None
    bias: Optional[float] = None
    backtest_days: Optional[int] = None
    evaluated_at: Optional[str] = None


class ForecastView(ContractBaseModel):
    """Unified 90-day forecast view for dashboard and screens."""
    headline: str
    generated_at: str
    as_of: str
    cash_last_updated: str
    stale: bool
    dates: list[str]
    p10: list[int]
    p50: list[int]
    p90: list[int]
    safety_floor: int
    shortage_prob: float
    first_shortage_date: Optional[str] = None
    min_balance_p50: int
    why: list[WhyItem] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    accuracy: Optional[ForecastAccuracy] = None


class InvoiceForecast(ContractBaseModel):
    """Machine learning payment prediction for a specific invoice."""
    invoice_id: str
    expected_pay_date: str
    p_by_30d: float
    prob_late: float
    risk: Literal["low", "medium", "high"]


class Alert(ContractBaseModel):
    """Actionable alert item."""
    id: str
    kind: Literal["shortage_warning", "late_invoice", "msme_due", "stale_cash", "new_match", "other"]
    severity: Literal["info", "warning", "critical"]
    title: str
    body: str
    created_at: str
    read: bool
    dedupe_key: str
    link: Optional[str] = None


class ActionEffect(ContractBaseModel):
    """Impact of an action card on cash runway and shortage probability."""
    shortage_prob_before: float
    shortage_prob_after: float
    first_shortage_before: Optional[str] = None
    first_shortage_after: Optional[str] = None
    runway_days_gained: int


class ActionExecute(ContractBaseModel):
    """Payload and action execution parameters."""
    kind: str
    payload: dict[str, Any] = Field(default_factory=dict)


class ActionCard(ContractBaseModel):
    """Ranked corrective action card."""
    id: str
    type: Literal["chase_invoice", "early_discount", "invoice_discounting", "delay_supplier", "overdraft", "cut_expense"]
    title: str
    who: str
    amount: int
    by_date: str
    effect: ActionEffect
    cost: int
    risk: Literal["low", "medium", "high"]
    note: str
    execute: ActionExecute


class Reminder(ContractBaseModel):
    """Dunning and collections reminder message."""
    id: str
    invoice_ids: list[str]
    customer_id: str
    rung: int
    channel: Literal["email", "whatsapp", "sms", "letter"]
    subject: str
    body: str
    status: Literal["draft", "approved", "sent"]
    created_at: str
    sent_at: Optional[str] = None
