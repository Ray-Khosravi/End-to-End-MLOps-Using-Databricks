"""
FastAPI app — serves the churn classifier.

Routes:
    GET  /              → simple status
    GET  /health        → liveness (always 200 if process is up)
    GET  /ready         → readiness (200 only after model loaded)
    GET  /model-info    → which model + version is currently loaded
    POST /predict       → run an inference
    GET  /metrics       → Prometheus metrics
"""

from __future__ import annotations

import logging
import time
import uuid
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from prometheus_client import (CONTENT_TYPE_LATEST, Counter, Histogram,
                                generate_latest)

from .model_loader import load_predictor, PredictorProtocol
from .schemas import (ChurnFeatures, HealthResponse, ModelInfoResponse,
                      PredictionResponse, ReadyResponse)
from .settings import settings


# ─────────────────────────────────────────────────────────────────────────
# Structured logging
# ─────────────────────────────────────────────────────────────────────────
def _configure_logging() -> None:
    shared = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
    ]
    renderer = (
        structlog.processors.JSONRenderer() if settings.log_env == "prod"
        else structlog.dev.ConsoleRenderer(colors=True)
    )
    structlog.configure(
        processors=shared + [renderer],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, settings.log_level.upper(), logging.INFO)
        ),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

_configure_logging()
log = structlog.get_logger("api")


# ─────────────────────────────────────────────────────────────────────────
# Prometheus metrics
# ─────────────────────────────────────────────────────────────────────────
REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "path", "status"],
)
REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency",
    ["method", "path"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5),
)
PREDICTIONS = Counter(
    "model_predictions_total",
    "Predictions broken down by predicted class",
    ["predicted_class"],
)
PREDICTION_LATENCY = Histogram(
    "model_prediction_seconds",
    "Time spent in model.predict()",
)


# ─────────────────────────────────────────────────────────────────────────
# Lifespan — load the model at startup, release at shutdown
# ─────────────────────────────────────────────────────────────────────────
_predictor: PredictorProtocol | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _predictor
    log.info("startup_began")
    try:
        _predictor = load_predictor()
        log.info("startup_finished", model_loaded=True)
    except Exception:
        log.exception("model_load_failed")
        _predictor = None
    yield
    log.info("shutdown_began")


app = FastAPI(
    title="Customer Churn Predictor",
    version="1.0.0",
    description="A FastAPI service that serves the MLflow-registered churn model.",
    lifespan=lifespan,
)


# CORS — relax in dev, tighten in prod via env var
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",")],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


# ─────────────────────────────────────────────────────────────────────────
# Middleware: per-request structured logging + metrics
# ─────────────────────────────────────────────────────────────────────────
@app.middleware("http")
async def logging_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-Id") or f"req_{uuid.uuid4().hex[:12]}"
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(
        request_id=request_id,
        http_method=request.method,
        http_path=request.url.path,
    )

    t0 = time.perf_counter()
    try:
        response = await call_next(request)
        elapsed = time.perf_counter() - t0
        REQUEST_COUNT.labels(request.method, request.url.path, str(response.status_code)).inc()
        REQUEST_LATENCY.labels(request.method, request.url.path).observe(elapsed)
        log.info("request_finished",
                 status_code=response.status_code,
                 duration_ms=round(elapsed * 1000, 2))
        response.headers["X-Request-Id"] = request_id
        return response
    except Exception:
        log.exception("request_failed", duration_ms=round((time.perf_counter() - t0) * 1000, 2))
        REQUEST_COUNT.labels(request.method, request.url.path, "500").inc()
        return JSONResponse(
            status_code=500,
            content={"error": "internal_server_error", "request_id": request_id},
            headers={"X-Request-Id": request_id},
        )
    finally:
        structlog.contextvars.clear_contextvars()


# ─────────────────────────────────────────────────────────────────────────
# Routes
# ─────────────────────────────────────────────────────────────────────────
@app.get("/")
def root():
    return {
        "service":  "churn-predictor",
        "version":  app.version,
        "docs":     "/docs",
        "metrics":  "/metrics",
    }


@app.get("/health", response_model=HealthResponse)
def health():
    """Liveness probe — always 200 if the process is alive."""
    return HealthResponse(status="ok")


@app.get("/ready", response_model=ReadyResponse)
def ready():
    """Readiness probe — 200 only once the model has been loaded."""
    if _predictor is None:
        return JSONResponse(
            status_code=503,
            content=ReadyResponse(
                ready=False, model_loaded=False,
                detail="Model not loaded yet."
            ).model_dump(),
        )
    return ReadyResponse(ready=True, model_loaded=True)


@app.get("/model-info", response_model=ModelInfoResponse)
def model_info():
    if _predictor is None:
        raise HTTPException(503, "Model not loaded")
    return ModelInfoResponse(
        name=_predictor.name,
        version=_predictor.version,
        alias=_predictor.alias,
        flavor=_predictor.flavor,
    )


@app.post("/predict", response_model=PredictionResponse)
def predict(features: ChurnFeatures, request: Request):
    if _predictor is None:
        raise HTTPException(503, "Model not loaded")

    feature_dict = features.model_dump()

    t0 = time.perf_counter()
    try:
        pred, prob = _predictor.predict(feature_dict)
    finally:
        PREDICTION_LATENCY.observe(time.perf_counter() - t0)

    PREDICTIONS.labels(str(pred)).inc()

    request_id = request.headers.get("X-Request-Id") or "-"
    log.info("prediction_returned",
             predicted_class=pred, probability=round(prob, 4))

    return PredictionResponse(
        prediction=pred,
        probability=round(prob, 4),
        model_version=_predictor.version,
        model_name=_predictor.name,
        request_id=request_id,
    )


@app.get("/metrics")
def metrics():
    return PlainTextResponse(generate_latest(), media_type=CONTENT_TYPE_LATEST)
