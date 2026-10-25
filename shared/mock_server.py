"""Mock server serving contract sample JSON for standalone frontend development.

Run with:
    python shared/mock_server.py
or:
    uvicorn shared.mock_server:app --port 8001 --reload
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

SAMPLES_DIR = Path(__file__).resolve().parent / "samples"

app = FastAPI(
    title="CashFlow Mock Contract Server",
    description="Serves frozen contract models and samples for frontend decoupling",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def load_sample(filename: str) -> Any:
    file_path = SAMPLES_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"Sample {filename} not found")
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


@app.get("/api/state")
def get_state() -> dict[str, Any]:
    return {
        "business_id": "b-mock-01",
        "name": "Apex Enterprises (Mock)",
        "as_of": "2026-10-24",
        "cash_balance": 450000,
        "cash_updated_on": "2026-10-24T18:30:00Z",
        "safety_floor": 100000,
        "stale": False,
        "open_invoices_count": 8,
        "unresolved_alerts_count": 1,
        "pending_actions_count": 1,
    }


@app.get("/api/forecast/view")
def get_forecast_view() -> dict[str, Any]:
    return load_sample("forecast_view.json")


@app.get("/api/forecast/backtest")
def get_forecast_backtest() -> dict[str, Any]:
    return {
        "mape": 0.082,
        "median_abs_error_days": 4.5,
        "p10_p90_coverage": 0.81,
        "backtest_dataset": "public_sample",
        "n_invoices_evaluated": 2500,
        "evaluated_at": "2026-10-24T00:00:00Z",
        "caveats": "Evaluated on historical MSME trade credit dataset.",
    }


@app.get("/api/invoices")
def get_invoices() -> list[dict[str, Any]]:
    return [load_sample("invoice.json")]


@app.post("/api/invoices")
def create_invoice(invoice: dict[str, Any]) -> dict[str, Any]:
    return invoice


@app.get("/api/customers")
def get_customers() -> list[dict[str, Any]]:
    return [load_sample("customer.json")]


@app.get("/api/alerts")
def get_alerts() -> list[dict[str, Any]]:
    return [load_sample("alert.json")]


@app.post("/api/alerts/{alert_id}/read")
def mark_alert_read(alert_id: str) -> dict[str, Any]:
    alert = load_sample("alert.json")
    alert["id"] = alert_id
    alert["read"] = True
    return {"status": "ok", "alert": alert}


@app.get("/api/reminders/queue")
def get_reminders() -> list[dict[str, Any]]:
    return [load_sample("reminder.json")]


@app.post("/api/reminders/{reminder_id}/approve")
def approve_reminder(reminder_id: str) -> dict[str, Any]:
    reminder = load_sample("reminder.json")
    reminder["id"] = reminder_id
    reminder["status"] = "approved"
    return reminder


@app.post("/api/reminders/{reminder_id}/send")
def send_reminder(reminder_id: str) -> dict[str, Any]:
    reminder = load_sample("reminder.json")
    reminder["id"] = reminder_id
    reminder["status"] = "sent"
    reminder["sent_at"] = "2026-10-25T11:00:00Z"
    return reminder


@app.get("/api/actions/cards")
def get_actions() -> list[dict[str, Any]]:
    return [load_sample("action_card.json")]


@app.post("/api/actions/{action_id}/execute")
def execute_action(action_id: str) -> dict[str, Any]:
    action = load_sample("action_card.json")
    return {
        "status": "executed",
        "action_id": action_id,
        "effect": action["effect"],
    }


@app.get("/api/transactions")
def get_transactions() -> list[dict[str, Any]]:
    return [load_sample("transaction.json")]


@app.post("/api/transactions/import")
def import_transactions() -> dict[str, Any]:
    return {
        "imported_count": 1,
        "transactions": [load_sample("transaction.json")],
    }


@app.get("/api/transactions/proposed-obligations")
def get_proposed_obligations() -> list[dict[str, Any]]:
    return [load_sample("proposed_obligation.json")]


@app.get("/api/transactions/proposed-matches")
def get_proposed_matches() -> list[dict[str, Any]]:
    return [load_sample("proposed_match.json")]


@app.post("/api/connect/bank")
def connect_bank() -> dict[str, Any]:
    return {
        "status": "connected",
        "accounts": 1,
        "consent_id": "CONSENT-MOCK-9912",
    }


@app.post("/api/connect/sms")
def connect_sms() -> dict[str, Any]:
    return {
        "status": "parsed",
        "transactions": [load_sample("transaction.json")],
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8001)
