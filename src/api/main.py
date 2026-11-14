"""
Minimal FastAPI service for the gold price LSTM model.

Exactly three endpoints (decision D12): ``/health``, ``/model-info`` and
``/predict``. There is no MLOps wiring: the app starts even when the model
artifacts are absent, and ``/health`` reports ``model_loaded`` accordingly.
API-key authentication is read from the environment by ``src/api/security.py``.
"""
from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator

from config.logging import setup_logging
from src.api.security import (
    RATE_LIMIT_ENABLED,
    client_key,
    rate_limiter,
    require_api_key,
)

try:
    from src.api.predictor import GoldPricePredictor
except ImportError:  # script-style import (python src/api/main.py)
    from predictor import GoldPricePredictor

setup_logging(base_log_dir="logs", level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent.parent
MODEL_PATH = BASE_DIR / "models" / "gold_lstm_v2.keras"
SCALER_X_PATH = BASE_DIR / "models" / "scaler_X.pkl"
SCALER_Y_PATH = BASE_DIR / "models" / "scaler_y.pkl"

SEQUENCE_LENGTH = 30
N_FEATURES = 15
FEATURE_NAMES = [
    'Gold_LogRet', 'USD_LogRet', 'Ounce_LogRet', 'Oil_LogRet',
    'SMA_7', 'RSI_14', 'MACD', 'MACD_Signal',
    'Bollinger_Upper', 'Bollinger_Lower',
    'Gold_LogRet_Lag_1', 'Gold_LogRet_Lag_2', 'Gold_LogRet_Lag_3',
    'USD_LogRet_Lag_1', 'USD_LogRet_Lag_2',
]

# --- Schemas ---

class PredictionRequest(BaseModel):
    """30 timesteps x 15 features, plus the price the return is applied to."""

    features: List[List[float]] = Field(
        ...,
        min_length=SEQUENCE_LENGTH,
        max_length=SEQUENCE_LENGTH,
        description="Feature array of shape (30, 15)",
    )
    current_price: float = Field(
        ...,
        gt=0,
        description="Current 18k gold price in IRR per gram",
    )

    @field_validator("features")
    @classmethod
    def _validate_features(cls, value: List[List[float]]) -> List[List[float]]:
        if not all(len(row) == N_FEATURES for row in value):
            raise ValueError(f"Each feature row must have exactly {N_FEATURES} features")
        arr = np.asarray(value, dtype=float)
        if not np.isfinite(arr).all():
            raise ValueError("Features must contain only finite numeric values")
        return value


class PredictionResponse(BaseModel):
    success: bool
    prediction: Dict[str, Any]
    timestamp: str


class HealthResponse(BaseModel):
    status: bool
    model_loaded: bool
    timestamp: str


# --- Lifespan ---

model_artifacts: Dict[str, Any] = {"predictor": None, "status": "startup"}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load the model once at startup; never prevent the server from starting."""
    missing = [
        path.name
        for path in (MODEL_PATH, SCALER_X_PATH, SCALER_Y_PATH)
        if not path.exists()
    ]
    if missing:
        model_artifacts["status"] = "model_missing"
        logger.warning(
            "Model artifacts missing (%s). Server starts; /predict returns 503.",
            ", ".join(missing),
        )
    else:
        try:
            model_artifacts["predictor"] = GoldPricePredictor(
                model_path=str(MODEL_PATH),
                scaler_X_path=str(SCALER_X_PATH),
                scaler_y_path=str(SCALER_Y_PATH),
            )
            model_artifacts["status"] = "ready"
            logger.info("Model and scalers loaded from %s", MODEL_PATH)
        except Exception as exc:  # keep /health alive for diagnosis
            model_artifacts["status"] = "failed"
            logger.error("Failed to load model: %s", exc)

    yield

    model_artifacts["predictor"] = None
    model_artifacts["status"] = "shutdown"


app = FastAPI(
    title="Gold Price Prediction API",
    description="LSTM next-day return prediction for 18k gold in IRR per gram",
    version="2.0.0",
    lifespan=lifespan,
)


def _cors_origins() -> List[str]:
    raw = os.getenv("CORS_ALLOW_ORIGINS", "http://localhost:3000,http://localhost:8000")
    origins = [item.strip() for item in raw.split(",") if item.strip()]
    return origins or ["http://localhost:3000", "http://localhost:8000"]


app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-API-Key"],
)

PROTECTED_PATH_PREFIXES = ("/predict", "/model-info")
EXEMPT_PATHS = ("/health", "/docs", "/openapi.json")


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    if not RATE_LIMIT_ENABLED:
        return await call_next(request)
    path = request.url.path
    if path in EXEMPT_PATHS:
        return await call_next(request)
    if not any(path.startswith(prefix) for prefix in PROTECTED_PATH_PREFIXES):
        return await call_next(request)

    key = client_key(request)
    if not rate_limiter.allow(key):
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={"detail": "Rate limit exceeded"},
            headers={"Retry-After": str(rate_limiter.retry_after_seconds(key))},
        )
    return await call_next(request)


# --- Endpoints ---

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Liveness plus whether the model artifacts were loaded."""
    is_ready = model_artifacts["status"] == "ready"
    return HealthResponse(
        status=is_ready,
        model_loaded=is_ready,
        timestamp=datetime.now().isoformat(),
    )


@app.get("/model-info")
async def get_model_info(_: None = Depends(require_api_key)):
    """Shape, parameter count and expected feature order of the loaded model."""
    predictor = model_artifacts.get("predictor")
    if predictor is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Model not loaded (status: {model_artifacts['status']})",
        )
    return {
        "model_path": predictor.model_path,
        "input_shape": str(predictor.model.input_shape),
        "output_shape": str(predictor.model.output_shape),
        "total_parameters": int(predictor.model.count_params()),
        "expected_features": {
            "sequence_length": SEQUENCE_LENGTH,
            "n_features": N_FEATURES,
            "feature_names": FEATURE_NAMES,
        },
    }


@app.post("/predict", response_model=PredictionResponse)
async def predict_price(request: PredictionRequest, _: None = Depends(require_api_key)):
    """Predict the next day's gold price from a (30, 15) feature window."""
    predictor = model_artifacts.get("predictor")
    if predictor is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Model not loaded (status: {model_artifacts['status']})",
        )

    try:
        features = np.asarray(request.features, dtype=float)
        result = predictor.predict_price(features, request.current_price)
        return PredictionResponse(
            success=True,
            prediction=result,
            timestamp=datetime.now().isoformat(),
        )
    except Exception as exc:
        logger.error("Prediction error: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Prediction failed: {exc}",
        ) from exc


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
