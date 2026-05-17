"""
Application settings, read from environment variables once at startup.
"""

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    # MLflow / Databricks
    mlflow_tracking_uri: str = os.getenv("MLFLOW_TRACKING_URI", "databricks")
    mlflow_registry_uri: str = os.getenv("MLFLOW_REGISTRY_URI", "databricks-uc")
    model_name:          str = os.getenv("MODEL_NAME",
                                         "churn_mlops.models.churn_classifier")
    model_alias:         str = os.getenv("MODEL_ALIAS", "production")

    databricks_host:     str = os.getenv("DATABRICKS_HOST", "")
    databricks_token:    str = os.getenv("DATABRICKS_TOKEN", "")

    # Service
    log_level:           str = os.getenv("LOG_LEVEL", "INFO")
    log_env:             str = os.getenv("LOG_ENV", "dev")     # "dev" | "prod"
    cors_origins:        str = os.getenv("CORS_ORIGINS", "*")  # comma-separated

    # Mock mode — useful for tests / when Databricks is not reachable
    mock_model:          bool = os.getenv("MOCK_MODEL", "false").lower() == "true"


settings = Settings()
