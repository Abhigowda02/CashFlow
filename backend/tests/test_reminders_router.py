"""Tests for reminder router endpoints and workflows."""
from backend import database as db, ledger
from backend.tests.conftest import signed_in_client


def _setup_invoices(client):
    # Commit sample invoices for the client's business
    business = ledger.load_business(client.business_id)
    business["customers"] = [
        {"id": "C-1", "name": "Apex Corp", "contact_email": "apex@example.com", "contact_phone": "9876543210"}
    ]
    business["invoices"] = [
        {
            "id": "INV-101",
            "customer_id": "C-1",
            "amount": 150000,
            "received_amount": 0,
            "status": "open",
            "issue_date": "2026-09-01",
            "due_date": "2026-10-17",  # 7 days overdue relative to 2026-10-24
        }
    ]
    ledger.save_business(business, client.business_id)


def test_reminders_queue_and_lifecycle(client):
    _setup_invoices(client)

    # 1. Fetch queue
    res = client.get("/api/reminders/queue")
    assert res.status_code == 200, res.text
    queue = res.json()
    assert len(queue) == 1
    rem = queue[0]
    assert rem["customer_id"] == "C-1"
    assert rem["rung"] == 3
    assert rem["status"] == "draft"
    assert "INV-101" in rem["invoice_ids"]
    assert "Rs 1,50,000" in rem["body"]

    rem_id = rem["id"]

    # 2. Cannot send before approval (Rule 5: No silent send)
    send_bad = client.post(f"/api/reminders/{rem_id}/send", json={})
    assert send_bad.status_code == 400
    assert "approve" in send_bad.text.lower()

    # 3. Edit draft
    edit_res = client.post(
        f"/api/reminders/{rem_id}/edit",
        json={
            "subject": "Custom subject line",
            "body": "Custom body text",
            "channel": "email",
            "recipient": "apex@example.com",
        },
    )
    assert edit_res.status_code == 200

    # 4. Approve draft
    appr_res = client.post(f"/api/reminders/{rem_id}/approve")
    assert appr_res.status_code == 200
    assert appr_res.json()["status"] == "approved"

    # 5. Send approved draft
    send_ok = client.post(f"/api/reminders/{rem_id}/send", json={})
    assert send_ok.status_code == 200
    assert send_ok.json()["status"] == "sent"

    # 6. Verify audit history log
    hist_res = client.get("/api/reminders/history")
    assert hist_res.status_code == 200
    logs = hist_res.json()
    assert len(logs) == 1
    assert logs[0]["customer_id"] == "C-1"
    assert logs[0]["reminder_id"] == rem_id


def test_reminders_settings(client):
    save_res = client.post(
        "/api/reminders/settings",
        json={
            "sender_name": "My Company Accounts",
            "upi_id": "company@icici",
            "bank_name": "HDFC Bank",
            "account_number": "1234567890",
            "ifsc_code": "HDFC0001234",
        },
    )
    assert save_res.status_code == 200
    get_res = client.get("/api/reminders/settings")
    assert get_res.status_code == 200
    settings = get_res.json()
    assert settings["sender_name"] == "My Company Accounts"
    assert settings["upi_id"] == "company@icici"


def test_reminders_tenant_isolation(client):
    _setup_invoices(client)
    res = client.get("/api/reminders/queue")
    rem_id = res.json()[0]["id"]

    # Second user shouldn't be able to approve or send first user's reminder
    client2 = signed_in_client("other@example.com")
    resp = client2.post(f"/api/reminders/{rem_id}/approve")
    assert resp.status_code == 404
