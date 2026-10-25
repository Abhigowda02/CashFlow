"""Owner alert rules engine (pure module).

Input: Forecast view, open invoices, recurring obligations, today date, user preferences, existing dedupe keys.
Output: Deduplicated, actionable owner alert objects.

Alert categories:
- Shortage warning: Shortage probability >= threshold within horizon days, identifying root causes.
- Upcoming due expenses: Consolidated 7/3/1 day reminders, escalated if forecast dips below safety floor.
- Late invoice: Receivables reaching escalation rungs, linking to reminders queue.
- Stale cash: Replaces ungrounded shortage claims until reconciled bank balance is updated.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any
from backend.modules.reminder_engine import format_inr, get_ladder_rung


def _parse_date(d: date | str | None) -> date | None:
    if not d:
        return None
    if isinstance(d, date):
        return d
    try:
        return date.fromisoformat(str(d).split("T")[0].strip())
    except Exception:
        return None


def evaluate_alerts(
    business_id: str,
    forecast_view: dict[str, Any],
    invoices: list[dict[str, Any]],
    obligations: list[dict[str, Any]],
    today: date | str,
    prefs: dict[str, Any] | None = None,
    existing_dedupe_keys: set[str] | None = None,
) -> list[dict[str, Any]]:
    """Evaluate business state and forecast trajectory to generate new alerts.

    Deduplicates alerts by business, event kind, key date, and stage.
    """
    now = _parse_date(today) or date.today()
    p = prefs or {}
    existing_keys = existing_dedupe_keys or set()

    # Threshold: support either decimal 0.40 or integer 40
    raw_thresh = p.get("risk_threshold", 40)
    risk_threshold = raw_thresh / 100.0 if raw_thresh > 1 else float(raw_thresh)
    horizon_days = int(p.get("horizon_days", 14))

    stale = bool(forecast_view.get("stale", False))
    cash_last_updated = forecast_view.get("cash_last_updated") or str(now)
    shortage_prob = float(forecast_view.get("shortage_prob", 0.0))
    first_shortage_str = forecast_view.get("first_shortage_date")
    first_shortage_date = _parse_date(first_shortage_str)

    new_alerts: list[dict[str, Any]] = []

    # 1. Stale cash balance alert
    if stale:
        dedupe_key = f"{business_id}:stale:{cash_last_updated}"
        if dedupe_key not in existing_keys:
            new_alerts.append({
                "kind": "stale_cash",
                "severity": "warning",
                "title": "Cash balance is stale",
                "body": f"Your cash balance was last updated on {cash_last_updated}. Update verified bank balance in Invoices & Cash to keep forecasts reliable.",
                "dedupe_key": dedupe_key,
                "link": "/ledger",
            })

    # 2. Shortage risk warning (suppressed if cash balance is stale!)
    if not stale and shortage_prob >= risk_threshold and first_shortage_date:
        days_to_shortage = (first_shortage_date - now).days
        if 0 <= days_to_shortage <= horizon_days:
            # Round prob to 1 decimal place (10% bins) for meaningful change deduplication
            prob_bin = round(shortage_prob, 1)
            dedupe_key = f"{business_id}:shortage:{first_shortage_date}:{prob_bin}"
            if dedupe_key not in existing_keys:
                # Find driving obligations and late invoices
                late_inv_total = sum(
                    inv.get("amount", 0) - inv.get("received_amount", 0)
                    for inv in invoices
                    if inv.get("status") == "open"
                    and _parse_date(inv.get("due_date"))
                    and _parse_date(inv.get("due_date")) < now
                )

                # Find major upcoming obligation near shortage date
                upcoming_ob = next((
                    ob for ob in obligations
                    if ob.get("amount", 0) >= 20000
                ), None)

                ob_desc = f" before {upcoming_ob['name']}" if upcoming_ob else ""
                cause_parts = []
                if late_inv_total > 0:
                    cause_parts.append(f"delayed customer receivables ({format_inr(late_inv_total)})")
                if upcoming_ob:
                    cause_parts.append(f"scheduled {upcoming_ob['name']} ({format_inr(upcoming_ob['amount'])})")

                cause_str = f" due to {' and '.join(cause_parts)}" if cause_parts else ""

                severity = "critical" if shortage_prob >= 0.7 else "warning"
                prob_pct = int(round(shortage_prob * 100))

                new_alerts.append({
                    "kind": "shortage_warning",
                    "severity": severity,
                    "title": f"Cash Shortage Warning: {days_to_shortage} days runway ({first_shortage_date})",
                    "body": f"Forecast shows a {prob_pct}% probability of cash dipping below safety floor on {first_shortage_date}{ob_desc}{cause_str}. Review recommended collections to accelerate receipts.",
                    "dedupe_key": dedupe_key,
                    "link": "/forecast",
                })

    # 3. Upcoming due expenses / obligations (7, 3, 1 day windows)
    # Determine due date for each monthly obligation this month or next month
    grouped_by_date: dict[date, list[dict[str, Any]]] = {}
    for ob in obligations:
        day_num = int(ob.get("day_of_month", 1))
        # Find next occurrence of this day
        try:
            target_date = date(now.year, now.month, day_num)
        except ValueError:
            target_date = date(now.year, now.month, 28)
        if target_date < now:
            # Next month
            next_month = now.month + 1 if now.month < 12 else 1
            next_year = now.year if now.month < 12 else now.year + 1
            try:
                target_date = date(next_year, next_month, day_num)
            except ValueError:
                target_date = date(next_year, next_month, 28)

        grouped_by_date.setdefault(target_date, []).append(ob)

    for due_date, ob_list in grouped_by_date.items():
        days_until = (due_date - now).days
        if days_until in (1, 3, 7):
            stage = f"{days_until}d"
            dedupe_key = f"{business_id}:due:{due_date}:{stage}"
            if dedupe_key not in existing_keys:
                total_amt = sum(int(ob.get("amount", 0)) for ob in ob_list)
                names = [f"{ob['name']} ({format_inr(ob['amount'])})" for ob in ob_list]
                items_str = ", ".join(names)

                # Check if forecast around due date indicates pressure
                forecast_dates = forecast_view.get("dates", [])
                p50_list = forecast_view.get("p50", [])
                safety_floor = int(forecast_view.get("safety_floor", 0))

                escalated = False
                due_str = str(due_date)
                if due_str in forecast_dates:
                    idx = forecast_dates.index(due_str)
                    if idx < len(p50_list) and p50_list[idx] < safety_floor:
                        escalated = True

                severity = "warning" if escalated else "info"
                pressure_note = " Low cash buffer projected near this date." if escalated else ""

                new_alerts.append({
                    "kind": "msme_due",
                    "severity": severity,
                    "title": f"Obligations due in {days_until} day(s) ({format_inr(total_amt)})",
                    "body": f"Scheduled commitments due on {due_date}: {items_str}.{pressure_note}",
                    "dedupe_key": dedupe_key,
                    "link": "/expenses",
                })

    # 4. Overdue receivables reaching escalation ladder rungs
    for inv in invoices:
        if inv.get("status") != "open":
            continue
        amt = int(inv.get("amount", 0)) - int(inv.get("received_amount", 0))
        if amt <= 0:
            continue
        due_d = _parse_date(inv.get("due_date"))
        if not due_d:
            continue
        delta = (now - due_d).days
        if delta in (0, 7, 15, 30):
            rung = get_ladder_rung(delta)
            if rung:
                dedupe_key = f"{business_id}:ladder:{inv['id']}:{rung}"
                if dedupe_key not in existing_keys:
                    cust_name = inv.get("customer_name") or inv.get("customer_id", "Customer")
                    title = f"Payment due: {cust_name} ({format_inr(amt)})"
                    if delta == 0:
                        body = f"Invoice #{inv['id']} for {format_inr(amt)} is due today. Polite reminder is ready in queue."
                    else:
                        body = f"Invoice #{inv['id']} for {format_inr(amt)} is {delta} days overdue. Reminder ready in queue."
                    new_alerts.append({
                        "kind": "late_invoice",
                        "severity": "warning",
                        "title": title,
                        "body": body,
                        "dedupe_key": dedupe_key,
                        "link": "/reminders",
                    })

    return new_alerts
