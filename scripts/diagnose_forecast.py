"""
scripts/diagnose_forecast.py
Diagnose why an imported or newly created workspace shows a flat or blank
forecast while the synthetic demo data exhibits realistic shortage risk.
"""

import base64
import sys
from pathlib import Path

# Add project root to sys.path so modules can be imported directly
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine.datagen import generate_business
from engine.forecast import run_forecast
from backend.ledger import import_invoices, forecast_business


def diagnose():
    print("================================================================================")
    print("DIAGNOSIS: Demo Data vs. Imported Workspace Forecast")
    print("================================================================================\n")

    # (a) Demo business (generate_business(7))
    demo_biz = generate_business(7)
    demo_fc = run_forecast(demo_biz)
    print("--- (a) Synthetic Demo Business (engine.generate_business(7)) ---")
    print(f"  as_of:                {demo_biz.get('as_of')}")
    print(f"  opening_cash:         Rs {demo_biz.get('opening_cash'):,}")
    print(f"  safety_floor:         Rs {demo_biz.get('safety_floor'):,}")
    print(f"  p50 start:            Rs {demo_fc['p50'][0]:,}")
    print(f"  p50 end:              Rs {demo_fc['p50'][-1]:,}")
    print(f"  shortage_prob:        {demo_fc['shortage_prob']:.2%} ({demo_fc['shortage_prob']})")
    print(f"  first_shortage_date:  {demo_fc['first_shortage_date']}")
    print(f"  min_balance_p50:      Rs {demo_fc['min_balance_p50']:,}")
    print(f"  drivers count:        {len(demo_fc.get('drivers', []))}")

    # (b) Imported workspace (tests/sample_data/01_textile_wholesale.csv)
    csv_file = ROOT / "tests" / "sample_data" / "01_textile_wholesale.csv"
    if not csv_file.exists():
        csv_file = ROOT / "examples" / "demo_datasets" / "01_textile_wholesale.csv"
    if not csv_file.exists():
        raise FileNotFoundError(f"Missing sample dataset: {csv_file}")

    content_b64 = base64.b64encode(csv_file.read_bytes()).decode("utf-8")
    # import_invoices(filename, content, name, as_of, opening_cash, safety_floor)
    imported_biz = import_invoices(
        "01_textile_wholesale.csv",
        content_b64,
        "Textile Wholesale",
        as_of="2026-10-24",
        opening_cash=150000,
        safety_floor=75000,
    )
    # Apply ledger forecast transformations (e.g. model_amount, net amounts)
    prepared_imported_biz = forecast_business(imported_biz)
    imported_fc = run_forecast(prepared_imported_biz)

    print("\n--- (b) Imported Workspace (01_textile_wholesale.csv via import_invoices) ---")
    print(f"  as_of:                {imported_biz.get('as_of')}")
    print(f"  opening_cash:         Rs {imported_biz.get('opening_cash'):,}")
    print(f"  safety_floor:         Rs {imported_biz.get('safety_floor'):,}")
    print(f"  p50 start:            Rs {imported_fc['p50'][0]:,}")
    print(f"  p50 end:              Rs {imported_fc['p50'][-1]:,}")
    print(f"  shortage_prob:        {imported_fc['shortage_prob']:.2%} ({imported_fc['shortage_prob']})")
    print(f"  first_shortage_date:  {imported_fc['first_shortage_date']}")
    print(f"  min_balance_p50:      Rs {imported_fc['min_balance_p50']:,}")
    print(f"  drivers count:        {len(imported_fc.get('drivers', []))}")

    # (c) Empty inputs inspection
    obligations = imported_biz.get("obligations", [])
    supplier_bills = imported_biz.get("supplier_bills", [])
    sales_plan = imported_biz.get("sales_plan", {})
    sales_monthly = sales_plan.get("monthly_amount", 0)

    print("\n--- (c) Empty / Zero Inputs in Imported Workspace ---")
    print(f"  obligations:                 {obligations} (Empty: {len(obligations) == 0})")
    print(f"  supplier_bills:              {supplier_bills} (Empty: {len(supplier_bills) == 0})")
    print(f"  sales_plan.monthly_amount:   {sales_monthly} (Zero: {sales_monthly == 0})")

    print("\n--- ROOT CAUSE SUMMARY ---")
    print("In demo data, generate_business(7) calibrates realistic recurring obligations (payroll, rent, EMIs),")
    print("supplier bills, and monthly sales, creating cash outflows that trigger realistic shortage risk (60-80%).")
    print("When an invoice CSV is imported, backend.ledger.import_invoices initializes obligations=[],")
    print("supplier_bills=[], and sales_plan.monthly_amount=0. With ZERO expenses and zero planned outflows,")
    print("the Monte Carlo simulation has no cash drains: cash only increases or stays flat from receivables.")
    print("Consequently, shortage_prob is 0%, first_shortage_date is None, and the UI chart displays a misleading")
    print("flat/growing line without warning the user that their regular expenses and obligations have not been entered.")
    print("================================================================================\n")


if __name__ == "__main__":
    diagnose()
