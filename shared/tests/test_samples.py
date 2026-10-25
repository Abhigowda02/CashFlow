"""Unit tests verifying sample files against shared contract models."""

import json
from pathlib import Path
import pytest

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
from shared.validate import SAMPLE_MODEL_MAP, validate_samples

SAMPLES_DIR = Path(__file__).resolve().parent.parent / "samples"


def test_all_sample_files_exist_and_validate():
    """Verify that all mapped sample files exist and pass schema validation."""
    assert validate_samples(SAMPLES_DIR) is True


@pytest.mark.parametrize("filename,model_cls", list(SAMPLE_MODEL_MAP.items()))
def test_individual_sample_file(filename, model_cls):
    """Test each sample file individually with model validation."""
    path = SAMPLES_DIR / filename
    assert path.exists(), f"Sample file {filename} does not exist"
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    instance = model_cls.model_validate(data)
    assert instance is not None


def test_forecast_view_contract_guarantees():
    """Verify 90-day forecast view specific contract rules."""
    path = SAMPLES_DIR / "forecast_view.json"
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    view = ForecastView.model_validate(data)

    assert len(view.dates) == 90
    assert len(view.p10) == 90
    assert len(view.p50) == 90
    assert len(view.p90) == 90
    assert 0.0 <= view.shortage_prob <= 1.0

    for i in range(90):
        assert view.p10[i] <= view.p50[i] <= view.p90[i], f"Percentile order violated on day {i}"

    assert len(view.why) >= 1
    assert isinstance(view.warnings, list)


def test_indian_business_context_in_samples():
    """Verify realistic Indian business names and lakh INR amounts."""
    # Invoice
    with open(SAMPLES_DIR / "invoice.json", "r", encoding="utf-8") as f:
        inv = Invoice.model_validate(json.load(f))
    assert inv.amount >= 100000
    assert "Patel" in (inv.customer_name or "") or "Textiles" in (inv.customer_name or "")

    # Customer
    with open(SAMPLES_DIR / "customer.json", "r", encoding="utf-8") as f:
        cust = Customer.model_validate(json.load(f))
    assert cust.gstin is not None
    assert len(cust.gstin) == 15

    # Transaction
    with open(SAMPLES_DIR / "transaction.json", "r", encoding="utf-8") as f:
        txn = Transaction.model_validate(json.load(f))
    assert txn.amount >= 100000
    assert "HDFC" in txn.description or "NEFT" in txn.description


def test_mock_server_routes():
    """Verify that mock_server responds on contract endpoints with valid models."""
    from fastapi.testclient import TestClient
    from shared.mock_server import app
    from shared.validate import LIVE_ENDPOINTS
    from pydantic import TypeAdapter

    client = TestClient(app)
    for endpoint, model_type in LIVE_ENDPOINTS:
        resp = client.get(endpoint)
        assert resp.status_code == 200, f"Endpoint {endpoint} failed: {resp.text}"
        data = resp.json()
        adapter = TypeAdapter(model_type)
        validated = adapter.validate_python(data)
        assert validated is not None

