"""
backend/tests/test_forecast_api.py
Tests verifying GET /api/forecast warnings and invariant properties:
- Empty obligations returns warnings
- Forecast arrays have 90 points (dates, p10, p50, p90)
- Percentiles ordering: p10 <= p50 <= p90
"""

import pytest
from backend.tests.test_ledger_api import payload


def test_empty_obligations_returns_warnings(client):
    # 1. Workspace imported with no obligations and no future sales plan
    import_res = client.post("/api/import", json=payload())
    assert import_res.status_code == 200, import_res.text

    response = client.get("/api/forecast")
    assert response.status_code == 200, response.text
    data = response.json()

    assert "warnings" in data
    assert isinstance(data["warnings"], list)
    assert len(data["warnings"]) > 0
    assert "No expenses entered: forecast only shows invoice receipts" in data["warnings"]

    # 2. Add an obligation to the plan; warnings should now be cleared
    plan_res = client.post(
        "/api/plan",
        json={
            "obligations": [
                {
                    "id": "O1",
                    "name": "Office Rent",
                    "amount": 25000,
                    "day_of_month": 5,
                    "frequency": "monthly",
                    "category": "rent",
                }
            ],
            "supplier_bills": [],
            "monthly_sales": 0,
            "terms_days": 30,
            "monthly_noise_pct": 0,
        },
    )
    assert plan_res.status_code == 200, plan_res.text

    response_updated = client.get("/api/forecast")
    assert response_updated.status_code == 200
    data_updated = response_updated.json()
    assert data_updated["warnings"] == []


def test_forecast_arrays_have_90_points(client):
    client.post("/api/import", json=payload())
    response = client.get("/api/forecast")
    assert response.status_code == 200
    data = response.json()

    assert len(data["dates"]) == 90
    assert len(data["p10"]) == 90
    assert len(data["p50"]) == 90
    assert len(data["p90"]) == 90


def test_forecast_percentiles_order(client):
    client.post("/api/import", json=payload())
    response = client.get("/api/forecast")
    assert response.status_code == 200
    data = response.json()

    p10 = data["p10"]
    p50 = data["p50"]
    p90 = data["p90"]

    for i in range(90):
        assert (
            p10[i] <= p50[i] <= p90[i]
        ), f"Percentile ordering violated at day {i}: p10={p10[i]}, p50={p50[i]}, p90={p90[i]}"
