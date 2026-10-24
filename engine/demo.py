"""
engine/demo.py
Demonstration script for Predictive Cash-Flow Management Engine.
Runs the baseline forecast, scenario comparison, and action ranking.
Exports contract-compliant JSON fixtures to fixtures_engine/.
"""

import datetime
import json
import os
import sys

# Ensure current directory is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from engine.datagen import generate_business
from engine.forecast import compare_scenario, format_inr, rank_actions, run_forecast


def ordinal_suffix(day: int) -> str:
    if 11 <= day <= 13:
        return "th"
    return {1: "st", 2: "nd", 3: "rd"}.get(day % 10, "th")


def main():
    print("=" * 76)
    print("  PREDICTIVE CASH-FLOW MANAGEMENT ENGINE (INDIA)")
    print("  NOTE: ALL DATA IS SYNTHETIC FOR DEMONSTRATION PURPOSES")
    print("=" * 76)

    # 1. Generate Business Profile
    business = generate_business(seed=7)
    print(f"\n[1] Business Profile: {business['name']}")
    print(f"    As of Date:         {business['as_of']}")
    print(f"    Opening Cash:       {format_inr(business['opening_cash'])}")
    print(f"    Safety Floor:       {format_inr(business['safety_floor'])}")
    print(f"    Sales Plan:         {format_inr(business['sales_plan']['monthly_amount'])}/month ({business['sales_plan']['terms_days']}-day terms)")

    paid_invoices = [i for i in business["invoices"] if i["status"] == "paid"]
    open_invoices = [i for i in business["invoices"] if i["status"] == "open"]
    total_open_val = sum(i["amount"] for i in open_invoices)

    settlements = []
    for inv in paid_invoices:
        p_d = datetime.date.fromisoformat(inv["paid_date"])
        iss_d = datetime.date.fromisoformat(inv["issue_date"])
        settlements.append((p_d - iss_d).days)
    avg_settle = sum(settlements) / len(settlements) if settlements else 0

    print(f"    Customers:          {len(business['customers'])} (1 Government, 2 Corporate, 5 Small)")
    print(f"    Paid History:       {len(paid_invoices)} invoices over 12 months")
    print(f"    Average Settlement: {avg_settle:.1f} days (calibrated ~70-73 days)")
    print(f"    Open Receivables:   {len(open_invoices)} invoices totaling {format_inr(total_open_val)}")
    print(f"    Supplier Bills:     {len(business['supplier_bills'])} open bills ({sum(1 for b in business['supplier_bills'] if b['is_msme'])} MSME)")
    print("    Monthly Obligations:")
    for ob in business["obligations"]:
        day_n = ob["day_of_month"]
        print(f"      - {ob['name']:<12}: {format_inr(ob['amount'])} on {day_n}{ordinal_suffix(day_n)}")

    # 2. Run Baseline Forecast
    print("\n[2] Running 90-Day Baseline Monte Carlo Forecast (n_sims=500)...")
    baseline = run_forecast(business, scenario=None, n_sims=500, seed=42)
    print(f"    Shortage Probability: {baseline['shortage_prob'] * 100:.1f}%")
    print(f"    First Shortage Date:  {baseline['first_shortage_date']}")
    print(f"    Min Balance (p50):    {format_inr(baseline['min_balance_p50'])}")
    print("    Key Cash Crunch Drivers:")
    for idx, d in enumerate(baseline["drivers"], start=1):
        print(f"      {idx}. [{d['type']}] {d['text']} (Ref: {d['ref']})")

    # 3. Simulate What-If Scenario
    sample_scenario = {
        "name": "Market Shock: 20% sales drop, corporate delay, unexpected machine repair",
        "changes": [
            {"type": "delay_customer", "customer_id": "C2", "extra_days": 30},
            {"type": "sales_change", "pct": -20},
            {"type": "extra_expense", "amount": 200000, "date": "2026-11-10"},
            {"type": "supplier_terms", "extra_days": 15},
        ],
    }

    print(f"\n[3] Comparing What-If Scenario: '{sample_scenario['name']}'...")
    comp = compare_scenario(business, sample_scenario, n_sims=500, seed=42)
    scen = comp["scenario"]
    print(f"    {'Metric':<24} | {'Baseline':<16} | {'Scenario':<16}")
    print(f"    {'-'*24}-|-{'-'*16}-|-{'-'*16}")
    print(f"    {'Shortage Probability':<24} | {baseline['shortage_prob']*100:>15.1f}% | {scen['shortage_prob']*100:>15.1f}%")
    print(f"    {'First Shortage Date':<24} | {str(baseline['first_shortage_date']):>16} | {str(scen['first_shortage_date']):>16}")
    print(f"    {'Min Balance (p50)':<24} | {format_inr(baseline['min_balance_p50']):>16} | {format_inr(scen['min_balance_p50']):>16}")

    # 4. Rank Corrective Actions
    print("\n[4] Ranking Corrective Actions (Best-First)...")
    actions = rank_actions(business)
    for idx, a in enumerate(actions, start=1):
        cost_str = format_inr(a['cost']) if a['cost'] > 0 else "Free"
        print(f"    {idx}. [{a['type']}] {a['title']}")
        print(f"       Shortage: {a['shortage_prob_after']*100:.1f}% | Runway Gained: +{a['runway_days_gained']} days | Cost: {cost_str} | Risk: {a['risk'].upper()}")
        print(f"       Note: {a['note']}")

    # 5. Export JSON Fixtures
    out_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "fixtures_engine"))
    os.makedirs(out_dir, exist_ok=True)

    files_to_save = {
        "business.json": business,
        "forecast.json": baseline,
        "scenario.json": sample_scenario,
        "compare.json": comp,
        "actions.json": actions,
    }

    print(f"\n[5] Saving Contract-Compliant JSON Fixtures to {out_dir}/:")
    for fname, data in files_to_save.items():
        path = os.path.join(out_dir, fname)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        print(f"    -> Saved {fname} ({os.path.getsize(path)} bytes)")

    print("\n" + "=" * 76)
    print("  DEMO COMPLETED SUCCESSFULLY!")
    print("=" * 76)


if __name__ == "__main__":
    main()
