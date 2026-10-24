import json
from functools import lru_cache
from pathlib import Path
from typing import Literal, Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel


FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"


@lru_cache(maxsize=1)
def load_fixture(name: str):
    with (FIXTURES_DIR / name).open(encoding="utf-8") as fixture_file:
        return json.load(fixture_file)


class ScenarioChange(BaseModel):
    type: Literal[
        "delay_customer", "sales_change", "extra_expense", "supplier_terms"
    ]
    customer_id: Optional[str] = None
    extra_days: Optional[int] = None
    pct: Optional[float] = None
    amount: Optional[int] = None
    date: Optional[str] = None


class Scenario(BaseModel):
    name: str
    changes: list[ScenarioChange]


def load_engine():
    from engine import (
        compare_scenario,
        generate_business,
        rank_actions,
        run_forecast,
    )

    return generate_business, run_forecast, compare_scenario, rank_actions


@lru_cache(maxsize=1)
def engine_business():
    generate_business, _, _, _ = load_engine()
    return generate_business()


def fixture_response(payload, source="fixture"):
    return JSONResponse(content=payload, headers={"X-Source": source})


def forecast_for_scenario(baseline, scenario):
    result = json.loads(json.dumps(baseline))
    balance_change = 0
    for change in scenario.changes:
        if change.type == "sales_change":
            balance_change += int(1400000 * (change.pct or 0) / 100)
        elif change.type == "extra_expense":
            balance_change -= change.amount or 0
        elif change.type == "delay_customer":
            balance_change -= 100000
        elif change.type == "supplier_terms":
            balance_change -= 50000

    change_date = min(20, len(result["dates"]) - 1)
    for index in range(change_date, len(result["dates"])):
        result["p10"][index] += balance_change
        result["p50"][index] += balance_change
        result["p90"][index] += balance_change

    under_floor = [
        index for index, balance in enumerate(result["p50"])
        if balance < result["safety_floor"]
    ]
    result["first_shortage_date"] = (
        result["dates"][under_floor[0]] if under_floor else None
    )
    result["min_balance_p50"] = min(result["p50"])
    result["shortage_prob"] = min(
        1.0, result["shortage_prob"] + min(0.25, abs(balance_change) / 1000000)
    )
    return result


app = FastAPI(title="CashFlow API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Source"],
)


@app.get("/api/business")
def get_business():
    try:
        return fixture_response(engine_business(), "engine")
    except Exception:
        return fixture_response(load_fixture("business.json"))


@app.get("/api/forecast")
def get_forecast():
    try:
        _, run_forecast, _, _ = load_engine()
        return fixture_response(run_forecast(engine_business()), "engine")
    except Exception:
        return fixture_response(load_fixture("forecast.json"))


@app.post("/api/scenario")
def post_scenario(scenario: Scenario):
    try:
        _, _, compare_scenario, _ = load_engine()
        return fixture_response(
            compare_scenario(engine_business(), scenario.dict()), "engine"
        )
    except Exception:
        baseline = load_fixture("forecast.json")
        return fixture_response(
            {
                "baseline": baseline,
                "scenario": forecast_for_scenario(baseline, scenario),
            }
        )


@app.get("/api/actions")
def get_actions():
    try:
        _, _, _, rank_actions = load_engine()
        return fixture_response(rank_actions(engine_business()), "engine")
    except Exception:
        return fixture_response(load_fixture("actions.json"))
