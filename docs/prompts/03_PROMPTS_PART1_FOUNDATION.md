# PART 1: FOUNDATION (P00 to P09)
Paste `02_MASTER_PREAMBLE.md` first, then one prompt below. Run in order. Commit after each.
Time guide for a 6-hour session: P00-P03 about 45 min, P04-P06 about 75 min, P07-P09 about 60 min.

---
## P00: Safe cleanup and git rollback point
```
TASK: Clean the repo and create a rollback point. Do NOT delete source code.
1. Run `git status`, `git branch -a`, `git log --oneline -15` and show me the output. Tell me which branch I am on. Do not switch branches or merge anything.
2. Delete (they are generated or duplicated): .venv, venv, .pytest_cache, any folder starting with .chrome- or .edge-temp, frontend/dist, frontend/node_modules (I will reinstall), all __pycache__,
   backend/.local/*.sqlite3, ml/artifacts/ (generated), ml/results/synthetic.csv if regenerable, frontend/public/demo-datasets/ (duplicate copy), examples/demo_datasets/cashflow_demo_datasets.zip.
3. data/payment_date.csv is 7 MB: first copy a 5,000-row random sample (seed 7) to ml/sample/payment_date_sample.csv, keep the full file out of git (it is already ignored by .gitignore "data/"), and tell me where the full file lives.
4. Rewrite .gitignore (UTF-8, LF) to ignore: node_modules/, dist/, __pycache__/, *.pyc, .venv/, venv/, .env, .DS_Store, data/, ml/artifacts/, backend/.local/, *.sqlite3, .pytest_cache/, .chrome-*/, .edge-temp/, *.swp, *.swo, uploads/, android/app/build/.
5. Remove tracked files that are now ignored: `git rm -r --cached` for them (only if tracked).
6. Reinstall: `pip install -r backend/requirements.txt -r ml/requirements.txt pytest httpx` inside a new .venv; `cd frontend && npm install`.
7. Run all checks (pytest, check_contract, npm run build) and report pass/fail counts.
8. Commit: "P00: cleanup and rollback point". Then tag: `git tag rollback-before-rebuild`.
ACCEPTANCE: repo size drops sharply, all checks as green as before, tag exists.
```

---
## P01: Reproduce "the forecaster isn't forecasting" and fix the root cause
```
TASK: Diagnose why a real (imported/new) workspace shows a blank or flat forecast while the engine works on demo data.
1. Write scripts/diagnose_forecast.py that: (a) runs engine.run_forecast on engine.generate_business(7) and prints p50 start/end, shortage_prob, first_shortage_date; (b) builds a workspace as an imported CSV would (use examples/demo_datasets/01_textile_wholesale.csv via backend.ledger.import_invoices) and prints the same; (c) prints which inputs are empty (obligations, supplier_bills, sales_plan.monthly_amount).
2. Check GET /api/forecast in backend/main.py + backend/ledger.forecast_business for error swallowing, empty arrays, or auth/CSRF problems, and check how frontend App.tsx renders an empty or flat forecast.
3. Fix: when obligations are empty and future sales are zero, the API must return forecast plus a `warnings` list (e.g. "No expenses entered: forecast only shows invoice receipts") and the UI must show an empty-state card "Add your expenses (or connect bank data) to see shortage risk" with a primary button. Never draw a misleading flat line without that explanation.
4. Add backend tests for: empty obligations returns warnings; forecast arrays have 90 points; p10<=p50<=p90.
ACCEPTANCE: diagnosis printed, warnings shown in UI, tests green.
```

---
## P02: Shared schema and contract kit (inside the project, so pieces always fit)
```
TASK: Create a frozen contract layer so every new module and screen agree on shapes. Do not touch existing logic yet.
Create:
- shared/schema.py: pydantic v2 models: Invoice, Customer, Transaction{id,date,amount,direction(credit|debit),description,balance|None,source(statement|sms|aa|manual|synthetic),dedupe_hash}, ProposedObligation, ProposedMatch,
  ForecastView{headline,generated_at,as_of,cash_last_updated,stale:bool,dates,p10,p50,p90,safety_floor,shortage_prob,first_shortage_date,min_balance_p50,why:[WhyItem],warnings,accuracy|None},
  WhyItem{type,ref,text,amount,expected_date,spread_days}, InvoiceForecast{invoice_id,expected_pay_date,p_by_30d,prob_late,risk}, Alert{id,kind,severity,title,body,created_at,read,dedupe_key,link},
  ActionCard{id,type,title,who,amount,by_date,effect{shortage_prob_before,shortage_prob_after,first_shortage_before,first_shortage_after,runway_days_gained},cost,risk,note,execute{kind,payload}},
  Reminder{id,invoice_ids,customer_id,rung,channel(email|whatsapp|sms|letter),subject,body,status(draft|approved|sent),created_at,sent_at}.
- shared/samples/*.json: one realistic sample file per model (Indian names, INR, lakh values).
- shared/validate.py: `python shared/validate.py` validates every sample against the models; `python shared/validate.py --live http://localhost:8000 --cookie "name=value"` calls the real endpoints in shared/ENDPOINTS.md and reports the exact wrong field.
- shared/ENDPOINTS.md: the new API list I will implement over the next prompts (GET /api/state, GET /api/forecast/view, GET /api/forecast/backtest, GET/POST /api/invoices..., GET /api/alerts, POST /api/alerts/{id}/read, GET /api/reminders/queue, POST /api/reminders/{id}/approve, POST /api/reminders/{id}/send, GET /api/actions/cards, POST /api/actions/{id}/execute, POST /api/transactions/..., POST /api/connect/...).
- shared/mock_server.py: FastAPI app serving the sample JSON on those endpoints so the frontend can be built without the backend.
- shared/README.md: "Do not edit shared/ except by deliberate decision; run validate.py after every backend or UI-contract change."
Add tests in shared/tests/ that validate the samples. Frontend TypeScript types: generate frontend/src/types/contract.ts mirroring the models by hand.
ACCEPTANCE: validate.py passes; mock server starts; contract.ts compiles (npm run build).
```

---
## P03: Remove demo code and fix the onboarding path
```
TASK: Remove the demo from the user-facing product.
1. Delete backend/demo.py, frontend/src/DemoControl.tsx, examples/jury_invoices.csv, examples/jury_invoices.xlsx, examples/jury_setup.json, examples/make_jury_demo.py, the /api/demo route and demo path in /api/onboarding, "Explore synthetic demo" UI, "Synthetic demo data" banners, and demo tests.
2. engine/demo.py and engine.generate_business stay ONLY as dev/test fixtures: rename usage so tests import from engine.datagen; nothing in backend/ or frontend/ references them.
3. Keep examples/demo_datasets/*.csv/.xlsx as "sample files for testing import" but move them to tests/sample_data/ and update docs. Fix any broken test imports.
4. Onboarding now asks only: business name, current bank/cash balance, "balance as of" date (default today), safety buffer. Then drops the owner on the Invoices tab with an empty state that offers: Upload invoices, Connect data.
5. Update README: remove the "Judge demo" section; add "Developer fixtures" note.
ACCEPTANCE: grep -ri "demo" backend frontend/src returns only comments about developer fixtures; all tests and build green.
```

---
## P04: Dynamic dates (today in Asia/Kolkata) with a cash "last updated" date
```
TASK: Replace the frozen observation date with today's date (Asia/Kolkata) while preserving accounting honesty.
1. Add backend/clock.py: today_ist() (zoneinfo Asia/Kolkata), is_stale(last_updated, max_days=3). All tests can monkeypatch it.
2. Business payload gets cash_balance, cash_updated_on (ISO). `as_of` passed to the engine = today_ist() on every request (recalculated at every open). Overdue days, aging, forecast start use today.
3. Cash is NOT rolled forward silently. If cash_updated_on < today: forecast starts from the cash balance on that date, simulates the gap days (receipts expected and obligations due between that date and today, shown as "estimated since last update"), and the API returns stale=true with a banner message "Your balance is from <date>. Update it for an accurate forecast." Include a one-field "Update balance" modal (value + date).
4. Migration for existing workspaces: on load, if as_of exists in the payload, set cash_updated_on = old as_of.
5. Remove the observation-date field from workspace settings; add `cash_updated_on` display and Update button.
6. Update docs/README sections accordingly ("Observation date" section becomes "Cash balance freshness").
7. Tests: stale detection, gap simulation not creating phantom receipts, overdue days computed from patched today.
ACCEPTANCE: opening the app on any date shows correct overdue days and a forecast from today; stale banner works.
```

---
## P05: Real invoice import (CSV/XLSX auto-mapping, text PDF, GST e-invoice JSON, basics)
```
TASK: Upgrade invoice ingestion. Reuse backend/pdf_import.py and ledger.import_invoices patterns; every path is preview -> correct -> confirm. Nothing unreviewed is saved.
1. backend/modules/invoice_mapper.py (pure): detect headers for Tally, Zoho Books, Vyapar, generic exports (aliases: "Voucher No/Invoice No/Bill No", "Party Name/Customer Name/Customer", "Date/Invoice Date", "Due Date", "Amount/Total/Gross Total/Invoice Amount", "Balance/Outstanding", "GSTIN", "Place of supply"). Return mapping + confidence + unmapped columns. Owner can override mapping in the UI.
2. backend/modules/gst_einvoice.py (pure): parse GST e-invoice JSON (IRN schema: DocDtls.No/Dt, BuyerDtls.LglNm/Gstin, ValDtls.TotInvVal, etc.) to invoice rows.
3. Text PDF: keep existing preview flow; extend to allow multiple invoices per page and a table-style "statement of outstanding" PDF where possible; still reject scanned PDFs with a clear message (OCR comes in P31).
4. New endpoints under backend/routers/invoices.py: POST /api/invoices/preview (file -> rows + mapping + confidence + duplicate flags), POST /api/invoices/commit (confirmed rows, add or replace mode), GET /api/invoices, PATCH /api/invoices/{id} (edit), DELETE /api/invoices/{id}, POST /api/invoices/{id}/mark-paid (creates idempotent receipt), POST /api/invoices/bulk (mark paid, delete, set customer segment, set terms).
5. Duplicate detection: same invoice id, or same (customer, amount, issue_date). Flag in preview; blocked unless owner says "keep both".
6. Per-customer segment and payment terms default (e.g., 30 days) editable. Keep INR confirmation rule for missing currency.
7. Tests with fixtures for Tally-style, Zoho-style and Vyapar-style CSVs, GST JSON, duplicate cases, bulk actions.
ACCEPTANCE: each fixture imports through preview and commit; duplicates flagged; edit/delete/mark-paid work; tenant isolation test passes.
```

---
## P06: Forecast model upgrade A (shrinkage, features, common shock)
```
TASK: Improve the payment-delay model in ml/ and engine/ without breaking contracts/CONTRACT.md. Keep delay_model="empirical" fallback and determinism (same seed = same output).
1. Shrinkage: blend customer history -> segment -> business with weights n/(n+k) (k configurable, default 5), so customers with few payments do not give wild estimates. Expose `shrinkage_weight` per customer in the customer profile API.
2. Features for the survival model (only when data supports them; keep the existing amount-provenance safety rule): invoice amount (log), payment terms days, month-end indicator (due date in last 5 days of month), customer's recent delay trend (mean of last 3 vs previous), previous late count, dispute flag from customer-context. Document each feature in ml/README.md.
3. Common-shock factor: per simulation draw one shared multiplier on delays (lognormal, sigma estimated from historical cross-customer correlation of monthly mean delay; default 0.15 if not estimable) applied to all customers so they can be late together. Record in forecast meta: {common_shock_sigma}.
4. Tests: shrinkage monotonic in n; common shock widens P90-P10 at the same median; determinism; ordering p10<=p50<=p90; engine.check_contract still passes; run_forecast < 3 s at 500 sims.
ACCEPTANCE: all tests and contract check green; meta shows delay model used and shock sigma.
```

---
## P07: Forecast model upgrade B (promise-to-pay, real run-rate, learned outflows)
```
TASK: Feed owner knowledge and real data into the forecast.
1. Promise-to-pay: table `promises` (business_id, invoice_id, promised_date, logged_on, outcome_note, kept bool|null). Endpoint POST /api/promises. In the engine, for an invoice with an active promise, sample the payment date around the promised date: with probability p_keep (customer's historical keep rate shrunk toward 0.6) pay within +-3 days of promise, else fall back to the model distribution shifted after the promise date. Mark promise kept/broken automatically when promised_date passes (broken if still unpaid after 3 days). Show promise in invoice forecast + "why" list.
2. Future sales from actual invoicing run-rate: compute monthly invoiced amount from the last 3 to 6 months of issue dates (trimmed mean), average terms; use it as sales_plan.monthly_amount unless the owner overrides. Show "Based on your last N months of invoicing" in the UI; allow override.
3. Outflows learned from bank data: engine accepts `obligations` produced by confirmed recurring detection (P23); until then manual entry still works. Add `source` field (manual|detected) to obligations.
4. Tests: promise shifts expected date; broken promise falls back; run-rate calc with gaps; determinism.
ACCEPTANCE: logging a promise changes the forecast and the "why" text; run-rate shows without typing a monthly number.
```

---
## P08: Walk-forward backtest and accuracy badge
```
TASK: Build an honest accuracy measure, shown in the UI.
1. ml/backtest.py: walk-forward on a dataset (default ml/sample/payment_date_sample.csv, or full data/payment_date.csv if present). For each of >=6 cut-off dates, train only on invoices settled before the cut-off, forecast payment dates for invoices open at the cut-off, compare with actual. Metrics: payment-date MAE (days), median absolute error, P10-P90 coverage of actual payment dates (target ~80%), and for cash balance bands (using synthetic outflows where needed) coverage of actual balance, plus shortage-alert hit rate (precision/recall at a threshold of 50%). Output ml/results/backtest.json with n_cutoffs, n_invoices, label "backtest on public data", and caveats.
2. Forecast log: table `forecast_log` (business_id, generated_at, horizon dates, p10/p50/p90 json, shortage_prob, first_shortage_date, model meta). Save one row per day per business at most (upsert) whenever the forecast view endpoint is called. Add backend/modules/live_accuracy.py that, once dates have passed, compares logged forecasts to actual balances/receipts and returns live MAE and coverage when >=14 days of history exist; else returns null.
3. API: GET /api/forecast/backtest returns the backtest.json plus live accuracy if available.
4. Badge text rules (used by UI in P10): "Backtested on public data: payments predicted within X days on average; 80% band contained actual Y% of the time" and "Live accuracy builds after 14 days of use". Never present synthetic or public-data accuracy as this business's accuracy.
5. Tests for metric functions with tiny hand-calculated cases.
ACCEPTANCE: `python -m ml.backtest` writes backtest.json; API returns it; forecast log fills.
```

---
## P09: Forecast view API (the single payload the Home screen needs)
```
TASK: Add GET /api/forecast/view (and GET /api/state for shell data) in backend/routers/forecast_view.py returning shared.schema.ForecastView.
1. headline: build from shortage_prob and first_shortage_date: "Likely short by Rs 1.2L around 14 Nov (68% chance)". If probability < 10%: "No cash shortage expected in the next 90 days (X% risk)". If stale or missing expenses: say so instead of making a confident headline.
2. why: top 3 to 5 drivers ranked by impact: late big invoice ("Customer X's Rs 4.2L is expected around 28 Nov +- 9 days, but payroll is due 5 Nov"), upcoming obligation clusters, supplier bills. Use spread = (p90 date - p10 date)/2.
3. per-invoice table via GET /api/forecast/invoices: expected pay date, probability paid within 30 days, risk label (low/medium/high), promise info.
4. Include accuracy block from P08, stale flag from P04, warnings from P01.
5. Validate responses with shared/validate.py --live. Add tests.
ACCEPTANCE: validate.py --live passes; headline strings match the rules for four test cases (shortage, no shortage, stale, no expenses).
```
