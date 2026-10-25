"""Tests for owner alerts router endpoints."""
from backend import ledger
from backend.tests.conftest import signed_in_client


def test_alerts_lifecycle_and_prefs(client, monkeypatch):
    monkeypatch.setenv("APP_FAKE_TODAY", "2026-10-24")

    # 1. Fetch alerts (fresh setup should have at least stale alert since cash is old)
    res = client.get("/api/alerts")
    assert res.status_code == 200, res.text
    alerts = res.json()
    assert isinstance(alerts, list)

    # 2. Preferences
    prefs_res = client.get("/api/alerts/prefs")
    assert prefs_res.status_code == 200
    prefs = prefs_res.json()
    assert "risk_threshold" in prefs

    save_prefs = client.post(
        "/api/alerts/prefs",
        json={
            "risk_threshold": 30,
            "horizon_days": 21,
            "email_enabled": True,
            "owner_email": "owner@example.com",
            "digest_weekly": False,
        },
    )
    assert save_prefs.status_code == 200
    updated_prefs = client.get("/api/alerts/prefs").json()
    assert updated_prefs["risk_threshold"] == 30
    assert updated_prefs["horizon_days"] == 21
    assert updated_prefs["email_enabled"] is True

    # 3. Test email dispatch
    test_email = client.post("/api/alerts/test-email", json={"recipient_email": "owner@example.com"})
    assert test_email.status_code == 200
    assert test_email.json()["status"] == "dispatched"


def test_alerts_read_and_snooze(client):
    # Setup business with obligations
    business = ledger.load_business(client.business_id)
    business["cash_updated_on"] = "2026-10-24"
    business["as_of"] = "2026-10-24"
    business["obligations"] = [{"id": "ob-1", "name": "Office Rent", "amount": 50000, "day_of_month": 27}]
    ledger.save_business(business, client.business_id)

    alerts = client.get("/api/alerts").json()
    if alerts:
        target = alerts[0]
        # Mark read
        read_res = client.post(f"/api/alerts/{target['id']}/read")
        assert read_res.status_code == 200
        assert read_res.json()["read"] is True

        # Snooze
        snooze_res = client.post(f"/api/alerts/{target['id']}/snooze", json={"days": 2})
        assert snooze_res.status_code == 200
        assert snooze_res.json()["status"] == "snoozed"

        # Mark all read
        all_read = client.post("/api/alerts/mark-all-read")
        assert all_read.status_code == 200


def test_alerts_tenant_isolation(client):
    alerts = client.get("/api/alerts").json()
    if alerts:
        alt_id = alerts[0]["id"]
        client2 = signed_in_client("tenant2@example.com")
        res = client2.post(f"/api/alerts/{alt_id}/read")
        assert res.status_code == 404
