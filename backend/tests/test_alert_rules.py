"""Unit tests for owner alert rules engine."""
from datetime import date
from backend.modules.alert_rules import evaluate_alerts


def test_stale_balance_alert():
    forecast_view = {
        "stale": True,
        "cash_last_updated": "2026-10-15",
        "shortage_prob": 0.85,  # Should be suppressed because stale
        "first_shortage_date": "2026-10-30",
    }
    alerts = evaluate_alerts(
        business_id="b-1",
        forecast_view=forecast_view,
        invoices=[],
        obligations=[],
        today="2026-10-25",
        prefs={"risk_threshold": 40, "horizon_days": 14},
    )
    # Stale alert must be present
    assert any(a["kind"] == "stale_cash" for a in alerts)
    # Speculative shortage alert must be SUPPRESSED when stale
    assert not any(a["kind"] == "shortage_warning" for a in alerts)


def test_shortage_alert_naming_cause_and_threshold():
    forecast_view = {
        "stale": False,
        "cash_last_updated": "2026-10-25",
        "shortage_prob": 0.65,
        "first_shortage_date": "2026-11-02",  # 8 days away, within 14d horizon
        "safety_floor": 100000,
    }
    invoices = [
        {
            "id": "INV-101",
            "customer_id": "CUST-1",
            "amount": 250000,
            "received_amount": 0,
            "status": "open",
            "due_date": "2026-10-15",
        }
    ]
    obligations = [
        {"name": "Payroll", "amount": 180000, "day_of_month": 5}
    ]

    alerts = evaluate_alerts(
        business_id="b-1",
        forecast_view=forecast_view,
        invoices=invoices,
        obligations=obligations,
        today="2026-10-25",
        prefs={"risk_threshold": 40, "horizon_days": 14},
    )

    shortage = next((a for a in alerts if a["kind"] == "shortage_warning"), None)
    assert shortage is not None
    assert shortage["severity"] == "warning"
    assert "2026-11-02" in shortage["body"]
    assert "delayed customer receivables" in shortage["body"]
    assert "Payroll" in shortage["body"]


def test_deduplication():
    forecast_view = {
        "stale": False,
        "cash_last_updated": "2026-10-25",
        "shortage_prob": 0.65,
        "first_shortage_date": "2026-11-02",
    }
    existing_keys = {"b-1:shortage:2026-11-02:0.7"}

    alerts = evaluate_alerts(
        business_id="b-1",
        forecast_view=forecast_view,
        invoices=[],
        obligations=[],
        today="2026-10-25",
        prefs={"risk_threshold": 40, "horizon_days": 14},
        existing_dedupe_keys=existing_keys,
    )
    # Already in existing dedupe keys -> should not generate duplicate
    assert not any(a["kind"] == "shortage_warning" for a in alerts)


def test_upcoming_obligations_consolidation_and_escalation():
    today = date(2026, 10, 25)
    # Obligation on 28th (in 3 days)
    obligations = [
        {"name": "Office Rent", "amount": 60000, "day_of_month": 28},
        {"name": "Server Hosting", "amount": 15000, "day_of_month": 28},
    ]
    forecast_view = {
        "stale": False,
        "cash_last_updated": "2026-10-25",
        "shortage_prob": 0.1,
        "dates": ["2026-10-25", "2026-10-28"],
        "p50": [150000, 40000],  # p50 drops below safety floor 50000 on 28th
        "safety_floor": 50000,
    }

    alerts = evaluate_alerts(
        business_id="b-1",
        forecast_view=forecast_view,
        invoices=[],
        obligations=obligations,
        today=today,
    )

    ob_alert = next((a for a in alerts if a["kind"] == "msme_due"), None)
    assert ob_alert is not None
    # Both obligations consolidated into one alert
    assert "Office Rent" in ob_alert["body"]
    assert "Server Hosting" in ob_alert["body"]
    assert "Rs 75,000" in ob_alert["title"]
    # Escalated because p50 < safety floor near due date
    assert ob_alert["severity"] == "warning"
