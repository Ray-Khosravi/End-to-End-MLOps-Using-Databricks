# Phase 5 — Backend (FastAPI)

> **Goal:** Build a FastAPI service that loads the registered MLflow model and exposes `/predict`, `/health`, `/metrics`, and `/model-info`.

---

## 5.1 Architecture

```mermaid
flowchart LR
    Client[Browser / curl] -->|POST /predict<br/>{features}| API[FastAPI]
    API -->|first request| MLflow[Databricks<br/>MLflow Registry]
    MLflow -.->|download<br/>once| API
    API -->|cached| Model[(In-memory<br/>model)]
    API --> Resp[{prediction, probability,<br/>model_version}]
    API -->|/metrics| Prom[Prometheus<br/>scraper]
```

Key design decisions:
- **Load model once at startup** (FastAPI's `lifespan` hook).
- **Expose Prometheus metrics** on `/metrics`.
- **Structured JSON logging** via `structlog`.
- **Pydantic schemas** for input/output validation.
- **Health & readiness endpoints** separately (`/health` for liveness, `/ready` for readiness).

---

## 5.2 Project Layout

```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py             ← FastAPI app, routes
│   ├── model_loader.py     ← Loads the MLflow model
│   ├── schemas.py          ← Pydantic input/output models
│   └── settings.py         ← Reads env vars
├── tests/
│   └── test_main.py        ← Pytest tests
├── requirements.txt
└── Dockerfile
```

---

## 5.3 Environment Variables

The backend reads these at startup (set them via Kubernetes secrets in prod, or `.env` locally):

| Variable | Required | Default | What |
|---|---|---|---|
| `MLFLOW_TRACKING_URI` | ✅ | — | `databricks` (uses Databricks-hosted MLflow) |
| `MLFLOW_REGISTRY_URI` | ✅ | — | `databricks-uc` (Unity Catalog) |
| `MODEL_NAME` | ✅ | — | `churn_mlops.models.churn_classifier` |
| `MODEL_ALIAS` | ✅ | `production` | Which alias to load |
| `DATABRICKS_HOST` | ✅ | — | `https://dbc-xxx.cloud.databricks.com` |
| `DATABRICKS_TOKEN` | ✅ | — | PAT or service-principal token |
| `LOG_LEVEL` | — | `INFO` | |

In local dev:
```bash
cd backend
cp .env.example .env
# edit .env with your values
export $(grep -v '^#' .env | xargs)
uvicorn app.main:app --reload --port 8000
```

---

## 5.4 Try It Out Locally

```bash
# Health check
curl http://localhost:8000/health
# {"status":"ok"}

# Model info (proves the model loaded)
curl http://localhost:8000/model-info
# {"name":"churn_mlops.models.churn_classifier","version":"5","alias":"production"}

# A prediction
curl -X POST http://localhost:8000/predict \
  -H 'Content-Type: application/json' \
  -d '{
    "tenure_months": 12,
    "monthly_charges": 75.50,
    "total_charges": 906.00,
    "senior_citizen": 0,
    "partner": 1,
    "dependents": 0,
    "phone_service": 1,
    "paperless_billing": 1,
    "gender_male": 0,
    "is_long_tenure": 0,
    "is_high_spender": 1,
    "avg_charge_per_month": 75.50,
    "internet_service_dsl": 0,
    "internet_service_fiber_optic": 1,
    "internet_service_no": 0,
    "contract_type_month_to_month": 1,
    "contract_type_one_year": 0,
    "contract_type_two_year": 0,
    "payment_method_electronic_check": 1,
    "payment_method_mailed_check": 0,
    "payment_method_bank_transfer": 0,
    "payment_method_credit_card": 0
  }'
# {"prediction":1,"probability":0.73,"model_version":"5"}

# Prometheus metrics
curl http://localhost:8000/metrics | head -20
```

---

## 5.5 Tests

`tests/test_main.py` covers:
- `/health` returns 200
- `/predict` rejects invalid payloads (Pydantic validation)
- `/predict` returns the right shape when given valid input
- The MLflow loader is mocked so tests don't need Databricks

```bash
cd backend
pip install -r requirements.txt pytest
pytest -v
```

---

## 5.6 Production Considerations (already wired in)

✅ **Liveness vs Readiness** — k8s uses `/health` for liveness (am I alive?) and `/ready` for readiness (am I ready to take traffic? Has the model loaded?).
✅ **Structured logs** — every request emits a JSON line with `request_id`, `latency_ms`, `status`.
✅ **CORS** — relaxed in dev, restricted in prod via env var.
✅ **Graceful shutdown** — `lifespan` hook ensures clean termination.
✅ **Prometheus metrics** — `request_count`, `request_latency_seconds`, `model_predictions_total`.

---

## ✅ Phase 5 Checklist

- [ ] `pip install -r requirements.txt` succeeds
- [ ] `uvicorn app.main:app --reload` starts
- [ ] `/health` returns 200
- [ ] `/predict` returns a sensible prediction
- [ ] `/metrics` shows Prometheus output
- [ ] `pytest` passes

**Next:** [`06-frontend.md`](06-frontend.md) →
