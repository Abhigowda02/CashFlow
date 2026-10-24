# Project: Predictive Cash-Flow Management for Small Businesses (India)

## Problem (hackathon statement F-03)
Small businesses can be profitable on paper but run out of cash because customers
pay late and obligations fall due. Build a tool that shows current liquidity, predicts
WHEN cash will run short (with probability), lets owners simulate what-ifs, and ranks
corrective actions. Must separate expected income (invoices) from money actually received.

## Key facts to calibrate synthetic data (India)
- Average invoice settles in ~73 days even though most invoices carry 0-30 day terms.
- Micro/small suppliers should be paid within 45 days (15 without written agreement);
  Section 43B(h) defers the buyer's tax deduction until actual payment.
- Data is SYNTHETIC. Say so in the demo.

## Team
- Person A: engine/ (Python, no web code). Person B: backend/ + frontend/.
- Never edit the other person's folder. Change this contract together only.

## Repo layout
contracts/CONTRACT.md | fixtures/*.json | engine/ | backend/ | frontend/

## Engine functions (Person A implements, in engine/__init__.py)
- generate_business(seed: int = 7) -> dict          # returns Business (below)
- run_forecast(business: dict, scenario: dict | None = None, n_sims: int = 500, seed: int = 42) -> dict   # Forecast
- compare_scenario(business: dict, scenario: dict) -> dict   # {"baseline": Forecast, "scenario": Forecast}
- rank_actions(business: dict, scenario: dict | None = None) -> list[dict]   # Action[]

## Business (JSON)
{
  "name": "string", "as_of": "2026-10-24", "opening_cash": 450000, "safety_floor": 100000,
  "customers": [{"id": "C1", "name": "string", "segment": "government|corporate|small"}],
  "invoices": [{"id": "INV-001", "customer_id": "C1", "amount": 120000,
                "issue_date": "2026-09-10", "due_date": "2026-10-10",
                "status": "open|paid", "paid_date": null}],      // paid invoices = history
  "supplier_bills": [{"id": "B1", "supplier": "string", "amount": 90000,
                      "due_date": "2026-11-05", "is_msme": true, "status": "open|paid"}],
  "obligations": [{"id": "O1", "name": "Payroll", "amount": 600000,
                   "frequency": "monthly", "day_of_month": 1}],   // also Rent, EMI, GST
  "sales_plan": {"monthly_amount": 1400000, "terms_days": 30, "monthly_noise_pct": 15}
}
All money is INR (integers). Dates are ISO strings.

## Forecast (JSON) - horizon is 90 days starting at as_of
{
  "dates": ["2026-10-24", "..."], "p10": [..], "p50": [..], "p90": [..],
  "safety_floor": 100000, "shortage_prob": 0.68,
  "first_shortage_date": "2026-11-14" | null,
  "min_balance_p50": -120000,
  "drivers": [{"type": "late_invoice|obligation|supplier_bill", "ref": "INV-004",
               "text": "Sharma Textiles Rs 4,00,000 expected ~25 days late"}]
}
shortage_prob = share of simulations where balance dips below safety_floor.

## Scenario (JSON) - list of changes, all optional
{ "name": "string", "changes": [
  {"type": "delay_customer", "customer_id": "C2", "extra_days": 30},
  {"type": "sales_change", "pct": -20},
  {"type": "extra_expense", "amount": 200000, "date": "2026-11-10"},
  {"type": "supplier_terms", "extra_days": 15}
]}

## Action (JSON)
{ "id": "A1", "title": "Chase INV-004 (Sharma Textiles)",
  "type": "chase_invoice|early_discount|invoice_discounting|delay_supplier|overdraft|cut_expense",
  "cost": 0, "risk": "low|medium|high", "note": "string",
  "shortage_prob_after": 0.31, "first_shortage_date_after": "2026-12-02" | null,
  "runway_days_gained": 18 }
rank_actions returns actions sorted best-first (lowest shortage_prob_after, then lowest cost).
Delaying an MSME supplier past 45 days must have risk "high" and a note about the
43B(h) tax-deduction deferral.

## API (Person B, FastAPI, prefix /api)
GET /api/business  | GET /api/forecast | POST /api/scenario (body: Scenario) -> {baseline, scenario}
GET /api/actions

## Fixtures (Person B creates first): fixtures/business.json, forecast.json, scenario.json, actions.json


## ADDENDUM v1 - alignment rules (both people must follow)

### Folder ownership
- engine/ = Person A. ml/ = Person B (delay model). backend/, frontend/, fixtures/ = Person B.
- Only contracts/ is shared; change it only by agreeing first.

### Engine signature changes (additive only, old calls must still work)
- run_forecast(business, scenario=None, n_sims=500, seed=42, delay_model="empirical") -> Forecast
- compare_scenario(business, scenario, delay_model="empirical") -> {"baseline","scenario"}
- rank_actions(business, scenario=None, delay_model="empirical") -> Action[]
- delay_model values: "empirical" (default, engine's own sampler) or "survival".
- When delay_model == "survival", the engine calls:
      from ml.delay_model import fit, sample_delay
      model = fit(table_or_business)               # once per run, cached
      sample_delay(invoice, customer, rng, days_overdue)  -> int delay days
  If ml/ is missing or raises ImportError/any error, the engine must silently fall back to
  "empirical" and record it in meta (below). It must never crash.
- Forecast gets ONE new OPTIONAL field: "meta": {"delay_model_used": "empirical|survival",
  "n_sims": 500, "seed": 42}. Consumers must ignore unknown fields.

### Engine robustness rules (needed because users will upload their own data)
- The engine accepts ANY valid Business, not only generate_business() output.
- Never mutate the input dict (deep copy inside).
- Must work with: zero paid invoices, a customer with 1 invoice, no open invoices,
  no supplier bills, no obligations, missing paid_date on open invoices, negative
  delays (early payments), and amounts of 0.
- Deterministic: same business + scenario + seed + delay_model => identical output.
- Money = integer INR. Dates = ISO "YYYY-MM-DD". Horizon = 90 days from as_of,
  so len(dates) == len(p10) == len(p50) == len(p90) == 90.
- Ordering: p10 <= p50 <= p90 on every day.
- Performance: run_forecast < 3 s at 500 sims; rank_actions < 20 s.

### Contract check
- engine/check_contract.py (Person A writes it) validates Business, Forecast, Scenario
  comparison and Action outputs against this document. Run it before every push:
      python -m engine.check_contract