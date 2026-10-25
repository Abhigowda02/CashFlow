# PROJECT MEMORY: everything discussed (single source of truth)

## 1. Product
A forecaster for small businesses that invoice on credit. Home screen answers one question:
**"When will I run out of cash, and why?"** Output is a headline like "Likely short by Rs 1.2L around 14 Nov (68% chance)",
a P10/P50/P90 chart with a floor line, a "why" list, a per-invoice table (expected pay date + probability), and an accuracy badge.
It is a **cash-flow copilot, not an accountant** (#10): reads invoices and bank data, predicts shortages, tells the owner what to do.
Owner approves every action (reminder, payment plan). Design goal: fewest taps, not zero interaction.

## 2. The 13 points the evaluator/user raised (all must be covered)
1 Forecaster must visibly forecast (screen explains it). 2 Customer reminders. 3 Real invoices, no demo.
4 Recommended actions practical. 5 Customer actions (instalments, revised schedules). 6 Legal/escalation.
7 Mobile + laptop. 8 Setu / Account Aggregator. 9 UI/UX done properly. 10 Does it replace an accountant? (No.)
11 Real data connectors (statement, SMS, AA, synthetic). 12 Work without merge confusion. 13 Accuracy/model quality.

## 3. Current state of the repo (from the zip)
- Backend FastAPI `backend/main.py` routes: /api/demo, /api/onboarding, /api/business, /api/forecast, /api/scenario, /api/scenarios (GET/POST/DELETE),
  /api/actions, /api/customers, /api/customer-context, /api/collections, /api/customers/retrain, /api/ledger, /api/expenses,
  /api/import, /api/import/pdf/preview, /api/import/pdf/apply, /api/receipts, /api/plan. Auth in backend/auth.py (Argon2id, cookie sessions, CSRF).
- DB: SQLAlchemy tables in backend/database.py (workspaces with JSON payload, users, sessions, receipts, scenarios, auth_rate_limits). No migrations; created from metadata.
- Engine: engine/forecast.py (Monte Carlo 90 days, 500 sims), actions.py, collections.py, schedules.py (monthly only), datagen.py, check_contract.py, demo.py.
- ML: ml/delay_model.py survival model; needs >=20 invoices and >=10 settlements; evaluate.py; payment_date.csv (7 MB, USD/CAD public data, not INR).
- Frontend: App.tsx is 1,317 lines, 7 tabs (dashboard, forecast, simulator, actions, ledger, customers, expenses); DemoControl.tsx; Tailwind + Recharts.
- Demo code to remove: backend/demo.py, engine/demo.py (keep only as test fixture if tests need it), frontend DemoControl.tsx, examples/jury_*, demo path in onboarding, /api/demo.
- README states: `as_of` frozen on purpose; imports start with no obligations and zero future sales (flat forecast); weekly/yearly recurrence, expense auto-detection, revised payment schedules, live accuracy tracker are NOT implemented.
- Junk to delete before work: .venv, .pytest_cache, .chrome-*, .edge-temp, frontend/dist, duplicate demo-dataset copies, data/payment_date.csv (7 MB; keep a small sample for backtest), *.sqlite3 files, ml/artifacts. Fix .gitignore.
- A demo-business run of the engine worked: P50 Rs 1,00,000 -> ~Rs 6,20,000, shortage probability 32%, first shortage date 2026-11-01. So a blank forecast on a real workspace = no obligations/future sales, or a UI/API problem.

## 4. Model upgrades (priority order)
1 Shrinkage: customer -> segment -> business blend. 2 Better features: amount, terms, month-end effect, recent delay trend, previous late count, dispute flag.
3 Promise-to-pay dates feed the forecast. 4 Future sales from actual invoicing run-rate. 5 Outflows from detected recurring bank expenses.
6 Common-shock factor so customers can be late together (fatter bad tail).
**Accuracy**: walk-forward backtest at past cut-offs: payment-date error (MAE), P10-P90 coverage (~80% target), shortage-alert hit rate.
Show in UI. Label "backtest on public data" (payment_date.csv). Save every forecast so live forecast-vs-actual can be shown later.

## 5. Real invoices, dynamic dates
Remove demo. Use today's date (Asia/Kolkata) for overdue days, aging, forecast start; recalc on every open.
Keep accounting idea: store cash balance + "last updated" date; prompt owner (or bank data) when stale; no alerts on stale data.
Readers: CSV/XLSX with auto column-mapping (Tally, Zoho, Vyapar), text PDF, scanned PDF/photo via OCR, GST e-invoice JSON.
OCR/LLM extraction returns JSON (invoice no., customer, amount, GST, dates, terms) + confidence + confirm table. Never save unreviewed extractions.
Tell users images go to a third party. Basics: duplicate detection, edit/delete, mark paid, bulk actions.

## 6. Reminders, alerts, legal
Owner alerts: when shortage probability within N days crosses a threshold, name the cause. In-app bell first, then email.
Follow docs/NOTIFICATIONS_PLAN.md (dedupe key business+obligation+date+stage, no alerts on stale data, Asia/Kolkata worker, quiet hours, privacy).
Customer reminder ladder: 3 days before due = friendly; due date = polite; +7 = firm; +15 = final demand with interest; +30 = legal-notice draft.
Templates personalised by invoice list, amount, UPI/bank details, tone (use existing relationship-context fields).
Delivery: SMTP email; WhatsApp via wa.me prefilled link; SMS via sms: link. Log every message (evidence). Owner approves each send. Never auto-send legal notices.
Legal facts (I am not a lawyer; an advocate must verify): MSMED Act: registered micro/small suppliers must be paid within 45 days (15 if no written agreement);
interest = compound with monthly rests at 3x RBI bank rate; medium enterprises generally not covered; formal advocate notice about 15 days after due date is commonly advised;
recovery via state Facilitation Council; reportedly since Oct 2025 new references go through the MSME ODR portal instead of Samadhaan (verify current portal);
cheque bounce = Section 138 NI Act, parallel route. Section 43B(h) defers buyer's tax deduction until payment.
Feature: compute statutory interest (RBI rate editable setting) and generate a "DRAFT - for advocate review" notice (PDF) with invoice table, interest, documents checklist.

## 7. Actions (action cards)
Each card: what, with whom, how much, by when, effect on shortage date and probability, cost, and an execute button. Types:
chase named customer for named invoices; instalment plan (e.g. 50% now, 50% in 15 days) = revised payment schedule; early-payment discount (cost vs benefit);
invoice discounting/TReDS (cost); supplier deferral (warn for MSME suppliers; 43B(h)); overdraft (cost).
Customers page = worklist: risk, expected pay date, current ladder rung, message history, next step date, one-tap send, "outcome of call" field (feeds promise-to-pay).

## 8. UI/UX rules
5 tabs only: Home, Invoices, Customers, Actions, Connect data. One primary action per screen (Hick). Headline answer top-left (hierarchy).
Show ~5-7 items then expand (Miller). One accent colour reserved for risk (Von Restorff). WCAG AA, never colour alone. 44px+ tap targets, thumb-zone actions on mobile (Fitts).
Familiar fintech patterns: cards, right-aligned amounts, bottom nav on mobile (Jakob). Trust: data freshness + "estimates, not guarantees". Skeleton loaders, helpful empty states.
Indian formatting. Rebuild the 1,300-line App.tsx into page files. Keep Tailwind + Recharts. Mobile-first.

## 9. Data connectors (all feed ONE pipeline)
Common output = list of bank transactions {date, amount, direction, description, balance, source}. Pipeline: detect recurring expenses -> match credits to open invoices -> owner confirms.
- Debits that repeat become obligations (rent, payroll, EMI, utilities). Credits matching an open invoice become receipts. Closing balance becomes opening cash.
- Shared transaction layer: backend/transactions.py, tenant-scoped table, dedupe hash (same upload twice must not double count).
- Statement upload CSV + text PDF (pypdf), column mappings HDFC/SBI/ICICI, reuse pdf_import preview-correct-confirm flow.
- Recurring detection: normalise descriptions (strip UPI/NEFT/IMPS prefixes and refs), group by merchant; recurring if >=3 occurrences, amount within +-5%, consistent gap (7, 30 or 365 days);
  category by keywords: salary, rent, EMI/loan, GST/tax, electricity; propose obligations for approval.
- Weekly + yearly recurrence: extend engine/schedules.py and Obligation model; re-run python -m engine.check_contract.
- Credit-to-invoice matching: by amount, then customer name in description; propose receipts.
- Synthetic data: extend engine/datagen.py to make 12 months of matching bank transactions, receipts on paid dates (test tool only, not user-facing). Gives survival model enough history.
- SMS: web app cannot read SMS -> "paste bank SMS" box with regex parser for debit/credit/UPI messages -> same layer. Pitch: companion Android app would read automatically.
- Setu AA sandbox: register on Setu Bridge early (setup can take hours); FIU + AA data product; consent details + branding; notification endpoint (Beeceptor for quick mock);
  credentials x-product-instance-id, x-client_id, x-client-secret; try in Postman; sample app github.com/SetuHQ/account-aggregator-sample-app.
  Flow: create consent -> user approves on Setu screen -> webhook consent active -> request data -> webhook data ready -> fetch -> convert to transaction format.
  Sandbox data is Setu's mock data (23 FI types). Production needs KYC, product review, Sahamati onboarding, regulated FIU partner.
  If not ready: ship clearly labelled "AA sandbox (mock)" adapter behind the same interface. Pitch line: "AA-integrated, tested on Setu sandbox." Never say it reads real users' expenses.
- One "Connect data" screen: four tabs (statement, SMS, AA sandbox, demo data), review table of detected expenses + invoice matches, then forecast refreshes.
  (Demo data tab = dev/test only, hidden in production build.)

## 10. Mobile + laptop (#7)
Wrap React app with Capacitor -> web + Android APK. SMS reading needs a small Android plugin with SMS permission; iOS cannot. Google Play restricts SMS permissions: sideload APK for demo.
Phone needs to reach backend: host on Render/Railway or use ngrok.

## 11. Standalone modules (fixed JSON in/out)
sms_parser.py (SMS->transaction) | statement_parser.py (CSV/PDF->transactions) | recurring_detector.py (transactions->proposed obligations) | invoice_extractor.py (file->invoice rows + confidence) |
payment_model.py (invoices+history->per-invoice date distribution) | forecast.py | reminder_engine.py (invoices+today->ladder step+message) | legal_notice.py (invoice+interest->draft PDF) | setu_client.py (credentials->transactions) | UI one .tsx per page.
Put new ones under backend/modules/ (pure functions) so the existing engine stays untouched.

## 12. Honest pitch lines
- "Cash-flow copilot, not an accountant. The owner approves every action."
- "AA-integrated, tested on Setu sandbox; production needs a regulated FIU partner."
- "Accuracy shown is a walk-forward backtest on public data; live forecast-vs-actual tracking is built in."
- "A companion Android app would read bank SMS automatically; the web app uses paste-SMS."
- "Legal notice is a draft for advocate review. Not legal advice."
