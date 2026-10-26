"""Generate a 3,000-row synthetic shortage-then-recovery invoice dataset."""
from __future__ import annotations

import csv
import json
import random
import shutil
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "sample_data" / "shortage_then_recovery_3000.csv"
PUBLIC = ROOT / "frontend" / "public" / "sample_data" / OUTPUT.name
SETUP = ROOT / "sample_data" / "shortage_then_recovery_3000_setup.json"
FIELDS = ["invoice_id", "customer_id", "customer_name", "email", "phone", "segment", "amount",
          "issue_date", "due_date", "status", "received_amount", "paid_date", "currency"]


def generate(as_of: date = date(2026, 10, 26)) -> None:
    """Write deterministic fictional invoice rows and companion forecast settings."""
    rng = random.Random(3000)
    rows = []
    segments = ["small", "corporate", "government"]
    for customer_number in range(1, 201):
        customer_id = f"REC-C{customer_number:03}"
        name = f"Synthetic Recovery Buyer {customer_number:03}"
        segment = segments[customer_number % len(segments)]
        email = f"buyer{customer_number:03}@example.test"
        phone = f"+919{customer_number:09d}"[-13:]
        delay_base = 5 if segment == "small" else 25 if segment == "corporate" else 55
        for invoice_number in range(1, 16):
            amount = rng.randrange(10_000, 150_001, 1_000)
            invoice_id = f"REC-{customer_number:03}-{invoice_number:02}"
            if invoice_number <= 5:
                due = as_of - timedelta(days=220 - invoice_number * 25 + customer_number % 10)
                paid = due + timedelta(days=max(-3, delay_base + rng.randint(-8, 12)))
                rows.append(dict(invoice_id=invoice_id, customer_id=customer_id, customer_name=name,
                    email=email, phone=phone, segment=segment, amount=amount,
                    issue_date=(due - timedelta(days=30)).isoformat(), due_date=due.isoformat(), status="paid",
                    received_amount=amount, paid_date=paid.isoformat(), currency="INR"))
            else:
                due_offset = -90 + ((invoice_number - 6) * 17 + customer_number * 3) % 150
                due = as_of + timedelta(days=due_offset)
                received = amount // 4 if (customer_number + invoice_number) % 3 == 0 else 0
                rows.append(dict(invoice_id=invoice_id, customer_id=customer_id, customer_name=name,
                    email=email, phone=phone, segment=segment, amount=amount,
                    issue_date=(due - timedelta(days=30)).isoformat(), due_date=due.isoformat(), status="open",
                    received_amount=received, paid_date="", currency="INR"))
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    PUBLIC.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS)
        writer.writeheader(); writer.writerows(rows)
    shutil.copyfile(OUTPUT, PUBLIC)
    setup = {
        "synthetic": True,
        "observation_date": as_of.isoformat(),
        "available_cash_inr": 200000,
        "safety_floor_inr": 500000,
        "monthly_sales_inr": 15000000,
        "payment_terms_days": 30,
        "sales_uncertainty_percent": 15,
        "recurring_expenses": [
            {"name": "Payroll", "category": "salary", "amount_inr": 7000000, "day_of_month": 1},
            {"name": "Rent and utilities", "category": "rent", "amount_inr": 1500000, "day_of_month": 5},
            {"name": "Loan EMI", "category": "loan", "amount_inr": 1000000, "day_of_month": 10},
        ],
        "expected_behavior": "Cash starts below the safety floor, then may recover as receivables and future sales arrive. This is cash flow, not accounting profit.",
    }
    SETUP.write_text(json.dumps(setup, indent=2) + "\n", encoding="utf-8")
    print(f"Created {len(rows)} rows at {OUTPUT}")


if __name__ == "__main__":
    generate()
