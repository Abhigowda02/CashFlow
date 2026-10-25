"""Local, text-only PDF invoice draft extraction."""
import hashlib
import io
import re
import unicodedata
from datetime import date, datetime
from pathlib import Path

from pypdf import PdfReader

MAX_PDF_BYTES = 5_000_000
MAX_PDF_PAGES = 25
MAX_SOURCE_TEXT = 12_000
_AMOUNT = r"((?:\d{1,3}(?:,\d{2,3})+|\d+)(?:\.\d{1,2})?)"
_DATE = r"([A-Za-z]{3,9}\s+\d{1,2},?\s+\d{4}|\d{4}[-/]\d{1,2}[-/]\d{1,2}|\d{1,2}[-/]\d{1,2}[-/]\d{4})"


def _label_value(text: str, labels: str) -> str | None:
    match = re.search(rf"(?im)^\s*(?:{labels})\s*[:#-]?\s*(.*?)\s*$", text)
    if not match:
        return None
    value = match.group(1).strip()
    if not value:
        lines = text[match.end():].splitlines()
        value = next((line.strip() for line in lines if line.strip()), "")
    return value or None


def _invoice_date(value: str | None) -> tuple[str | None, bool]:
    if not value:
        return None, False
    value = value.strip().rstrip(".,")
    iso = re.fullmatch(r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})", value)
    if iso:
        try:
            return date(int(iso.group(1)), int(iso.group(2)), int(iso.group(3))).isoformat(), False
        except ValueError:
            return None, False
    numeric = re.fullmatch(r"(\d{1,2})[-/](\d{1,2})[-/](\d{4})", value)
    if numeric:
        first, second, year = map(int, numeric.groups())
        if first <= 12 and second <= 12:
            return None, True
        day, month = (first, second) if first > 12 else (second, first)
        try:
            return date(year, month, day).isoformat(), False
        except ValueError:
            return None, False
    for fmt in ("%d %B %Y", "%d %b %Y", "%B %d %Y", "%b %d %Y"):
        try:
            return datetime.strptime(value.replace(",", ""), fmt).date().isoformat(), False
        except ValueError:
            continue
    return None, False


def _amount(value: str | None) -> int | None:
    if not value:
        return None
    normalized = value.replace(",", "").strip()
    try:
        number = float(normalized)
    except ValueError:
        return None
    if not number.is_integer() or number < 0:
        return None
    return int(number)


def _currency(text: str) -> str:
    if re.search(r"(?:₹|\bINR\b|\bRs\.?)", text, re.IGNORECASE):
        return "INR"
    for code, pattern in (
        ("USD", r"\bUSD\b|\$"),
        ("CAD", r"\bCAD\b"),
        ("EUR", r"\bEUR\b|€"),
        ("GBP", r"\bGBP\b|£"),
    ):
        if re.search(pattern, text, re.IGNORECASE):
            return code
    return "unknown"


def _customer_id(name: str) -> str:
    normalized = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^A-Za-z0-9]+", "-", normalized).strip("-").upper()[:32] or "CUSTOMER"
    return f"PDF-{slug}-{hashlib.sha256(name.casefold().encode()).hexdigest()[:6].upper()}"


def _extract_page(text: str, page_number: int, business: dict) -> dict | None:
    invoice_id = _label_value(
        text, r"invoice\s*(?:number|no\.?|#|id)|tax\s*invoice\s*(?:number|no\.?|#)"
    )
    # Avoid mistaking the entire body of a page for an invoice ID.
    if invoice_id:
        invoice_id = re.split(r"\s{2,}|(?:\s+)(?:date|invoice date)\b", invoice_id, maxsplit=1, flags=re.I)[0]
        invoice_id = invoice_id.strip().strip("#:;,.")
        if len(invoice_id) > 100 or len(invoice_id.split()) > 4:
            invoice_id = None

    customer_name = _label_value(text, r"bill\s*to|billed\s*to|customer|buyer|invoice\s*to")
    if customer_name:
        customer_name = re.split(r"\s{2,}", customer_name)[0].strip(" ,")
        if len(customer_name) > 200:
            customer_name = None

    issue_raw = _label_value(text, r"invoice\s*date|date\s*of\s*issue|issue\s*date")
    due_raw = _label_value(text, r"due\s*date|payment\s*due\s*date")
    issue_match = re.search(_DATE, issue_raw or "", re.IGNORECASE)
    due_match = re.search(_DATE, due_raw or "", re.IGNORECASE)
    issue_date, issue_ambiguous = _invoice_date(issue_match.group(1) if issue_match else None)
    due_date, due_ambiguous = _invoice_date(due_match.group(1) if due_match else None)

    amount_raw = _label_value(text, r"grand\s*total|invoice\s*total|total\s*amount|total\s*due|amount\s*due")
    amount_match = re.search(_AMOUNT, amount_raw or "")
    amount = _amount(amount_match.group(1) if amount_match else None)
    received_raw = _label_value(text, r"amount\s*(?:paid|received)|payment\s*received|received\s*amount")
    received_match = re.search(_AMOUNT, received_raw or "")
    received = _amount(received_match.group(1) if received_match else None)
    paid_raw = _label_value(text, r"paid\s*date|payment\s*date|date\s*paid")
    paid_match = re.search(_DATE, paid_raw or "", re.IGNORECASE)
    paid_date, paid_ambiguous = _invoice_date(paid_match.group(1) if paid_match else None)
    payment_date_from_document = paid_date
    payment_date_supported = (
        received is not None and amount is not None and received == amount and paid_date is not None
    )
    if not payment_date_supported:
        paid_date = None

    currency = _currency(text)
    existing_customers = business.get("customers", [])
    matched_customer = next(
        (item for item in existing_customers if item.get("name", "").strip().casefold() == (customer_name or "").casefold()),
        None,
    )
    customer_id = matched_customer["id"] if matched_customer else (_customer_id(customer_name) if customer_name else "")
    segment = matched_customer.get("segment") if matched_customer else None
    fields = {
        "invoice_id": "high" if invoice_id else "missing",
        "customer_name": "high" if customer_name else "missing",
        "customer_id": "high" if matched_customer else "medium" if customer_id else "missing",
        "amount": "high" if amount is not None else "missing",
        "issue_date": "medium" if issue_date else "missing",
        "due_date": "medium" if due_date else "missing",
        "currency": "high" if currency != "unknown" else "missing",
        "received_amount": "high" if received is not None else "missing",
        "paid_date": "high" if paid_date else "missing",
    }
    if not any((invoice_id, customer_name, amount is not None, issue_date, due_date)):
        return None
    issues = []
    if not invoice_id:
        issues.append("Invoice number was not found; enter it before import.")
    if not customer_name:
        issues.append("Customer name was not found; enter it before import.")
    if amount is None:
        issues.append("Whole-rupee invoice total was not confidently found; check and enter it.")
    if not issue_date:
        issues.append("Issue date is missing, invalid, or ambiguous; enter an ISO date.")
    if not due_date:
        issues.append("Due date is missing, invalid, or ambiguous; enter an ISO date.")
    if issue_ambiguous:
        issues.append("Issue date has ambiguous numeric ordering; confirm the date.")
    if due_ambiguous:
        issues.append("Due date has ambiguous numeric ordering; confirm the date.")
    if paid_ambiguous:
        issues.append("Payment date has ambiguous numeric ordering; confirm the date.")
    if currency == "unknown":
        issues.append("Currency was not identified; confirm the amount is INR or convert it yourself.")
    if currency != "INR":
        issues.append(f"Detected {currency} currency; convert the amount manually and select INR, or remove this invoice.")
    if received is None:
        issues.append("Payment amount was not found; enter the received amount, including 0 only if nothing has been received.")
    if received is not None and received > 0 and received < (amount or 0) and not paid_date:
        issues.append("A payment amount was found without a payment date; verify it before import.")
    if payment_date_from_document and not payment_date_supported:
        issues.append("A payment date was found, but the invoice model records a date only for full payment; verify the payment details.")
    if received is not None and amount is not None and received > amount:
        issues.append("Extracted payment exceeds the invoice total; correct it before import.")
    if received == amount and amount and not paid_date:
        issues.append("Full payment is indicated but no payment date was found; add the date or correct the received amount.")

    return {
        "invoice_id": invoice_id or "",
        "customer_id": customer_id,
        "customer_name": customer_name or "",
        "segment": segment,
        "amount": amount,
        "issue_date": issue_date or "",
        "due_date": due_date or "",
        "currency": currency,
        "received_amount": received,
        "paid_date": paid_date,
        "source_page": page_number,
        "source_text": text[:MAX_SOURCE_TEXT],
        "field_confidence": fields,
        "issues": issues,
    }


def preview_pdf(filename: str, content_base64: str, business: dict) -> dict:
    if Path(filename).suffix.lower() != ".pdf":
        raise ValueError("Choose a PDF invoice file.")
    import base64
    try:
        payload = base64.b64decode(content_base64, validate=True)
    except (ValueError, TypeError) as error:
        raise ValueError("The uploaded file could not be decoded.") from error
    if len(payload) > MAX_PDF_BYTES:
        raise ValueError("PDF must be smaller than 5 MB.")
    if not payload.startswith(b"%PDF-"):
        raise ValueError("This file is not a valid PDF.")
    try:
        reader = PdfReader(io.BytesIO(payload), strict=True)
        if reader.is_encrypted:
            raise ValueError("Encrypted PDFs are not supported. Upload an unlocked copy.")
        if not 1 <= len(reader.pages) <= MAX_PDF_PAGES:
            raise ValueError(f"PDF must contain between 1 and {MAX_PDF_PAGES} pages.")
        page_text = []
        for number, page in enumerate(reader.pages, start=1):
            text = page.extract_text(extraction_mode="layout") or ""
            if text.strip():
                page_text.append((number, text.strip()))
    except ValueError:
        raise
    except Exception as error:
        raise ValueError("The PDF is malformed or could not be read.") from error
    if not page_text:
        raise ValueError("No selectable text was found. Scanned/image-only PDFs and OCR are not supported yet.")

    drafts = []
    for number, text in page_text:
        draft = _extract_page(text, number, business)
        if draft is not None:
            drafts.append(draft)
    if not drafts:
        raise ValueError("No invoice fields were recognized. Try a text-based invoice PDF or use CSV/XLSX.")

    counts = {}
    for draft in drafts:
        if draft["invoice_id"]:
            counts[draft["invoice_id"]] = counts.get(draft["invoice_id"], 0) + 1
    existing_ids = {str(invoice.get("id", "")) for invoice in business.get("invoices", [])}
    for draft in drafts:
        duplicate = draft["invoice_id"] in existing_ids or counts.get(draft["invoice_id"], 0) > 1
        draft["duplicate"] = duplicate
        if duplicate:
            draft["issues"].append("Invoice number already exists in this workspace or PDF. Remove or correct the duplicate.")
    return {
        "drafts": drafts,
        "page_count": len(reader.pages),
        "supported_pages": len(drafts),
        "duplicate_count": sum(draft["duplicate"] for draft in drafts),
        "mode": "append",
        "ocr_supported": False,
    }
