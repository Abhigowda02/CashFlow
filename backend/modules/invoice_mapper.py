"""Map invoice-export headers and convert rows into reviewable invoice dictionaries.

Input is headers/rows from a spreadsheet; output contains only proposed rows and
validation flags.  This module never reads a database or persists anything.
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Any

FIELDS = ("invoice_id", "customer_name", "issue_date", "due_date", "amount", "balance", "gstin", "place_of_supply")
ALIASES = {
    "invoice_id": ("voucher no", "invoice no", "invoice number", "bill no", "bill number", "document no"),
    "customer_name": ("party name", "customer name", "customer", "party", "buyer name"),
    "issue_date": ("date", "invoice date", "bill date", "document date"),
    "due_date": ("due date", "payment due date"),
    "amount": ("amount", "total", "gross total", "invoice amount", "total amount", "total invoice value"),
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
        invoice_id, customer = str(get("invoice_id")).strip(), str(get("customer_name")).strip()
        flags: list[str] = []
        if not invoice_id: flags.append("missing_invoice_id")
        if not customer: flags.append("missing_customer")
        if not issue: flags.append("missing_or_invalid_issue_date")
        if amount is None or amount <= 0: flags.append("missing_or_invalid_amount")
        if not due and issue:
            due = issue
            flags.append("missing_due_date")
        proposals.append({"row_number": number, "invoice_id": invoice_id, "customer_id": customer, "customer_name": customer,
            "issue_date": issue, "due_date": due, "amount": amount, "currency": "INR", "segment": "small",
            "received_amount": 0, "paid_date": None, "flags": flags, "source": source})
    return proposals
