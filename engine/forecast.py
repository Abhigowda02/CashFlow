"""
engine/forecast.py
Predictive cash flow forecast engine with Monte Carlo simulations,
scenario what-if comparisons, and driver identification.
"""

import datetime
import numpy as np


def format_inr(number: int | float) -> str:
    """
    Format an integer/float amount in Indian digit grouping system:
    e.g., 600000 -> "Rs 6,00,000", -120000 -> "-Rs 1,20,000".
    """
    is_negative = number < 0
    num = abs(int(round(number)))
    s = str(num)
    if len(s) <= 3:
        formatted = s
    else:
        last3 = s[-3:]
        remaining = s[:-3]
        chunks = []
        while len(remaining) > 2:
            chunks.insert(0, remaining[-2:])
            remaining = remaining[:-2]
        if remaining:
            chunks.insert(0, remaining)
        formatted = ",".join(chunks) + "," + last3
    prefix = "-Rs " if is_negative else "Rs "
    return prefix + formatted


def run_forecast(
    business: dict,
    scenario: dict | None = None,
    n_sims: int = 500,
    seed: int = 42,
) -> dict:
    """
    Run a 90-day Monte Carlo cash flow forecast starting at business['as_of'].

    Returns Forecast dict per contracts/CONTRACT.md:
    {
      "dates": [...], "p10": [...], "p50": [...], "p90": [...],
      "safety_floor": 100000, "shortage_prob": 0.68,
      "first_shortage_date": "2026-11-14" | null,
      "min_balance_p50": -120000,
      "drivers": [...]
    }
    """
    rng = np.random.default_rng(seed)
    as_of = datetime.date.fromisoformat(business["as_of"])
    n_days = 90
    dates = [(as_of + datetime.timedelta(days=i)).isoformat() for i in range(n_days)]

    opening_cash = int(business.get("opening_cash", 450000))
    safety_floor = int(business.get("safety_floor", 100000))
    sales_plan = business.get(
        "sales_plan",
        {"monthly_amount": 1400000, "terms_days": 30, "monthly_noise_pct": 15},
    )

    customers = business.get("customers", [])
    cust_map = {c["id"]: c for c in customers}
    cust_segment = {c["id"]: c.get("segment", "small") for c in customers}

    # Empirical payment delays from paid invoices
    invoices = business.get("invoices", [])
    paid_invoices = [
        inv
        for inv in invoices
        if inv.get("status") == "paid" and inv.get("paid_date") is not None
    ]
    open_invoices = [
        inv for inv in invoices if inv.get("status", "open") == "open"
    ]

    cust_delays: dict[str, list[int]] = {}
    segment_delays: dict[str, list[int]] = {
        "government": [],
        "corporate": [],
        "small": [],
    }
    segment_revenue: dict[str, int] = {
        "government": 0,
        "corporate": 0,
        "small": 0,
    }

    for inv in paid_invoices:
        p_d = datetime.date.fromisoformat(inv["paid_date"])
        d_d = datetime.date.fromisoformat(inv["due_date"])
        delay = (p_d - d_d).days
        cid = inv["customer_id"]
        seg = cust_segment.get(cid, "small")

        cust_delays.setdefault(cid, []).append(delay)
        segment_delays.setdefault(seg, []).append(delay)
        segment_revenue[seg] = segment_revenue.get(seg, 0) + int(inv["amount"])

    # Fallback delay distributions if segment data empty
    if not segment_delays["government"]:
        segment_delays["government"] = [70]
    if not segment_delays["corporate"]:
        segment_delays["corporate"] = [25]
    if not segment_delays["small"]:
        segment_delays["small"] = [12]

    # Segment mix for future sales
    total_rev = sum(segment_revenue.values())
    seg_names = ["government", "corporate", "small"]
    if total_rev > 0:
        seg_probs = [segment_revenue[s] / total_rev for s in seg_names]
    else:
        seg_probs = [0.2, 0.4, 0.4]

    # Parse scenario changes
    customer_extra_days: dict[str, int] = {}
    sales_pct_change = 0.0
    extra_expenses: list[dict] = []
    supplier_extra_days = 0

    if scenario and "changes" in scenario:
        for change in scenario.get("changes", []):
            ctype = change.get("type")
            if ctype == "delay_customer":
                cid = change.get("customer_id")
                customer_extra_days[cid] = customer_extra_days.get(cid, 0) + int(
                    change.get("extra_days", 0)
                )
            elif ctype == "sales_change":
                sales_pct_change += float(change.get("pct", 0.0))
            elif ctype == "extra_expense":
                extra_expenses.append({
                    "amount": int(change.get("amount", 0)),
                    "date": change.get("date"),
                })
            elif ctype == "supplier_terms":
                supplier_extra_days += int(change.get("extra_days", 0))

    # Pre-allocate inflow and outflow matrices (n_sims x 90)
    inflows = np.zeros((n_sims, n_days), dtype=np.int64)
    outflows = np.zeros((n_sims, n_days), dtype=np.int64)

    # 1. Outflows: Obligations (Payroll, Rent, EMI, GST)
    obligations = business.get("obligations", [])
    for d in range(n_days):
        day_date = as_of + datetime.timedelta(days=d)
        for ob in obligations:
            if day_date.day == ob.get("day_of_month"):
                outflows[:, d] += int(ob.get("amount", 0))

    # 2. Outflows: Extra expenses from scenario
    for exp in extra_expenses:
        if exp.get("date"):
            exp_date = datetime.date.fromisoformat(exp["date"])
            idx = (exp_date - as_of).days
            if 0 <= idx < n_days:
                outflows[:, idx] += exp.get("amount", 0)

    # 3. Outflows: Supplier bills on due_date (plus tiny noise)
    supplier_bills = business.get("supplier_bills", [])
    for bill in supplier_bills:
        if bill.get("status", "open") == "open":
            base_due = datetime.date.fromisoformat(bill["due_date"])
            adjusted_due = base_due + datetime.timedelta(days=supplier_extra_days)
            b_amt = int(bill.get("amount", 0))

            for s in range(n_sims):
                tiny_noise = int(rng.integers(-1, 2))  # -1, 0, or 1 day
                pay_date = adjusted_due + datetime.timedelta(days=tiny_noise)
                if pay_date < as_of:
                    pay_date = as_of
                day_idx = (pay_date - as_of).days
                if 0 <= day_idx < n_days:
                    outflows[s, day_idx] += b_amt

    # 4. Inflows: Open invoices (strictly synchronized RNG consumption)
    for inv in open_invoices:
        cid = inv["customer_id"]
        due_d = datetime.date.fromisoformat(inv["due_date"])
        is_overdue = due_d < as_of
        inv_amt = int(inv.get("amount", 0))

        # Check for action overrides
        if "override_amount" in inv:
            inv_amt = int(inv["override_amount"])
        elif "amount_multiplier" in inv:
            inv_amt = int(round(inv_amt * float(inv["amount_multiplier"])))

        # Empirical delay pool for customer (fallback to segment if < 3 paid)
        if len(cust_delays.get(cid, [])) >= 3:
            pool = cust_delays[cid]
        else:
            seg = cust_segment.get(cid, "small")
            pool = segment_delays.get(seg, [15])

        extra_days = customer_extra_days.get(cid, 0)
        accelerate_days = int(inv.get("accelerate_days", 0))
        override_pay_day = inv.get("override_pay_day")

        for s in range(n_sims):
            # Deterministic RNG consumption per invoice to maintain synchronization
            sampled_pay = None
            for _ in range(10):
                base_delay = int(rng.choice(pool))
                jitter = int(rng.integers(-2, 3))
                cand_pay = due_d + datetime.timedelta(days=base_delay + jitter + extra_days)
                if not is_overdue or cand_pay > as_of:
                    sampled_pay = cand_pay
                    break

            if sampled_pay is None or sampled_pay <= as_of:
                rand_offset = int(rng.integers(1, 15))
                sampled_pay = as_of + datetime.timedelta(days=rand_offset)

            # Apply action adjustments after RNG draw
            if override_pay_day is not None:
                final_pay = as_of + datetime.timedelta(days=int(override_pay_day))
            elif accelerate_days > 0:
                final_pay = sampled_pay - datetime.timedelta(days=accelerate_days)
                if final_pay <= as_of:
                    final_pay = as_of + datetime.timedelta(days=1)
            else:
                final_pay = sampled_pay

            idx = (final_pay - as_of).days
            if 0 <= idx < n_days:
                inflows[s, idx] += inv_amt

    # 5. Inflows: Future sales created weekly from sales_plan
    monthly_amt = float(sales_plan.get("monthly_amount", 1400000))
    sales_multiplier = max(0.0, 1.0 + sales_pct_change / 100.0)
    weekly_base = (monthly_amt / 4.33333) * sales_multiplier
    terms_days = int(sales_plan.get("terms_days", 30))
    noise_pct = float(sales_plan.get("monthly_noise_pct", 15))

    # Weekly schedule starting after as_of (e.g. days 7, 14, 21, ..., 84)
    weekly_offsets = [7 * w for w in range(1, 13)]
    for w_day in weekly_offsets:
        iss_date = as_of + datetime.timedelta(days=w_day)
        due_date = iss_date + datetime.timedelta(days=terms_days)

        for s in range(n_sims):
            noise = float(rng.normal(0, noise_pct / 100.0))
            amt = max(0, int(round(weekly_base * (1.0 + noise))))
            chosen_seg = rng.choice(seg_names, p=seg_probs)
            delay_pool = segment_delays.get(chosen_seg, [15])
            sampled_delay = int(rng.choice(delay_pool)) + int(rng.integers(-2, 3))

            pay_date = due_date + datetime.timedelta(days=sampled_delay)
            idx = (pay_date - as_of).days
            if 0 <= idx < n_days:
                inflows[s, idx] += amt

    # 6. Compute daily cumulative balances per simulation
    balance = np.zeros((n_sims, n_days), dtype=np.int64)
    balance[:, 0] = opening_cash + inflows[:, 0] - outflows[:, 0]
    for d in range(1, n_days):
        balance[:, d] = balance[:, d - 1] + inflows[:, d] - outflows[:, d]

    # Percentiles per day
    p10 = [int(round(np.percentile(balance[:, d], 10))) for d in range(n_days)]
    p50 = [int(round(np.percentile(balance[:, d], 50))) for d in range(n_days)]
    p90 = [int(round(np.percentile(balance[:, d], 90))) for d in range(n_days)]

    # Shortage statistics
    is_shortage = np.any(balance < safety_floor, axis=1)
    shortage_prob = round(float(np.mean(is_shortage)), 2)

    crossing_sims = np.where(is_shortage)[0]
    first_shortage_date = None
    if len(crossing_sims) > 0:
        first_days = [
            int(np.where(balance[s, :] < safety_floor)[0][0])
            for s in crossing_sims
        ]
        median_day = int(round(float(np.median(first_days))))
        first_shortage_date = dates[median_day]

    min_balance_p50 = int(min(p50))

    # Drivers: top 3 reasons (largest expected-late open invoices and big upcoming obligations)
    driver_candidates = []

    # Large expected-late open invoices
    for inv in open_invoices:
        cid = inv["customer_id"]
        c_obj = cust_map.get(cid, {})
        c_name = c_obj.get("name", cid)
        pool = cust_delays.get(cid)
        if not pool or len(pool) < 3:
            pool = segment_delays.get(cust_segment.get(cid, "small"), [15])
        avg_delay = float(np.mean(pool)) if pool else 0.0
        extra_delay = customer_extra_days.get(cid, 0)
        tot_delay = int(round(avg_delay + extra_delay))

        if tot_delay > 0:
            inv_amt = int(inv.get("amount", 0))
            driver_candidates.append({
                "type": "late_invoice",
                "ref": inv.get("id", ""),
                "severity": inv_amt * (tot_delay / 30.0),
                "text": f"{c_name} {format_inr(inv_amt)} expected ~{tot_delay} days late",
            })

    # Big upcoming obligations
    for ob in obligations:
        ob_amt = int(ob.get("amount", 0))
        day_num = ob.get("day_of_month", 1)
        suffix = "th" if 11 <= day_num <= 13 else {1: "st", 2: "nd", 3: "rd"}.get(day_num % 10, "th")
        driver_candidates.append({
            "type": "obligation",
            "ref": ob.get("id", ""),
            "severity": ob_amt,
            "text": f"{ob.get('name', 'Obligation')} {format_inr(ob_amt)} due monthly on {day_num}{suffix}",
        })

    # Open supplier bills
    for bill in supplier_bills:
        if bill.get("status", "open") == "open":
            b_amt = int(bill.get("amount", 0))
            driver_candidates.append({
                "type": "supplier_bill",
                "ref": bill.get("id", ""),
                "severity": b_amt,
                "text": f"{bill.get('supplier', 'Supplier')} {format_inr(b_amt)} due on {bill.get('due_date')}",
            })

    # Sort drivers by financial severity descending and take top 3
    driver_candidates.sort(key=lambda x: x["severity"], reverse=True)
    top_drivers = [
        {"type": c["type"], "ref": c["ref"], "text": c["text"]}
        for c in driver_candidates[:3]
    ]

    return {
        "dates": dates,
        "p10": p10,
        "p50": p50,
        "p90": p90,
        "safety_floor": safety_floor,
        "shortage_prob": shortage_prob,
        "first_shortage_date": first_shortage_date,
        "min_balance_p50": min_balance_p50,
        "drivers": top_drivers,
    }


def compare_scenario(
    business: dict,
    scenario: dict,
    n_sims: int = 500,
    seed: int = 42,
) -> dict:
    """
    Compare baseline forecast with a what-if scenario.
    Returns: {"baseline": Forecast, "scenario": Forecast}
    """
    baseline = run_forecast(business, scenario=None, n_sims=n_sims, seed=seed)
    scen_fc = run_forecast(business, scenario=scenario, n_sims=n_sims, seed=seed)
    return {
        "baseline": baseline,
        "scenario": scen_fc,
    }


# Also expose rank_actions for convenience
def rank_actions(business: dict, scenario: dict | None = None, n_sims: int = 500, seed: int = 42):
    from engine.actions import rank_actions as _rank_actions
    return _rank_actions(business, scenario=scenario, n_sims=n_sims, seed=seed)
