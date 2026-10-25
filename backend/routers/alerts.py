"""Owner alert notification center and preferences routes."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from uuid import uuid4
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import insert, select, update

from backend import auth, clock, database as db, ledger
from backend.modules import alert_rules, delivery
from backend.modules.forecast_view_builder import build_headline, build_why

router = APIRouter(prefix="/api/alerts", tags=["alerts"])


class AlertPrefsPayload(BaseModel):
    risk_threshold: int = Field(ge=1, le=100, default=40)
    horizon_days: int = Field(ge=1, le=90, default=14)
    email_enabled: bool = False
    owner_email: str | None = Field(default=None, max_length=254)
    quiet_hours: str | None = Field(default=None, max_length=50)
    digest_weekly: bool = False


class SnoozePayload(BaseModel):
    days: int = Field(ge=1, le=30, default=1)


class TestEmailPayload(BaseModel):
    recipient_email: str | None = None


def _get_alert_prefs(business_id: str, default_email: str | None = None) -> dict:
    with db.engine().connect() as conn:
        row = conn.execute(
            select(db.alert_prefs).where(db.alert_prefs.c.business_id == business_id)
        ).first()
        if row:
            return dict(row._mapping)
    return {
        "business_id": business_id,
        "risk_threshold": 40,
        "horizon_days": 14,
        "email_enabled": False,
        "email_verified": False,
        "owner_email": default_email,
        "quiet_hours": None,
        "digest_weekly": False,
    }


@router.get("")
def list_alerts(user: auth.Account = Depends(auth.require_user)):
    """Evaluate business state, persist any newly triggered alerts, and return active alerts."""
    business = ledger.load_business(user.business_id)
    if not business:
        raise HTTPException(409, "Complete business setup first")

    today = clock.today_ist()
    now_iso = datetime.now(timezone.utc).isoformat()

    # Build forecast view
    from engine import run_forecast
    forecast = run_forecast(ledger.forecast_business(business, user.business_id))
    cash_updated = business.get("cash_updated_on") or business.get("as_of")
    stale = clock.is_stale(cash_updated, 3)
    try:
        stale = stale or date.fromisoformat(str(cash_updated).split("T")[0]) < today
    except (TypeError, ValueError):
        stale = True

    obligations = business.get("obligations", [])
    names = {item["id"]: item.get("name", item["id"]) for item in business.get("customers", [])}
    invoices = []
    for invoice in business.get("invoices", []):
        if invoice.get("status") != "open":
            continue
        amt = invoice["amount"] - invoice.get("received_amount", 0)
        invoices.append({
            "id": invoice["id"],
            "customer_id": invoice.get("customer_id"),
            "customer_name": names.get(invoice.get("customer_id"), invoice.get("customer_id")),
            "amount": amt,
            "due_date": invoice["due_date"],
            "expected_date": invoice["due_date"],
            "spread_days": 0,
        })

    forecast_view = {
        **forecast,
        "as_of": today.isoformat(),
        "cash_last_updated": cash_updated,
        "stale": stale,
        "why": build_why(invoices, obligations, forecast, today.isoformat()),
    }

    prefs = _get_alert_prefs(user.business_id, user.email)

    # Load existing dedupe keys from database
    with db.engine().connect() as conn:
        existing_keys_rows = conn.execute(
            select(db.alerts.c.dedupe_key).where(db.alerts.c.business_id == user.business_id)
        ).fetchall()
        existing_keys = {r[0] for r in existing_keys_rows}

    # Evaluate new alerts
    generated = alert_rules.evaluate_alerts(
        business_id=user.business_id,
        forecast_view=forecast_view,
        invoices=invoices,
        obligations=obligations,
        today=today,
        prefs=prefs,
        existing_dedupe_keys=existing_keys,
    )

    # Persist newly generated alerts
    if generated:
        with db.transaction() as conn:
            for item in generated:
                alt_id = f"ALT-{uuid4().hex[:8].upper()}"
                conn.execute(
                    insert(db.alerts).values(
                        id=alt_id,
                        business_id=user.business_id,
                        kind=item["kind"],
                        severity=item["severity"],
                        title=item["title"],
                        body=item["body"],
                        created_at=now_iso,
                        read=False,
                        dedupe_key=item["dedupe_key"],
                        link=item.get("link"),
                    )
                )

                # Send email notification if enabled and alert is critical shortage
                if prefs.get("email_enabled") and item["kind"] == "shortage_warning":
                    target_email = prefs.get("owner_email") or user.email
                    if target_email:
                        outbox_id = f"OUT-{uuid4().hex[:8].upper()}"
                        email_res = delivery.send_email(
                            to_email=target_email,
                            subject=f"[CashFlow Alert] {item['title']}",
                            body=f"Important Cash Flow Notice for your business:\n\n{item['body']}\n\nLog in to review and take action: https://cashflow.local{item.get('link', '')}",
                        )
                        conn.execute(
                            insert(db.alert_outbox).values(
                                id=outbox_id,
                                business_id=user.business_id,
                                alert_id=alt_id,
                                channel="email",
                                status=email_res.get("status", "sent"),
                                attempts=1,
                                last_error=email_res.get("error"),
                                created_at=now_iso,
                            )
                        )

    # Query active alerts for business
    with db.engine().connect() as conn:
        rows = conn.execute(
            select(db.alerts)
            .where(db.alerts.c.business_id == user.business_id)
            .order_by(db.alerts.c.created_at.desc())
            .limit(50)
        ).fetchall()

    today_str = today.isoformat()
    alerts_list = []
    for r in rows:
        m = dict(r._mapping)
        snooze_val = m.get("snoozed_until")
        if snooze_val and snooze_val > today_str:
            # currently snoozed
            continue
        alerts_list.append({
            "id": m["id"],
            "kind": m["kind"],
            "severity": m["severity"],
            "title": m["title"],
            "body": m["body"],
            "created_at": m["created_at"],
            "read": bool(m["read"]),
            "dedupe_key": m["dedupe_key"],
            "link": m.get("link"),
        })

    return alerts_list


@router.post("/{alert_id}/read")
def mark_read(alert_id: str, user: auth.Account = Depends(auth.require_user)):
    now_iso = datetime.now(timezone.utc).isoformat()
    with db.transaction() as conn:
        row = conn.execute(
            select(db.alerts).where(
                db.alerts.c.id == alert_id,
                db.alerts.c.business_id == user.business_id,
            )
        ).first()
        if not row:
            raise HTTPException(404, "Alert not found")
        conn.execute(
            update(db.alerts)
            .where(db.alerts.c.id == alert_id)
            .values(read=True, read_at=now_iso)
        )
    return {"status": "ok", "id": alert_id, "read": True}


@router.post("/{alert_id}/snooze")
def snooze_alert(
    alert_id: str,
    payload: SnoozePayload = SnoozePayload(),
    user: auth.Account = Depends(auth.require_user),
):
    today = clock.today_ist()
    snooze_until = (today + timedelta(days=payload.days)).isoformat()
    with db.transaction() as conn:
        row = conn.execute(
            select(db.alerts).where(
                db.alerts.c.id == alert_id,
                db.alerts.c.business_id == user.business_id,
            )
        ).first()
        if not row:
            raise HTTPException(404, "Alert not found")
        conn.execute(
            update(db.alerts)
            .where(db.alerts.c.id == alert_id)
            .values(snoozed_until=snooze_until)
        )
    return {"status": "snoozed", "id": alert_id, "snoozed_until": snooze_until}


@router.post("/mark-all-read")
def mark_all_read(user: auth.Account = Depends(auth.require_user)):
    now_iso = datetime.now(timezone.utc).isoformat()
    with db.transaction() as conn:
        conn.execute(
            update(db.alerts)
            .where(db.alerts.c.business_id == user.business_id, db.alerts.c.read == False)
            .values(read=True, read_at=now_iso)
        )
    return {"status": "ok"}


@router.get("/prefs")
def get_prefs(user: auth.Account = Depends(auth.require_user)):
    return _get_alert_prefs(user.business_id, user.email)


@router.post("/prefs")
def update_prefs(payload: AlertPrefsPayload, user: auth.Account = Depends(auth.require_user)):
    data = payload.model_dump()
    with db.transaction() as conn:
        existing = conn.execute(
            select(db.alert_prefs.c.business_id).where(db.alert_prefs.c.business_id == user.business_id)
        ).first()
        if existing:
            conn.execute(
                update(db.alert_prefs)
                .where(db.alert_prefs.c.business_id == user.business_id)
                .values(**data)
            )
        else:
            conn.execute(
                insert(db.alert_prefs).values(business_id=user.business_id, **data)
            )
    return {"status": "saved", "prefs": _get_alert_prefs(user.business_id, user.email)}


@router.post("/test-email")
def send_test_email(payload: TestEmailPayload, user: auth.Account = Depends(auth.require_user)):
    prefs = _get_alert_prefs(user.business_id, user.email)
    target_email = payload.recipient_email or prefs.get("owner_email") or user.email
    if not target_email:
        raise HTTPException(400, "Provide a valid email address for test notification.")

    today = clock.today_ist()
    subject = "[CashFlow Alert Test] Cash Runway & Due Notification"
    body = f"""Hello,

This is a test notification from CashFlow Copilot.
When cash shortage risks or upcoming obligations are detected for your business, you will receive timely actionable alerts like this:

Sample Alert:
• Event: Projected cash shortage within 14 days
• Date: {today + timedelta(days=12)}
• Action: Follow up on overdue receivables to protect payroll runway.

Status: Configured successfully.
"""
    result = delivery.send_email(to_email=target_email, subject=subject, body=body)
    return {"status": "dispatched", "delivery": result}
