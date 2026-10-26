"""Map invoice-export headers and convert rows into reviewable invoice dictionaries.

Input is headers/rows from a spreadsheet; output contains only proposed rows and
validation flags.  This module never reads a database or persists anything.
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Any

FIELDS = ("invoice_id", "customer_id", "customer_name", "issue_date", "due_date", "amount", "received_amount", "paid_date", "segment", "currency", "balance", "gstin", "place_of_supply")
ALIASES = {
    "invoice_id": ("invoice id", "voucher no", "invoice no", "invoice number", "bill no", "bill number", "document no"),
    "customer_id": ("customer id", "party id", "buyer id", "client id"),
    "customer_name": ("party name", "customer name", "customer", "party", "buyer name"),
    "issue_date": ("date", "issue date", "invoice date", "bill date", "document date"),
    "due_date": ("due date", "payment due date"),
    "amount": ("amount", "total", "gross total", "invoice amount", "total amount", "total invoice value"),
    "received_amount": ("received amount", "amount received", "paid amount", "receipt amount", "amount paid"),
    "paid_date": ("paid date", "payment date", "receipt date"),
    "segment": ("segment", "customer type", "party type"),
    "currency": ("currency", "currency code"),
    "balance": ("balance", "outstanding", "pending amount", "balance due"),
    "gstin": ("gstin", "buyer gstin", "party gstin"),
    "place_of_supply": ("place of supply", "pos"),
}


def _norm(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value).casefold()).strip()


def map_columns(headers: list[str]) -> dict[str, Any]:
    """Return suggested field-to-header mapping, confidence, and unmapped headers."""
    mapping: dict[str, str] = {}
    used: set[str] = set()
    for field, aliases in ALIASES.items():
        for header in headers:
            normalized = _norm(header)
            if header not in used and normalized in aliases:
                mapping[field] = header
                used.add(header)
                break
    required = {"invoice_id", "customer_name", "issue_date", "amount"}
    confidence = round(len(required & mapping.keys()) / len(required), 2)
    return {"mapping": mapping, "confidence": confidence, "unmapped": [h for h in headers if h not in used]}


def _integer(value: object) -> int | None:
    text = str(value or "").replace(",", "").replace("₹", "").replace("INR", "").strip()
    try:
        number = float(text)
        return int(number) if number >= 0 and number.is_integer() else None
    except ValueError:
        return None


def _date(value: object) -> str | None:
    text = str(value or "").strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d/%m/%y", "%d-%b-%Y"):
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            pass
    return None


def parse_rows(rows: list[dict[str, object]], mapping: dict[str, str], *, default_terms_days: int = 30) -> list[dict[str, Any]]:
    """Convert spreadsheet rows to proposals; each row has flags for owner review."""
    proposals: list[dict[str, Any]] = []
    for number, source in enumerate(rows, start=1):
        get = lambda field: source.get(mapping.get(field, ""), "")
        issue = _date(get("issue_date"))
        due = _date(get("due_date"))
        amount = _integer(get("amount"))
        received = _integer(get("received_amount")) if mapping.get("received_amount") else 0
        paid_date = _date(get("paid_date")) if mapping.get("paid_date") else None
        invoice_id, customer = str(get("invoice_id")).strip(), str(get("customer_name")).strip()
        customer_id = str(get("customer_id")).strip() or customer
        segment = str(get("segment")).strip().lower() or "small"
        currency = str(get("currency")).strip().upper() or "INR"
        flags: list[str] = []
        if not invoice_id: flags.append("missing_invoice_id")
        if not customer: flags.append("missing_customer")
        if not issue: flags.append("missing_or_invalid_issue_date")
        if amount is None or amount <= 0: flags.append("missing_or_invalid_amount")
        if received is None or received < 0 or (amount is not None and received > amount): flags.append("invalid_received_amount")
        if paid_date and (not issue or paid_date < issue): flags.append("invalid_paid_date")
        if received == amount and not paid_date: flags.append("missing_paid_date")
        if received is not None and amount is not None and received < amount and paid_date: flags.append("paid_date_requires_full_payment")
        if segment not in ("small", "corporate", "government"): flags.append("invalid_segment")
        if currency != "INR": flags.append("currency_must_be_inr")
        if not due and issue:
            due = issue
            flags.append("missing_due_date")
        proposals.append({"row_number": number, "invoice_id": invoice_id, "customer_id": customer_id, "customer_name": customer,
            "issue_date": issue, "due_date": due, "amount": amount, "currency": currency, "segment": segment,
            "received_amount": received, "paid_date": paid_date, "flags": flags, "source": source})
    return proposals
