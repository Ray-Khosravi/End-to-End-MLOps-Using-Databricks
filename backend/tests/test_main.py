"""
Tests for the FastAPI churn service.

We set MOCK_MODEL=true in the test fixture so we don't need a Databricks
token at test time.
"""

import os
os.environ["MOCK_MODEL"] = "true"

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    # Using `with TestClient(app)` triggers FastAPI lifespan hooks
    with TestClient(app) as c:
        yield c


def _valid_payload(**overrides):
    base = {
        "tenure_months": 12,
        "monthly_charges": 75.50,
        "total_charges": 906.00,
        "avg_charge_per_month": 75.50,
        "senior_citizen": 0,
        "partner": 1,
        "dependents": 0,
        "phone_service": 1,
        "paperless_billing": 1,
        "gender_male": 0,
        "is_long_tenure": 0,
        "is_high_spender": 1,
        "internet_service_dsl": 0,
        "internet_service_fiber_optic": 1,
        "internet_service_no": 0,
        "contract_type_month_to_month": 1,
        "contract_type_one_year": 0,
        "contract_type_two_year": 0,
        "payment_method_electronic_check": 1,
        "payment_method_mailed_check": 0,
        "payment_method_bank_transfer": 0,
        "payment_method_credit_card": 0,
    }
    base.update(overrides)
    return base


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_ready_after_startup(client):
    r = client.get("/ready")
    assert r.status_code == 200
    assert r.json()["ready"] is True
    assert r.json()["model_loaded"] is True


def test_model_info(client):
    r = client.get("/model-info")
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == "mock"
    assert "version" in body


def test_predict_valid(client):
    r = client.post("/predict", json=_valid_payload())
    assert r.status_code == 200
    body = r.json()
    assert body["prediction"] in (0, 1)
    assert 0.0 <= body["probability"] <= 1.0
    assert "model_version" in body
    assert "request_id" in body


def test_predict_high_churn_rule(client):
    """Mock predictor says: month-to-month + short tenure → churn = 1."""
    payload = _valid_payload(
        tenure_months=2,
        contract_type_month_to_month=1,
        contract_type_one_year=0,
        contract_type_two_year=0,
    )
    r = client.post("/predict", json=payload)
    assert r.status_code == 200
    assert r.json()["prediction"] == 1


def test_predict_invalid_payload_missing_field(client):
    payload = _valid_payload()
    del payload["tenure_months"]
    r = client.post("/predict", json=payload)
    assert r.status_code == 422        # Pydantic validation error


def test_predict_invalid_payload_wrong_type(client):
    payload = _valid_payload(senior_citizen=2)  # Literal[0,1] only
    r = client.post("/predict", json=payload)
    assert r.status_code == 422


def test_metrics_endpoint(client):
    # Hit /predict once so we have non-zero counters
    client.post("/predict", json=_valid_payload())

    r = client.get("/metrics")
    assert r.status_code == 200
    text = r.text
    assert "http_requests_total" in text
    assert "model_predictions_total" in text


def test_request_id_round_trip(client):
    rid = "req_custom_test_001"
    r = client.get("/health", headers={"X-Request-Id": rid})
    assert r.headers.get("X-Request-Id") == rid
