# LAPTOP B RUNBOOK (Face: frontend + pure parser modules)
For each line: paste `02_MASTER_PREAMBLE.md` + TWO-LAPTOP PREAMBLE (in 10_EXTRA_PROMPTS_INT_SYNC.md), then the prompt from the file shown, using ONLY the items listed.
**Start immediately** on your copy of the ORIGINAL CashFlow.zip, no need to wait for A. Put your modules in the file names listed. Test with inline fixtures. A's BASE drop arrives at ~0:25 (S0): run SYNC-IN, your files stay untouched because A does not own them.
Until the base arrives, tell the agent: "backend.deps and backend.transactions do not exist yet; write routers against the interfaces in OWNERSHIP section 4 and use a local stub in backend/stubs_b.py."

| # | Time | Prompt | File | Items to run | Output files |
|---|---|---|---|---|---|
| B1 | 0:00 | P27 | 05 | all (SMS parser + router backend/routers/b_sms.py using IF-0, IF-1) | modules/sms_parser.py, routers/b_sms.py, tests/test_b_sms.py |
| B2 | 0:12 | P22 | 05 | all (statement parser, bank layouts, PDF via pypdf, router b_statements.py, fixtures in backend/tests/fixtures/statements/) | modules/statement_parser.py ... |
| B3 | 0:25 | SYNC-IN | 10 | apply A's BASE drop, run tests | |
| B4 | 0:32 | P23 | 05 | all (recurring detector, router b_recurring.py; accept uses IF-2 add_obligations; rejected-merchant memory table in backend/tables/b_recurring.py) | |
| B5 | 0:45 | P25 | 05 | all (matcher + router b_matches.py; confirm uses IF-2 record_receipt_for_invoice) | |
| B6 | 0:57 | P05 | 03 | items 1, 2 only (invoice_mapper.py, gst_einvoice.py + tests) | |
| B7 | 1:05 | P13 | 04 | items 1, 2, 3, 7 only (reminder_engine.py pure + tests, IF-3) | |
| **S1** | 1:15 | SYNC-OUT | 10 | | Send B drop 1 to A (all modules + routers) |
| B8 | 1:20 | P03 | 03 | frontend parts: remove DemoControl.tsx, demo banners, "Explore synthetic demo" UI, onboarding UI with 4 fields; remove demo-datasets from frontend/public | |
| B9 | 1:30 | P10 | 04 | all (shell, design system, 5 tabs; build against `uvicorn shared.mock_server:app --port 8000`) | |
| B10 | 1:50 | P11 | 04 | all (Home) | pages/Home.tsx |
| B11 | 2:05 | P12 | 04 | all (Invoices) | pages/Invoices.tsx |
| **S2** | 2:15 | SYNC | 10 | | Receive A's real API; switch `VITE_API_URL` from mock to real; fix field mismatches (report any contract mistakes to A via NEEDS.md) |
| B12 | 2:25 | P14 | 04 | item 4 only (ReminderSheet UI) | |
| B13 | 2:35 | P15 | 04 | item 5 only (bell, dropdown, prefs modal); also P01 UI part: empty-state card with warnings; P04 UI part: Update-balance modal | |
| B14 | 2:50 | P18 | 04 | UI (Customers worklist, call-outcome modal, contact editor) using A's /api/customers/worklist | |
| B15 | 3:00 | P19 | 04 | items 1, 4 (Actions page + What-if section) | **S3** |
| B16 | 3:10 | P16 | 04 | item 5 only (interest breakdown + notice button UI) | |
| B17 | 3:15 | P24 | 05 | UI only: frequency/weekday/month fields in the Expenses form | |
| B18 | 3:20 | P29 | 05 | all (Connect data: four tabs + review tables, AA tab uses A's connect endpoints) | pages/ConnectData.tsx |
| B19 | 3:35 | P20 | 04 | all (UX pass, docs/UX_CHECKLIST.md) | |
| B20 | 3:40 | P30 | 05 | all (Capacitor Android + SMS plugin) | frontend/android/... |
| **S4** | 3:30-3:50 | SYNC-OUT | 10 | | Final B drop to A |
| B21 | 3:50 | P33 | 05 | item 2 only (docs/TEST_SCRIPT.md, scripts/e2e_smoke.py), then run through the demo script in 06_CHECKLIST_AND_PITCH.md | |

Frontend env: `VITE_API_URL=http://localhost:8000/api` for the real backend (laptop A's IP over WiFi when testing together, e.g. http://192.168.x.x:8000/api; A starts uvicorn with `--host 0.0.0.0` and adds that origin to ALLOWED_ORIGINS in env).
If B20 (Android) or B19 (P20) are not finished at 3:50, finish after the demo run-through.
