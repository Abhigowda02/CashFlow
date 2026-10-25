# LAPTOP A RUNBOOK (Brain: DB, engine, ML, API, services)
For each line: paste `02_MASTER_PREAMBLE.md` + TWO-LAPTOP PREAMBLE (in 10_EXTRA_PROMPTS_INT_SYNC.md), then the prompt from the file shown, using ONLY the items listed.
Item numbers refer to the numbered points inside each prompt.

| # | Time | Prompt | File | Items to run | Notes |
|---|---|---|---|---|---|
| A1 | 0:00 | P00 | 03 | all | Cleanup, tag. Do NOT reinstall frontend deps (B owns frontend). |
| A2 | 0:08 | P02 | 03 | all | Contract kit, ENDPOINTS.md, mock_server. B needs this at S0. |
| A3 | 0:15 | INT-1 | 10 | all | Auto-loaders, deps.py, OWNERSHIP.md, pack/unpack scripts |
| A4 | 0:22 | INT-2 | 10 | all | ledger_api.py + minimal transactions.py, then `pack.py A` -> **S0 BASE drop to B** |
| A5 | 0:30 | P21 | 05 | all | Full transaction layer (IF-1) |
| A6 | 0:45 | P01 | 03 | all | Forecast diagnosis + warnings API (UI part belongs to B: put it in NEEDS_A.md for B's empty-state card) |
| A7 | 0:55 | P03 | 03 | items 1 (backend parts only: backend/demo.py, /api/demo, onboarding demo path, demo tests), 2, 3, 5; item 4 backend only (onboarding API accepts name, cash balance, balance-as-of date, safety buffer) | Frontend demo removal is B's (P03b) |
| A8 | 1:05 | P04 | 03 | all backend items (1-7); UI "Update balance" modal is B's | Tell B the endpoint in NEEDS_A.md |
| **S1** | 1:15 | SYNC-OUT / SYNC-IN | 10 | | Receive B drop 1 (modules batch) |
| A9 | 1:20 | P05 | 03 | items 3 (PDF extension), 4, 5, 6, 7. Items 1, 2 are B's modules, call them via IF-4 | Router backend/routers/invoices.py |
| A10 | 1:35 | P06 | 03 | all | |
| A11 | 1:50 | P07 | 03 | all | Item 3 uses obligations source field |
| A12 | 2:00 | P08 | 03 | all | Backtest uses ml/sample/payment_date_sample.csv |
| A13 | 2:08 | P09 | 03 | all | Forecast view API; then `shared/validate.py --live` |
| **S2** | 2:15 | SYNC | 10 | | Send B the real API; B switches from mock |
| A14 | 2:20 | P13 | 04 | items 4, 5, 6 (tables, endpoints, rung-5 rule). Items 1, 2, 3, 7 are B's pure module via IF-3 | |
| A15 | 2:30 | P14 | 04 | items 1, 2, 3 (delivery.py, send endpoint, contact fields). Item 4 UI is B's | |
| A16 | 2:40 | P15 | 04 | items 1, 2, 3, 4 (tables, rules, worker, endpoints, email). Item 5 UI is B's | |
| A17 | 2:50 | P17 | 04 | all | Action cards |
| A18 | 3:00 | P16 | 04 | items 1, 2, 3, 4, 6 (module, PDF, endpoints, tests). UI item 5 is B's | **S3** |
| A19 | 3:05 | P19 | 04 | items 2, 3 (plans table, engine use of instalments, execute endpoint backend), 5 | UI items 1, 4 are B's |
| A20 | 3:12 | P18 | 04 | backend only: GET /api/customers/worklist, customer_events table, backend tests | UI is B's |
| A21 | 3:18 | P24 | 05 | all backend/engine items (1-5). Frequency form UI in Expenses is B's | Run check_contract |
| A22 | 3:25 | P26 | 05 | all | Dev dataset for acceptance tests of B's modules |
| A23 | 3:30 | P28 | 05 | all backend (client, router, mock, tests, AA_SETUP.md). The UI is in B's P29 | |
| A24 | 3:40 | P31 | 05 | all (backend/modules/invoice_extractor.py + hook into invoices preview) | |
| A25 | 3:45 | P32 | 05 | all | |
| **S4** | 3:30-3:50 | SYNC | 10 | | Final drop from B |
| A26 | 3:50 | P33 | 05 | items 1, 3, 4, 5, 6 (hosting, full test run, README, PITCH, tag). Item 2: test script docs/TEST_SCRIPT.md and e2e_smoke.py are B's | |

Setu: do the Bridge registration yourself right now in a browser while the agent runs A1 (P00).
If A24/A25 are not finished at 3:50, finish them AFTER P33's test run, but do not skip them.
