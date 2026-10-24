"""
engine/datagen.py
Synthetic data generator for predictive cash-flow management.
Generates realistic financial profiles for small Indian businesses.
"""

import datetime
import numpy as np


def generate_business(seed: int = 7) -> dict:
    """
    Generate a Business profile per contracts/CONTRACT.md:
    Kaveri Textile Supplies (Bengaluru garment-supply firm).
    Calibrated with 12 months of paid history (settlement ~70 days)
    and ~10 open invoices so that the 90-day baseline forecast
    shows shortage_prob between 0.6 and 0.8 with first shortage
    date occurring 2-4 weeks after as_of.
    """
    rng = np.random.default_rng(seed)
    as_of = datetime.date(2026, 10, 24)

    # 8 Customers: 1 government, 2 corporate, 5 small
    customers = [
        {
            "id": "C1",
            "name": "Karnataka State Handloom Development Corp",
            "segment": "government",
        },
        {
            "id": "C2",
            "name": "Bangalore Retail Fashion Ltd",
            "segment": "corporate",
        },
        {
            "id": "C3",
            "name": "Mysore Silk House Pvt Ltd",
            "segment": "corporate",
        },
        {
            "id": "C4",
            "name": "Ananya Boutique",
            "segment": "small",
        },
        {
            "id": "C5",
            "name": "Balaji Garments",
            "segment": "small",
        },
        {
            "id": "C6",
            "name": "Cauvery Trends",
            "segment": "small",
        },
        {
            "id": "C7",
            "name": "Deccan Drapers",
            "segment": "small",
        },
        {
            "id": "C8",
            "name": "East West Tailoring",
            "segment": "small",
        },
    ]

    # Typical payment delays per customer:
    # Government: 50-90 days late
    # Two chronically late (C2, C5): 30-60 days late
    # Rest: 0-20 days late
    delay_ranges = {
        "C1": (65, 90),
        "C2": (35, 60),
        "C3": (10, 20),
        "C4": (5, 18),
        "C5": (35, 60),
        "C6": (5, 20),
        "C7": (3, 15),
        "C8": (0, 12),
    }

    # 12 months of PAID invoices
    # Calibrated invoice counts to reach overall average settlement near 70 days
    paid_invoice_counts = {
        "C1": 12,
        "C2": 10,
        "C3": 5,
        "C4": 4,
        "C5": 10,
        "C6": 4,
        "C7": 4,
        "C8": 4,
    }

    invoices = []
    inv_counter = 1

    for cust in customers:
        cid = cust["id"]
        count = paid_invoice_counts[cid]
        min_d, max_d = delay_ranges[cid]

        for _ in range(count):
            # Issue date across the past 12 months (120 to 360 days ago)
            days_ago = int(rng.integers(120, 360))
            issue_date = as_of - datetime.timedelta(days=days_ago)
            terms = 30
            due_date = issue_date + datetime.timedelta(days=terms)
            delay = int(rng.integers(min_d, max_d + 1))
            paid_date = due_date + datetime.timedelta(days=delay)

            # Ensure paid_date is strictly before or at as_of
            if paid_date > as_of:
                paid_date = as_of - datetime.timedelta(days=int(rng.integers(1, 10)))

            amount = int(rng.integers(70, 220)) * 1000
            invoices.append({
                "id": f"INV-{inv_counter:03d}",
                "customer_id": cid,
                "amount": amount,
                "issue_date": issue_date.isoformat(),
                "due_date": due_date.isoformat(),
                "status": "paid",
                "paid_date": paid_date.isoformat(),
            })
            inv_counter += 1

    # ~10 OPEN invoices (some already overdue, some upcoming)
    # Tuned amounts and dates so that baseline forecast shortage_prob is 0.6-0.8
    # with first shortage date 2-4 weeks after as_of (2026-11-07 to 2026-11-21)
    open_invoices_specs = [
        # INV-054: Corporate (C3) - Overdue by 12 days, expected late Oct / early Nov
        {"customer_id": "C3", "amount": 360000, "issue_days_ago": 42, "terms": 30},
        # INV-055: Small (C4) - Overdue by 4 days, expected early Nov
        {"customer_id": "C4", "amount": 140000, "issue_days_ago": 34, "terms": 30},
        # INV-056: Small (C6) - Due Oct 31, expected mid Nov
        {"customer_id": "C6", "amount": 110000, "issue_days_ago": 23, "terms": 30},
        # INV-057: Government (C1) - Overdue by 49 days, large expected late Nov / Dec
        {"customer_id": "C1", "amount": 450000, "issue_days_ago": 79, "terms": 30},
        # INV-058: Corporate chronic (C2) - Overdue by 19 days, expected late Nov
        {"customer_id": "C2", "amount": 380000, "issue_days_ago": 49, "terms": 30},
        # INV-059: Small chronic (C5) - Overdue by 9 days, expected late Nov
        {"customer_id": "C5", "amount": 220000, "issue_days_ago": 39, "terms": 30},
        # INV-060: Small (C7) - Due Nov 9, expected mid Nov
        {"customer_id": "C7", "amount": 95000, "issue_days_ago": 14, "terms": 30},
        # INV-061: Small (C8) - Due Nov 14, expected late Nov
        {"customer_id": "C8", "amount": 85000, "issue_days_ago": 9, "terms": 30},
        # INV-062: Corporate (C3) - Due Nov 17, expected early Dec
        {"customer_id": "C3", "amount": 180000, "issue_days_ago": 6, "terms": 30},
        # INV-063: Small (C4) - Due Nov 21, expected early Dec
        {"customer_id": "C4", "amount": 125000, "issue_days_ago": 2, "terms": 30},
    ]

    for spec in open_invoices_specs:
        issue_d = as_of - datetime.timedelta(days=spec["issue_days_ago"])
        due_d = issue_d + datetime.timedelta(days=spec["terms"])
        invoices.append({
            "id": f"INV-{inv_counter:03d}",
            "customer_id": spec["customer_id"],
            "amount": spec["amount"],
            "issue_date": issue_d.isoformat(),
            "due_date": due_d.isoformat(),
            "status": "open",
            "paid_date": None,
        })
        inv_counter += 1

    # 3 Open supplier bills including 2 MSME suppliers
    supplier_bills = [
        {
            "id": "B1",
            "supplier": "Sri Laxmi Threads",
            "amount": 85000,
            "due_date": (as_of + datetime.timedelta(days=11)).isoformat(),  # 2026-11-04
            "is_msme": True,
            "status": "open",
        },
        {
            "id": "B2",
            "supplier": "Venkateshwara Dyes & Fabrics",
            "amount": 140000,
            "due_date": (as_of + datetime.timedelta(days=19)).isoformat(),  # 2026-11-12
            "is_msme": True,
            "status": "open",
        },
        {
            "id": "B3",
            "supplier": "Apex Packaging Solutions",
            "amount": 75000,
            "due_date": (as_of + datetime.timedelta(days=25)).isoformat(),  # 2026-11-18
            "is_msme": False,
            "status": "open",
        },
    ]

    # Recurring Obligations:
    # Payroll Rs 6,00,000 on the 1st
    # Rent Rs 80,000 on the 5th
    # EMI Rs 60,000 on the 10th
    # GST Rs 1,20,000 on the 20th
    obligations = [
        {
            "id": "O1",
            "name": "Payroll",
            "amount": 600000,
            "frequency": "monthly",
            "day_of_month": 1,
        },
        {
            "id": "O2",
            "name": "Rent",
            "amount": 80000,
            "frequency": "monthly",
            "day_of_month": 5,
        },
        {
            "id": "O3",
            "name": "EMI",
            "amount": 60000,
            "frequency": "monthly",
            "day_of_month": 10,
        },
        {
            "id": "O4",
            "name": "GST",
            "amount": 120000,
            "frequency": "monthly",
            "day_of_month": 20,
        },
    ]

    return {
        "name": "Kaveri Textile Supplies",
        "as_of": as_of.isoformat(),
        "opening_cash": 450000,
        "safety_floor": 100000,
        "customers": customers,
        "invoices": invoices,
        "supplier_bills": supplier_bills,
        "obligations": obligations,
        "sales_plan": {
            "monthly_amount": 1400000,
            "terms_days": 30,
            "monthly_noise_pct": 15,
        },
    }
