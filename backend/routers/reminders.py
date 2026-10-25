"""Customer payment reminder ladder and delivery routes."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from uuid import uuid4
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import delete, insert, select, update

from backend import auth, clock, database as db, ledger
from backend.modules import delivery, reminder_engine

router = APIRouter(prefix="/api/reminders", tags=["reminders"])


class ReminderEditPayload(BaseModel):
    subject: str = Field(min_length=1, max_length=500)
    body: str = Field(min_length=1)
    channel: str = Field(pattern="^(email|whatsapp|sms|letter)$")
    recipient: str | None = None


class ReminderSendPayload(BaseModel):
    confirm_legal_draft: bool = False


class BusinessSettingsPayload(BaseModel):
    sender_name: str | None = Field(default=None, max_length=120)
    contact_email: str | None = Field(default=None, max_length=254)
    contact_phone: str | None = Field(default=None, max_length=30)
    upi_id: str | None = Field(default=None, max_length=100)
    bank_name: str | None = Field(default=None, max_length=120)
    account_name: str | None = Field(default=None, max_length=120)
    account_number: str | None = Field(default=None, max_length=50)
    ifsc_code: str | None = Field(default=None, max_length=20)


def _get_business_settings(business_id: str) -> dict:
    with db.engine().connect() as conn:
        row = conn.execute(
            select(db.business_settings).where(db.business_settings.c.business_id == business_id)
        ).first()
        if row:
            return dict(row._mapping)
    return {}


@router.get("/settings")
def get_settings(user: auth.Account = Depends(auth.require_user)):
    return _get_business_settings(user.business_id)


@router.post("/settings")
def save_settings(payload: BusinessSettingsPayload, user: auth.Account = Depends(auth.require_user)):
    data = payload.model_dump()
    with db.transaction() as conn:
        existing = conn.execute(
            select(db.business_settings.c.business_id).where(db.business_settings.c.business_id == user.business_id)
        ).first()
        if existing:
            conn.execute(
                update(db.business_settings)
                .where(db.business_settings.c.business_id == user.business_id)
                .values(**data)
            )
        else:
            conn.execute(
                insert(db.business_settings).values(business_id=user.business_id, **data)
            )
    return {"status": "saved", "settings": _get_business_settings(user.business_id)}


@router.get("/queue")
def get_queue(user: auth.Account = Depends(auth.require_user)):
    """Retrieve today's reminder queue, generating fresh drafts if not yet generated."""
    business = ledger.load_business(user.business_id)
    if not business:
        raise HTTPException(409, "Complete business setup first")

    today = clock.today_ist()
    settings = _get_business_settings(user.business_id)

    # Load sent logs for this business to prevent repeats
    with db.engine().connect() as conn:
        sent_rows = conn.execute(
            select(db.reminder_logs).where(db.reminder_logs.c.business_id == user.business_id)
        ).fetchall()
        sent_log = [dict(r._mapping) for r in sent_rows]

        # Load existing pending reminders
        existing_rows = conn.execute(
            select(db.reminders).where(
                db.reminders.c.business_id == user.business_id,
                db.reminders.c.status.in_(["draft", "approved"]),
            )
        ).fetchall()
        existing_by_cust = {r._mapping["customer_id"]: dict(r._mapping) for r in existing_rows}

    # Evaluate new drafts
    invoices = business.get("invoices", [])
    customers = business.get("customers", [])
    promises = business.get("promises", [])

    fresh_drafts = reminder_engine.generate_customer_reminders(
        invoices=invoices,
        customers=customers,
        sent_log=sent_log,
        promises=promises,
        today=today,
        settings=settings,
    )

    now_iso = datetime.now(timezone.utc).isoformat()
    with db.transaction() as conn:
        for draft in fresh_drafts:
            cust_id = draft["customer_id"]
            if cust_id in existing_by_cust:
                # Update draft content if still in draft status
                current = existing_by_cust[cust_id]
                if current["status"] == "draft":
                    conn.execute(
                        update(db.reminders)
                        .where(db.reminders.c.id == current["id"])
                        .values(
                            invoice_ids=json.dumps(draft["invoice_ids"]),
                            rung=draft["rung"],
                            subject=draft["subject"],
                            body=draft["body"],
                            recipient=draft["recipient"],
                        )
                    )
            else:
                rem_id = f"REM-{uuid4().hex[:8].upper()}"
                conn.execute(
                    insert(db.reminders).values(
                        id=rem_id,
                        business_id=user.business_id,
                        customer_id=cust_id,
                        customer_name=draft["customer_name"],
                        invoice_ids=json.dumps(draft["invoice_ids"]),
                        rung=draft["rung"],
                        channel=draft["channel"],
                        subject=draft["subject"],
                        body=draft["body"],
                        status="draft",
                        recipient=draft["recipient"],
                        created_at=now_iso,
                        delivery_status="pending",
                    )
                )

    # Return all open/active reminders in contract format
    with db.engine().connect() as conn:
        all_reminders = conn.execute(
            select(db.reminders).where(
                db.reminders.c.business_id == user.business_id,
                db.reminders.c.status.in_(["draft", "approved"]),
            ).order_by(db.reminders.c.rung.desc(), db.reminders.c.created_at.desc())
        ).fetchall()

    result = []
    for row in all_reminders:
        m = dict(row._mapping)
        raw_inv = m.get("invoice_ids")
        inv_list = json.loads(raw_inv) if isinstance(raw_inv, str) else (raw_inv or [])
        result.append({
            "id": m["id"],
            "invoice_ids": inv_list,
            "customer_id": m["customer_id"],
            "customer_name": m.get("customer_name"),
            "rung": m["rung"],
            "channel": m["channel"],
            "subject": m["subject"],
            "body": m["body"],
            "status": m["status"],
            "recipient": m.get("recipient"),
            "created_at": m["created_at"],
            "sent_at": m.get("sent_at"),
        })
    return result


@router.post("/{reminder_id}/edit")
@router.patch("/{reminder_id}")
def edit_reminder(
    reminder_id: str,
    payload: ReminderEditPayload,
    user: auth.Account = Depends(auth.require_user),
):
    with db.transaction() as conn:
        row = conn.execute(
            select(db.reminders).where(
                db.reminders.c.id == reminder_id,
                db.reminders.c.business_id == user.business_id,
            )
        ).first()
        if not row:
            raise HTTPException(404, "Reminder draft not found")
        conn.execute(
            update(db.reminders)
            .where(db.reminders.c.id == reminder_id)
            .values(
                subject=payload.subject,
                body=payload.body,
                channel=payload.channel,
                recipient=payload.recipient,
            )
        )
    return {"status": "updated", "id": reminder_id}


@router.post("/{reminder_id}/approve")
def approve_reminder(reminder_id: str, user: auth.Account = Depends(auth.require_user)):
    now_iso = datetime.now(timezone.utc).isoformat()
    with db.transaction() as conn:
        row = conn.execute(
            select(db.reminders).where(
                db.reminders.c.id == reminder_id,
                db.reminders.c.business_id == user.business_id,
            )
        ).first()
        if not row:
            raise HTTPException(404, "Reminder draft not found")
        conn.execute(
            update(db.reminders)
            .where(db.reminders.c.id == reminder_id)
            .values(status="approved", approved_at=now_iso)
        )
    return {"status": "approved", "id": reminder_id, "approved_at": now_iso}


@router.post("/{reminder_id}/cancel")
def cancel_reminder(reminder_id: str, user: auth.Account = Depends(auth.require_user)):
    with db.transaction() as conn:
        row = conn.execute(
            select(db.reminders).where(
                db.reminders.c.id == reminder_id,
                db.reminders.c.business_id == user.business_id,
            )
        ).first()
        if not row:
            raise HTTPException(404, "Reminder draft not found")
        conn.execute(
            update(db.reminders)
            .where(db.reminders.c.id == reminder_id)
            .values(status="cancelled")
        )
    return {"status": "cancelled", "id": reminder_id}


@router.post("/{reminder_id}/send")
def send_reminder(
    reminder_id: str,
    payload: ReminderSendPayload = ReminderSendPayload(),
    user: auth.Account = Depends(auth.require_user),
):
    with db.engine().connect() as conn:
        row = conn.execute(
            select(db.reminders).where(
                db.reminders.c.id == reminder_id,
                db.reminders.c.business_id == user.business_id,
            )
        ).first()
        if not row:
            raise HTTPException(404, "Reminder not found")
        rem = dict(row._mapping)

    if rem["status"] != "approved":
        raise HTTPException(400, "Review and approve the draft reminder before sending.")

    # Rung 5 requires explicit confirmation
    if rem["rung"] == 5 and not payload.confirm_legal_draft:
        raise HTTPException(
            400,
            "Rung 5 is a legal demand draft. Explicitly confirm advocate review to proceed.",
        )

    channel = rem["channel"]
    recipient = rem.get("recipient")
    subject = rem["subject"]
    body = rem["body"]
    now_iso = datetime.now(timezone.utc).isoformat()

    delivery_res = {}
    external_link = None

    if channel == "email":
        if not recipient:
            raise HTTPException(400, "Customer email address is required for email dispatch.")
        delivery_res = delivery.send_email(to_email=recipient, subject=subject, body=body)
    elif channel == "whatsapp":
        if not recipient:
            raise HTTPException(400, "Customer phone number is required for WhatsApp dispatch.")
        external_link = delivery.build_whatsapp_link(recipient, body)
        delivery_res = {"status": "link_generated", "link": external_link}
    elif channel == "sms":
        if not recipient:
            raise HTTPException(400, "Customer phone number is required for SMS dispatch.")
        external_link = delivery.build_sms_link(recipient, body)
        delivery_res = {"status": "link_generated", "link": external_link}
    else:
        delivery_res = {"status": "manual", "message": "Manual letter draft ready for print."}

    # Record in immutable reminder_logs table
    log_id = f"LOG-{uuid4().hex[:8].upper()}"
    with db.transaction() as conn:
        conn.execute(
            insert(db.reminder_logs).values(
                id=log_id,
                business_id=user.business_id,
                reminder_id=reminder_id,
                customer_id=rem["customer_id"],
                invoice_ids=rem["invoice_ids"],
                rung=rem["rung"],
                channel=channel,
                subject=subject,
                body=body,
                recipient=recipient,
                status=delivery_res.get("status", "sent"),
                evidence=json.dumps(delivery_res),
                timestamp=now_iso,
            )
        )
        conn.execute(
            update(db.reminders)
            .where(db.reminders.c.id == reminder_id)
            .values(
                status="sent",
                sent_at=now_iso,
                delivery_status=delivery_res.get("status", "sent"),
            )
        )

    return {
        "status": "sent",
        "reminder_id": reminder_id,
        "channel": channel,
        "delivery": delivery_res,
        "link": external_link,
        "sent_at": now_iso,
    }


@router.get("/history")
def get_history(user: auth.Account = Depends(auth.require_user)):
    with db.engine().connect() as conn:
        rows = conn.execute(
            select(db.reminder_logs)
            .where(db.reminder_logs.c.business_id == user.business_id)
            .order_by(db.reminder_logs.c.timestamp.desc())
            .limit(100)
        ).fetchall()
        return [dict(r._mapping) for r in rows]
