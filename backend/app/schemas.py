"""
Pydantic schemas for the churn prediction API.

These define the input contract for /predict and the output shape returned
to the client. Pydantic v2 gives us validation + auto-generated JSON Schema
in the OpenAPI docs at /docs.
"""

from typing import Literal
from pydantic import BaseModel, Field


class ChurnFeatures(BaseModel):
    """Input features for a single customer churn prediction.

    Field names match the columns produced by the Gold feature notebook
    (databricks/03_gold_features.py).
    """
    # Numeric features
    tenure_months: int          = Field(..., ge=0, le=120, example=12)
    monthly_charges: float      = Field(..., ge=0.0,       example=75.50)
    total_charges: float        = Field(..., ge=0.0,       example=906.00)
    avg_charge_per_month: float = Field(..., ge=0.0,       example=75.50)

    # Binary flags
    senior_citizen: Literal[0, 1]    = Field(..., example=0)
    partner: Literal[0, 1]           = Field(..., example=1)
    dependents: Literal[0, 1]        = Field(..., example=0)
    phone_service: Literal[0, 1]     = Field(..., example=1)
    paperless_billing: Literal[0, 1] = Field(..., example=1)
    gender_male: Literal[0, 1]       = Field(..., example=0)
    is_long_tenure: Literal[0, 1]    = Field(..., example=0)
    is_high_spender: Literal[0, 1]   = Field(..., example=1)

    # One-hot: internet service
    internet_service_dsl: Literal[0, 1]         = 0
    internet_service_fiber_optic: Literal[0, 1] = 0
    internet_service_no: Literal[0, 1]          = 0

    # One-hot: contract
    contract_type_month_to_month: Literal[0, 1] = 0
    contract_type_one_year: Literal[0, 1]       = 0
    contract_type_two_year: Literal[0, 1]       = 0

    # One-hot: payment method
    payment_method_electronic_check: Literal[0, 1] = 0
    payment_method_mailed_check: Literal[0, 1]     = 0
    payment_method_bank_transfer: Literal[0, 1]    = 0
    payment_method_credit_card: Literal[0, 1]      = 0

    class Config:
        json_schema_extra = {
            "example": {
                "tenure_months": 12, "monthly_charges": 75.50,
                "total_charges": 906.00, "avg_charge_per_month": 75.50,
                "senior_citizen": 0, "partner": 1, "dependents": 0,
                "phone_service": 1, "paperless_billing": 1, "gender_male": 0,
                "is_long_tenure": 0, "is_high_spender": 1,
                "internet_service_dsl": 0, "internet_service_fiber_optic": 1,
                "internet_service_no": 0,
                "contract_type_month_to_month": 1, "contract_type_one_year": 0,
                "contract_type_two_year": 0,
                "payment_method_electronic_check": 1,
                "payment_method_mailed_check": 0,
                "payment_method_bank_transfer": 0,
                "payment_method_credit_card": 0,
            }
        }


class PredictionResponse(BaseModel):
    prediction: Literal[0, 1]   = Field(..., description="1 = will churn, 0 = will stay")
    probability: float          = Field(..., ge=0.0, le=1.0,
                                        description="Confidence in the positive class")
    model_version: str          = Field(..., description="The MLflow registry version")
    model_name: str             = Field(..., description="Registered model name")
    request_id: str             = Field(..., description="Correlation ID for this call")


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"] = "ok"


class ReadyResponse(BaseModel):
    ready: bool
    model_loaded: bool
    detail: str | None = None


class ModelInfoResponse(BaseModel):
    name: str
    version: str
    alias: str
    flavor: str
