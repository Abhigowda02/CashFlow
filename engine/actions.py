"""
engine/actions.py
Generates and ranks corrective actions to resolve cash flow shortages.
Per contracts/CONTRACT.md
"""

import copy
import datetime
import numpy as np

from engine.forecast import format_inr, run_forecast


def rank_actions(
    business: dict,
    scenario: dict | None = None,
    n_sims: int = 500,
    seed: int = 42,
) -> list[dict]:
    """
    Generate and rank corrective actions sorted by:
    shortage_prob_after, then cost, then id.

    Candidate specifications per CONTRACT.md:
    1. chase_invoice: only the largest OVERDUE invoice, paid ~15 days earlier, cost 0.
    2. early_discount: the three biggest open invoices together, paid ~20 days earlier,
       2% discount cost on those invoices.
    3. invoice_discounting: the largest open invoice becomes cash in ~3 days; cost =
       amount * 12% * remaining_days/365. No 80% advance.
    4. delay_supplier: (one per open bill)
       - non-MSME bill: +15 days, risk low.
       - MSME bill: assume the bill was dated 30 days before due_date, push by at least
         16 days, risk high, note about Section 43B(h) tax-deduction deferral and statutory interest.
    5. overdraft: Rs 2,00,000 for 30 days at 14% annualised.
    6. cut_expense: reduce a discretionary outflow (e.g. rent) by 20%.

    Never lists an action that worsens the baseline.
    """
    as_of = datetime.date.fromisoformat(business["as_of"])
    baseline = run_forecast(business, scenario=scenario, n_sims=n_sims, seed=seed)
    base_shortage = baseline["shortage_prob"]
    base_date = (
        datetime.date.fromisoformat(baseline["first_shortage_date"])
        if baseline.get("first_shortage_date")
        else None
    )

    customers = {c["id"]: c for c in business.get("customers", [])}
    open_invoices = [
        inv for inv in business.get("invoices", []) if inv.get("status", "open") == "open"
    ]
    overdue_invoices = [
        inv
        for inv in open_invoices
        if datetime.date.fromisoformat(inv["due_date"]) < as_of
    ]
    supplier_bills = [
        b for b in business.get("supplier_bills", []) if b.get("status", "open") == "open"
    ]

    # Precalculate customer average delays for discounting tenor calculation
    cust_delays = {}
    for inv in business.get("invoices", []):
        if inv.get("status") == "paid" and inv.get("paid_date"):
            p_d = datetime.date.fromisoformat(inv["paid_date"])
            d_d = datetime.date.fromisoformat(inv["due_date"])
            cust_delays.setdefault(inv["customer_id"], []).append((p_d - d_d).days)

    candidates = []
    cand_id = 1

    # 1. chase_invoice: only the largest OVERDUE invoice, paid ~15 days earlier, cost 0
    if overdue_invoices:
        target_inv = max(overdue_invoices, key=lambda x: int(x.get("amount", 0)))
        cid = target_inv["customer_id"]
        c_name = customers.get(cid, {}).get("name", cid)
        amt = int(target_inv["amount"])

        b_mod = copy.deepcopy(business)
        for inv in b_mod.get("invoices", []):
            if inv["id"] == target_inv["id"]:
                inv["accelerate_days"] = 15
                break

        fc = run_forecast(b_mod, scenario=scenario, n_sims=n_sims, seed=seed)
        candidates.append({
            "id": f"A{cand_id}",
            "title": f"Chase {target_inv['id']} ({c_name})",
            "type": "chase_invoice",
            "cost": 0,
            "risk": "low",
            "note": f"Follow up on largest overdue invoice ({format_inr(amt)}) to accelerate collection by ~15 days.",
            "forecast": fc,
        })
        cand_id += 1

    # 2. early_discount: the three biggest open invoices together, paid ~20 days earlier, 2% discount cost
    if len(open_invoices) >= 3:
        top3_invoices = sorted(open_invoices, key=lambda x: int(x.get("amount", 0)), reverse=True)[:3]
        top3_ids = {inv["id"] for inv in top3_invoices}
        total_top3_amt = sum(int(inv["amount"]) for inv in top3_invoices)
        discount_cost = int(round(total_top3_amt * 0.02))

        b_mod = copy.deepcopy(business)
        for inv in b_mod.get("invoices", []):
            if inv["id"] in top3_ids:
                inv["accelerate_days"] = 20
                inv["amount_multiplier"] = 0.98

        fc = run_forecast(b_mod, scenario=scenario, n_sims=n_sims, seed=seed)
        candidates.append({
            "id": f"A{cand_id}",
            "title": "Offer 2% early payment discount on top 3 open invoices",
            "type": "early_discount",
            "cost": discount_cost,
            "risk": "low",
            "note": f"Offer 2% prompt settlement discount ({format_inr(discount_cost)}) across 3 largest receivables to accelerate cash by ~20 days.",
            "forecast": fc,
        })
        cand_id += 1

    # 3. invoice_discounting: the largest open invoice becomes cash in ~3 days; cost = amount * 12% * remaining_days/365. No 80% advance.
    if open_invoices:
        target_inv = max(open_invoices, key=lambda x: int(x.get("amount", 0)))
        cid = target_inv["customer_id"]
        c_name = customers.get(cid, {}).get("name", cid)
        amt = int(target_inv["amount"])
        due_d = datetime.date.fromisoformat(target_inv["due_date"])

        delays_pool = cust_delays.get(cid, [30])
        expected_delay = float(np.mean(delays_pool)) if delays_pool else 30.0
        expected_pay_d = due_d + datetime.timedelta(days=int(round(expected_delay)))
        remaining_days = max(1, (expected_pay_d - as_of).days)
        cost = int(round(amt * 0.12 * remaining_days / 365.0))

        b_mod = copy.deepcopy(business)
        for inv in b_mod.get("invoices", []):
            if inv["id"] == target_inv["id"]:
                inv["override_pay_day"] = 3
                inv["override_amount"] = amt - cost
                break

        fc = run_forecast(b_mod, scenario=scenario, n_sims=n_sims, seed=seed)
        candidates.append({
            "id": f"A{cand_id}",
            "title": f"Discount {target_inv['id']} ({c_name})",
            "type": "invoice_discounting",
            "cost": cost,
            "risk": "low",
            "note": f"100% advance on {format_inr(amt)} in ~3 days via invoice discounting at 12% p.a. ({format_inr(cost)} fee for {remaining_days} days).",
            "forecast": fc,
        })
        cand_id += 1

    # 4. delay_supplier: (one per open bill)
    for bill in supplier_bills:
        is_msme = bill.get("is_msme", False)
        b_amt = int(bill.get("amount", 0))
        supp = bill.get("supplier", "Supplier")

        if is_msme:
            extra_days = 16
            risk = "high"
            note = (
                f"MSME supplier: Pushing {format_inr(b_amt)} by {extra_days} days (total > 45 days from bill date) "
                "triggers Section 43B(h) tax-deduction deferral and statutory compound interest at 3x RBI bank rate."
            )
        else:
            extra_days = 15
            risk = "low"
            note = f"Commercial non-MSME supplier: Negotiate standard 15-day payment extension on {format_inr(b_amt)}."

        b_mod = copy.deepcopy(business)
        for mod_b in b_mod.get("supplier_bills", []):
            if mod_b["id"] == bill["id"]:
                orig_d = datetime.date.fromisoformat(mod_b["due_date"])
                mod_b["due_date"] = (orig_d + datetime.timedelta(days=extra_days)).isoformat()
                break

        fc = run_forecast(b_mod, scenario=scenario, n_sims=n_sims, seed=seed)
        candidates.append({
            "id": f"A{cand_id}",
            "title": f"Delay bill {bill['id']} ({supp}) by {extra_days} days",
            "type": "delay_supplier",
            "cost": 0,
            "risk": risk,
            "note": note,
            "forecast": fc,
        })
        cand_id += 1

    # 5. overdraft: Rs 2,00,000 for 30 days at 14% annualised
    od_amount = 200000
    od_tenor = 30
    od_rate = 0.14
    od_cost = int(round(od_amount * od_rate * od_tenor / 365.0))
    repay_date = (as_of + datetime.timedelta(days=od_tenor)).isoformat()

    b_mod = copy.deepcopy(business)
    b_mod["opening_cash"] = int(b_mod["opening_cash"]) + od_amount

    od_scen = copy.deepcopy(scenario) if scenario else {"name": "Overdraft", "changes": []}
    od_scen.setdefault("changes", []).append({
        "type": "extra_expense",
        "amount": od_amount + od_cost,
        "date": repay_date,
    })

    fc = run_forecast(b_mod, scenario=od_scen, n_sims=n_sims, seed=seed)
    candidates.append({
        "id": f"A{cand_id}",
        "title": "Draw down Rs 2,00,000 overdraft facility",
        "type": "overdraft",
        "cost": od_cost,
        "risk": "medium",
        "note": f"Draw 30-day overdraft of Rs 2,00,000 at 14% p.a. ({format_inr(od_cost)} interest) to bridge payroll gap.",
        "forecast": fc,
    })
    cand_id += 1

    # 6. cut_expense: reduce a discretionary outflow (e.g. rent) by 20%
    b_mod = copy.deepcopy(business)
    reduced_rent = 0
    orig_rent = 0
    for ob in b_mod.get("obligations", []):
        if ob.get("name", "").lower() == "rent":
            orig_rent = int(ob["amount"])
            reduced_rent = int(round(orig_rent * 0.80))
            ob["amount"] = reduced_rent
            break

    fc = run_forecast(b_mod, scenario=scenario, n_sims=n_sims, seed=seed)
    monthly_saving = orig_rent - reduced_rent if orig_rent else 16000
    candidates.append({
        "id": f"A{cand_id}",
        "title": "Renegotiate Rent obligation (20% reduction)",
        "type": "cut_expense",
        "cost": 0,
        "risk": "low",
        "note": f"Reduce monthly rent by 20% from {format_inr(orig_rent)} to {format_inr(reduced_rent)} (saving {format_inr(monthly_saving)}/month).",
        "forecast": fc,
    })
    cand_id += 1

    # Filter and sort
    actions = []
    for cand in candidates:
        fc = cand["forecast"]
        prob_after = fc["shortage_prob"]
        date_after_str = fc["first_shortage_date"]
        date_after = (
            datetime.date.fromisoformat(date_after_str)
            if date_after_str
            else None
        )

        if base_date and date_after:
            runway_gained = max(0, (date_after - base_date).days)
        elif base_date and not date_after:
            runway_gained = (as_of + datetime.timedelta(days=90) - base_date).days
        else:
            runway_gained = 0

        # Never list an action that worsens the baseline
        if prob_after <= base_shortage:
            actions.append({
                "id": cand["id"],
                "title": cand["title"],
                "type": cand["type"],
                "cost": cand["cost"],
                "risk": cand["risk"],
                "note": cand["note"],
                "shortage_prob_after": prob_after,
                "first_shortage_date_after": date_after_str,
                "runway_days_gained": runway_gained,
            })

    # Sort by shortage_prob_after, then cost, then id
    actions.sort(key=lambda a: (a["shortage_prob_after"], a["cost"], a["id"]))
    return actions
