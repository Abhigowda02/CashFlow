"""Unit tests for reminder escalation ladder and template engine."""
from datetime import date
from backend.modules.reminder_engine import (
    format_inr,
    generate_customer_reminders,
    get_ladder_rung,
    is_invoice_disputed,
    is_promise_active,
    next_step,
    render_template,
)


def test_format_inr():
    assert format_inr(0) == "Rs 0"
    assert format_inr(500) == "Rs 500"
    assert format_inr(1500) == "Rs 1,500"
    assert format_inr(85000) == "Rs 85,000"
    assert format_inr(120000) == "Rs 1,20,000"
    assert format_inr(1500000) == "Rs 15,00,000"
    assert format_inr(-45000) == "-Rs 45,000"


def test_get_ladder_rung():
    assert get_ladder_rung(-5) is None
    assert get_ladder_rung(-3) == 1
    assert get_ladder_rung(-1) == 1
    assert get_ladder_rung(0) == 2
    assert get_ladder_rung(4) == 2
    assert get_ladder_rung(7) == 3
    assert get_ladder_rung(10) == 3
    assert get_ladder_rung(15) == 4
    assert get_ladder_rung(29) == 4
    assert get_ladder_rung(30) == 5
    assert get_ladder_rung(45) == 5


def test_promise_active():
    today = date(2026, 10, 25)
    promises = [
        {"customer_id": "CUST-1", "promise_date": "2026-10-28"},
        {"customer_id": "CUST-2", "promise_date": "2026-10-20"},
    ]
    # Future promise -> active (paused)
    assert is_promise_active("CUST-1", promises, today) is True
    # Past promise -> broken (resumed)
    assert is_promise_active("CUST-2", promises, today) is False
    # No promise -> False
    assert is_promise_active("CUST-3", promises, today) is False


def test_invoice_dispute():
    context = {"disputed_invoice_ids": ["INV-101"]}
    assert is_invoice_disputed("INV-101", context) is True
    assert is_invoice_disputed("INV-102", context) is False


def test_next_step_ladder_boundaries_and_dedupe():
    today = date(2026, 10, 25)
    invoice = {
        "id": "INV-1",
        "customer_id": "CUST-A",
        "amount": 100000,
        "received_amount": 0,
        "status": "open",
        "due_date": "2026-10-18",  # 7 days overdue -> rung 3
    }
    sent_log = []

    step = next_step(invoice, today, sent_log)
    assert step is not None
    assert step["rung"] == 3
    assert step["overdue_days"] == 7

    # If rung 3 was already sent, it should not repeat
    sent_log.append({
        "invoice_ids": ["INV-1"],
        "rung": 3,
        "status": "sent",
    })
    step_after = next_step(invoice, today, sent_log)
    assert step_after is None


def test_grouping_multiple_invoices_per_customer():
    today = date(2026, 10, 25)
    invoices = [
        {
            "id": "INV-1",
            "customer_id": "CUST-A",
            "amount": 50000,
            "received_amount": 0,
            "status": "open",
            "due_date": "2026-10-18",  # 7 days overdue -> rung 3
        },
        {
            "id": "INV-2",
            "customer_id": "CUST-A",
            "amount": 75000,
            "received_amount": 0,
            "status": "open",
            "due_date": "2026-10-10",  # 15 days overdue -> rung 4
        },
    ]
    customers = [
        {
            "id": "CUST-A",
            "name": "Acme Corp",
            "contact_email": "acme@example.com",
            "contact_phone": "9876543210",
        }
    ]
    reminders = generate_customer_reminders(
        invoices=invoices,
        customers=customers,
        sent_log=[],
        promises=[],
        today=today,
        settings={"sender_name": "Apex Finance", "upi_id": "apex@upi"},
    )

    # Exactly one reminder for Acme Corp grouping both invoices
    assert len(reminders) == 1
    rem = reminders[0]
    assert rem["customer_id"] == "CUST-A"
    assert set(rem["invoice_ids"]) == {"INV-1", "INV-2"}
    assert rem["rung"] == 4  # Highest rung among the invoices
    assert rem["total_amount"] == 125000
    assert "Rs 1,25,000" in rem["body"]
    assert "apex@upi" in rem["body"]


def test_strategic_relationship_tone():
    customer = {
        "id": "CUST-B",
        "name": "Bharat Traders",
        "collection_context": {"importance": "strategic"},
    }
    invoices = [
        {"invoice_id": "INV-201", "amount": 200000, "due_date": "2026-10-25"}
    ]
    rendered = render_template(customer, invoices, rung=2)
    assert "truly value our ongoing partnership" in rendered["body"]


def test_rung_5_advocate_review_warning():
    customer = {"id": "CUST-C", "name": "Defaulter LLC"}
    invoices = [{"invoice_id": "INV-301", "amount": 350000, "due_date": "2026-09-01"}]
    rendered = render_template(customer, invoices, rung=5)
    assert "DRAFT - FOR ADVOCATE REVIEW ONLY" in rendered["subject"]
    assert "THIS IS NOT LEGAL ADVICE" in rendered["body"]
    assert "MSMED" in rendered["body"]
