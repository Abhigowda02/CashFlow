"""
engine/tests/test_engine.py
Comprehensive test suite verifying engine against contracts/CONTRACT.md and ADDENDUM v1.

Tests:
- determinism: same seed gives identical output
- no input mutation: inputs are never mutated (deep copied)
- output keys match the contract (including optional meta)
- a worse scenario never lowers shortage_prob
- no action is worse than baseline
- actions are non-empty and sorted by (shortage_prob_after, cost, id)
- edge cases: zero paid history, single-invoice customers, no open invoices,
  no supplier bills, no obligations, missing paid_date on open invoices,
  negative delays (early payments), amounts of 0
- guarantee p10 <= p50 <= p90 and len(dates) == 90
- delay model switch and fallback when ml is missing
- performance limits (marked slow): run_forecast < 3s, rank_actions < 20s
- contract validation functions in engine/check_contract.py
"""

import copy
import datetime
import sys
import time
import types
import unittest
from unittest.mock import patch
import pytest

from engine import compare_scenario, format_inr, generate_business, rank_actions, run_forecast
from engine.check_contract import (
    ContractValidationError,
    validate_actions,
    validate_business,
    validate_comparison,
    validate_forecast,
)


class TestEngineContract(unittest.TestCase):
    def setUp(self):
        self.business = generate_business(seed=7)
        self.as_of = datetime.date.fromisoformat(self.business["as_of"])

    def test_same_seed_gives_identical_output(self):
        """Verify determinism: same seed gives identical output for datagen and forecast."""
        # 1. Business generation determinism
        biz1 = generate_business(seed=7)
        biz2 = generate_business(seed=7)
        self.assertEqual(biz1, biz2)

        # 2. Forecast determinism (empirical)
        fc1 = run_forecast(self.business, n_sims=300, seed=42, delay_model="empirical")
        fc2 = run_forecast(self.business, n_sims=300, seed=42, delay_model="empirical")
        self.assertEqual(fc1["shortage_prob"], fc2["shortage_prob"])
        self.assertEqual(fc1["first_shortage_date"], fc2["first_shortage_date"])
        self.assertEqual(fc1["min_balance_p50"], fc2["min_balance_p50"])
        self.assertEqual(fc1["p10"], fc2["p10"])
        self.assertEqual(fc1["p50"], fc2["p50"])
        self.assertEqual(fc1["p90"], fc2["p90"])
        self.assertEqual(fc1["drivers"], fc2["drivers"])
        self.assertEqual(fc1["meta"], fc2["meta"])

    def test_no_input_mutation(self):
        """Verify engine never mutates input dicts (deep copy inside)."""
        biz_orig = generate_business(seed=7)
        biz_clone = copy.deepcopy(biz_orig)
        scenario_orig = {
            "name": "Test Mutation",
            "changes": [{"type": "sales_change", "pct": -10}],
        }
        scenario_clone = copy.deepcopy(scenario_orig)

        run_forecast(biz_orig, scenario=scenario_orig, n_sims=100, seed=42)
        self.assertEqual(biz_orig, biz_clone, "run_forecast mutated business input!")
        self.assertEqual(scenario_orig, scenario_clone, "run_forecast mutated scenario input!")

        compare_scenario(biz_orig, scenario=scenario_orig, n_sims=100, seed=42)
        self.assertEqual(biz_orig, biz_clone, "compare_scenario mutated business input!")
        self.assertEqual(scenario_orig, scenario_clone, "compare_scenario mutated scenario input!")

        rank_actions(biz_orig, scenario=scenario_orig, n_sims=100, seed=42)
        self.assertEqual(biz_orig, biz_clone, "rank_actions mutated business input!")
        self.assertEqual(scenario_orig, scenario_clone, "rank_actions mutated scenario input!")

    def test_output_keys_match_contract(self):
        """Verify output keys and types match contracts/CONTRACT.md and Addendum v1."""
        # Business shape
        biz = self.business
        validate_business(biz)

        # Forecast shape
        fc = run_forecast(self.business, n_sims=300, seed=42)
        validate_forecast(fc)
        self.assertIn("meta", fc)
        self.assertEqual(fc["meta"]["delay_model_used"], "empirical")
        self.assertEqual(fc["meta"]["n_sims"], 300)
        self.assertEqual(fc["meta"]["seed"], 42)

        # Action shape
        actions = rank_actions(self.business, n_sims=300, seed=42)
        validate_actions(actions)

    def test_worse_scenario_never_lowers_shortage_prob(self):
        """Verify that a worse scenario never lowers shortage_prob."""
        baseline = run_forecast(self.business, scenario=None, n_sims=300, seed=42)
        base_shortage = baseline["shortage_prob"]

        worse_scenario = {
            "name": "Severe Stress Scenario",
            "changes": [
                {"type": "delay_customer", "customer_id": "C2", "extra_days": 30},
                {"type": "sales_change", "pct": -20},
                {"type": "extra_expense", "amount": 200000, "date": "2026-11-10"},
                {"type": "supplier_terms", "extra_days": 15},
            ],
        }

        res = compare_scenario(self.business, worse_scenario, n_sims=300, seed=42)
        validate_comparison(res)
        scen_shortage = res["scenario"]["shortage_prob"]
        self.assertGreaterEqual(scen_shortage, base_shortage)

    def test_no_action_is_worse_than_baseline(self):
        """Verify that no action listed by rank_actions worsens baseline shortage_prob."""
        baseline = run_forecast(self.business, scenario=None, n_sims=300, seed=42)
        base_shortage = baseline["shortage_prob"]

        actions = rank_actions(self.business, n_sims=300, seed=42)
        self.assertGreater(len(actions), 0)

        for a in actions:
            self.assertLessEqual(
                a["shortage_prob_after"],
                base_shortage,
                msg=f"Action {a['id']} ({a['title']}) has shortage_prob_after {a['shortage_prob_after']} > baseline {base_shortage}",
            )

    def test_actions_non_empty_and_sorted(self):
        """Verify actions are non-empty and sorted by (shortage_prob_after, cost, id)."""
        actions = rank_actions(self.business, n_sims=300, seed=42)
        validate_actions(actions)

        # Check sorting order
        sort_keys = [(a["shortage_prob_after"], a["cost"], a["id"]) for a in actions]
        self.assertEqual(sort_keys, sorted(sort_keys))

        # Check candidate specifications
        action_types = [a["type"] for a in actions]
        self.assertEqual(action_types.count("chase_invoice"), 1)
        self.assertEqual(action_types.count("early_discount"), 1)
        self.assertEqual(action_types.count("invoice_discounting"), 1)
        self.assertEqual(action_types.count("overdraft"), 1)
        self.assertEqual(action_types.count("cut_expense"), 1)
        # Delay supplier: one per open supplier bill (3 bills)
        self.assertEqual(action_types.count("delay_supplier"), 3)

        # MSME action verification
        msme_actions = [
            a
            for a in actions
            if a["type"] == "delay_supplier"
            and "msme" in a.get("note", "").lower()
            and "non-msme" not in a.get("note", "").lower()
        ]
        self.assertEqual(len(msme_actions), 2)
        for a in msme_actions:
            self.assertEqual(a["risk"], "high")
            self.assertIn("43B(h)", a["note"])
            self.assertIn("statutory", a["note"].lower())

    def test_baseline_calibration(self):
        """Verify calibration numbers: shortage_prob in [0.6, 0.8], first date in 2-4 weeks, settlement ~70d."""
        fc = run_forecast(self.business, n_sims=500, seed=42)
        self.assertEqual(fc["shortage_prob"], 0.78)
        self.assertEqual(fc["first_shortage_date"], "2026-11-11")
        self.assertEqual(fc["min_balance_p50"], 185000)

        # Settlement history calibration ~70 days
        paid = [inv for inv in self.business["invoices"] if inv["status"] == "paid"]
        settlements = []
        for inv in paid:
            p = datetime.date.fromisoformat(inv["paid_date"])
            iss = datetime.date.fromisoformat(inv["issue_date"])
            settlements.append((p - iss).days)
        avg_settlement = sum(settlements) / len(settlements)
        self.assertAlmostEqual(avg_settlement, 70.0, delta=4.0)

    def test_inr_formatting(self):
        """Verify Indian numbering format."""
        self.assertEqual(format_inr(0), "Rs 0")
        self.assertEqual(format_inr(85000), "Rs 85,000")
        self.assertEqual(format_inr(120000), "Rs 1,20,000")
        self.assertEqual(format_inr(600000), "Rs 6,00,000")
        self.assertEqual(format_inr(1400000), "Rs 14,00,000")
        self.assertEqual(format_inr(-120000), "-Rs 1,20,000")

    # =========================================================================
    # Edge Cases per Addendum v1 & Task 4
    # =========================================================================

    def test_edge_case_zero_paid_history(self):
        """Robustness: Works with zero paid invoices."""
        biz = copy.deepcopy(self.business)
        biz["invoices"] = [inv for inv in biz["invoices"] if inv.get("status") == "open"]
        fc = run_forecast(biz, n_sims=200, seed=42)
        validate_forecast(fc)
        actions = rank_actions(biz, n_sims=200, seed=42)
        validate_actions(actions)

    def test_edge_case_single_invoice_customer(self):
        """Robustness: Works with customers having only 1 invoice."""
        biz = copy.deepcopy(self.business)
        # Retain only 1 invoice per customer
        seen = set()
        new_invoices = []
        for inv in biz["invoices"]:
            cid = inv["customer_id"]
            if cid not in seen:
                seen.add(cid)
                new_invoices.append(inv)
        biz["invoices"] = new_invoices
        fc = run_forecast(biz, n_sims=200, seed=42)
        validate_forecast(fc)
        actions = rank_actions(biz, n_sims=200, seed=42)
        validate_actions(actions)

    def test_edge_case_no_open_invoices(self):
        """Robustness: Works with no open invoices."""
        biz = copy.deepcopy(self.business)
        biz["invoices"] = [inv for inv in biz["invoices"] if inv.get("status") == "paid"]
        fc = run_forecast(biz, n_sims=200, seed=42)
        validate_forecast(fc)
        actions = rank_actions(biz, n_sims=200, seed=42)
        validate_actions(actions)

    def test_edge_case_no_supplier_bills(self):
        """Robustness: Works with no supplier bills."""
        biz = copy.deepcopy(self.business)
        biz["supplier_bills"] = []
        fc = run_forecast(biz, n_sims=200, seed=42)
        validate_forecast(fc)
        actions = rank_actions(biz, n_sims=200, seed=42)
        validate_actions(actions)

    def test_edge_case_no_obligations(self):
        """Robustness: Works with no obligations."""
        biz = copy.deepcopy(self.business)
        biz["obligations"] = []
        fc = run_forecast(biz, n_sims=200, seed=42)
        validate_forecast(fc)
        actions = rank_actions(biz, n_sims=200, seed=42)
        validate_actions(actions)

    def test_edge_case_missing_paid_date_on_open_invoices(self):
        """Robustness: Works when paid_date key is omitted entirely on open invoices."""
        biz = copy.deepcopy(self.business)
        for inv in biz["invoices"]:
            if inv.get("status") == "open" and "paid_date" in inv:
                del inv["paid_date"]
        fc = run_forecast(biz, n_sims=200, seed=42)
        validate_forecast(fc)

    def test_edge_case_negative_delays_early_payments(self):
        """Robustness: Works when historical payments were made before due_date (early payments)."""
        biz = copy.deepcopy(self.business)
        as_of = datetime.date.fromisoformat(biz["as_of"])
        # Give all paid invoices a negative delay of -10 days
        for inv in biz["invoices"]:
            if inv.get("status") == "paid":
                d_d = datetime.date.fromisoformat(inv["due_date"])
                p_d = d_d - datetime.timedelta(days=10)
                inv["paid_date"] = p_d.isoformat()

        fc = run_forecast(biz, n_sims=200, seed=42)
        validate_forecast(fc)

    def test_edge_case_zero_amounts(self):
        """Robustness: Works when amounts are 0."""
        biz = copy.deepcopy(self.business)
        for inv in biz["invoices"]:
            inv["amount"] = 0
        for b in biz["supplier_bills"]:
            b["amount"] = 0
        for ob in biz["obligations"]:
            ob["amount"] = 0
        biz["sales_plan"]["monthly_amount"] = 0

        fc = run_forecast(biz, n_sims=200, seed=42)
        validate_forecast(fc)
        actions = rank_actions(biz, n_sims=200, seed=42)
        validate_actions(actions)

    def test_percentiles_order_and_horizon_guarantee(self):
        """Robustness: Guarantee p10 <= p50 <= p90 and len == 90 on arbitrary data."""
        biz = copy.deepcopy(self.business)
        biz["opening_cash"] = 0
        biz["safety_floor"] = 500000
        fc = run_forecast(biz, n_sims=200, seed=123)
        self.assertEqual(len(fc["dates"]), 90)
        self.assertEqual(len(fc["p10"]), 90)
        self.assertEqual(len(fc["p50"]), 90)
        self.assertEqual(len(fc["p90"]), 90)
        for d in range(90):
            self.assertLessEqual(fc["p10"][d], fc["p50"][d])
            self.assertLessEqual(fc["p50"][d], fc["p90"][d])

    # =========================================================================
    # Delay Model Switch & Fallback per Task 2
    # =========================================================================

    def test_delay_model_fallback_when_ml_missing(self):
        """When ml/ is missing, delay_model='survival' falls back to empirical without error."""
        # None explicitly blocks imports even when ml/ exists on disk.
        with patch.dict(sys.modules, {"ml.delay_model": None}):
            fc = run_forecast(self.business, n_sims=200, seed=42, delay_model="survival")
        validate_forecast(fc)
        self.assertEqual(fc["meta"]["delay_model_used"], "empirical")

    def test_delay_model_survival_with_stub(self):
        """When ml.delay_model is present, delay_model='survival' uses it and records meta."""
        stub_ml = types.ModuleType("ml")
        stub_dm = types.ModuleType("ml.delay_model")

        fit_called = False

        def stub_fit(b):
            nonlocal fit_called
            fit_called = True
            return {"model": "mock_survival"}

        sample_call_count = 0

        def stub_sample_delay(inv, cust, rng, days_overdue, model=None):
            nonlocal sample_call_count
            sample_call_count += 1
            return int(rng.integers(10, 30))

        stub_dm.fit = stub_fit
        stub_dm.sample_delay = stub_sample_delay
        stub_ml.delay_model = stub_dm

        modules = patch.dict(sys.modules, {"ml": stub_ml, "ml.delay_model": stub_dm})
        modules.start()

        try:
            fc = run_forecast(self.business, n_sims=200, seed=42, delay_model="survival")
            validate_forecast(fc)
            self.assertTrue(fit_called, "ml.delay_model.fit was not called!")
            self.assertGreater(sample_call_count, 0, "sample_delay was not called!")
            self.assertEqual(fc["meta"]["delay_model_used"], "survival")
        finally:
            modules.stop()

    def test_delay_model_fallback_on_fit_exception(self):
        """If ml.delay_model.fit raises an exception, engine silently falls back to empirical."""
        stub_ml = types.ModuleType("ml")
        stub_dm = types.ModuleType("ml.delay_model")

        def buggy_fit(b):
            raise RuntimeError("Model training failed unexpectedly")

        stub_dm.fit = buggy_fit
        stub_dm.sample_delay = lambda *args, **kwargs: 10
        stub_ml.delay_model = stub_dm

        modules = patch.dict(sys.modules, {"ml": stub_ml, "ml.delay_model": stub_dm})
        modules.start()

        try:
            fc = run_forecast(self.business, n_sims=200, seed=42, delay_model="survival")
            validate_forecast(fc)
            self.assertEqual(fc["meta"]["delay_model_used"], "empirical")
        finally:
            modules.stop()

    # =========================================================================
    # Check Contract Validator Tests per Task 5
    # =========================================================================

    def test_check_contract_validators_reject_invalid(self):
        """Verify check_contract validators reject malformed payloads."""
        # Bad date in business
        bad_biz = copy.deepcopy(self.business)
        bad_biz["as_of"] = "not-a-date"
        with self.assertRaises(ContractValidationError) as ctx:
            validate_business(bad_biz)
        self.assertIn("as_of", str(ctx.exception))

        # Float money in business
        bad_biz2 = copy.deepcopy(self.business)
        bad_biz2["opening_cash"] = 450000.50
        with self.assertRaises(ContractValidationError) as ctx:
            validate_business(bad_biz2)
        self.assertIn("opening_cash", str(ctx.exception))

        # Boolean in integer money
        bad_biz3 = copy.deepcopy(self.business)
        bad_biz3["safety_floor"] = True
        with self.assertRaises(ContractValidationError) as ctx:
            validate_business(bad_biz3)
        self.assertIn("safety_floor", str(ctx.exception))

        # Inverted percentiles in forecast
        fc = run_forecast(self.business, n_sims=100, seed=42)
        bad_fc = copy.deepcopy(fc)
        bad_fc["p10"][5] = bad_fc["p90"][5] + 1000
        with self.assertRaises(ContractValidationError) as ctx:
            validate_forecast(bad_fc)
        self.assertIn("percentiles violated", str(ctx.exception))

        # Bad action risk
        actions = rank_actions(self.business, n_sims=100, seed=42)
        bad_actions = copy.deepcopy(actions)
        bad_actions[0]["risk"] = "critical"
        with self.assertRaises(ContractValidationError) as ctx:
            validate_actions(bad_actions)
        self.assertIn("invalid risk", str(ctx.exception))

        # Unsorted actions
        if len(actions) >= 2:
            bad_sort_actions = copy.deepcopy(actions)
            bad_sort_actions[0], bad_sort_actions[1] = bad_sort_actions[1], bad_sort_actions[0]
            # Ensure they were strictly distinct keys
            k0 = (bad_sort_actions[0]["shortage_prob_after"], bad_sort_actions[0]["cost"], bad_sort_actions[0]["id"])
            k1 = (bad_sort_actions[1]["shortage_prob_after"], bad_sort_actions[1]["cost"], bad_sort_actions[1]["id"])
            if k0 > k1:
                with self.assertRaises(ContractValidationError) as ctx:
                    validate_actions(bad_sort_actions)
                self.assertIn("not properly sorted", str(ctx.exception))

    # =========================================================================
    # Performance Limits per Task 6 & Addendum v1 (Marked slow)
    # =========================================================================

    @pytest.mark.slow
    def test_run_forecast_performance(self):
        """Contract performance: run_forecast < 3 s at 500 sims."""
        t0 = time.perf_counter()
        fc = run_forecast(self.business, n_sims=500, seed=42)
        elapsed = time.perf_counter() - t0
        self.assertLess(
            elapsed,
            3.0,
            f"run_forecast took {elapsed:.2f} s, exceeds contract limit of 3.0 s",
        )
        validate_forecast(fc)

    @pytest.mark.slow
    def test_rank_actions_performance(self):
        """Contract performance: rank_actions < 20 s."""
        t0 = time.perf_counter()
        actions = rank_actions(self.business, n_sims=500, seed=42)
        elapsed = time.perf_counter() - t0
        self.assertLess(
            elapsed,
            20.0,
            f"rank_actions took {elapsed:.2f} s, exceeds contract limit of 20.0 s",
        )
        validate_actions(actions)


if __name__ == "__main__":
    unittest.main()
