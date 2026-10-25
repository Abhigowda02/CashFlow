# ONE LAPTOP: 9 PROMPTS TOTAL (8 build + 1 final audit), EVERYTHING INCLUDED (all 34 tasks P00 to P33)
No splitting, no syncing, no pack/unpack. Ignore files 07 to 11 (two-laptop material).

## ONE-TIME SETUP (3 minutes, no agent)
1. Unzip `CashFlow_Prompt_Pack.zip`. Copy the folder `CashFlow_Prompt_Pack` into your project as `docs/prompts/`.
2. Copy `docs/prompts/AGENTS_SINGLE.md` to the project root and rename it `AGENTS.md` (rules for every task).
3. **Right now, in a browser:** register on Setu Bridge (FIU + Account Aggregator data product, sandbox credentials). Approval can take hours and P28 needs it. If it is not ready by then, P28 ships the labelled mock mode.
4. Paste the 9 prompts below one at a time. Wait until each finishes, check the acceptance lines, then paste the next.

## RESUME PROMPT (if the IDE session limit cuts you off)
```
Read AGENTS.md and PROGRESS.md. Find the last task marked DONE, check `git status`, finish any half-written file, then continue with the next unfinished task of the bundle I was running (<bundle id>), in order.
```

---
## S-1: Foundation (P00, P01, P02, P03, P04)
```
Read AGENTS.md. Execute in order, fully, every numbered item:
P00, P01, P02, P03, P04 from docs/prompts/03_PROMPTS_PART1_FOUNDATION.md.
(Cleanup + rollback tag; forecast diagnosis; contract kit; remove demo; dynamic dates with cash "last updated".)
Log each in PROGRESS.md and commit after each P-number.
```
Check: tests green, `git tag` shows `rollback-before-rebuild`, no demo in backend/frontend, stale-balance banner works.

## S-2: Real invoices, model upgrades, backtest, forecast API (P05, P06, P07, P08, P09)
```
Read AGENTS.md. Execute in order, fully, every numbered item:
P05, P06, P07, P08, P09 from docs/prompts/03_PROMPTS_PART1_FOUNDATION.md.
(Invoice import with mapping/GST JSON/duplicates/edit/bulk; shrinkage + features + common shock; promise-to-pay + run-rate; walk-forward backtest + forecast log; /api/forecast/view.)
Finish by running shared/validate.py --live against the running backend. Log and commit after each P-number.
```
Check: all tests + `python -m engine.check_contract`; `python -m ml.backtest` writes backtest.json; headline strings correct for 4 cases.

## S-3: New UI core (P10, P11, P12)
```
Read AGENTS.md. Execute in order, fully, every numbered item:
P10, P11, P12 from docs/prompts/04_PROMPTS_PART2_PRODUCT.md.
(5-tab shell and design system, split App.tsx; Home screen with headline, bands chart, why list, per-invoice table, accuracy badge; Invoices page with upload/mapping/review/edit/promise/bulk.)
Use the real API (backend running). Log and commit after each P-number.
```
Check: `npm run build` passes; 5 tabs at 375px and 1280px; App.tsx under 150 lines.

## S-4: Bank-data pipeline (P21, P22, P24, P23, P25)
```
Read AGENTS.md. Execute in this order, fully, every numbered item, from docs/prompts/05_PROMPTS_PART3_DATA_AND_POLISH.md:
P21, P22, P24, P23, P25.
(Transaction layer with dedupe; HDFC/SBI/ICICI statements CSV+PDF; weekly/yearly recurrence in engine + check_contract; recurring detection; credit-to-invoice matching.)
Use inline fixtures for tests (the synthetic dataset comes in S-7, then re-run the acceptance checks). Log and commit after each P-number.
```
Check: re-uploading the same file adds 0 rows; weekly/yearly appear in forecast; check_contract green.

## S-5: Reminders, alerts, legal (P13, P14, P15, P16)
```
Read AGENTS.md. Execute in order, fully, every numbered item, from docs/prompts/04_PROMPTS_PART2_PRODUCT.md:
P13, P14, P15, P16.
(Reminder ladder + templates + queue; SMTP/wa.me/SMS delivery + ReminderSheet UI + send log; owner alerts with bell, dedupe, stale suppression, email; MSMED interest + DRAFT-for-advocate notice PDF.)
Log and commit after each P-number.
```
Check: queue shows correct rung drafts; one shortage alert, not duplicated; PDF has DRAFT text and correct interest.

## S-6: Actions, customers, UX (P17, P18, P19, P20)
```
Read AGENTS.md. Execute in order, fully, every numbered item, from docs/prompts/04_PROMPTS_PART2_PRODUCT.md:
P17, P18, P19, P20.
(Action cards with before/after; Customers worklist with call outcomes; Actions page with instalment plans/revised schedules and What-if; full UX/accessibility pass and docs/UX_CHECKLIST.md.)
Log and commit after each P-number.
```
Check: instalment card creates a plan and shifts the forecast once agreed; UX_CHECKLIST passes; Home shows top 3 cards.

## S-7: Synthetic data, SMS, Setu, Connect screen (P26, P27, P28, P29)
```
Read AGENTS.md. Execute in order, fully, every numbered item, from docs/prompts/05_PROMPTS_PART3_DATA_AND_POLISH.md:
P26, P27, P28, P29.
(12-month synthetic bank+invoice data as dev tool; SMS parser; Setu AA client with mock fallback and webhooks; one Connect data screen with four tabs and review tables.)
After P26, re-run the acceptance checks of P22, P23 and P25 on the synthetic data. Log and commit after each P-number.
```
Check: statement -> recurring accepted -> matches confirmed -> Home forecast changes; AA mock badge visible.

## S-8: Tier 3 and finish (P30, P31, P32, P33)
```
Read AGENTS.md. Execute in order, fully, every numbered item, from docs/prompts/05_PROMPTS_PART3_DATA_AND_POLISH.md:
P30, P31, P32, P33.
(Capacitor Android + live SMS plugin; OCR for scanned invoices/photos; WhatsApp Cloud API with mock mode; hosting files, e2e smoke test, README, PITCH.md, final test run, tag v1-hackathon.)
Run everything at the end: pytest all, check_contract, validate --live, backtest, npm run build, scripts/e2e_smoke.py. Log and commit after each P-number.
```
Check: smoke script passes; README and pitch match the app.

---

## S-9: Final audit, make every feature work (no half features)
```
Read AGENTS.md (especially DEFINITION OF DONE). Do a full audit of the finished app. Do NOT add features.
1. Create docs/FEATURE_STATUS.md covering every feature from P00 to P33 (Home headline/chart/why/table/accuracy badge, invoice upload CSV/XLSX/PDF/GST JSON/OCR, edit/mark paid/bulk, promise-to-pay, reminders ladder + email/WhatsApp/SMS/log, alerts + bell + email, legal interest + notice PDF, action cards + execute, instalment plans, customers worklist + call outcomes, statement upload HDFC/SBI/ICICI CSV+PDF, recurring detection, weekly/yearly, credit matching, SMS paste, AA sandbox/mock, synthetic dev tool, backtest + live accuracy, dynamic dates + stale balance, Android SMS, WhatsApp API mock, hosting files).
2. For each feature, test it through the real running app and API from a fresh account (use scripts/e2e_smoke.py extended where useful, plus manual curl/API checks) and record PASS/FAIL.
3. Fix every FAIL. Re-test. Repeat until all are PASS. If one truly cannot work (for example external credentials unavailable), make sure its mock/fallback mode works and is labelled, and say exactly what is missing.
4. Sweep the UI: no dead buttons, no console errors, no TODO/placeholder text, every list has empty and error states, every page works at 375px and 1280px, keyboard focus works.
5. Run everything: pytest all, check_contract, validate --live, backtest, npm run build, e2e smoke. Fix failures.
6. Confirm README and docs/PITCH.md match FEATURE_STATUS.md (no claim of anything marked FAIL or mock-only).
7. Commit and tag v1-final.
Reply with the final FEATURE_STATUS.md table and any remaining limitation, in plain words.
```
Check: every row in FEATURE_STATUS.md is PASS or "PASS (mock mode, labelled)".

---
## After S-9 (you)
0. If time is running out, run S-9 anyway: it is what makes everything working and honest.
1. Walk the demo script in `06_CHECKLIST_AND_PITCH.md` from a fresh account, once at phone width.
2. Confirm the honest labels show: "Estimates, not guarantees", "Backtest on public data", "AA sandbox", "Draft for advocate review".
3. Back up the folder (zip without node_modules/.venv) and keep `git tag v1-hackathon`.
4. Rehearse the 90-second pitch twice.

## Coverage cross-check
S-1: P00 P01 P02 P03 P04 | S-2: P05 P06 P07 P08 P09 | S-3: P10 P11 P12 | S-4: P21 P22 P24 P23 P25 | S-5: P13 P14 P15 P16 | S-6: P17 P18 P19 P20 | S-7: P26 P27 P28 P29 | S-8: P30 P31 P32 P33 | S-9: audit of everything. All 34 tasks, every item.
