"""Parse GST e-invoice JSON into reviewable invoice rows; input/output are dictionaries."""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any


def _date(value: object) -> str | None:
    for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d"):
        try: return datetime.strptime(str(value), fmt).date().isoformat()
        except ValueError: pass
    return None


def parse_gst_einvoice(payload: str | dict[str, Any] | list[dict[str, Any]]) -> dict[str, Any]:
    """Return ``{rows, errors}``; malformed entries become errors rather than exceptions."""
    try:
        records = json.loads(payload) if isinstance(payload, str) else payload
    except json.JSONDecodeError as error:
        return {"rows": [], "errors": [{"index": 0, "message": f"Invalid GST e-invoice JSON: {error.msg}"}]}
    if isinstance(records, dict): records = [records]
    if not isinstance(records, list): return {"rows": [], "errors": [{"index": 0, "message": "GST e-invoice JSON must be an object or list."}]}
    rows, errors = [], []
    for index, record in enumerate(records):
        try:
            doc, buyer, values = record["DocDtls"], record.get("BuyerDtls", {}), record["ValDtls"]
            amount = values.get("TotInvVal")
            amount = int(float(str(amount))) if float(str(amount)).is_integer() and float(str(amount)) > 0 else None
            issue = _date(doc.get("Dt"))
            if not doc.get("No") or not buyer.get("LglNm") or not issue or amount is None: raise ValueError("missing invoice number, buyer, date, or whole-INR total")
            rows.append({"row_number": index + 1, "invoice_id": str(doc["No"]).strip(), "customer_id": str(buyer["LglNm"]).strip(),
                "customer_name": str(buyer["LglNm"]).strip(), "issue_date": issue, "due_date": issue, "amount": amount,
                "currency": "INR", "segment": "small", "received_amount": 0, "paid_date": None, "gstin": buyer.get("Gstin"), "flags": ["missing_due_date"]})
        except (KeyError, TypeError, ValueError) as error:
            errors.append({"index": index, "message": f"Invalid GST e-invoice entry: {error}"})
    return {"rows": rows, "errors": errors}
