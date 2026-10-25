"""Contract validation utility for CashFlow.

Usage:
    python shared/validate.py
        Validates all sample files in shared/samples/ against their schema models.

    python shared/validate.py --live http://localhost:8000 --cookie "session_id=xyz"
        Calls live API endpoints and verifies their JSON responses against schema models,
        reporting exact field paths and error messages on mismatches.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Type

from pydantic import TypeAdapter, ValidationError

# Add repository root to path
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from shared.schema import (
    ActionCard,
    Alert,
    Customer,
    ForecastView,
    Invoice,
    InvoiceForecast,
    ProposedMatch,
    ProposedObligation,
    Reminder,
    Transaction,
    WhyItem,
)

SAMPLE_MODEL_MAP: dict[str, Type[Any]] = {
    "invoice.json": Invoice,
    "customer.json": Customer,
    "transaction.json": Transaction,
    "proposed_obligation.json": ProposedObligation,
    "proposed_match.json": ProposedMatch,
    "forecast_view.json": ForecastView,
    "why_item.json": WhyItem,
    "invoice_forecast.json": InvoiceForecast,
    "alert.json": Alert,
    "action_card.json": ActionCard,
    "reminder.json": Reminder,
}

LIVE_ENDPOINTS: list[tuple[str, Any]] = [
    ("/api/forecast/view", ForecastView),
    ("/api/alerts", list[Alert]),
    ("/api/reminders/queue", list[Reminder]),
    ("/api/actions/cards", list[ActionCard]),
    ("/api/invoices", list[Invoice]),
    ("/api/customers", list[Customer]),
    ("/api/transactions", list[Transaction]),
]


def format_validation_error(err: ValidationError) -> list[str]:
    lines = []
    for error in err.errors():
        loc = " -> ".join(str(item) for item in error.get("loc", []))
        msg = error.get("msg", "Validation error")
        err_type = error.get("type", "unknown")
        lines.append(f"    Field: '{loc}' | Error: {msg} (type: {err_type})")
    return lines


def validate_samples(samples_dir: Path) -> bool:
    print(f"--- Validating Samples in {samples_dir} ---")
    if not samples_dir.exists():
        print(f"[FAIL] Samples directory does not exist: {samples_dir}")
        return False

    all_passed = True
    for filename, model_cls in SAMPLE_MODEL_MAP.items():
        sample_path = samples_dir / filename
        if not sample_path.exists():
            print(f"[FAIL] Missing sample file: {filename}")
            all_passed = False
            continue

        try:
            with open(sample_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            model_cls.model_validate(data)
            print(f"[PASS] {filename:<25} -> {model_cls.__name__}")
        except ValidationError as err:
            all_passed = False
            print(f"[FAIL] {filename:<25} schema mismatch:")
            for line in format_validation_error(err):
                print(line)
        except json.JSONDecodeError as err:
            all_passed = False
            print(f"[FAIL] {filename:<25} invalid JSON: {err}")

    return all_passed


def validate_live(base_url: str, cookie: str | None = None) -> bool:
    print(f"--- Validating Live API Endpoints at {base_url} ---")
    base_url = base_url.rstrip("/")
    all_passed = True

    for endpoint, target_type in LIVE_ENDPOINTS:
        url = f"{base_url}{endpoint}"
        req = urllib.request.Request(url)
        if cookie:
            req.add_header("Cookie", cookie)

        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                status = resp.status
                body = resp.read().decode("utf-8")
                data = json.loads(body)

            adapter = TypeAdapter(target_type)
            adapter.validate_python(data)
            type_name = getattr(target_type, "__name__", str(target_type))
            print(f"[PASS] {endpoint:<25} (HTTP {status}) -> {type_name}")

        except urllib.error.HTTPError as http_err:
            all_passed = False
            body_snippet = http_err.read().decode("utf-8", errors="ignore")[:200]
            print(f"[FAIL] {endpoint:<25} HTTP {http_err.code}: {http_err.reason} ({body_snippet})")
        except urllib.error.URLError as url_err:
            all_passed = False
            print(f"[FAIL] {endpoint:<25} Network error: {url_err.reason}")
        except ValidationError as val_err:
            all_passed = False
            print(f"[FAIL] {endpoint:<25} Schema mismatch:")
            for line in format_validation_error(val_err):
                print(line)
        except json.JSONDecodeError as json_err:
            all_passed = False
            print(f"[FAIL] {endpoint:<25} Response is not valid JSON: {json_err}")
        except Exception as ex:
            all_passed = False
            print(f"[FAIL] {endpoint:<25} Unexpected error: {ex}")

    return all_passed


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate contract samples and live API endpoints.")
    parser.add_argument("--samples-dir", type=Path, default=Path(__file__).parent / "samples",
                        help="Path to sample files directory")
    parser.add_argument("--live", type=str, default=None,
                        help="Base URL of live API (e.g. http://localhost:8000)")
    parser.add_argument("--cookie", type=str, default=None,
                        help="Session cookie for live requests (e.g. 'session=xyz')")

    args = parser.parse_args()

    samples_ok = validate_samples(args.samples_dir)

    live_ok = True
    if args.live:
        live_ok = validate_live(args.live, args.cookie)

    if samples_ok and live_ok:
        print("\nAll contract checks PASSED.")
        sys.exit(0)
    else:
        print("\nContract validation FAILED.")
        sys.exit(1)


if __name__ == "__main__":
    main()
