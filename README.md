# CashFlow

The demo uses synthetic business and cash-flow data; it is not financial advice.

## Run the API

From the repository root, install the backend requirements and start the API:

```powershell
pip install -r backend/requirements.txt
uvicorn backend.main:app --reload --port 8000
```

The API is available under `/api` on port 8000. CORS is enabled for the frontend
at `http://localhost:5173`.

## Run the frontend

```powershell
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`. The frontend proxies `/api` to port 8000 so session
cookies remain on the same origin. Both `localhost` and `127.0.0.1` are accepted
by the API's local development CORS policy. Keep both terminals running.

## Developer fixtures: synthetic data generation

Synthetic data generators and test fixtures exist solely for offline development, contract verification, and automated testing:
- `engine/datagen.py`: `generate_business(seed)` generates contract-compliant synthetic MSME business profiles for engine tests and contract verification.
- `tests/sample_data/`: Sample CSV and Excel files (e.g. `01_textile_wholesale.csv`, `02_it_services.csv`) used for testing file ingestion and invoice auto-mapping.

The user-facing application operates strictly on user-entered or imported business data without seeded demo fixtures or simulated demo modes.


## SaaS MVP accounts

Create an account with an email and a 5–10 character password containing at
least one special character, then enter your business name, observation date,
cash and safety buffer. This short password policy is intended for the demo;
use a stronger policy before any production deployment. Existing accounts can
continue signing in with their existing passwords. Each owner gets one
isolated workspace with no seeded invoices or synthetic data. Sign out is in the
app header. All financial routes require a valid session. Passwords use Argon2id;
session tokens are opaque, revocable, expire after seven days, and are stored
hashed on the server. The browser cookie is HttpOnly with SameSite=Lax. Mutations
require an allowed Origin and a session-bound CSRF header. Signup/login attempts
are throttled in the database. Authentication tokens are not stored in localStorage.

Default development storage is ignored `backend/.local/saas.sqlite3`. The older
single-workspace `ledger.sqlite3` is preserved but is not exposed or silently
assigned to any new account. Re-import your own invoices into the intended account.

For hosting, supply `DATABASE_URL=postgresql+psycopg://...`, `APP_ENV=production`,
`COOKIE_SECURE=true`, and explicit HTTPS `ALLOWED_ORIGINS`; see `backend/.env.example`.
The example is documentation, not automatically loaded. Production startup rejects
SQLite and insecure cookie/origin settings. Serve the frontend and `/api` behind
one HTTPS origin and configure your reverse proxy and trusted forwarding addresses.
The production frontend must have an `/api` reverse proxy; Vite's proxy is for
development only. Provision database access, TLS and backups before deployment.
The initial schema is created from SQLAlchemy metadata; future schema changes
need a reviewed migration process. A live PostgreSQL deployment is not yet tested.

Email ownership verification, password recovery, invitations/roles, subscriptions,
audit-history expansion, monitoring and a public production rollout remain pending.
No password-reset email or public hosting is claimed. This is a tested local
multi-account MVP foundation, not a completed production SaaS launch.

## Observation date and accounting reconciliation

**The application does not automatically tick forward with your computer's clock:**

- **Observation Date (`as_of`)**: The application anchors to an Observation Date (`as_of`) (e.g., `2026-10-25`). All 90-day cash forecasts, overdue receivables calculations, and upcoming obligation schedules project forward from this anchor.
- **Why it does not auto-advance**: When tomorrow arrives, the app does not silently advance the date by 1 day and pretend bank debits or customer receipts occurred. In financial accounting, bank balances must be reconciled against actual bank statements, not guessed by a timer.
- **Reconciliation-Driven Updates**: When a new bank statement arrives or a new accounting period begins, users advance the observation date in workspace settings or record settled receipts, ensuring that simulated liquidity always reflects verifiable ledger reality.

## Integrated payment model

Install `ml/requirements.txt`. Choose **Survival model** in the app header to use
a model fitted exclusively to the signed-in business's records for existing
unpaid invoices, scenario comparisons, and action simulations. Future-sales
delays still use empirical segment pools.
The header reports the actual model and labels fallback when survival is
unavailable. Model parameters are cached per invoice; sampling remains seeded.
The offline command `python -m ml.train --csv data/payment_date.csv` still works,
but its shared dataset artifact is not used for authenticated SaaS forecasts.

## Customer payment behaviour

Open **Customers** to see each customer's paid-invoice count, median/mean delay,
delay variability, on-time share, and outstanding balance. Descriptive statistics
use observed settled invoices only; they have survivor/selection bias and should
not be confused with survival-model estimates. Unpaid and partly paid invoices
remain censored training observations, rather than being labelled paid.

For outstanding invoices, a fitted business model shows estimated 70%/90% paid-by
dates and the chance of payment within 7/30/60 days through the API (30 days in
the UI). These estimates condition on still being unpaid at the observation date,
including invoices not yet due. They concern final settlement, not timing of
future partial receipts. Dates more than ten years away are not displayed.

At least 20 invoices and 10 observed settlements are required before attempting
a fit. This is a practical data gate, not statistical evidence of calibration.
Customers with fewer than three observed settlements use a censored segment fit,
or the pool for this business when that segment has no observed payments.
Insufficient history or failed fitting leaves probability dates unavailable;
survival forecast requests fall back to empirical forecasting and say so.

Models refresh lazily when insights or a survival forecast are requested after
relevant history, segments, invoice amounts, or observation date changes. Cash
and supplier-plan edits alone do not retrain the payment model. A manual refresh
is limited to five requests per five minutes per business. No automatic accuracy
or calibration claim is made. Offline forward-time evaluation is available; a
live business accuracy tracker remains future work.

See [forecast evidence and reproducible evaluation](docs/FORECAST_EVIDENCE.md).
The checked-in `ml/results/metrics.csv`, `calibration.png` and `report.json` are a
three-origin **synthetic pipeline smoke test only**. Unsupported follow-up
horizons and small-sample intervals are explicitly unavailable. They do not
establish accuracy on representative real businesses or validate cash-shortage
probabilities. Run the documented protocol on suitable, consented records before
making any accuracy or calibration claim.

The invoice-amount predictor is excluded unless explicit metadata establishes
one declared currency and original-invoice-amount semantics. Mixed USD/CAD raw
export values and legacy workspaces without that provenance do not qualify.
Owner declarations are not independent verification. Older saved models without
the safe feature-policy version are refitted from supplied data or rejected with
a retraining message; they are never silently reused as safe models.

Tenant artifacts are atomically saved under ignored
`ml/artifacts/businesses/<hashed-business-id>/delay_model.joblib`. Set
`PAYMENT_MODEL_DIR` to a private server directory when deploying. The store is
never served over HTTP and never accepts uploaded pickles. Fingerprints prevent
reuse after relevant data changes; a bounded, process-local cache speeds repeated
forecasts. A read-only store uses memory-only fits, which are rebuilt after restart.
Keep this directory private and apply a deletion/retention policy when adding
account deletion. Each worker can reconstruct its model from database records.

## Collections prioritisation and relationship context

In **Customers**, open **Relationship & service context** to mark customer
importance, repeat business, open/resolving service issues, disputed outstanding
invoices, and private notes. Records are tenant scoped and updated atomically
without altering receipts or cash. Missing context is explicitly unreviewed.
These fields do not become payment-model features or change observed history.

In **Recommended actions → Prioritised collections**, the app evaluates each
customer with overdue outstanding invoices under a 7/15/30-day earlier-payment
assumption. It uses 500 paired paths: the same sampled receipts and unrelated
cash flows are held fixed, then that customer's overdue receipts are moved
earlier, never before tomorrow. This produces the same cash-impact comparison
as rerunning those receipt accelerations, without repeating all other draws.
Invoices paid partly contribute only their outstanding balance; settled and
future-due invoices are excluded. Raw simulation paths never leave the engine.

Ranking uses shortage-probability reduction, expected peak cash-gap reduction,
expected runway gain, then cash advanced by the comparison date. Expected peak
gap averages the maximum below-floor gap over all paths, including zeros. Runway
is the average first-crossing day, capped at the 90-day horizon. The comparison
date is the baseline estimated shortage date, or day 30 if none is forecast.
Overdue amount and customer ID break ties. No arbitrary relationship-weighted
score is claimed. Collections move receipt timing rather than creating revenue.

Relationship sensitivity and recommended approach appear separately. Open
service issues or disputed overdue invoices call for issue resolution first;
strategic/repeat customers get a personal account-owner approach; usually on-time
customers get a courtesy reminder. Other overdue accounts can get a professional
payment-commitment request. The owner decides what to do; messages are never sent.

Benefits are conditional what-if results, not learned estimates of reminder
effectiveness. Actual collection success, outreach cost, discounts, and future
relationship revenue are not modelled. Resolve disputes before relying on that
invoice's timing benefit. The older engine `chase_invoice` action remains for
contract compatibility; the UI's collections table supersedes that single-largest
invoice recommendation. Re-importing a workspace resets relationship context.

## Expenses dashboard

Open **Expenses & obligations** for one view of salary/payroll, rent, EMI/loans,
tax provisions, utilities, subscriptions, insurance and other monthly expenses.
Use **Manage expenses & plan** to add/edit them, assign categories, and maintain
supplier bills and sales assumptions. The same records feed the forecast.
Legacy obligations without a category appear under Other until the owner tags them.

The dashboard shows the recurring monthly total, scheduled outflows in the next
7/30 days, overdue open supplier bills, monthly category breakdowns, upcoming
calendar-month totals, all recurring definitions and a searchable 7/30/90-day
payment schedule. Windows include the observation date and exclude the day after
the selected period. Overdue supplier totals are listed separately from future
7/30-day totals. Calendar totals cover only the displayed 90-day window, so the
first and last months may be partial.

Forecasts and the dashboard share `engine.schedules.monthly_occurrences`, including
month-end and leap-year handling. Amounts describe scheduled commitments rather
than bank-reconciled spending. Weekly/yearly recurrence, completed-occurrence
tracking and automatic expense detection are not implemented. Statutory dates
remain owner supplied. No notification delivery is enabled yet; see
[the notification proposal](docs/NOTIFICATIONS_PLAN.md).

## Invoice file format

Open **Ledger & import** and download the template. CSV and Excel `.xlsx` are
accepted, up to 2,000 invoice rows and 5 MB per workspace. Required columns:
`invoice_id,customer_id,amount,issue_date,due_date`. Optional columns:
`customer_name,segment,status,received_amount,paid_date,currency`.
Use ISO dates, nonnegative whole INR, unique invoice IDs, and customer segments
`small`, `corporate`, or `government`. Fully paid invoices need a paid date;
partial payments use `status=open` and `received_amount` less than the total.

Import explicitly replaces the workspace and receipt log. Enter cash already
available on the observation date; earlier invoice receipts are not added again.
Imported workspaces initially have no supplier bills or obligations and zero
future sales. Add these in **Outflows & future sales** before interpreting a
forecast. Recurring dates are user supplied, without automatic tax-deadline
validation. Days 29–31 use the last day of shorter months. Advancing the
observation date does not automatically book actual bank debits or credits.

**Record money received** adds a new receipt to available cash and reduces the
outstanding invoice balance. Do not record payments already included in the
entered cash. Repeated requests with the same receipt ID are idempotent;
overpayments are rejected. Only the outstanding part enters the forecast.
The ledger shows issued/due/overdue/partly paid/received states, receivable and
payable aging, and customers owing at least 30% of outstanding receivables.

### Text PDF invoice review

The PDF workflow accepts text-based PDFs up to 5 MB and 25 pages, with one
invoice per page. The backend extracts selectable text locally; no document is
sent to an OCR or AI service. Scanned/image-only and encrypted PDFs are not
supported. Each extracted invoice is a draft with its source page, source text,
confidence indicators and correction flags. Review and correct the fields
before proceeding. If currency is missing or unclear, explicitly confirm INR;
foreign currencies must be converted by the owner before entry. No amount is
converted and no payment status is inferred.

Applying drafts requires separate confirmation that the amounts are INR and
that the invoices should be **added** to the existing workspace. Existing
invoice IDs and duplicates within the PDF are blocked rather than overwritten.
Adding does not replace records, modify available cash, or create new receipts.
For scanned PDFs or layouts that do not extract reliably, use the dependable
CSV/XLSX workflow instead. PDF extraction is a convenience for review, not
verified accounting data.

State is isolated per account in the configured database. New workspaces start
empty; import and receipt operations affect only the authenticated owner's business.
The API no longer replaces engine errors with unrelated static forecasts.

The raw `data/payment_date.csv` is supported by the ML training CLI, but is not
the browser invoice template: it contains USD/CAD amounts and cannot silently
be treated as INR. Tally and bank exports need mapping; automatic parsing,
Account Aggregator connections, and bank reconciliation remain future work.

Uploads with missing/blank currency require explicit confirmation that the
original invoice amounts are INR; known foreign currencies are rejected even
with confirmation. The UI also requires the owner to confirm the INR units.
No exchange-rate conversion is performed. Owner declarations are recorded as
provenance, not independent verification of source records. Legacy workspaces
without amount provenance do not qualify to use the amount predictor.

## Verification

```powershell
python -m pytest engine/tests ml/tests backend/tests -q
python -m engine.check_contract
cd frontend
npm run build
```

Backend tests also require `pytest` and `httpx`; ML test dependencies are in
`ml/requirements.txt`. Saved scenario definitions and comparison are implemented.
Remaining work includes individual revised-payment schedules,
an action-combination optimiser, seasonality, a compliance calendar, collection
messages, external alerts, sharing, and a live accuracy dashboard.

See [problem-statement alignment](docs/PROBLEM_ALIGNMENT.md) for the exact
requirement mapping and remaining financial functionality.
