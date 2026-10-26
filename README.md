# CashFlow

### AI-powered cash-flow forecasting and collections copilot for Indian small businesses

CashFlow helps a business that sells on credit answer three practical questions:

1. **When could cash fall below the safety buffer?**
2. **Which invoices, customers, or expenses are driving the risk?**
3. **What can the owner review or do next?**

The application combines invoice and payment history, planned expenses, supplier bills, and future-sales assumptions into a 90-day probabilistic cash forecast. It is a hackathon prototype—not accounting software, financial advice, legal advice, or a replacement for an accountant.

> **AI disclosure:** This project was developed with AI-assisted engineering and contains local AI/ML functionality. Payment-timing models, Monte Carlo forecasts, and fraud anomaly scoring run in the Python application. It does not require a hosted generative-AI API at runtime.

## Contents

- [Why CashFlow](#why-cashflow)
- [Features](#features)
- [How the AI works](#how-the-ai-works)
- [Architecture](#architecture)
- [Quick start](#quick-start)
- [First run and demo](#first-run-and-demo)
- [Invoice import format](#invoice-import-format)
- [Mock-bank and fraud demo](#mock-bank-and-fraud-demo)
- [Configuration](#configuration)
- [Testing](#testing)
- [Project structure](#project-structure)
- [Limitations](#limitations)

## Why CashFlow

Small businesses can be profitable on paper and still run short of cash while waiting for customers to pay. A simple total-receivables number does not show timing uncertainty. CashFlow keeps actual receipts separate from expected collections, estimates when outstanding invoices may settle, and compares those inflows with upcoming obligations.

## Features

### Overview and 90-day cash forecast

- Available cash, cash runway, overdue receivables, and shortage probability.
- Daily P10/P50/P90 cash bands for the next 90 days.
- Estimated first shortage date and likely cash-pressure drivers.
- Clear warnings when expenses are missing or the cash balance is stale.
- Large workspaces remain interactive by using a smaller, disclosed simulation count.

### Invoice and receipt ledger

- CSV invoice import with common Tally/Zoho-style header aliases.
- Text-PDF draft extraction for review; scanned PDFs are not treated as OCR results.
- Automatic append to the current invoice list; existing records are preserved.
- Duplicate invoice IDs and invalid rows are reported instead of overwritten.
- Whole-INR amounts and ISO dates throughout the backend.
- Status derived from received amount, outstanding balance, payment evidence, and due date: issued, due, overdue, partly paid, or received.
- Idempotent receipt recording that updates cash and outstanding balance exactly once.
- Receivable aging and customer concentration views.

### Customer intelligence

- Customer records created from imported invoice data.
- Customer name, ID, segment, email, and phone persistence.
- Observed paid-invoice count, median/mean delay, variability, and on-time share.
- Estimated 7/30/60-day payment probabilities when enough business history exists.
- Sparse-history fallback to a business/segment pool.
- Owner-provided relationship, dispute, importance, and service context.
- Collections prioritisation based on estimated cash impact, kept separate from relationship guidance.

### Expenses, supplier bills, and planning

- Recurring salary, rent, loan, tax, utilities, subscription, insurance, and other outflows.
- Supplier bill tracking, including MSME identification.
- Upcoming 7/30/90-day schedules and overdue supplier totals.
- Future monthly sales, payment terms, and uncertainty assumptions.
- Scenario planner for customer delays, unexpected expenses, supplier terms, revised payment schedules, and related what-if changes.
- Saved scenarios and ranked corrective actions for normal-sized workspaces.

### Reminders and owner alerts

- Customer reminder ladder at -3, 0, +7, +15, and +30 days relative to due date.
- Grouped reminder drafts with customer contact details and an audit history.
- SMTP email delivery with a clearly labelled mock fallback.
- Optional automatic ordinary-email delivery when `AUTO_REMINDERS=true`.
- WhatsApp and SMS click-to-send links when no server-side provider is configured.
- Legal-demand drafts remain visibly identified for specialist review.
- Owner notification center for shortage risk, stale balances, due expenses, and overdue invoices.
- Configurable risk threshold, alert horizon, snooze, read state, and test email.

### Signed mock-bank and fraud review

- HMAC-signed webhook at `POST /webhooks/bank` and `POST /api/webhooks/bank`.
- Durable event idempotency so bank retries are not processed twice.
- Invoice matching by payment reference.
- Local fraud scoring before invoice settlement.
- Approve, manual-review, and block decisions with stored score and reasons.
- Owner payment-review screen with approve/reject actions.
- This is a mock integration; no production bank or card gateway is claimed.

### Accounts and tenant isolation

- Email/password accounts with Argon2id password hashing.
- Opaque, revocable, server-side sessions and HttpOnly cookies.
- Origin and CSRF checks on mutations.
- Database-backed rate limiting for signup/login attempts.
- Every workspace query and mutation is scoped to the signed-in business.

## How the AI works

### Payment timing

The empirical model learns payment-delay distributions from the signed-in business. The optional survival model uses censored observations, so unpaid invoices are not incorrectly labelled as paid. If there is not enough usable history or model fitting fails, the app reports the fallback instead of claiming unavailable precision.

### Cash simulation

The engine samples invoice collection timing and future-sales uncertainty, applies recurring expenses and supplier bills, then calculates daily cash paths. The UI reports percentile bands and the proportion of paths that fall below the owner's safety floor.

### Fraud scoring

The mock payment flow combines rules and a local `IsolationForest` anomaly model. Its score is for demonstration only and is not validated for production fraud prevention.

### Accuracy statement

Included datasets are synthetic pipeline tests. They prove that the data and modelling paths run; they do **not** establish accuracy or calibration on representative real businesses.

## Architecture

```text
React/Vite UI
    │  /api requests, session cookie, CSRF header
    ▼
FastAPI routers ───── SQLAlchemy ───── SQLite (local) / PostgreSQL (deployment)
    │
    ├── Invoice/customer/expense/reminder services
    ├── Monte Carlo cash-flow engine (NumPy)
    ├── Payment timing models (pandas/lifelines)
    └── Mock fraud model (scikit-learn)
```

| Layer | Main technology |
| --- | --- |
| Frontend | React 19, TypeScript, Vite, Tailwind CSS, Recharts |
| API | FastAPI, Pydantic, SQLAlchemy |
| Forecasting | Python, NumPy, pandas |
| ML | lifelines, scikit-learn, joblib |
| Local storage | SQLite |
| Deployment database | PostgreSQL configuration supported |

## Quick start

### Prerequisites

- Python 3.11 or newer (Python 3.12 is used in development)
- Node.js 20 or newer
- Git

### 1. Clone the repository

```bash
git clone <repository-url>
cd CashFlow
```

All backend commands below must run from the repository root. Running Uvicorn inside `frontend/` causes `ModuleNotFoundError: No module named 'backend'`.

### 2. Create a Python environment

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r backend\requirements.txt
python -m pip install -r ml\requirements.txt
```

macOS/Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r backend/requirements.txt
python -m pip install -r ml/requirements.txt
```

### 3. Start the API

```bash
python -m uvicorn backend.main:app --reload --port 8000
```

API: `http://127.0.0.1:8000`<br>
Interactive API docs: `http://127.0.0.1:8000/docs`

### 4. Start the frontend in a second terminal

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`.

If Windows PowerShell blocks `npm.ps1`, use:

```powershell
cmd /c npm run dev
```

The Vite development server proxies `/api` to port 8000, so cookies and CSRF behavior work locally.

## First run and demo

1. Create an account. The hackathon password policy requires 5–10 characters and at least one special character.
2. Enter the business name, available cash, balance date, and safety floor.
3. Open **Invoices & cash → Import data**.
4. Use the built-in blank template, overdue sample, or the [3,000-invoice recovery dataset](sample_data/shortage_then_recovery_3000.csv).
5. For the large demo, enter the values from [its companion setup file](sample_data/shortage_then_recovery_3000_setup.json) under **Outflows & sales**.
6. Explore **Overview**, **Customers**, **Expenses & obligations**, **Cash forecast**, **Scenario planner**, and **Recommended actions**.

The large dataset contains 3,000 fictional invoices: 1,000 paid, 666 partly paid, and 1,334 unpaid. It demonstrates initial cash pressure followed by estimated cash recovery. That recovery is not an accounting-profit calculation.

## Invoice import format

Recommended columns:

```text
invoice_id,customer_id,customer_name,email,phone,segment,amount,issue_date,due_date,status,received_amount,paid_date,currency
```

Rules:

- Amounts are nonnegative whole INR.
- Dates use `YYYY-MM-DD`.
- Invoice IDs must be unique within a workspace.
- Supported customer segments are `small`, `corporate`, and `government`.
- A fully settled invoice requires a payment date; the app does not invent payment evidence.
- Common aliases such as `Invoice No`, `Voucher No`, `Party Name`, `Gross Total`, `Outstanding`, `Email Address`, and `Mobile Number` are recognized.
- The upload limit is 5 MB. The provided 3,000-row CSV fits within this limit.

## Mock-bank and fraud demo

Set a webhook secret before starting the backend:

Windows PowerShell:

```powershell
$env:BANK_WEBHOOK_SECRET = "local-mock-bank-secret"
python -m uvicorn backend.main:app --reload --port 8000
```

macOS/Linux:

```bash
export BANK_WEBHOOK_SECRET=local-mock-bank-secret
python -m uvicorn backend.main:app --reload --port 8000
```

After signing in, obtain the tenant-mapped mock merchant account from `GET /api/payments/mock-bank-account`. Post a JSON credit or debit event to `/webhooks/bank` with an `X-Signature` HMAC-SHA256 header. A runnable integration example is covered by:

```bash
python -m pytest backend/tests/test_bank_webhooks.py -q
```

Open **Payment review** in the UI to inspect stored fraud decisions and approve or reject held payments.

## Configuration

The application reads environment variables directly. [`backend/.env.example`](backend/.env.example) documents deployment settings; it is not loaded automatically.

| Variable | Purpose | Local behavior when absent |
| --- | --- | --- |
| `DATABASE_URL` | SQLAlchemy database URL | Uses ignored local SQLite database |
| `APP_ENV` | Set to `production` for deployment checks | Development behavior |
| `ALLOWED_ORIGINS` | Comma-separated allowed browser origins | Local Vite origins |
| `COOKIE_SECURE` | Require HTTPS cookies | `false` locally |
| `BANK_WEBHOOK_SECRET` | HMAC secret for bank webhook | Local mock default; set explicitly for demos/deployment |
| `MOCK_DELIVERY` | Force mock email delivery | Mock is also used when SMTP is absent |
| `AUTO_REMINDERS` | Automatically dispatch ordinary email reminders when the queue is generated | Disabled |
| `SMTP_HOST`, `SMTP_PORT` | SMTP server | No live email |
| `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM` | SMTP authentication/sender | No live email |
| `PAYMENT_MODEL_DIR` | Private model-artifact directory | Ignored local artifact directory |
| `APP_FAKE_TODAY` | Fixed date for tests/development | Current Asia/Kolkata date |

Never commit real secrets. `.env`, local databases, model artifacts, uploads, build outputs, and virtual environments are excluded by `.gitignore`.

## Testing

Run from the repository root:

```bash
python -m pytest engine/tests ml/tests backend/tests -q
python -m engine.check_contract
python shared/validate.py
```

Build the frontend:

```bash
cd frontend
npm run build
```

On Windows systems that block `npm.ps1`:

```powershell
cmd /c npm run build
```

## Project structure

| Path | Purpose |
| --- | --- |
| `backend/main.py` | FastAPI application and core HTTP endpoints |
| `backend/routers/` | Invoice, reminder, alert, forecast-view, and mock-bank routers |
| `backend/modules/` | Pure mapping, delivery, reminder, alert, accuracy, and forecast helpers |
| `backend/tests/` | API, security, persistence, import, reminder, alert, and webhook tests |
| `engine/` | Forecast, schedules, collections, scenarios, actions, and contract validation |
| `engine/tests/` | Forecast-engine tests |
| `ml/` | Payment timing, personalization, training, and evaluation code |
| `frontend/src/` | React pages, components, API client, and styles |
| `sample_data/` | Downloadable fictional invoice datasets and companion setup values |
| `examples/` | Reproducible synthetic dataset generators |
| `shared/` | Cross-layer contracts, samples, and validation utilities |
| `docs/FEATURE_STATUS.md` | Feature-by-feature status and quick test instructions |

## Important API groups

| Route | Purpose |
| --- | --- |
| `/api/auth/*` | Signup, login, session status, logout |
| `/api/invoices/*` | Preview, append, edit, delete, and mark-paid operations |
| `/api/ledger`, `/api/receipts` | Ledger view and receipt recording |
| `/api/forecast`, `/api/forecast/view` | Raw and UI-ready forecasts |
| `/api/customers`, `/api/collections` | Customer behavior and collection ranking |
| `/api/plan`, `/api/expenses` | Outflows, supplier bills, sales plan, and expense dashboard |
| `/api/scenario`, `/api/scenarios` | What-if comparison and saved scenarios |
| `/api/reminders/*` | Reminder queue, settings, delivery, and history |
| `/api/alerts/*` | Owner alerts and preferences |
| `/webhooks/bank`, `/api/admin/payments` | Signed mock-bank events and payment review |

## Limitations

- Forecasts are estimates and have not been validated on representative real businesses.
- The application does not file GST/TDS/ITR, maintain statutory books, perform audits, or provide legal advice.
- The payment and bank integrations are mocks, not production Account Aggregator, bank, Razorpay, Stripe, or card connections.
- Text PDF extraction is rule-based; scanned/image-only PDFs require a separate OCR integration.
- Live email needs SMTP credentials. Automatic SMS and WhatsApp delivery need an external provider and consent workflow.
- The 3,000-row demo uses 25 Monte Carlo simulations for responsiveness; smaller workspaces use more paths.
- PostgreSQL configuration is supported, but public production hosting, monitoring, migrations, backups, email verification, password recovery, subscriptions, and organization roles need further work.

## Responsible-use note

CashFlow is designed as a decision-support prototype. Owners should reconcile cash with actual bank records, verify imported information, and consult qualified professionals for accounting, tax, lending, or legal decisions.
