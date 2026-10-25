"""Review-first invoice import and lifecycle HTTP routes."""
from __future__ import annotations

import base64, csv, io, json
from datetime import date
from pathlib import Path
from uuid import uuid4
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from backend import auth, ledger
from backend.modules import gst_einvoice, invoice_mapper

router = APIRouter(prefix="/api/invoices", tags=["invoices"])

class Preview(BaseModel): filename: str; content_base64: str; mapping: dict[str, str] | None = None
class Commit(BaseModel): rows: list[dict]; mode: str = "append"; confirm_currency_inr: bool; keep_duplicates: bool = False

def _rows(payload: Preview) -> tuple[list[dict], dict]:
    try: raw = base64.b64decode(payload.content_base64, validate=True)
    except Exception as error: raise ValueError("File contents are not valid base64") from error
    if len(raw) > 5_000_000: raise ValueError("Upload must be smaller than 5 MB")
    suffix = Path(payload.filename).suffix.lower()
    if suffix == ".json":
        result = gst_einvoice.parse_gst_einvoice(raw.decode("utf-8")); return result["rows"], {"mapping": {}, "confidence": 1, "unmapped": [], "errors": result["errors"]}
    if suffix != ".csv": raise ValueError("Choose a CSV or GST e-invoice JSON file. PDF preview remains available at /api/import/pdf/preview.")
    source = list(csv.DictReader(io.StringIO(raw.decode("utf-8-sig"))))
    if not source: raise ValueError("The invoice file has no rows")
    suggestion = invoice_mapper.map_columns(list(source[0]))
    mapping = payload.mapping or suggestion["mapping"]
    return invoice_mapper.parse_rows(source, mapping), suggestion

@router.post("/preview")
def preview(payload: Preview, user: auth.Account = Depends(auth.require_user)):
    try:
        rows, meta = _rows(payload)
        business = ledger.load_business(user.business_id)
        existing = {(i["id"], i["customer_id"], i["amount"], i["issue_date"]) for i in business["invoices"]}
        seen: set[tuple] = set()
        for row in rows:
            key = (row["invoice_id"], row["customer_id"], row["amount"], row["issue_date"])
            if key in existing or key in seen or any(i[0] == row["invoice_id"] for i in existing): row["flags"].append("duplicate")
            seen.add(key)
        return {"rows": rows, **meta, "saved": False}
    except (ValueError, UnicodeDecodeError) as error: raise HTTPException(400, str(error)) from error

@router.post("/commit")
def commit(payload: Commit, user: auth.Account = Depends(auth.require_user)):
    if not payload.confirm_currency_inr: raise HTTPException(400, "Confirm that reviewed amounts are in INR before saving.")
    if payload.mode not in ("append", "replace"): raise HTTPException(400, "Mode must be append or replace.")
    if not payload.rows: raise HTTPException(400, "Select at least one reviewed invoice.")
    if any(row.get("flags") and not payload.keep_duplicates for row in payload.rows): raise HTTPException(400, "Correct flagged rows or explicitly keep duplicates before saving.")
    try:
        return ledger.commit_reviewed_invoices(payload.rows, payload.mode, user.business_id, payload.keep_duplicates)
    except ValueError as error: raise HTTPException(400, str(error)) from error

@router.get("")
def list_invoices(user: auth.Account = Depends(auth.require_user)): return ledger.ledger_summary(ledger.load_business(user.business_id))["invoices"]

@router.patch("/{invoice_id}")
def edit_invoice(invoice_id: str, changes: dict, user: auth.Account = Depends(auth.require_user)):
    try: return ledger.edit_invoice(invoice_id, changes, user.business_id)
    except ValueError as error: raise HTTPException(400, str(error)) from error

@router.delete("/{invoice_id}", status_code=204)
def delete_invoice(invoice_id: str, user: auth.Account = Depends(auth.require_user)):
    if not ledger.delete_invoice(invoice_id, user.business_id): raise HTTPException(404, "Invoice not found")

@router.post("/{invoice_id}/mark-paid")
def mark_paid(invoice_id: str, amount: int = Query(gt=0), paid_date: date | None = None, user: auth.Account = Depends(auth.require_user)):
    try:
        ledger.record_receipt(ledger.load_business(user.business_id), invoice_id, amount, (paid_date or date.today()).isoformat(), f"manual-{uuid4()}", user.business_id)
        return {"saved": True}
    except ValueError as error: raise HTTPException(400, str(error)) from error
