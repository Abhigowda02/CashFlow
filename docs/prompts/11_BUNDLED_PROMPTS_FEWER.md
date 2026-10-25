# FEWER PROMPTS: 12 bundled prompts total (6 per laptop). Nothing removed.
Same 34 tasks, same item-level split. The trick: the full prompt text lives inside the repo, so each pasted prompt is a short pointer. This also saves tokens and avoids repeating the preamble.

## ONE-TIME SETUP (both laptops, 2 minutes, no agent needed)
1. Unzip `CashFlow_Prompt_Pack.zip`.
2. Copy the folder `CashFlow_Prompt_Pack` into your project as `docs/prompts/` (so files are `docs/prompts/03_PROMPTS_PART1_FOUNDATION.md` etc.).
3. Copy `docs/prompts/AGENTS.md` to the project root as `AGENTS.md` (rules for every task; also tell Antigravity to treat it as a workspace rule if it has a rules setting).
4. Replace `<X>` in the prompts below with your letter, A or B.
5. Laptop B only: until A's BASE drop arrives (about 0:25), `OWNERSHIP.md` does not exist. The prompt B-1 tells the agent to use the section 3 and 4 text in docs/prompts/07_TWO_LAPTOP_SPLIT.md instead.

## IF THE IDE SESSION LIMIT HITS MID-WAY: RESUME PROMPT
```
Read AGENTS.md and PROGRESS_<X>.md. Find the last task marked DONE, then continue with the next unfinished task of the bundle I was running (<bundle id>), in order. Check `git status` first and finish any half-written file before starting the next task.
```

---
# LAPTOP A BUNDLES

## A-1 (0:00 to 0:30) P00, P02, INT-1, INT-2, then base drop for B
```
Read AGENTS.md. I am Laptop A. Execute in order, fully, one at a time:
1. P00 (all items) from docs/prompts/03_PROMPTS_PART1_FOUNDATION.md. Skip the frontend npm install (Laptop B owns frontend).
2. P02 (all items) from the same file.
3. INT-1 and INT-2 (all) from docs/prompts/10_EXTRA_PROMPTS_INT_SYNC.md. For INT-1 item 3, copy sections 3 and 4 of docs/prompts/07_TWO_LAPTOP_SPLIT.md verbatim into OWNERSHIP.md.
End with `python scripts/pack.py A` and print the zip name. Log everything in PROGRESS_A.md.
```
**Then you:** send `A_drop_1.zip` to B (S0).

## A-2 (0:30 to 1:15) P21, P01, P03a, P04
```
Read AGENTS.md. I am Laptop A. Execute in order:
1. P21 (all) from docs/prompts/05_PROMPTS_PART3_DATA_AND_POLISH.md.
2. P01 (all backend items; for the UI empty-state card write the request in NEEDS_A.md for B) from 03_PROMPTS_PART1_FOUNDATION.md.
3. P03 items 1 (backend only: backend/demo.py, /api/demo, onboarding demo path, demo tests), 2, 3, 5, and item 4 backend only (onboarding API takes name, cash balance, balance-as-of date, safety buffer).
4. P04 backend items 1 to 7 (the Update-balance modal UI is B's; document the endpoint in NEEDS_A.md).
End with SYNC-OUT from 10_EXTRA_PROMPTS_INT_SYNC.md.
```
**Then you (S1):** send `A_drop_2.zip` to B; receive `B_drop_1.zip` from B; run SYNC-IN (below) before A-3.

## A-3 (1:15 to 2:15) P05a, P06, P07, P08, P09
```
Read AGENTS.md. I am Laptop A. First run SYNC-IN with the B drop from 10_EXTRA_PROMPTS_INT_SYNC.md. Then in order:
1. P05 items 3, 4, 5, 6, 7 (items 1 and 2 are Laptop B's modules invoice_mapper.py and gst_einvoice.py; call them via IF-4). Router: backend/routers/invoices.py.
2. P06 (all), 3. P07 (all), 4. P08 (all), 5. P09 (all), from docs/prompts/03_PROMPTS_PART1_FOUNDATION.md.
Finish by starting the backend and running `python shared/validate.py --live http://localhost:8000 --cookie ...`. End with SYNC-OUT.
```
**Then you (S2):** send `A_drop_3.zip` to B (real API for the UI).

## A-4 (2:15 to 3:00) P13b, P14a, P15a, P17, P16
```
Read AGENTS.md. I am Laptop A. Run SYNC-IN if a B drop arrived. In order, from docs/prompts/04_PROMPTS_PART2_PRODUCT.md:
1. P13 items 4, 5, 6 (tables, endpoints, rung-5 rule; call Laptop B's reminder_engine.py via IF-3; items 1, 2, 3, 7 are B's).
2. P14 items 1, 2, 3 (delivery.py, send endpoint, contact fields; item 4 UI is B's).
3. P15 items 1, 2, 3, 4 (tables, rules, worker, endpoints, verified email; item 5 UI is B's).
4. P17 (all).
5. P16 items 1, 2, 3, 4, 6 (UI item 5 is B's).
End with SYNC-OUT.
```
**Then you (S3):** exchange drops with B.

## A-5 (3:00 to 3:50) P19a, P18a, P24, P26, P28, P31, P32
```
Read AGENTS.md. I am Laptop A. SYNC-IN first. In order:
1. P19 items 2, 3, 5 (plans table, engine instalments, execute endpoint; UI items 1 and 4 are B's) from 04_PROMPTS_PART2_PRODUCT.md.
2. P18 backend only: GET /api/customers/worklist, customer_events table, backend tests.
3. P24 items 1 to 5 (engine, expenses backend, contract update, check_contract, tests; the Expenses form UI is B's) from 05_PROMPTS_PART3_DATA_AND_POLISH.md.
4. P26 (all), 5. P28 (all backend; UI is in B's P29), 6. P31 (all), 7. P32 (all), from the same file.
End with SYNC-OUT.
```
**Then you (S4):** send final `A_drop_5.zip` to B; receive B's final drop.

## A-6 (3:50 to 4:00+) integration and P33
```
Read AGENTS.md. I am Laptop A. SYNC-IN with B's final drop. Then P33 items 1, 3, 4, 5, 6 from docs/prompts/05_PROMPTS_PART3_DATA_AND_POLISH.md (hosting files, full test run: pytest all, check_contract, validate --live, backtest, frontend build; README; docs/PITCH.md; tag v1-hackathon). Item 2 (TEST_SCRIPT.md, e2e_smoke.py) is Laptop B's. Report any failing test with file and line.
```

---
# LAPTOP B BUNDLES

## B-1 (0:00 to 0:30) P27, P22 (on the ORIGINAL zip copy)
```
Read AGENTS.md. I am Laptop B. OWNERSHIP.md does not exist yet: use sections 3 and 4 of docs/prompts/07_TWO_LAPTOP_SPLIT.md instead, and put stubs for backend.deps and backend.transactions in backend/stubs_b.py (to be swapped when A's base arrives). Execute in order from docs/prompts/05_PROMPTS_PART3_DATA_AND_POLISH.md:
1. P27 (all): modules/sms_parser.py, routers/b_sms.py, tests.
2. P22 (all): modules/statement_parser.py, routers/b_statements.py, fixtures, tests.
Use inline fixtures; do not touch files outside the B ownership list.
```
**Then you (S0 at ~0:25):** receive `A_drop_1.zip`, run SYNC-IN (below).

## B-2 (0:30 to 1:15) SYNC-IN, P23, P25, P05b, P13a
```
Read AGENTS.md and OWNERSHIP.md. I am Laptop B. Run SYNC-IN with the A drop (10_EXTRA_PROMPTS_INT_SYNC.md), swap stubs for the real backend.deps / backend.transactions / backend.ledger_api. Then in order:
1. P23 (all) and 2. P25 (all) from 05_PROMPTS_PART3_DATA_AND_POLISH.md (routers b_recurring.py, b_matches.py using IF-0, IF-1, IF-2; rejected-merchant table in backend/tables/b_recurring.py).
3. P05 items 1 and 2 only (invoice_mapper.py, gst_einvoice.py, tests) from 03_PROMPTS_PART1_FOUNDATION.md.
4. P13 items 1, 2, 3, 7 only (backend/modules/reminder_engine.py pure + tests) from 04_PROMPTS_PART2_PRODUCT.md.
End with SYNC-OUT.
```
**Then you (S1 at 1:15):** send `B_drop_1.zip` to A.

## B-3 (1:15 to 2:15) P03b, P10, P11, P12
```
Read AGENTS.md and OWNERSHIP.md. I am Laptop B. Run SYNC-IN if A's second drop arrived. Backend not needed: run `uvicorn shared.mock_server:app --port 8000`. In order:
1. P03 frontend parts only: remove DemoControl.tsx, demo banners, "Explore synthetic demo" UI, demo-datasets under frontend/public; onboarding UI with the 4 fields (name, cash balance, balance-as-of date, safety buffer).
2. P10 (all), 3. P11 (all), 4. P12 (all) from docs/prompts/04_PROMPTS_PART2_PRODUCT.md (P10 to P12).
Add the empty-state card with warnings (P01 UI) and the Update-balance modal (P04 UI) if A's NEEDS_A.md lists their endpoints.
End with SYNC-OUT.
```
**Then you (S2 at 2:15):** receive `A_drop_3.zip` (real API), SYNC-IN.

## B-4 (2:15 to 3:00) real API switch, P14b, P15b, P18, P19b, P16b
```
Read AGENTS.md and OWNERSHIP.md. I am Laptop B. SYNC-IN with A's real API drop; switch VITE_API_URL from mock to the real backend and fix every field mismatch in my files (if the contract is wrong, write it in NEEDS.md). Then in order from docs/prompts/04_PROMPTS_PART2_PRODUCT.md:
1. P14 item 4 only (ReminderSheet UI). 2. P15 item 5 only (bell, dropdown, prefs modal).
3. P18 UI (Customers worklist, call-outcome modal, contact editor) on A's /api/customers/worklist (if not delivered yet, use the mock sample and mark TODO).
4. P19 items 1 and 4 (Actions page, What-if section). 5. P16 item 5 only (interest breakdown + notice draft button UI).
End with SYNC-OUT.
```
**Then you (S3):** exchange drops.

## B-5 (3:00 to 3:50) P24 UI, P29, P20, P30
```
Read AGENTS.md and OWNERSHIP.md. I am Laptop B. SYNC-IN first. In order:
1. P24 UI only: frequency, weekday, month fields in the Expenses form (05_PROMPTS_PART3_DATA_AND_POLISH.md).
2. P29 (all): Connect data page with four tabs and review tables; AA tab uses A's /api/connect endpoints (mock mode if sandbox not ready).
3. P20 (all) from 04_PROMPTS_PART2_PRODUCT.md, writing docs/UX_CHECKLIST.md.
4. P30 (all) Capacitor Android + SMS plugin + docs/ANDROID.md from 05_PROMPTS_PART3_DATA_AND_POLISH.md.
End with SYNC-OUT (final B drop).
```

## B-6 (3:50 to 4:00+) P33 item 2 and demo run-through
```
Read AGENTS.md. I am Laptop B. SYNC-IN with A's final drop. Then P33 item 2 only: docs/TEST_SCRIPT.md and scripts/e2e_smoke.py. Run frontend build, the e2e smoke script against the running backend, and walk through the demo script in docs/prompts/06_CHECKLIST_AND_PITCH.md. List every bug found with file and line; fix those in my files, send the rest to NEEDS.md.
```

---
## SYNC prompts (short form, paste when told)
SYNC-IN, SYNC-OUT and their full text are in `10_EXTRA_PROMPTS_INT_SYNC.md`; since the bundles already say "run SYNC-IN / SYNC-OUT", the agent reads them from `docs/prompts/10_EXTRA_PROMPTS_INT_SYNC.md`.

## Count
Before: 47 pasted prompts across both laptops (26 on A, 21 on B), each with a long preamble.
Now: 12 short bundles (A-1..A-6, B-1..B-6) plus the resume prompt only if the IDE cuts you off. Every original item is still assigned (see the cross-check in the item list below).

## Cross-check: every prompt item covered
P00 A-1 | P01 A-2 (+UI in B-3) | P02 A-1 | P03 A-2 + B-3 | P04 A-2 (+UI in B-3) | P05 B-2 (1,2) + A-3 (3-7) | P06-P09 A-3 | P10-P12 B-3 | P13 B-2 (1,2,3,7) + A-4 (4,5,6) | P14 A-4 (1-3) + B-4 (4) | P15 A-4 (1-4) + B-4 (5) | P16 A-4 (1-4,6) + B-4 (5) |
P17 A-4 | P18 A-5 (backend) + B-4 (UI) | P19 A-5 (2,3,5) + B-4 (1,4) | P20 B-5 | P21 A-2 | P22 B-1 | P23 B-2 | P24 A-5 (1-5) + B-5 (UI) | P25 B-2 | P26 A-5 | P27 B-1 | P28 A-5 | P29 B-5 | P30 B-5 | P31 A-5 | P32 A-5 | P33 A-6 (1,3-6) + B-6 (2) | INT-1, INT-2 A-1
