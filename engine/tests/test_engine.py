"""
engine/tests/test_engine.py
Comprehensive test suite verifying engine against contracts/CONTRACT.md.
Tests:
- same seed gives identical output
- output keys match the contract
- a worse scenario never lowers shortage_prob
- no action is worse than baseline
- actions are non-empty and sorted by (shortage_prob_after, cost, id)
"""

import datetime
import unittest

from engine import compare_scenario, format_inr, generate_business, rank_actions, run_forecast


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

        # 2. Forecast determinism
        fc1 = run_forecast(self.business, n_sims=300, seed=42)
        fc2 = run_forecast(self.business, n_sims=300, seed=42)
        self.assertEqual(fc1["shortage_prob"], fc2["shortage_prob"])
        self.assertEqual(fc1["first_shortage_date"], fc2["first_shortage_date"])
        self.assertEqual(fc1["min_balance_p50"], fc2["min_balance_p50"])
        self.assertEqual(fc1["p10"], fc2["p10"])
        self.assertEqual(fc1["p50"], fc2["p50"])
        self.assertEqual(fc1["p90"], fc2["p90"])
        self.assertEqual(fc1["drivers"], fc2["drivers"])

    def test_output_keys_match_contract(self):
        """Verify output keys and types match contracts/CONTRACT.md exactly."""
        # Business shape
        biz = self.business
        self.assertIsInstance(biz["name"], str)
        self.assertIsInstance(biz["as_of"], str)
        self.assertIsInstance(biz["opening_cash"], int)
        self.assertIsInstance(biz["safety_floor"], int)
        self.assertIsInstance(biz["customers"], list)
        self.assertIsInstance(biz["invoices"], list)
        self.assertIsInstance(biz["supplier_bills"], list)
        self.assertIsInstance(biz["obligations"], list)
        self.assertIsInstance(biz["sales_plan"], dict)

        self.assertEqual(biz["name"], "Kaveri Textile Supplies")
        self.assertEqual(biz["opening_cash"], 450000)
        self.assertEqual(biz["safety_floor"], 100000)
        self.assertEqual(len(biz["customers"]), 8)

        # Forecast shape
        fc = run_forecast(self.business, n_sims=300, seed=42)
        forecast_expected_keys = {
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
        self.assertEqual(set(fc.keys()), forecast_expected_keys)
        self.assertEqual(len(fc["dates"]), 90)
        self.assertEqual(len(fc["p10"]), 90)
        self.assertEqual(len(fc["p50"]), 90)
        self.assertEqual(len(fc["p90"]), 90)
        self.assertIsInstance(fc["safety_floor"], int)
        self.assertIsInstance(fc["shortage_prob"], float)
        self.assertTrue(fc["first_shortage_date"] is None or isinstance(fc["first_shortage_date"], str))
        self.assertIsInstance(fc["min_balance_p50"], int)
        self.assertIsInstance(fc["drivers"], list)
        self.assertEqual(len(fc["drivers"]), 3)

        for d in fc["drivers"]:
            self.assertIn(d["type"], ["late_invoice", "obligation", "supplier_bill"])
            self.assertIsInstance(d["ref"], str)
            self.assertIsInstance(d["text"], str)

        # Action shape
        actions = rank_actions(self.business, n_sims=300, seed=42)
        action_expected_keys = {
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
        valid_action_types = {
            "chase_invoice",
            "early_discount",
            "invoice_discounting",
            "delay_supplier",
            "overdraft",
            "cut_expense",
        }

        for a in actions:
            self.assertEqual(set(a.keys()), action_expected_keys)
            self.assertIn(a["type"], valid_action_types)
            self.assertIn(a["risk"], ["low", "medium", "high"])
            self.assertIsInstance(a["cost"], int)
            self.assertIsInstance(a["shortage_prob_after"], float)
            self.assertIsInstance(a["runway_days_gained"], int)
            self.assertTrue(a["first_shortage_date_after"] is None or isinstance(a["first_shortage_date_after"], str))

    def test_worse_scenario_never_lowers_shortage_prob(self):
        """Verify that a worse scenario never lowers shortage_prob."""
        baseline = run_forecast(self.business, scenario=None, n_sims=300, seed=42)
        base_shortage = baseline["shortage_prob"]

        # Scenario with 20% sales drop, customer payment delay, extra expense
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
        self.assertGreater(len(actions), 0)

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
        msme_actions = [a for a in actions if a["type"] == "delay_supplier" and a.get("note", "").startswith("MSME supplier")]
        self.assertEqual(len(msme_actions), 2)
        for a in msme_actions:
            self.assertEqual(a["risk"], "high")
            self.assertIn("43B(h)", a["note"])
            self.assertIn("statutory", a["note"].lower())

        # Non-MSME action verification
        non_msme_actions = [a for a in actions if a["type"] == "delay_supplier" and not a.get("note", "").startswith("MSME supplier")]
        self.assertEqual(len(non_msme_actions), 1)
        for a in non_msme_actions:
            self.assertEqual(a["risk"], "low")

    def test_baseline_calibration(self):
        """Verify calibration numbers: shortage_prob in [0.6, 0.8], first date in 2-4 weeks, settlement ~70d."""
        fc = run_forecast(self.business, n_sims=500, seed=42)
        self.assertGreaterEqual(fc["shortage_prob"], 0.60)
        self.assertLessEqual(fc["shortage_prob"], 0.80)

        self.assertIsNotNone(fc["first_shortage_date"])
        first_date = datetime.date.fromisoformat(fc["first_shortage_date"])
        min_date = self.as_of + datetime.timedelta(days=14)
        max_date = self.as_of + datetime.timedelta(days=28)
        self.assertGreaterEqual(first_date, min_date)
        self.assertLessEqual(first_date, max_date)

        # Average settlement days ~70 days
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


if __name__ == "__main__":
    unittest.main()
