"""
Loads the registered MLflow model from Databricks Unity Catalog.

The model is loaded ONCE at app startup (via FastAPI's lifespan hook) and
cached in process memory. Each request just calls `.predict()` against the
already-loaded object — no I/O per request.

In MOCK_MODEL mode, we return a deterministic dummy predictor for tests.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Protocol

import pandas as pd
import structlog

from .settings import settings

log = structlog.get_logger("model_loader")


# ─────────────────────────────────────────────────────────────────────────
# Protocol the rest of the app codes against
# ─────────────────────────────────────────────────────────────────────────
class PredictorProtocol(Protocol):
    name: str
    version: str
    alias: str
    flavor: str

    def predict(self, features: dict) -> tuple[int, float]:
        """Return (predicted_class, probability_of_positive_class)."""
        ...


# ─────────────────────────────────────────────────────────────────────────
# Mock predictor — used in tests or when MOCK_MODEL=true
# ─────────────────────────────────────────────────────────────────────────
@dataclass
class MockPredictor:
    name:    str = "mock"
    version: str = "0"
    alias:   str = "mock"
    flavor:  str = "mock"

    def predict(self, features: dict) -> tuple[int, float]:
        # Toy rule: high churn risk if month-to-month + short tenure
        is_m2m = features.get("contract_type_month_to_month", 0)
        short  = features.get("tenure_months", 99) < 12
        if is_m2m and short:
            return 1, 0.85
        return 0, 0.15


# ─────────────────────────────────────────────────────────────────────────
# Real MLflow predictor
# ─────────────────────────────────────────────────────────────────────────
class MlflowPredictor:
    def __init__(self):
        import mlflow

        # Configure tracking + registry endpoints
        mlflow.set_tracking_uri(settings.mlflow_tracking_uri)
        mlflow.set_registry_uri(settings.mlflow_registry_uri)

        # Databricks PAT auth uses these env vars
        if settings.databricks_host:
            os.environ["DATABRICKS_HOST"]  = settings.databricks_host
        if settings.databricks_token:
            os.environ["DATABRICKS_TOKEN"] = settings.databricks_token

        self.name   = settings.model_name
        self.alias  = settings.model_alias

        model_uri = f"models:/{self.name}@{self.alias}"
        log.info("loading_model", uri=model_uri)
        self.model = mlflow.pyfunc.load_model(model_uri)

        # Pull metadata
        meta = self.model.metadata
        self.flavor = list(meta.flavors.keys())[0] if meta.flavors else "unknown"

        # Resolve which version this alias points to
        from mlflow.tracking import MlflowClient
        client = MlflowClient()
        mv = client.get_model_version_by_alias(self.name, self.alias)
        self.version = mv.version

        log.info("model_loaded",
                 name=self.name, version=self.version, alias=self.alias,
                 flavor=self.flavor)

    def predict(self, features: dict) -> tuple[int, float]:
        df = pd.DataFrame([features])
        # MLflow pyfunc models return either a numpy array or Series of preds.
        raw = self.model.predict(df)
        try:
            value = raw[0]
        except (IndexError, TypeError):
            value = raw

        # Some pyfunc models return probabilities, some return class labels.
        # We treat the value as the probability when it's in [0, 1] and not
        # exactly 0 or 1; otherwise treat it as the class label.
        if isinstance(value, (float,)) and 0.0 < value < 1.0:
            prob = float(value)
            pred = int(prob >= 0.5)
        else:
            pred = int(value)
            prob = float(pred)        # 0.0 or 1.0 — we don't have a real prob

        return pred, prob


# ─────────────────────────────────────────────────────────────────────────
# Public factory
# ─────────────────────────────────────────────────────────────────────────
def load_predictor() -> PredictorProtocol:
    """Build the predictor based on settings."""
    if settings.mock_model:
        log.info("mock_model_enabled")
        return MockPredictor()
    return MlflowPredictor()
