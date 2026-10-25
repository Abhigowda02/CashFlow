"""Simulate cash flow across gap days between cash_updated_on and today.

Preserves accounting honesty:
- Invoices are NOT assumed paid during gap days (no phantom receipts).
- Actual recorded receipts falling in gap days are counted.
- Scheduled obligations and paid supplier bills falling in gap days are deducted.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any


def simulate_gap_cash(business: dict[str, Any], cash_updated_on: date, today: date) -> tuple[int, dict[str, Any]]:
    """Simulates receipts and obligations due between cash_updated_on and today.

    Args:
        business: Workspace business dictionary.
        cash_updated_on: Date of last verified bank/cash balance.
        today: Current simulation start date (today in IST).

    Returns:
        tuple[int, dict]: (adjusted_starting_cash, gap_summary)
    """
    start_cash = int(business.get("cash_balance", business.get("opening_cash", 0)))
    if cash_updated_on >= today:
        return start_cash, {
            "gap_days": 0,
            "estimated_receipts": 0,
            "obligations_due": 0,
            "net_change": 0,
            "detail": "Cash balance is current",
        }

    gap_days = (today - cash_updated_on).days
    obligations = business.get("obligations") or []
    bills = business.get("supplier_bills") or []

    total_obligations_due = 0
    total_receipts_recorded = 0

    curr = cash_updated_on + timedelta(days=1)
    while curr <= today:
        # Check recurring monthly obligations
        for ob in obligations:
            dom = ob.get("day_of_month", 1)
            if curr.day == dom:
                total_obligations_due += int(ob.get("amount", 0))

        # Check supplier bills due on this day that were marked paid
        curr_iso = curr.isoformat()
        for bill in bills:
            if bill.get("due_date") == curr_iso and bill.get("status") == "paid":
                total_obligations_due += int(bill.get("amount", 0))

        curr += timedelta(days=1)

    # Count only actual recorded receipts between cash_updated_on and today.
    # Open invoices falling due in the gap are NOT assumed received (no phantom receipts).
    for inv in business.get("invoices") or []:
        paid_date_str = inv.get("paid_date")
        if paid_date_str and inv.get("status") == "paid":
            try:
                p_date = date.fromisoformat(paid_date_str.split("T")[0])
                if cash_updated_on < p_date <= today:
                    total_receipts_recorded += int(inv.get("amount", 0))
            except (ValueError, TypeError):
                pass

    net_change = total_receipts_recorded - total_obligations_due
    adjusted_cash = max(0, start_cash + net_change)

    summary = {
        "gap_days": gap_days,
        "estimated_receipts": total_receipts_recorded,
        "obligations_due": total_obligations_due,
        "net_change": net_change,
        "detail": f"{gap_days} days estimated since last update",
    }
    return adjusted_cash, summary
