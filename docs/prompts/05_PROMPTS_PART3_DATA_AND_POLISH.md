# PART 3: DATA CONNECTORS AND POLISH (P21 to P33)
Paste `02_MASTER_PREAMBLE.md` first, then one prompt.
**Do this FIRST, before anything else today (takes minutes, approval can take hours): register on Setu Bridge (bridge.setu.co), create an FIU and an Account Aggregator data product, note the three sandbox credentials. See P28.**
Time guide: P21-P25 about 100 min, P26-P29 about 90 min, P30-P33 as time allows (Tier 3).

---
## P21: Shared transaction layer (tenant-scoped, deduped)
```
TASK: Create backend/transactions.py and backend/routers/transactions.py.
1. Table `bank_transactions` (id, business_id, date, amount (positive integer INR), direction credit|debit, description, normalized_description, balance nullable, source statement|sms|aa|manual|synthetic, dedupe_hash, import_batch_id, status raw|matched|ignored, created_at), unique (business_id, dedupe_hash).
2. dedupe_hash = sha256 of (date, signed amount, normalized description lower-cased with refs stripped, balance if present, occurrence index within identical same-day rows so two genuine identical payments on one day are both kept). Uploading the same file twice must add 0 new rows.
3. `import_batches` (id, business_id, source, filename, created_at, row_count, new_rows, duplicate_rows, status preview|committed). Preview endpoint returns parsed rows without saving; commit saves.
4. Functions: normalize_description(text) (strip UPI/NEFT/IMPS/RTGS/POS/ATM prefixes, transaction/reference numbers, VPA handles keep merchant name), save_transactions(rows, source, business_id), list_transactions(filters), closing_balance(business_id) (latest dated balance).
5. Endpoints: POST /api/transactions/preview, POST /api/transactions/commit, GET /api/transactions, DELETE /api/transactions/batch/{id} (undo an import).
6. Closing balance suggestion: after commit, return `suggested_cash` and ask the owner to confirm updating cash balance + cash_updated_on (never automatic).
7. Tests: dedupe on re-upload, same-day identical rows, normalization cases, tenant isolation, undo.
ACCEPTANCE: re-uploading the same transactions leaves the count unchanged.
```

---
## P22: Statement upload (CSV and text PDF) with HDFC, SBI, ICICI mappings
```
TASK: Create backend/modules/statement_parser.py (pure: bytes + filename -> {transactions, detected_bank, confidence, warnings}).
1. CSV/XLS(X) mappings: HDFC (Date, Narration, Chq./Ref.No., Value Dt, Withdrawal Amt., Deposit Amt., Closing Balance; dd/mm/yy), SBI (Txn Date, Value Date, Description, Ref No./Cheque No., Debit, Credit, Balance; dd Mon yyyy), ICICI (S No., Value Date, Transaction Date, Cheque Number, Transaction Remarks, Withdrawal Amount (INR), Deposit Amount (INR), Balance (INR)), plus generic detection by header aliases. Skip junk header/footer lines, handle Dr/Cr suffixes, commas, parentheses negatives, DD/MM vs ISO dates.
2. Text PDF via pypdf: extract text per page, parse rows with regexes per bank layout (date + narration + amounts + balance), use balance deltas to decide credit vs debit when columns are ambiguous; password-protected or scanned PDFs return a clear error (scanned = OCR is a later prompt).
3. Reuse the preview -> correct -> confirm flow from P12/pdf_import: owner can edit/delete rows and fix direction before commit.
4. Fixtures: create small synthetic statements for each bank in tests/sample_data/statements/ (CSV and a generated text PDF using reportlab).
5. Tests per bank + generic + PDF + malformed inputs.
ACCEPTANCE: each fixture produces correct row counts, totals and closing balance.
```

---
## P23: Recurring-expense detection -> proposed obligations
```
TASK: Create backend/modules/recurring_detector.py (pure: transactions -> proposed obligations) and endpoints.
1. Consider debits only. Group by normalized merchant key (fuzzy: lowercase, remove digits/refs, token-sort, similarity >= 0.85).
2. A group is recurring if: >= 3 occurrences, amounts within +-5% of the group median, and gaps consistent with 7, 30 (28 to 31) or 365 days (+-3 days tolerance, +-5 for yearly) in >= 70% of consecutive gaps. Return frequency weekly|monthly|yearly, typical day_of_month or weekday, amount (median), confidence 0 to 1, occurrences list, next_due_date.
3. Category guess by keywords: salary/payroll/wages = payroll; rent/lease = rent; emi/loan/finance/nbfc = emi; gst/tds/tax/challan/itns = tax; electricity/bescom/power/water/internet/broadband/mobile = utilities; insurance; subscription; else other.
4. Endpoints: POST /api/recurring/detect (runs on stored transactions) -> proposals list; POST /api/recurring/accept (owner-approved subset, optionally edited) -> creates obligations with source=detected; POST /api/recurring/reject (remember rejected merchant keys so they are not re-proposed). Nothing is created without accept.
5. Tests: monthly salary with +-2% drift, weekly vendor, yearly insurance, irregular grocery (not recurring), two similar merchants, rejected memory.
ACCEPTANCE: on the synthetic dataset from P26, rent, payroll, EMI and electricity are detected with correct frequency and category.
```

---
## P24: Weekly and yearly recurrence in the engine
```
TASK: Extend engine/schedules.py and the Obligation model additively (old monthly obligations behave identically).
1. Obligation gets `frequency` monthly|weekly|yearly (default monthly), `weekday` (0 to 6) for weekly, `month` + `day_of_month` for yearly, optional `end_date`, `source` manual|detected.
2. Add weekly_occurrences, yearly_occurrences and a single `occurrences(obligations, as_of, horizon_days)` dispatcher; keep monthly_occurrences signature. Month-end and leap-year handling (29 Feb yearly falls on 28 Feb in non-leap years).
3. Update engine/forecast.py and backend/expenses.py (dashboard, recurring monthly total should convert weekly x 52/12 and yearly /12 for the "monthly equivalent") to use the dispatcher. Update frontend Expenses UI forms to allow frequency choice.
4. Update contracts/CONTRACT.md additively (new optional obligation fields) and engine/check_contract.py to validate them. Run `python -m engine.check_contract` and all engine tests.
5. Tests: weekly count over 90 days (12 or 13), yearly within/outside horizon, leap year, end_date, backward compatibility fixtures.
ACCEPTANCE: contract check and all tests green; weekly/yearly expenses appear in forecast and dashboard.
```

---
## P25: Credit-to-invoice matching -> proposed receipts
```
TASK: Create backend/modules/invoice_matcher.py (pure: credits + open invoices -> proposed matches) and endpoints.
1. For each credit transaction: candidates = open invoices (outstanding > 0). Score: exact amount match to an invoice or to outstanding balance (+0.6); amount equals sum of a small set of one customer's invoices (<=4, subset-sum) (+0.5); customer name similarity in description (fuzzy token match, aliases from customer names/GSTIN) (+0.3 to 0.4); invoice number appearing in description (+0.7); date plausibility (after issue date) (+0.1). Return best match with confidence and reasons, plus alternatives. Partial payments allowed when customer matches strongly (confidence flagged lower).
2. Endpoints: POST /api/matches/propose, POST /api/matches/confirm (owner-approved list -> creates idempotent receipts through the existing receipt logic and marks the transaction matched; must not double-add cash that is already in the entered balance: show a prominent note and a toggle "this credit is already included in my balance"), POST /api/matches/ignore.
3. Unmatched credits are listed as "unrecognised income" for the owner to assign or ignore.
4. Tests: exact amount, bundled invoices, name-only match, ambiguity (two same-amount invoices), already-included toggle, idempotency.
ACCEPTANCE: synthetic credits match their invoices with >= 90% precision on the P26 dataset.
```

---
## P26: Synthetic bank + invoice data (developer/test tool only)
```
TASK: Extend engine/datagen.py (keep generate_business working) with generate_bank_history(business, months=12, seed) that outputs matching bank transactions:
rent, payroll (salary day), EMI, electricity, GST payment, weekly vendor, yearly insurance (debits with small noise), credits on invoices' paid dates (amount, with narrations like "NEFT-<ref>-SHARMA TEXTILES"), some partial payments, random small unrelated debits/credits, running balance column. Also emit CSV/PDF statements in HDFC, SBI and ICICI layouts for tests.
Also generate 12 months of invoices (>= 60) with >= 40 settlements so the survival model has history (needs >= 20 invoices and >= 10 settlements).
Expose only through scripts/make_synthetic.py and tests/sample_data; add NOTHING to the user-facing UI except the dev-only "Demo data" tab that is hidden unless VITE_DEV_TOOLS=true and backend APP_ENV != production. Label clearly "Synthetic test data".
Tests: totals reconcile (opening + credits - debits = closing), receipts on paid dates, recurring items detectable by P23, matching by P25.
ACCEPTANCE: running scripts/make_synthetic.py produces CSVs and a PDF; P22, P23, P25 tests use them.
```

---
## P27: SMS parser (paste bank SMS box)
```
TASK: Create backend/modules/sms_parser.py (pure: text -> list of transactions) and endpoint POST /api/sms/parse (preview) + commit through the transaction layer (source="sms").
1. Support multiple SMS pasted at once (split by blank lines or sender headers). Regexes for common Indian bank formats: "Rs 1,250.00 debited from A/c XX1234 on 24-10-26 ... UPI Ref 4321..." , "INR 45,000.00 credited to a/c ...", "Your a/c no. XX1234 is credited by Rs.5000 on 24Oct26 by a/c linked to VPA name@bank (UPI Ref No 123)", "Sent Rs.500 to MERCHANT via UPI", "Rs.2,000 withdrawn at ATM", "Avl Bal Rs 1,23,456.78", "NEFT/IMPS/RTGS credit", card spends "spent on card XX1234 at AMAZON". Extract: amount, direction, date (several formats; default to today if missing, flagged), counterparty/merchant, UPI ref, available balance, last-4 account digits.
2. Ignore OTP, promo, and non-transaction messages; return them as "ignored" with reason.
3. Confidence per message; the owner reviews a table (editable) before commit. Messages may contain personal data: process in memory only, store only the structured row plus a truncated redacted raw text (mask account numbers to last 4).
4. UI box lives in Connect data (P29).
5. Tests with >= 25 realistic sample messages (HDFC, SBI, ICICI, Axis, Kotak, PhonePe/GPay style) including negative cases.
ACCEPTANCE: >= 95% of valid samples parsed correctly; OTP/promo ignored.
```

---
## P28: Setu Account Aggregator sandbox client (with labelled mock fallback)
```
TASK: Create backend/modules/setu_client.py and backend/routers/connect_aa.py. Same output as every other source: list of Transaction (source="aa").
Environment variables (document in backend/.env.example): SETU_BASE_URL, SETU_PRODUCT_INSTANCE_ID, SETU_CLIENT_ID, SETU_CLIENT_SECRET, SETU_REDIRECT_URL, SETU_WEBHOOK_BASE, AA_MODE=sandbox|mock.
Before coding, read Setu's current AA docs (docs.setu.co, "Account Aggregator" section) and the sample app SetuHQ/account-aggregator-sample-app if network is available; use the exact current endpoint paths and headers (x-product-instance-id, x-client-id, x-client-secret) from the docs rather than guessing. If docs are not reachable, implement against an interface and say clearly what must be verified.
Flow: create consent (purpose, FI types DEPOSIT, date range 12 months, frequency, mobile number of the owner) -> return redirect URL for the owner to approve on Setu's screen -> webhook endpoint POST /api/connect/aa/webhook/consent (signature/secret check, tenant mapped by consent id) marks consent ACTIVE -> request FI data session -> webhook /api/connect/aa/webhook/data marks data READY -> fetch FI data -> convert to Transaction list (map FIP statement entries: txn date, amount, type CREDIT/DEBIT, narrative, balance) -> go through the SAME preview/commit pipeline.
`consents` table (id, business_id, handle, status, created_at, data_session_id, last_error). Polling fallback endpoint GET /api/connect/aa/status for when webhooks cannot reach localhost (use ngrok or Beeceptor during development; document in docs/AA_SETUP.md with Postman checks).
MOCK adapter: AA_MODE=mock returns deterministic fake transactions via the same class interface and the UI shows a permanent badge "AA SANDBOX (MOCK DATA)". In sandbox mode show "Setu sandbox: test data, not real accounts".
Pitch constraint: never claim real users' expenses are read; production needs KYC, product review, Sahamati onboarding and a regulated FIU partner. Put this text in the UI info popover.
Tests with mocked HTTP: consent creation, webhook handling, conversion, error states, tenant mapping.
ACCEPTANCE: in mock mode the full flow works end to end; in sandbox mode it works once credentials are filled.
```

---
## P29: One "Connect data" screen (four tabs + review table)
```
TASK: Build frontend/src/pages/ConnectData.tsx.
1. Tabs: Statement (CSV/PDF upload), SMS (paste box), AA sandbox (consent flow with status stepper: Not connected, Waiting for approval, Fetching, Ready), and Demo data (dev-only, hidden in production builds, labelled "Synthetic test data").
2. Each tab ends in the same Review step: (a) transactions table (editable direction/description, duplicates flagged "already imported"), (b) "Detected recurring expenses" table with checkboxes, category/frequency editors, accept/reject, (c) "Invoice matches" table showing credit -> invoice with confidence and reasons, confirm/ignore, "already in my balance" toggle, (d) "Suggested cash balance" row with confirm button.
3. After confirmation the page shows a success summary ("Added 3 expenses, matched 5 payments, balance updated to Rs ...") and a button "See updated forecast" which refreshes Home.
4. Honest copy: explain what each source can/cannot do; Android SMS reading is a roadmap item (companion app); AA is sandbox; privacy note about what is stored.
5. Empty states and skeletons; mobile-friendly stacked cards instead of wide tables below 640px.
6. Component tests or manual test script in docs/TEST_SCRIPT.md covering all four tabs.
ACCEPTANCE: from a fresh account: upload a statement -> accept recurring expenses -> confirm matches -> Home forecast changes and shows expenses learned from bank data.
```

---
## P30: Capacitor Android app with live SMS reading (Tier 3)
```
TASK: Wrap the React app with Capacitor and add an Android-only SMS plugin.
1. `npm i @capacitor/core @capacitor/cli @capacitor/android`, `npx cap init`, `npx cap add android`. Build config so the app talks to a configurable API URL (VITE_API_URL pointing to the hosted backend or an ngrok URL); document CORS and cookie considerations (SameSite, HTTPS) for the native WebView or use a bearer-token fallback only if cookies fail (explain trade-off before changing auth).
2. Small custom plugin (Java or Kotlin) in android/ that, after the user taps "Allow SMS reading" and grants READ_SMS, lists recent SMS from known bank sender IDs (e.g. HDFCBK, SBIINB, ICICIB, AXISBK, KOTAKB, VM-/AD- prefixes) and returns text+timestamp to JS, which sends them to POST /api/sms/parse for the same preview/confirm flow. Never upload SMS that are not bank transaction messages (filter on-device first). Show clear consent copy.
3. Document that iOS cannot do this, that Google Play heavily restricts SMS permissions, so distribute via sideloaded APK for the demo. Provide docs/ANDROID.md with exact commands: build, `npx cap sync`, open in Android Studio, build debug APK, install by adb.
4. Same UI works as a web app on laptop.
ACCEPTANCE: debug APK installs, logs in, shows Home, and the SMS tab can read and preview bank SMS after permission.
```

---
## P31: OCR for scanned invoices and photos (Tier 3)
```
TASK: Create backend/modules/invoice_extractor.py (file -> invoice rows with per-field confidence).
1. Inputs: scanned PDF, JPG/PNG photo. Options: (a) local OCR with pytesseract + pdf2image (document system installs for Windows: Tesseract and Poppler paths in .env), (b) optional LLM extraction through an API key from env (e.g. ANTHROPIC_API_KEY) which returns strict JSON {invoice_no, customer, amount, gst_amount, issue_date, due_date, terms_days, currency} with a confidence score. Choose via OCR_MODE=local|llm, default local.
2. A prominent UI notice before upload when using LLM mode: "Invoice images are sent to a third party service for reading." Local mode keeps files on the server. Never store images after extraction unless the owner asks (delete temp files).
3. Output goes through the same invoices preview -> correct -> confirm table (P12); low-confidence fields highlighted; never saved unreviewed.
4. Tests with a few generated invoice images (render text with Pillow) and mocked LLM responses; validate JSON schema strictly and reject malformed outputs.
ACCEPTANCE: a photo of an invoice produces a review row with sensible fields and confidence flags.
```

---
## P32: WhatsApp Cloud API (Tier 3, optional upgrade over wa.me links)
```
TASK: Add optional WhatsApp Business Cloud API delivery behind the existing delivery interface (P14). Default stays wa.me links.
1. Env: WHATSAPP_TOKEN, WHATSAPP_PHONE_ID, WHATSAPP_TEMPLATE_NAMES (reminder templates approved in Meta). Business-initiated messages outside the 24-hour window must use approved templates; parameterize template variables (customer, amount, invoice no, due date, payment link).
2. Customer opt-in flag required before any API send; log every send in reminder_log with message id and status from webhooks; GET/POST /api/connect/whatsapp/webhook for delivery status with verify token.
3. Owner still approves each send; legal notices are never sent by WhatsApp automatically.
4. Mock mode when credentials absent. Document setup in docs/WHATSAPP_SETUP.md.
5. Tests with mocked HTTP.
ACCEPTANCE: with mock mode on, approving a reminder with channel WhatsApp API records a sent log; wa.me still works.
```

---
## P33: Hosting, end-to-end QA, docs and pitch pack
```
TASK: Finish and verify.
1. Hosting: prepare deployment for Render or Railway: Dockerfile or render.yaml (backend, serves built frontend or separate static site), PostgreSQL via DATABASE_URL, env var list, COOKIE_SECURE, ALLOWED_ORIGINS, health endpoint GET /api/health. Document an ngrok alternative for demos from a phone. Do not claim production readiness (README already lists missing items: email verification, password recovery, backups, monitoring).
2. End-to-end test script docs/TEST_SCRIPT.md and automated API smoke test scripts/e2e_smoke.py: signup, onboarding, upload invoices, upload statement, accept recurring, confirm matches, view forecast, log promise, send reminder (mock), alert created, action card executed, legal interest PDF.
3. Run everything: pytest all, check_contract, shared/validate.py --live, npm run build, backtest. Fix failures.
4. Update README.md: remove stale statements (frozen as_of, demo section), describe new features and honest limits (no accountant replacement, estimates not guarantees, AA sandbox only, SMS paste on web, legal drafts need advocate review, accuracy numbers are backtest on public data).
5. Create docs/PITCH.md: 90-second pitch, 5-minute demo script (Home headline -> why -> upload statement -> expenses detected -> chase customer with one tap -> instalment plan -> legal interest draft), likely judge questions with honest answers (accountant? real bank data? accuracy? privacy? business model?).
6. Final tag: git tag v1-hackathon.
ACCEPTANCE: smoke script passes; README and pitch consistent with what the app really does.
```
