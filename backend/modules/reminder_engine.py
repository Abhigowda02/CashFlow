"""Customer payment reminder ladder and escalation engine (pure module).

Input: Invoices, customers, sent_log, promises, today date, business settings.
Output: Grouped and formatted reminder drafts ready for owner review.

Ladder rungs relative to due date (today - due_date):
- Rung 1: -3 days (Friendly upcoming reminder: 3 days before due date)
- Rung 2: 0 days (Polite due reminder: on due date or within 1-6 days overdue)
- Rung 3: +7 days (Firm overdue reminder: 7 to 14 days overdue)
- Rung 4: +15 days (Final demand with statutory interest note: 15 to 29 days overdue)
- Rung 5: +30 days (Draft legal notice reminder: 30+ days overdue, marked draft for advocate review)
"""
from __future__ import annotations

from datetime import date
from typing import Any


def format_inr(value: int | float) -> str:
    """Format an integer or float amount into standard Indian grouped notation."""
    int_val = int(round(value))
    prefix = "-Rs " if int_val < 0 else "Rs "
    digits = str(abs(int_val))
    if len(digits) <= 3:
        return f"{prefix}{digits}"
    last_three = digits[-3:]
    remaining = digits[:-3]
    chunks = []
    while len(remaining) > 2:
        chunks.insert(0, remaining[-2:])
        remaining = remaining[:-2]
    if remaining:
        chunks.insert(0, remaining)
    return f"{prefix}{','.join(chunks)},{last_three}"


def get_ladder_rung(delta_days: int) -> int | None:
    """Determine the applicable reminder rung from overdue days (today - due_date).

    Args:
        delta_days: Days past due date (negative means before due date).

    Returns:
        Rung number (1..5) or None if not yet at reminder stage.
    """
    if delta_days < -3:
        return None
    if -3 <= delta_days < 0:
        return 1
    if 0 <= delta_days < 7:
        return 2
    if 7 <= delta_days < 15:
        return 3
    if 15 <= delta_days < 30:
        return 4
    return 5


def is_promise_active(customer_id: str, promises: list[dict[str, Any]], today: date) -> bool:
    """Check if an unbroken promise-to-pay exists for this customer."""
    for promise in promises:
        if promise.get("customer_id") == customer_id:
            promised_date_str = promise.get("promise_date") or promise.get("promised_date")
            if promised_date_str:
                try:
                    p_date = date.fromisoformat(str(promised_date_str).split("T")[0])
                    # If today is on or before promised date, promise is active
                    if today <= p_date:
                        return True
                except (ValueError, TypeError):
                    continue
    return False


def is_invoice_disputed(invoice_id: str, context: dict[str, Any] | None) -> bool:
    """Check whether the invoice has an active dispute flag."""
    if not context:
        return False
    disputed_ids = context.get("disputed_invoice_ids") or []
    if invoice_id in disputed_ids:
        return True
    if context.get("service_issue") == "open" and not disputed_ids:
        return True
    return False


def next_step(
    invoice: dict[str, Any],
    today: date | str,
    sent_log: list[dict[str, Any]],
    promises: list[dict[str, Any]] | None = None,
    customer_context: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Evaluate an open invoice and return its next eligible reminder step or None.

    Rules:
    - Never repeat a rung already sent for this invoice.
    - Skip paid or non-open invoices.
    - Pause if a promise-to-pay is active and not broken.
    - Pause if the invoice is disputed.
    """
    if invoice.get("status") != "open":
        return None

    amount = int(invoice.get("amount", 0))
    received = int(invoice.get("received_amount", 0))
    outstanding = amount - received
    if outstanding <= 0:
        return None

    inv_id = str(invoice.get("id", ""))
    cust_id = str(invoice.get("customer_id", ""))

    # Check dispute pause
    if is_invoice_disputed(inv_id, customer_context):
        return None

    now = date.fromisoformat(str(today).split("T")[0]) if isinstance(today, str) else today
    due = date.fromisoformat(str(invoice.get("due_date", "")).split("T")[0])
    delta_days = (now - due).days

    # Check promise pause
    if promises and is_promise_active(cust_id, promises, now):
        return None

    target_rung = get_ladder_rung(delta_days)
    if target_rung is None:
        return None

    # Check sent_log: never repeat a rung already sent for this invoice
    for entry in sent_log:
        if entry.get("status") not in ("sent", "mock_sent"):
            continue
        entry_inv_ids = entry.get("invoice_ids")
        if isinstance(entry_inv_ids, str):
            import json
            try:
                entry_inv_ids = json.loads(entry_inv_ids)
            except Exception:
                entry_inv_ids = [entry_inv_ids]
        if entry_inv_ids and inv_id in entry_inv_ids:
            sent_rung = int(entry.get("rung", 0))
            if sent_rung >= target_rung:
                return None

    return {
        "invoice_id": inv_id,
        "customer_id": cust_id,
        "rung": target_rung,
        "due_date": str(due),
        "overdue_days": max(0, delta_days),
        "amount": outstanding,
    }


def render_template(
    customer: dict[str, Any],
    invoices: list[dict[str, Any]],
    rung: int,
    settings: dict[str, Any] | None = None,
    lang: str = "en",
) -> dict[str, str]:
    """Render customer-facing personalized subject and message body.

    Tone derived from customer context:
    - strategic / repeat customer = softer opening
    - service issue open = acknowledgment first
    """
    cfg = settings or {}
    cust_name = customer.get("name") or customer.get("id") or "Valued Client"
    total_due = sum(inv.get("amount", 0) for inv in invoices)
    total_due_fmt = format_inr(total_due)
    sender_name = cfg.get("sender_name") or "Accounts Team"

    # Payment info lines
    payment_lines = []
    if cfg.get("upi_id"):
        payment_lines.append(f"UPI ID: {cfg['upi_id']}")
    if cfg.get("account_number"):
        bank = cfg.get("bank_name", "Bank")
        acct_name = cfg.get("account_name", sender_name)
        payment_lines.append(f"Bank Transfer: {bank} | A/C: {cfg['account_number']} | IFSC: {cfg.get('ifsc_code', '')} ({acct_name})")

    payment_block = "\n".join(payment_lines) if payment_lines else "Please contact us for bank clearance details."

    # Invoice breakdown table/text
    inv_lines = []
    for inv in invoices:
        inv_amt = format_inr(inv.get("amount", 0))
        inv_lines.append(f"  * Inv #{inv['invoice_id']}: {inv_amt} (Due: {inv['due_date']})")
    inv_block = "\n".join(inv_lines)

    context = customer.get("collection_context") or {}
    is_strategic = context.get("importance") == "strategic" or customer.get("repeat_customer", False)
    has_service_note = context.get("service_issue") in ("open", "resolving")

    softer_greeting = f"Dear {cust_name},\nWe hope business is thriving. We truly value our ongoing partnership with your team."
    standard_greeting = f"Dear {cust_name},\nGreetings from {sender_name}."

    greeting = softer_greeting if is_strategic else standard_greeting

    if has_service_note:
        greeting += "\nWe are actively prioritizing and resolving the open service matter discussed, and wanted to share the reconciled invoice details below."

    if rung == 1:
        subject = f"Friendly Reminder: Upcoming payment due - {total_due_fmt}"
        body = f"""{greeting}

This is a gentle reminder that the following receivable of {total_due_fmt} is scheduled for clearance shortly:
{inv_block}

Kindly arrange settlement by the due date.

Payment Details:
{payment_block}

Thank you,
{sender_name}"""

    elif rung == 2:
        subject = f"Payment Due Today: Reconciled dues of {total_due_fmt}"
        body = f"""{greeting}

The following invoice(s) totaling {total_due_fmt} are due today:
{inv_block}

We request you to process the payment today. If already initiated, please share the transaction UTR number so we may update our records.

Payment Details:
{payment_block}

Warm regards,
{sender_name}"""

    elif rung == 3:
        subject = f"Follow-up: Overdue payment notice for {total_due_fmt}"
        body = f"""{greeting}

Our records show that invoices totaling {total_due_fmt} remain overdue:
{inv_block}

Please arrange clearance at the earliest or let us know if there is any clarification needed on our billing.

Payment Details:
{payment_block}

Sincerely,
{sender_name}"""

    elif rung == 4:
        subject = f"Urgent Demand: Overdue settlement of {total_due_fmt} with statutory interest notice"
        body = f"""{greeting}

Despite previous reminders, the following invoices totaling {total_due_fmt} remain unpaid:
{inv_block}

Please note that under MSMED Act Section 16 provisions, delayed commercial payments attract compound interest with monthly rests. We request you to clear the outstanding {total_due_fmt} within 7 days to avoid formal escalation.

Payment Details:
{payment_block}

Sincerely,
{sender_name}"""

    else:
        # Rung 5: Draft notice for advocate review
        subject = f"DRAFT - FOR ADVOCATE REVIEW ONLY: Final demand notice for {total_due_fmt}"
        body = f"""*** DRAFT - FOR ADVOCATE REVIEW ONLY. THIS IS NOT LEGAL ADVICE. ***

To: {cust_name}
From: {sender_name}

DEMAND NOTICE FOR SETTLEMENT OF COMMERCIAL DUES

You are hereby requested to arrange immediate clearance of the outstanding principal amount of {total_due_fmt} in respect of supply of goods/services:
{inv_block}

Statutory notice:
Under Section 16 of the Micro, Small and Medium Enterprises Development (MSMED) Act, 2006, overdue amounts beyond the agreed period attract penal interest at 3 times the RBI bank rate compounded with monthly rests.

Kindly settle the entire balance within 15 days of this notice to the following bank account:
{payment_block}

*** DRAFT PREPARED FOR ADVOCATE REVIEW AND FORMAL DISPATCH ***"""

    return {"subject": subject.strip(), "body": body.strip()}


def generate_customer_reminders(
    invoices: list[dict[str, Any]],
    customers: list[dict[str, Any]],
    sent_log: list[dict[str, Any]],
    promises: list[dict[str, Any]],
    today: date | str,
    settings: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Group eligible overdue/due invoices by customer into one reminder draft per customer."""
    cust_map = {c["id"]: c for c in customers}
    grouped_steps: dict[str, list[dict[str, Any]]] = {}

    for inv in invoices:
        cust_id = inv.get("customer_id", "")
        customer = cust_map.get(cust_id, {})
        step = next_step(inv, today, sent_log, promises, customer.get("collection_context"))
        if step:
            grouped_steps.setdefault(cust_id, []).append(step)

    reminders: list[dict[str, Any]] = []
    for cust_id, steps in grouped_steps.items():
        customer = cust_map.get(cust_id, {"id": cust_id, "name": cust_id})
        # Customer rung is the highest ladder rung among the grouped invoices
        max_rung = max(s["rung"] for s in steps)
        rendered = render_template(customer, steps, max_rung, settings)

        email = customer.get("contact_email") or customer.get("email")
        phone = customer.get("contact_phone") or customer.get("phone")

        channel = "email" if email else "whatsapp" if phone else "email"
        recipient = email if channel == "email" else phone

        reminders.append({
            "customer_id": cust_id,
            "customer_name": customer.get("name", cust_id),
            "invoice_ids": [s["invoice_id"] for s in steps],
            "rung": max_rung,
            "channel": channel,
            "recipient": recipient,
            "subject": rendered["subject"],
            "body": rendered["body"],
            "total_amount": sum(s["amount"] for s in steps),
            "oldest_overdue_days": max(s["overdue_days"] for s in steps),
            "status": "draft",
        })

    return reminders
