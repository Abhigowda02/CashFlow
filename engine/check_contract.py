"""
engine/check_contract.py
Validates Business, Forecast, Scenario comparison, and Action outputs
against contracts/CONTRACT.md and ADDENDUM v1.

Validation functions:
- validate_business(business: dict) -> None
- validate_forecast(forecast: dict) -> None
- validate_comparison(comparison: dict) -> None
- validate_actions(actions: list[dict]) -> None

CLI:
    python -m engine.check_contract
"""

import datetime
import sys
import types
from unittest.mock import patch
from typing import Any


class ContractValidationError(ValueError):
    """Raised when an object fails contracts/CONTRACT.md validation."""
    pass


def _check_iso_date(val: Any, field_name: str) -> None:
    if not isinstance(val, str):
        raise ContractValidationError(
            f"Field '{field_name}' must be an ISO date string 'YYYY-MM-DD', got {type(val).__name__}: {val!r}"
        )
    try:
        parsed = datetime.date.fromisoformat(val)
        if len(val) != 10:
            raise ValueError()
    except Exception:
        raise ContractValidationError(
            f"Field '{field_name}' must be a valid ISO date string 'YYYY-MM-DD', got {val!r}"
        )


def _check_int_money(val: Any, field_name: str) -> None:
    # Python bool is a subclass of int, so reject booleans explicitly
    if type(val) is not int:
        raise ContractValidationError(
            f"Field '{field_name}' must be integer INR, got {type(val).__name__}: {val!r}"
        )


def validate_business(business: dict) -> None:
    """
    Validate a Business dict per contracts/CONTRACT.md.
    """
    if not isinstance(business, dict):
        raise ContractValidationError(f"Business must be a dict, got {type(business).__name__}")

    required_keys = {
        "name",
        "as_of",
        "opening_cash",
        "safety_floor",
        "customers",
        "invoices",
        "supplier_bills",
        "obligations",
        "sales_plan",
    }
    missing = required_keys - set(business.keys())
    if missing:
        raise ContractValidationError(f"Business missing required keys: {sorted(missing)}")

    if not isinstance(business["name"], str):
        raise ContractValidationError(
            f"Business field 'name' must be str, got {type(business['name']).__name__}"
        )

    _check_iso_date(business["as_of"], "business.as_of")
    _check_int_money(business["opening_cash"], "business.opening_cash")
    _check_int_money(business["safety_floor"], "business.safety_floor")

    # Customers
    customers = business["customers"]
    if not isinstance(customers, list):
        raise ContractValidationError(
            f"Business field 'customers' must be list, got {type(customers).__name__}"
        )
    valid_segments = {"government", "corporate", "small"}
    for idx, c in enumerate(customers):
        if not isinstance(c, dict):
            raise ContractValidationError(f"Customer at index {idx} must be dict")
        for k in ("id", "name", "segment"):
            if k not in c:
                raise ContractValidationError(f"Customer at index {idx} missing key '{k}'")
            if not isinstance(c[k], str):
                raise ContractValidationError(f"Customer at index {idx} field '{k}' must be str")
        if c["segment"] not in valid_segments:
            raise ContractValidationError(
                f"Customer at index {idx} invalid segment '{c['segment']}', allowed: {sorted(valid_segments)}"
            )

    # Invoices
    invoices = business["invoices"]
    if not isinstance(invoices, list):
        raise ContractValidationError(
            f"Business field 'invoices' must be list, got {type(invoices).__name__}"
        )
    valid_statuses = {"open", "paid"}
    for idx, inv in enumerate(invoices):
        if not isinstance(inv, dict):
            raise ContractValidationError(f"Invoice at index {idx} must be dict")
        for k in ("id", "customer_id", "amount", "issue_date", "due_date", "status"):
            if k not in inv:
                raise ContractValidationError(f"Invoice at index {idx} missing key '{k}'")
        if not isinstance(inv["id"], str):
            raise ContractValidationError(f"Invoice at index {idx} field 'id' must be str")
        if not isinstance(inv["customer_id"], str):
            raise ContractValidationError(f"Invoice at index {idx} field 'customer_id' must be str")
        _check_int_money(inv["amount"], f"invoices[{idx}].amount")
        _check_iso_date(inv["issue_date"], f"invoices[{idx}].issue_date")
        _check_iso_date(inv["due_date"], f"invoices[{idx}].due_date")
        if inv["status"] not in valid_statuses:
            raise ContractValidationError(
                f"Invoice at index {idx} invalid status '{inv['status']}', allowed: {sorted(valid_statuses)}"
            )
        paid_date = inv.get("paid_date")
        if inv["status"] == "paid":
            if paid_date is None:
                raise ContractValidationError(
                    f"Paid invoice at index {idx} ({inv['id']}) must have a valid paid_date string"
                )
            _check_iso_date(paid_date, f"invoices[{idx}].paid_date")
        elif paid_date is not None:
            _check_iso_date(paid_date, f"invoices[{idx}].paid_date")

    # Supplier bills
    bills = business["supplier_bills"]
    if not isinstance(bills, list):
        raise ContractValidationError(
            f"Business field 'supplier_bills' must be list, got {type(bills).__name__}"
        )
    for idx, b in enumerate(bills):
        if not isinstance(b, dict):
            raise ContractValidationError(f"Supplier bill at index {idx} must be dict")
        for k in ("id", "supplier", "amount", "due_date", "is_msme"):
            if k not in b:
                raise ContractValidationError(f"Supplier bill at index {idx} missing key '{k}'")
        if not isinstance(b["id"], str):
            raise ContractValidationError(f"Supplier bill at index {idx} field 'id' must be str")
        if not isinstance(b["supplier"], str):
            raise ContractValidationError(f"Supplier bill at index {idx} field 'supplier' must be str")
        _check_int_money(b["amount"], f"supplier_bills[{idx}].amount")
        _check_iso_date(b["due_date"], f"supplier_bills[{idx}].due_date")
        if not isinstance(b["is_msme"], bool):
            raise ContractValidationError(
                f"Supplier bill at index {idx} field 'is_msme' must be bool, got {type(b['is_msme']).__name__}"
            )

    # Obligations
    obligations = business["obligations"]
    if not isinstance(obligations, list):
        raise ContractValidationError(
            f"Business field 'obligations' must be list, got {type(obligations).__name__}"
        )
    for idx, ob in enumerate(obligations):
        if not isinstance(ob, dict):
            raise ContractValidationError(f"Obligation at index {idx} must be dict")
        for k in ("id", "name", "amount", "frequency", "day_of_month"):
            if k not in ob:
                raise ContractValidationError(f"Obligation at index {idx} missing key '{k}'")
        if not isinstance(ob["id"], str):
            raise ContractValidationError(f"Obligation at index {idx} field 'id' must be str")
        if not isinstance(ob["name"], str):
            raise ContractValidationError(f"Obligation at index {idx} field 'name' must be str")
        _check_int_money(ob["amount"], f"obligations[{idx}].amount")
        if not isinstance(ob["frequency"], str):
            raise ContractValidationError(f"Obligation at index {idx} field 'frequency' must be str")
        dom = ob["day_of_month"]
        if type(dom) is not int or not (1 <= dom <= 31):
            raise ContractValidationError(
                f"Obligation at index {idx} field 'day_of_month' must be integer in 1..31, got {dom!r}"
            )

    # Sales plan
    sales_plan = business["sales_plan"]
    if not isinstance(sales_plan, dict):
        raise ContractValidationError(
            f"Business field 'sales_plan' must be dict, got {type(sales_plan).__name__}"
        )
    for k in ("monthly_amount", "terms_days", "monthly_noise_pct"):
        if k not in sales_plan:
            raise ContractValidationError(f"sales_plan missing key '{k}'")
    _check_int_money(sales_plan["monthly_amount"], "sales_plan.monthly_amount")
    if type(sales_plan["terms_days"]) is not int:
        raise ContractValidationError(
            f"sales_plan.terms_days must be int, got {type(sales_plan['terms_days']).__name__}"
        )
    noise = sales_plan["monthly_noise_pct"]
    if type(noise) not in (int, float):
        raise ContractValidationError(
            f"sales_plan.monthly_noise_pct must be int or float, got {type(noise).__name__}"
        )


def validate_forecast(forecast: dict) -> None:
    """
    Validate a Forecast dict per contracts/CONTRACT.md and Addendum v1.
    """
    if not isinstance(forecast, dict):
        raise ContractValidationError(f"Forecast must be a dict, got {type(forecast).__name__}")

    required_keys = {
        "dates",
        "p10",
        "p50",
        "p90",
        "safety_floor",
        "shortage_prob",
        "first_shortage_date",
        "min_balance_p50",
        "drivers",
    }
    missing = required_keys - set(forecast.keys())
    if missing:
        raise ContractValidationError(f"Forecast missing required keys: {sorted(missing)}")

    # Horizon check: exactly 90 days
    dates = forecast["dates"]
    p10 = forecast["p10"]
    p50 = forecast["p50"]
    p90 = forecast["p90"]

    for name, arr in (("dates", dates), ("p10", p10), ("p50", p50), ("p90", p90)):
        if not isinstance(arr, list):
            raise ContractValidationError(f"Forecast field '{name}' must be list, got {type(arr).__name__}")
        if len(arr) != 90:
            raise ContractValidationError(f"Forecast field '{name}' must have length 90, got {len(arr)}")

    for idx, d in enumerate(dates):
        _check_iso_date(d, f"forecast.dates[{idx}]")

    for idx in range(90):
        _check_int_money(p10[idx], f"forecast.p10[{idx}]")
        _check_int_money(p50[idx], f"forecast.p50[{idx}]")
        _check_int_money(p90[idx], f"forecast.p90[{idx}]")
        if not (p10[idx] <= p50[idx] <= p90[idx]):
            raise ContractValidationError(
                f"Forecast percentiles violated at day {idx}: p10 ({p10[idx]}) <= p50 ({p50[idx]}) <= p90 ({p90[idx]}) is false"
            )

    _check_int_money(forecast["safety_floor"], "forecast.safety_floor")
    _check_int_money(forecast["min_balance_p50"], "forecast.min_balance_p50")

    prob = forecast["shortage_prob"]
    if type(prob) not in (float, int) or not (0.0 <= prob <= 1.0):
        raise ContractValidationError(
            f"Forecast field 'shortage_prob' must be float between 0.0 and 1.0, got {prob!r}"
        )

    first_date = forecast["first_shortage_date"]
    if first_date is not None:
        _check_iso_date(first_date, "forecast.first_shortage_date")

    drivers = forecast["drivers"]
    if not isinstance(drivers, list):
        raise ContractValidationError(
            f"Forecast field 'drivers' must be list, got {type(drivers).__name__}"
        )
    valid_driver_types = {"late_invoice", "obligation", "supplier_bill"}
    for idx, d in enumerate(drivers):
        if not isinstance(d, dict):
            raise ContractValidationError(f"Driver at index {idx} must be dict")
        for k in ("type", "ref", "text"):
            if k not in d:
                raise ContractValidationError(f"Driver at index {idx} missing key '{k}'")
            if not isinstance(d[k], str):
                raise ContractValidationError(f"Driver at index {idx} field '{k}' must be str")
        if d["type"] not in valid_driver_types:
            raise ContractValidationError(
                f"Driver at index {idx} invalid type '{d['type']}', allowed: {sorted(valid_driver_types)}"
            )

    # Optional meta field per Addendum v1
    if "meta" in forecast:
        meta = forecast["meta"]
        if not isinstance(meta, dict):
            raise ContractValidationError(f"Forecast field 'meta' must be dict, got {type(meta).__name__}")
        if "delay_model_used" not in meta or meta["delay_model_used"] not in {"empirical", "survival"}:
            raise ContractValidationError(
                f"Forecast meta field 'delay_model_used' must be 'empirical' or 'survival', got {meta.get('delay_model_used')!r}"
            )
        if "n_sims" in meta and type(meta["n_sims"]) is not int:
            raise ContractValidationError("Forecast meta field 'n_sims' must be int")
        if "seed" in meta and type(meta["seed"]) is not int:
            raise ContractValidationError("Forecast meta field 'seed' must be int")


def validate_comparison(comparison: dict) -> None:
    """
    Validate Scenario Comparison output per contracts/CONTRACT.md.
    """
    if not isinstance(comparison, dict):
        raise ContractValidationError(f"Comparison must be a dict, got {type(comparison).__name__}")

    for k in ("baseline", "scenario"):
        if k not in comparison:
            raise ContractValidationError(f"Comparison missing key '{k}'")
        try:
            validate_forecast(comparison[k])
        except ContractValidationError as e:
            raise ContractValidationError(f"Comparison '{k}' forecast failed validation: {e}") from e


def validate_actions(actions: list[dict]) -> None:
    """
    Validate Actions list per contracts/CONTRACT.md and Addendum v1.
    """
    if not isinstance(actions, list):
        raise ContractValidationError(f"Actions must be a list, got {type(actions).__name__}")

    valid_types = {
        "chase_invoice",
        "early_discount",
        "invoice_discounting",
        "delay_supplier",
        "overdraft",
        "cut_expense",
    }
    valid_risks = {"low", "medium", "high"}

    required_keys = {
        "id",
        "title",
        "type",
        "cost",
        "risk",
        "note",
        "shortage_prob_after",
        "first_shortage_date_after",
        "runway_days_gained",
    }

    for idx, a in enumerate(actions):
        if not isinstance(a, dict):
            raise ContractValidationError(f"Action at index {idx} must be dict")
        missing = required_keys - set(a.keys())
        if missing:
            raise ContractValidationError(f"Action at index {idx} missing keys: {sorted(missing)}")

        if not isinstance(a["id"], str):
            raise ContractValidationError(f"Action at index {idx} field 'id' must be str")
        if not isinstance(a["title"], str):
            raise ContractValidationError(f"Action at index {idx} field 'title' must be str")
        if a["type"] not in valid_types:
            raise ContractValidationError(
                f"Action at index {idx} invalid type '{a['type']}', allowed: {sorted(valid_types)}"
            )
        _check_int_money(a["cost"], f"actions[{idx}].cost")
        if a["risk"] not in valid_risks:
            raise ContractValidationError(
                f"Action at index {idx} invalid risk '{a['risk']}', allowed: {sorted(valid_risks)}"
            )
        if not isinstance(a["note"], str):
            raise ContractValidationError(f"Action at index {idx} field 'note' must be str")

        prob_after = a["shortage_prob_after"]
        if type(prob_after) not in (float, int) or not (0.0 <= prob_after <= 1.0):
            raise ContractValidationError(
                f"Action at index {idx} field 'shortage_prob_after' must be float in 0..1, got {prob_after!r}"
            )

        date_after = a["first_shortage_date_after"]
        if date_after is not None:
            _check_iso_date(date_after, f"actions[{idx}].first_shortage_date_after")

        runway = a["runway_days_gained"]
        if type(runway) is not int:
            raise ContractValidationError(
                f"Action at index {idx} field 'runway_days_gained' must be int, got {type(runway).__name__}"
            )

        # MSME supplier delay rule:
        # "Delaying an MSME supplier past 45 days must have risk 'high' and a note about the 43B(h) tax-deduction deferral."
        note_lower = a["note"].lower()
        title_lower = a["title"].lower()
        is_msme = ("msme" in note_lower or "msme" in title_lower) and ("non-msme" not in note_lower and "non-msme" not in title_lower)
        if a["type"] == "delay_supplier" and is_msme:
            if a["risk"] != "high":
                raise ContractValidationError(
                    f"Action at index {idx} delays an MSME supplier but risk is '{a['risk']}', must be 'high'"
                )
            if "43b(h)" not in note_lower:
                raise ContractValidationError(
                    f"Action at index {idx} delays an MSME supplier but note does not mention Section 43B(h)"
                )

    # Sorted order check per CONTRACT.md & Prompt:
    # "check_contract's sorted-order check must use the same key as rank_actions:
    #  shortage_prob_after, then cost, then id."
    for idx in range(len(actions) - 1):
        curr_key = (actions[idx]["shortage_prob_after"], actions[idx]["cost"], actions[idx]["id"])
        next_key = (actions[idx + 1]["shortage_prob_after"], actions[idx + 1]["cost"], actions[idx + 1]["id"])
        if curr_key > next_key:
            raise ContractValidationError(
                f"Actions not properly sorted at index {idx} vs {idx + 1}: {curr_key} > {next_key}"
            )


def check_all() -> None:
    """
    Run full contract validation across generate_business, run_forecast,
    compare_scenario, and rank_actions with both empirical and survival delay models.
    """
    from engine.actions import rank_actions
    from engine.datagen import generate_business
    from engine.forecast import compare_scenario, run_forecast

    # 1. Generate and validate business
    business = generate_business(seed=7)
    validate_business(business)

    # 2. Baseline empirical forecast
    fc_emp = run_forecast(business, seed=42, delay_model="empirical")
    validate_forecast(fc_emp)

    # 3. Empirical scenario comparison
    test_scenario = {
        "name": "Contract Validation Test Scenario",
        "changes": [
            {"type": "delay_customer", "customer_id": "C2", "extra_days": 15},
            {"type": "sales_change", "pct": -10},
        ],
    }
    comp_emp = compare_scenario(business, test_scenario, seed=42, delay_model="empirical")
    validate_comparison(comp_emp)

    # 4. Empirical action ranking
    actions_emp = rank_actions(business, seed=42, delay_model="empirical")
    validate_actions(actions_emp)

    # 5. Survival model test using stub if ml is absent
    ml_stub_installed = False
    try:
        import ml.delay_model
    except ImportError:
        stub_ml = types.ModuleType("ml")
        stub_dm = types.ModuleType("ml.delay_model")

        def stub_fit(b):
            return {"fitted": True}

        def stub_sample_delay(inv, cust, rng, days_overdue, model=None):
            return int(rng.integers(5, 25))

        stub_dm.fit = stub_fit
        stub_dm.sample_delay = stub_sample_delay
        stub_ml.delay_model = stub_dm

        sys.modules["ml"] = stub_ml
        sys.modules["ml.delay_model"] = stub_dm
        ml_stub_installed = True

    try:
        fc_surv = run_forecast(business, seed=42, delay_model="survival")
        validate_forecast(fc_surv)
        if fc_surv.get("meta", {}).get("delay_model_used") != "survival":
            raise ContractValidationError(
                f"Expected delay_model_used='survival', got {fc_surv.get('meta', {}).get('delay_model_used')!r}"
            )

        comp_surv = compare_scenario(business, test_scenario, seed=42, delay_model="survival")
        validate_comparison(comp_surv)

        actions_surv = rank_actions(business, seed=42, delay_model="survival")
        validate_actions(actions_surv)
    finally:
        if ml_stub_installed:
            sys.modules.pop("ml.delay_model", None)
            sys.modules.pop("ml", None)

    # 6. Fallback test: when ml is absent, survival gracefully falls back to empirical
    with patch.dict(sys.modules, {"ml.delay_model": None}):
        fc_fallback = run_forecast(business, seed=42, delay_model="survival")
    validate_forecast(fc_fallback)
    if fc_fallback.get("meta", {}).get("delay_model_used") != "empirical":
        raise ContractValidationError(
            f"Expected fallback to 'empirical' when ml is absent, got {fc_fallback.get('meta', {}).get('delay_model_used')!r}"
        )


def main():
    try:
        check_all()
        print("PASS")
        sys.exit(0)
    except Exception as e:
        print(f"FAIL: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
