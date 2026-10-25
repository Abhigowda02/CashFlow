import base64
import io

from pypdf import PdfReader, PdfWriter
import pytest

from backend import ledger
from backend.main import current_business


def text_pdf(*pages):
    page_ids = [3 + index * 2 for index in range(len(pages))]
    content_ids = [page_id + 1 for page_id in page_ids]
    font_id = 3 + len(pages) * 2
    objects = {
        1: b"<< /Type /Catalog /Pages 2 0 R >>",
        2: f"<< /Type /Pages /Kids [{' '.join(f'{page_id} 0 R' for page_id in page_ids)}] /Count {len(pages)} >>".encode(),
        font_id: b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    }
    for page_id, content_id, lines in zip(page_ids, content_ids, pages):
        objects[page_id] = (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            f"/Resources << /Font << /F1 {font_id} 0 R >> >> /Contents {content_id} 0 R >>"
        ).encode()
        commands = []
        for line in lines:
            escaped = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
            commands.append(f"({escaped}) Tj 0 -18 Td")
        stream = ("BT /F1 12 Tf 72 720 Td " + " ".join(commands) + " ET").encode()
        objects[content_id] = (
            f"<< /Length {len(stream)} >>\nstream\n".encode() + stream + b"\nendstream"
        )

    output = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for object_id in range(1, font_id + 1):
        offsets.append(len(output))
        output.extend(f"{object_id} 0 obj\n".encode())
        output.extend(objects[object_id])
        output.extend(b"\nendobj\n")
    xref_offset = len(output)
    output.extend(f"xref\n0 {font_id + 1}\n".encode())
    output.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        output.extend(f"{offset:010d} 00000 n \n".encode())
    output.extend(
        f"trailer\n<< /Size {font_id + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref_offset}\n%%EOF\n".encode()
    )
    return bytes(output)


def invoice_lines(invoice_id="INV-PDF-1", amount="INR 125000", issue="2026-10-20",
                  due="2026-11-20", customer="Kaveri Garments"):
    return [
        f"Invoice No: {invoice_id}",
        f"Bill To: {customer}",
        f"Invoice Date: {issue}",
        f"Due Date: {due}",
        f"Grand Total: {amount}",
    ]


def preview(client, pdf, filename="invoice.pdf"):
    return client.post("/api/import/pdf/preview", json={
        "filename": filename,
        "content_base64": base64.b64encode(pdf).decode(),
    })


def invoice_csv_payload():
    content = (
        "invoice_id,customer_id,customer_name,segment,amount,issue_date,due_date,status,"
        "received_amount,paid_date,currency\n"
        "EXISTING-1,C1,Existing Customer,small,1000,2026-10-01,2026-10-30,open,0,,INR\n"
    )
    return {
        "filename": "invoices.csv",
        "content_base64": base64.b64encode(content.encode()).decode(),
        "name": "Existing workspace",
        "as_of": "2026-10-24",
        "opening_cash": 10000,
        "safety_floor": 1000,
        "declared_currency": "INR",
    }


def reviewed_invoice(**overrides):
    return {
        "invoice_id": "INV-PDF-1",
        "customer_id": "PDF-KAVERI",
        "customer_name": "Kaveri Garments",
        "segment": "small",
        "amount": 125000,
        "issue_date": "2026-10-20",
        "due_date": "2026-11-20",
        "currency": "INR",
        "received_amount": 0,
        "paid_date": None,
        **overrides,
    }


def test_preview_extracts_reviewable_invoice_with_page_and_source_text(client):
    response = preview(client, text_pdf(invoice_lines()))

    assert response.status_code == 200, response.text
    result = response.json()
    assert result["mode"] == "append"
    assert result["ocr_supported"] is False
    assert result["duplicate_count"] == 0
    draft = result["drafts"][0]
    assert draft["invoice_id"] == "INV-PDF-1"
    assert draft["customer_name"] == "Kaveri Garments"
    assert draft["segment"] is None
    assert draft["amount"] == 125000
    assert draft["issue_date"] == "2026-10-20"
    assert draft["due_date"] == "2026-11-20"
    assert draft["currency"] == "INR"
    assert draft["received_amount"] is None
    assert draft["field_confidence"]["received_amount"] == "missing"
    assert any("Payment amount was not found" in issue for issue in draft["issues"])
    assert draft["source_page"] == 1
    assert draft["duplicate"] is False
    assert "Grand Total: INR 125000" in draft["source_text"]
    assert draft["field_confidence"]["amount"] == "high"
    assert current_business(client.business_id)["invoices"] == []


@pytest.mark.parametrize(
    ("filename", "pdf", "message"),
    [
        ("invoice.csv", text_pdf(invoice_lines()), "Choose a PDF"),
        ("invoice.pdf", b"not a PDF", "not a valid PDF"),
        ("invoice.pdf", b"%PDF-1.4\nnot a valid PDF structure", "malformed"),
        ("invoice.pdf", b"%PDF-" + b"0" * 5_000_000, "smaller than 5 MB"),
        ("invoice.pdf", text_pdf([]), "No selectable text"),
        ("invoice.pdf", text_pdf(*([[]] * 26)), "between 1 and 25 pages"),
    ],
    ids=["wrong-extension", "invalid-header", "malformed", "oversized", "image-only", "too-many-pages"],
)
def test_preview_rejects_wrong_malformed_unreadable_oversized_and_oversized_page_count(
    client, filename, pdf, message,
):
    response = preview(client, pdf, filename)

    assert response.status_code == 400
    assert message in response.json()["detail"]


def test_preview_rejects_encrypted_pdf(client):
    reader = PdfReader(io.BytesIO(text_pdf(invoice_lines())))
    writer = PdfWriter()
    writer.append_pages_from_reader(reader)
    writer.encrypt("secret")
    encrypted = io.BytesIO()
    writer.write(encrypted)

    response = preview(client, encrypted.getvalue())

    assert response.status_code == 400
    assert "Encrypted PDFs are not supported" in response.json()["detail"]


def test_preview_flags_existing_and_within_pdf_duplicate_invoice_ids(client):
    assert client.post("/api/import", json=invoice_csv_payload()).status_code == 200
    repeated_page = invoice_lines(invoice_id="EXISTING-1")

    response = preview(client, text_pdf(repeated_page, repeated_page))

    assert response.status_code == 200
    result = response.json()
    assert result["duplicate_count"] == 2
    assert [draft["source_page"] for draft in result["drafts"]] == [1, 2]
    assert all(draft["duplicate"] for draft in result["drafts"])
    applied = client.post("/api/import/pdf/apply", json={
        "invoices": [reviewed_invoice(invoice_id="EXISTING-1")],
        "confirm_append": True,
        "confirm_currency_inr": True,
    })
    assert applied.status_code == 400
    assert "already exists" in applied.json()["detail"]
    assert [invoice["id"] for invoice in ledger.load_business(client.business_id)["invoices"]] == ["EXISTING-1"]


def test_preview_flags_ambiguous_dates_and_unknown_currency(client):
    response = preview(client, text_pdf(
        invoice_lines(amount="125000", issue="05/06/2026", due="2026-11-20")
    ))

    assert response.status_code == 200
    draft = response.json()["drafts"][0]
    assert draft["currency"] == "unknown"
    assert draft["issue_date"] == ""
    assert any("ambiguous numeric ordering" in issue for issue in draft["issues"])
    assert any("Currency was not identified" in issue for issue in draft["issues"])


def test_preview_extracts_explicit_full_payment_without_inference(client):
    lines = invoice_lines() + [
        "Amount Paid: INR 125000",
        "Payment Date: 2026-10-22",
    ]

    response = preview(client, text_pdf(lines))

    assert response.status_code == 200
    draft = response.json()["drafts"][0]
    assert draft["received_amount"] == 125000
    assert draft["paid_date"] == "2026-10-22"
    assert draft["field_confidence"]["paid_date"] == "high"
    assert not any("Payment amount was not found" in issue for issue in draft["issues"])


def test_preview_does_not_attach_partial_payment_date_to_invoice_model(client):
    lines = invoice_lines() + [
        "Amount Paid: INR 25000",
        "Payment Date: 2026-10-22",
    ]

    response = preview(client, text_pdf(lines))

    assert response.status_code == 200
    draft = response.json()["drafts"][0]
    assert draft["received_amount"] == 25000
    assert draft["paid_date"] is None
    assert any("invoice model records a date only for full payment" in issue for issue in draft["issues"])


def test_apply_requires_confirmation_and_rejects_unsupported_currency(client):
    request = {
        "invoices": [reviewed_invoice(currency="unknown")],
        "confirm_append": True,
        "confirm_currency_inr": True,
    }
    response = client.post("/api/import/pdf/apply", json=request)
    assert response.status_code == 400
    assert "currency must be INR" in response.json()["detail"]

    request["invoices"] = [reviewed_invoice()]
    request["confirm_append"] = False
    response = client.post("/api/import/pdf/apply", json=request)
    assert response.status_code == 400
    assert "Confirm that these reviewed invoices should be added" in response.json()["detail"]
    assert current_business(client.business_id)["invoices"] == []
    request.update(confirm_append=True, confirm_currency_inr=False)
    response = client.post("/api/import/pdf/apply", json=request)
    assert response.status_code == 400
    assert "Confirm that every reviewed invoice amount is in INR" in response.json()["detail"]
    assert current_business(client.business_id)["invoices"] == []

    request.update(
        invoices=[reviewed_invoice(), reviewed_invoice(invoice_id="INV-PDF-1")],
        confirm_append=True,
        confirm_currency_inr=True,
    )
    response = client.post("/api/import/pdf/apply", json=request)
    assert response.status_code == 400
    assert "already exists" in response.json()["detail"]
    assert current_business(client.business_id)["invoices"] == []


@pytest.mark.parametrize(
    ("changes", "expected_status"),
    [
        ({"amount": -1}, 422),
        ({"issue_date": "not-a-date"}, 422),
        ({"due_date": "2026-10-19"}, 400),
        ({"received_amount": 125001}, 400),
    ],
)
def test_apply_rejects_invalid_amounts_dates_and_receipts(client, changes, expected_status):
    response = client.post("/api/import/pdf/apply", json={
        "invoices": [reviewed_invoice(**changes)],
        "confirm_append": True,
        "confirm_currency_inr": True,
    })

    assert response.status_code == expected_status
    assert current_business(client.business_id)["invoices"] == []


def test_apply_appends_and_preserves_cash_receipts_obligations_and_supplier_bills(client):
    assert client.post("/api/import", json=invoice_csv_payload()).status_code == 200
    receipt = client.post("/api/receipts", json={
        "invoice_id": "EXISTING-1",
        "receipt_id": "existing-receipt",
        "amount": 500,
        "date": "2026-10-24",
    })
    assert receipt.status_code == 200, receipt.text
    plan = {
        "as_of": "2026-10-24",
        "obligations": [{
            "id": "payroll", "name": "Payroll", "amount": 600000, "day_of_month": 1,
            "frequency": "monthly", "category": "salary",
        }],
        "supplier_bills": [{
            "id": "msme-bill", "supplier": "Mysore Threads", "amount": 90000,
            "due_date": "2026-11-01", "is_msme": True, "status": "open",
        }],
        "monthly_sales": 0,
        "terms_days": 30,
        "monthly_noise_pct": 0,
    }
    assert client.post("/api/plan", json=plan).status_code == 200

    response = client.post("/api/import/pdf/apply", json={
        "invoices": [reviewed_invoice()],
        "confirm_append": True,
        "confirm_currency_inr": True,
    })

    assert response.status_code == 200, response.text
    assert response.json()["invoice_count"] == 1
    business = ledger.load_business(client.business_id)
    assert [invoice["id"] for invoice in business["invoices"]] == ["EXISTING-1", "INV-PDF-1"]
    assert business["opening_cash"] == 10500
    assert business["obligations"] == plan["obligations"]
    assert business["supplier_bills"] == plan["supplier_bills"]
    summary = client.get("/api/ledger").json()
    assert summary["received"] == 500
    assert summary["invoices"][1]["outstanding"] == 125000
    assert client.get("/api/business").json()["opening_cash"] == 10500
