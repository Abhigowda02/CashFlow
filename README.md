# CashFlow — AI-Powered Cash-Flow Copilot for Indian Small Businesses

CashFlow helps small businesses that invoice on credit understand **when cash may run short**, why it may happen, and which receivables need attention. It is a hackathon prototype built for invoice-driven businesses, not an accounting, tax, audit, or legal product.

## Hackathon submission

### AI disclosure

This project was built with AI-assisted engineering and includes local AI/ML components:

- Payment-timing forecasting from invoice and customer payment history.
- A survival-model option for business-specific payment-date estimates, with an empirical fallback.
- Monte Carlo cash-flow simulation with shortage probability and uncertainty bands.
- Local anomaly-based fraud scoring for mock-bank payment events.

No external generative-AI API is required at runtime. All forecasting and fraud scoring run locally in the Python application. Forecasts are estimates, not guarantees or financial advice.

### What it demonstrates

- Import invoices from CSV, including common Tally/Zoho-style header variants.
- Automatically append valid imported invoices to the main ledger; duplicate or invalid rows are skipped with an explanation.
- Detect invoice state from outstanding balance, received amount, payment date, and due date: issued, due, overdue, partly paid, or received.
- Save customer name, segment, email, and phone number from invoice imports.
- Forecast 90-day cash position, downside/upside bands, shortage probability, and likely drivers.
- Show customer payment behaviour and collections priorities.
- Manage recurring outflows, supplier bills, and future-sales assumptions.
- Generate reminders and send ordinary email reminders automatically when enabled; SMTP has a clearly labelled mock fallback.
- Receive signed, idempotent mock-bank webhooks, score payment fraud, hold suspicious payments for review, and show payment-review records.

## Architecture

| Layer | Technology | Role |
| --- | --- | --- |
| Frontend | React, Vite, TypeScript, Tailwind, Recharts | Cash dashboard, invoice ledger, import, forecast, reminders and payment review |
| API | FastAPI, Pydantic, SQLAlchemy | Tenant-scoped business data, authentication, imports, forecast and webhook APIs |
| Forecast engine | Python, NumPy | Monte Carlo cash-flow simulation and scenario analysis |
| ML | pandas, scikit-learn, lifelines | Payment timing / survival modelling and local fraud anomaly scoring |
| Storage | SQLite locally; PostgreSQL configuration supported | User, workspace, receipt, reminder, payment-review and webhook-event data |

## Quick start (Windows / PowerShell)

Prerequisites: Python 3.11+ and Node.js 20+.

Open **two terminals**.

### Terminal 1 — backend

Run from the repository root, not from `frontend`:

```powershell
cd C:\Users\abhig\Desktop\CashFlow
python -m pip install -r backend\requirements.txt
python -m pip install -r ml\requirements.txt
python -m uvicorn backend.main:app --reload --port 8000
```

The API starts at `http://127.0.0.1:8000`.

### Terminal 2 — frontend

```powershell
cd C:\Users\abhig\Desktop\CashFlow\frontend
npm install
cmd /c npm run dev
```

Open `http://localhost:5173`.

`cmd /c` is useful on Windows machines that block PowerShell's `npm.ps1` execution policy.

## Environment settings

Copy the documented values from [`backend/.env.example`](backend/.env.example) into your shell or deployment environment. The example file is documentation only; it is not automatically loaded.

Useful local demo settings:

```powershell
$env:MOCK_DELIVERY = "true"
$env:AUTO_REMINDERS = "true"
$env:BANK_WEBHOOK_SECRET = "local-mock-bank-secret"
python -m uvicorn backend.main:app --reload --port 8000
```

With no SMTP configuration, email delivery returns a clearly labelled mock result. Real email requires `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, and `SMTP_FROM`.

## Hackathon demo flow

1. Sign up and complete the business setup.
2. Open **Invoices & cash → Import data**.
3. Download and import [the 3,000-invoice shortage/recovery dataset](sample_data/shortage_then_recovery_3000.csv).
4. Open [the companion setup values](sample_data/shortage_then_recovery_3000_setup.json) and enter its cash, safety floor, recurring expenses, and future-sales values in **Outflows & sales**.
5. Open **Cash forecast** to demonstrate an estimated initial shortage and later cash recovery.
6. Open **Customers** to show payment behaviour and collection priorities.
7. Open **Payment review** to show the signed mock-bank and fraud-review workflow.

The large dataset contains 3,000 fictional invoices: 1,000 paid, 666 partly paid, and 1,334 unpaid. Large workspaces use 25 Monte Carlo simulations to remain responsive; the reported simulation count is included in forecast metadata. The scenario demonstrates cash-flow recovery, not accounting profit.

## Invoice import format

Download the template from the Import page or provide standard invoice columns. The importer recognizes common header variants such as `Invoice No`, `Party Name`, `Invoice Date`, `Due Date`, `Invoice Amount`, `Outstanding`, `Email Address`, and `Mobile Number`.

Recommended columns:

```text
invoice_id,customer_id,customer_name,email,phone,segment,amount,issue_date,due_date,received_amount,paid_date,currency
```

- Money is whole INR.
- Dates use `YYYY-MM-DD`.
- Customer contact values are saved with the customer record.
- Invoice state is inferred from balances, received amounts, payment dates, and due dates.
- A fully settled invoice needs a payment date; the app does not invent payment evidence.

## Mock-bank and fraud flow

The app exposes a signed mock-bank webhook at `POST /webhooks/bank` (and an `/api` alias). It verifies the HMAC signature, prevents duplicate event processing, matches credits to invoice references, and runs fraud scoring before settlement:

- `approve`: record the receipt and mark the invoice paid.
- `review`: hold the payment and allow an owner to approve or reject it in **Payment review**.
- `block`: keep the invoice unpaid and record the fraud decision/reasons.

This is a local mock integration, not a production bank or payment gateway connection.

## Tests and build

From the repository root:

```powershell
python -m pytest engine/tests ml/tests backend/tests -q
python -m engine.check_contract
cd frontend
cmd /c npm run build
```

## Repository map

| Path | Purpose |
| --- | --- |
| `frontend/` | React application |
| `backend/` | FastAPI application, tenant data, imports, reminders and webhooks |
| `engine/` | Cash-flow simulation and action logic |
| `ml/` | Payment-timing models and evaluation utilities |
| `sample_data/` | Fictional invoice datasets and setup values |
| `examples/` | Deterministic dataset generators |
| `docs/FEATURE_STATUS.md` | Feature status and quick test paths |

## Limitations and responsible use

- The app estimates cash flow; it does not replace an accountant or provide GST/TDS/ITR, audit, or legal advice.
- The included datasets are fictional and do not prove predictive accuracy on real businesses.
- Payment fraud and bank-webhook flows are mock integrations only.
- Automatic reminder delivery depends on configured SMTP; phone and WhatsApp delivery require a real provider integration.
- Review the deployment/security settings in `backend/.env.example` before any production use.
