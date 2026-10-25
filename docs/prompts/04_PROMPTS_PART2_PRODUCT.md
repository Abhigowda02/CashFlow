# PART 2: PRODUCT (P10 to P20)
Paste `02_MASTER_PREAMBLE.md` first, then one prompt. Time guide: P10-P12 about 90 min, P13-P16 about 90 min, P17-P20 about 90 min.

---
## P10: App shell and design system (split App.tsx, 5 tabs)
```
TASK: Rebuild the frontend structure. Keep Tailwind + Recharts + existing AuthGate/api.ts. Mobile-first.
1. Create frontend/src/pages/{Home,Invoices,Customers,Actions,ConnectData}.tsx, frontend/src/components/{Shell,BottomNav,Sidebar,TopBar,Card,Money,RiskBadge,FreshnessChip,Skeleton,EmptyState,Modal,DataTable,Toast}.tsx, frontend/src/lib/{format.ts,useApi.ts}.
2. Shell: exactly 5 tabs: Home, Invoices, Customers, Actions, Connect data. Desktop = left sidebar; mobile (<768px) = bottom nav with 5 icons (lucide-react), 44px+ tap targets. Top bar: business name, FreshnessChip ("Balance as of 24 Oct, update"), bell (placeholder for P15), account menu with sign out.
3. Design tokens in index.css (CSS variables): neutral surfaces, ONE accent colour reserved for risk/shortage (e.g. a single red-orange), a calm primary for non-risk actions. WCAG AA contrast on all text. Never use colour alone: risk badges include icon + word.
4. format.ts: formatINR(n) with lakh/crore grouping ("Rs 1,20,000", "Rs 1.2L", "Rs 3.4Cr" compact variant), formatDateIN (e.g. "14 Nov"), relativeDays.
5. Skeleton loaders for every async block; helpful EmptyState component with title, one sentence, one primary button.
6. Move existing ledger/expenses/customers/scenario functionality behind the new tabs temporarily (e.g. render old LedgerPage under Invoices, old ScenarioPlanner under Actions > "What-if" section) so nothing is lost; later prompts replace them. Delete code from App.tsx until it is just routing + data bootstrap (<150 lines).
7. One primary action per screen (largest filled button); secondary actions are text/outline buttons.
8. Add "Estimates, not guarantees" footer text and a link to the accuracy popover (wired in P11).
ACCEPTANCE: `npm run build` passes; 5 tabs work on 375px and 1280px widths; App.tsx under 150 lines; no feature removed.
```

---
## P11: Home screen (the answer to "when will I run out of cash, and why?")
```
TASK: Build frontend/src/pages/Home.tsx using GET /api/forecast/view (build against shared/mock_server first if the backend is not ready, then switch).
Layout, top to bottom (headline top-left, details below):
1. Headline card: the `headline` string large; below it a one-line sub: "Estimate from <N> open invoices and <M> expenses. Balance as of <date>." If stale: amber banner with "Update balance" button. If warnings: banner listing them with a button to fix (e.g. "Add expenses" or "Connect data").
2. Chart (Recharts): P10-P90 shaded band, P50 line, dashed safety-floor line, vertical marker at first shortage date, tooltip with INR values, x-axis dates, y-axis lakh/crore ticks. Accessible: aria-label summary and a "view as table" toggle.
3. "Why" list: up to 5 WhyItem rows (icon + sentence + amount + date +- spread), "Show all" expands (Miller's law).
4. Next best step card: top ActionCard from /api/actions/cards (once available; placeholder until P17) with one button.
5. Per-invoice table (top 7 by amount at risk, "Show all" link to Invoices): customer, amount, due, expected pay date, probability within 30 days, risk badge, promise icon. Right-aligned amounts.
6. Accuracy badge: small chip "Backtested on public data" opening a popover with metrics and caveats from /api/forecast/backtest, plus "Live accuracy builds after 14 days of use".
7. Skeleton on load, EmptyState if no invoices.
ACCEPTANCE: against mock and real API, the page renders headline, chart bands, why list, table, badge; keyboard accessible; no horizontal scroll at 375px.
```

---
## P12: Invoices page (real data: upload, review, edit, mark paid, bulk)
```
TASK: Build frontend/src/pages/Invoices.tsx on the P05 endpoints.
1. Top: summary strip (outstanding, overdue, due in 7 days) + primary button "Upload invoices".
2. Upload flow in a Modal: step 1 choose file (CSV, XLSX, PDF, GST JSON; drag and drop); step 2 mapping preview (detected mapping with confidence, editable dropdowns); step 3 review table of parsed rows with inline-editable cells, red flags for duplicates/missing fields/low confidence, checkbox "These amounts are in INR"; step 4 confirm (Add to existing or Replace). Nothing saved before step 4.
3. Table with tabs All/Open/Overdue/Paid, search, sort, status chip with icon+text, aging bucket column, right-aligned amounts, row actions: Edit, Mark paid (partial amount allowed), Log promise-to-pay (date), Delete. Bulk select bar: Mark paid, Delete, Set segment, Set terms. Show 10 rows then "Show more".
4. Customer segment and terms editors; segment values small/corporate/government.
5. Empty state: "No invoices yet" with Upload and Connect data buttons.
ACCEPTANCE: import each fixture from P05 through the UI; edit, mark paid, bulk and promise actions work and refresh the Home forecast.
```

---
## P13: Reminder engine and escalation ladder (pure module + queue)
```
TASK: Create backend/modules/reminder_engine.py (pure, no DB) and backend/routers/reminders.py.
1. Ladder (days relative to due date): -3 friendly; 0 polite; +7 firm; +15 final demand with statutory interest; +30 legal-notice draft. Function next_step(invoice, today, sent_log) -> {rung, due_on, overdue_days} or None; never repeat a rung already sent for that invoice; skip paid invoices; pause if a promise-to-pay is active and not yet broken; pause if dispute flag set (suggest resolving the issue first).
2. Templates (English, with Hindi short variants as optional): personalised with customer name, invoice list (number, date, amount, due date), total outstanding, payment details (UPI ID, bank account name/number/IFSC from business settings, new fields), tone derived from relationship-context fields (strategic/repeat customer = softer; service issue open = acknowledge issue first).
3. Group multiple overdue invoices of the same customer into ONE reminder.
4. Tables: `reminders` (id, business_id, customer_id, invoice_ids json, rung, channel, subject, body, status draft|approved|sent|cancelled, created_at, approved_at, sent_at, delivery_status) and `reminder_log` (immutable append-only evidence: who, what text, when, channel, result). Business settings: payment details, sender name, contact email/phone.
5. Endpoints: GET /api/reminders/queue (today's due steps as drafts), POST /api/reminders/{id}/edit, POST /api/reminders/{id}/approve, POST /api/reminders/{id}/cancel.
6. Rung 5 is a draft only and requires an explicit second confirmation; it never sends automatically.
7. Tests: ladder boundaries (-3, 0, +7, +15, +30), no duplicates, grouping, promise/dispute pauses, template rendering with Indian number formatting.
ACCEPTANCE: queue endpoint returns correct drafts for a fixture with invoices at each stage.
```

---
## P14: Reminder delivery (SMTP email, WhatsApp link, SMS link) and approve-and-send screen
```
TASK: Delivery plus UI.
1. backend/modules/delivery.py: send_email(smtp settings from env: SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, SMTP_FROM, use STARTTLS) -> result; build_whatsapp_link(phone, text) -> https://wa.me/<digits>?text=<urlencoded> (normalise Indian numbers to 91XXXXXXXXXX); build_sms_link(phone, text) -> sms:<phone>?body=<urlencoded>. Env documented in backend/.env.example. If SMTP not configured, email send returns a clear "not configured" error and the UI offers "Copy text" and "Open in my email app" (mailto link).
2. POST /api/reminders/{id}/send: requires status approved; for email actually sends and logs; for WhatsApp/SMS returns the link and marks sent after the owner confirms in the UI ("I sent it"). Every action writes reminder_log. Rate limit per business.
3. Customer contact fields (email, phone) on customers; editable; missing contact blocks that channel with a helpful message.
4. UI: frontend/src/components/ReminderSheet.tsx, a drawer/bottom sheet: customer, rung chip, editable subject/body, invoice list, channel picker, buttons Approve then Send (one primary button that changes label). Shows history from reminder_log. Rung 5 shows a warning "Draft only: have an advocate review" and second confirmation.
5. Tests: link builders, SMTP mocked, approval required before send, logging immutable, tenant isolation.
ACCEPTANCE: from the queue I can edit, approve and send an email (or open WhatsApp link) and see the log entry.
```

---
## P15: Owner alerts (bell, rules, dedupe, stale suppression, email)
```
TASK: Implement docs/NOTIFICATIONS_PLAN.md as built, in-app first.
1. Tables: `alerts` (id, business_id, kind, severity, title, body, created_at, read_at, snoozed_until, dedupe_key unique per business, link), `alert_prefs` (business_id, risk_threshold default 0.4, horizon_days default 14, email_enabled bool, email_verified bool, quiet_hours, digest weekly bool), `alert_outbox` (alert_id, channel, status, attempts, last_error).
2. backend/modules/alert_rules.py (pure): evaluate(forecast_view, invoices, obligations, today, prefs) -> list of new alerts:
   a) shortage within N days with probability >= threshold, naming the cause ("Customer X's late payment will leave you short before payroll on 5 Nov"); b) upcoming big expense 7/3/1 days, consolidated per date, escalated if forecast shows a gap; c) invoice reached a ladder step (link to reminder queue); d) promise broken; e) stale balance (this replaces risk claims while stale); f) weekly digest.
   dedupe_key = business + kind + subject + date + stage, so the same alert is never duplicated; meaningfully changed forecast (probability moved +-15 points) can create a new key.
3. Worker: APScheduler (or a simple background thread) running daily at 08:00 Asia/Kolkata and also evaluating on forecast refresh; no alerts on stale data other than the stale alert.
4. Endpoints: GET /api/alerts, POST /api/alerts/{id}/read, POST /api/alerts/{id}/snooze, GET/POST /api/alert-prefs. Email delivery reuses delivery.py, only after the owner verifies their email (send a verification link/token) and opted in; privacy-conscious body (no balances on lock-screen style text; link into the app).
5. UI: bell in TopBar with unread count badge, dropdown list (5 items, "View all"), read/snooze, links to the relevant page, settings modal for prefs.
6. Tests: dedupe, stale suppression, threshold, consolidation, tenant isolation.
ACCEPTANCE: setting up a fixture where payroll precedes a large late invoice creates exactly one shortage alert naming the cause; running the evaluator twice does not duplicate it.
```

---
## P16: Legal: statutory interest and "DRAFT for advocate review" notice
```
TASK: Create backend/modules/legal_notice.py (pure) and endpoints.
1. Statutory interest (MSMED Act, Section 16): compound interest with monthly rests at 3x the RBI bank rate on the amount from the day after the deadline (45 days from acceptance/deemed acceptance; 15 days if no written agreement; use due_date if the written terms are shorter than 45 days). Function interest(invoice, as_of, rbi_rate_pct) -> {days_overdue, principal, interest, total, rate_used, method_note}. RBI rate is an editable business setting with a default clearly marked "verify current RBI bank rate" (do not hard-code as fact; show the source note).
2. Eligibility check: supplier must be a registered micro/small enterprise (Udyam registration number field in business settings; boolean) and buyer is not a consumer; if not registered or medium, show "MSMED statutory interest may not apply. Interest here would be contractual only."
3. Notice draft generator: A4 PDF using reportlab (add to requirements) titled "DRAFT, FOR ADVOCATE REVIEW, NOT LEGAL ADVICE" in header and footer of every page, with: parties, invoice table (no., date, amount, due date, days overdue), interest computation table, total claimed, payment demand within 15 days, mention of the options (MSME Facilitation Council reference; Section 138 NI Act if a cheque bounced; verify current portal), and a documents checklist (invoice copies, PO/work order, delivery proof/challan, acceptance email/confirmation, ledger statement, reminder log, Udyam certificate).
4. Endpoints: GET /api/legal/interest?invoice_id=, POST /api/legal/notice (invoice_ids) -> PDF download. Only available for invoices >=30 days overdue (rung 5) and requires explicit confirmation. Notice generation writes reminder_log.
5. UI: in the Customers worklist and ReminderSheet for rung 4/5 show interest breakdown and "Generate notice draft" button with the advocate-review warning.
6. Tests: interest compounding monthly against hand-calculated values; eligibility messages; PDF created and contains the DRAFT text.
ACCEPTANCE: PDF generated for a fixture with correct interest and checklist.
```

---
## P17: Action cards engine (practical, executable, quantified)
```
TASK: Add backend/modules/action_cards.py and GET /api/actions/cards returning list[ActionCard] sorted best-first. Reuse engine.rank_actions and engine.collections.rank_collections where possible; run what-if forecasts for each card to compute shortage_prob_before/after, first shortage date, runway gained.
Card types (each with who, how much, by when, effect, cost, risk, note, execute button payload):
1. chase_customer: named customer + named invoices -> execute opens a prepared reminder draft (P13/P14).
2. instalment_plan: propose e.g. 50% now and 50% in 15 days for a customer with large late invoice, sized to close the gap; execute creates a revised payment schedule (see P19) and a drafted message.
3. early_payment_discount: offer X% discount for payment within N days; show cost (discount) vs benefit (shortage reduction), choose X by cheapest that closes the gap, capped (e.g. 3%).
4. invoice_discounting (TReDS/factoring): cost = annualised rate x days x amount (configurable default range, labelled assumption); execute = informational checklist (no integration).
5. supplier_deferral: only for non-MSME suppliers as low risk; MSME suppliers beyond 45 days flagged HIGH risk with 43B(h) note; cost = possible interest/relationship.
6. overdraft: cost = rate x amount x days (editable assumption).
Each card shows assumptions explicitly. Cards that do not reduce shortage probability are filtered out. Cap list at 8, show top 3 on Home.
Tests: card ranking, MSME high-risk rule, cost formulas, determinism.
ACCEPTANCE: for the diagnostic business, cards list sensible actions with numbers; shared/validate.py --live passes for /api/actions/cards.
```

---
## P18: Customers page as a worklist
```
TASK: Build frontend/src/pages/Customers.tsx (replace old CustomersPage/CollectionsPanel use) on GET /api/customers/worklist (create it).
Per customer row: name, outstanding, overdue amount, risk badge (icon+word), expected pay date (from forecast view), current ladder rung chip, last message (date, channel), next step date, a one-tap "Send reminder" button (opens ReminderSheet), and "Log call outcome".
1. "Log call outcome" modal: outcome (promised date | will pay partially | dispute raised | not reachable | paid), promise date picker, note. Promised date writes a promise (P07); dispute sets the dispute flag (pauses reminders); outcomes stored in `customer_events`.
2. Sort default: highest cash impact first; filters: overdue only, at risk, has promise.
3. Expanding a row shows message history (reminder_log), promises, relationship context form (reuse CustomerContextForm), payment behaviour stats (paid count, median delay, on-time share with shrinkage note).
4. Show 7 rows then "Show more".
5. Contact details editor (email, phone) used for channels.
Backend: tests for worklist composition and customer_events.
ACCEPTANCE: from this page I can send a reminder, log a call promise, and see the forecast and expected date update.
```

---
## P19: Actions page, execute flows, and revised payment schedules
```
TASK: Build frontend/src/pages/Actions.tsx and POST /api/actions/{id}/execute.
1. Page: list ActionCards (3 visible, "Show all"), each with what/who/how much/by when, a before/after mini-bar of shortage probability, runway gained, cost, risk badge, and one primary button.
2. Revised payment schedules (README says missing): table `payment_plans` (id, business_id, invoice_id, installments json [{due_date, amount, status}], created_on, agreed_by_customer bool|null). Engine: invoices with an accepted/proposed plan use instalment dates (with the same delay model per instalment) instead of the single due date; proposed plans (not yet agreed) are shown as what-if only.
3. Execute: chase -> creates reminder draft and opens ReminderSheet; instalment plan -> creates plan (status proposed) + message draft with the schedule table, owner marks "customer agreed" later; early discount -> draft offer message; discounting/overdraft -> checklist modal plus "log as taken" that updates assumptions; supplier deferral -> draft message to supplier with MSME warning.
4. Keep the existing "What-if" scenario planner as a secondary section "Test your own scenario" (delay customer, sales change, extra expense, supplier terms), with saved scenarios.
5. Tests: plan creation, engine using instalments, execution logging.
ACCEPTANCE: executing an instalment-plan card creates the plan, shows revised schedule, and the forecast reflects it once marked agreed.
```

---
## P20: UI/UX polish and accessibility pass (mobile-first)
```
TASK: Audit and fix the whole UI against these rules, then write docs/UX_CHECKLIST.md with pass/fail per rule:
Hick (5 tabs, one primary action per screen), visual hierarchy (answer top-left), Miller (5 to 7 items then expand), Von Restorff (single risk accent, nothing else red/orange), WCAG AA contrast (check with a script or axe-core), never colour alone, Fitts (44px targets, key actions in thumb zone on mobile, sticky bottom action bars), Jakob (cards, right-aligned amounts, bottom nav), trust (freshness chip and "estimates, not guarantees" on forecast screens), perceived speed (skeletons, optimistic updates where safe), empty states on every list, Indian formatting everywhere (grep for toLocaleString without 'en-IN', and raw numbers).
Also: keyboard navigation and focus rings, aria labels on charts, reduced-motion, dark text on light surfaces only (no low-contrast greys), Lighthouse accessibility >= 90 on Home and Invoices, no horizontal scroll at 360px, tables scroll inside their own container.
Add Vitest or node tests for format.ts. Remove unused CSS and components (old workspace.css pieces no longer used).
ACCEPTANCE: UX_CHECKLIST.md all pass or has justified exceptions; build green.
```
