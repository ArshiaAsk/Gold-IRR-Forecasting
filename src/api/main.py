"""
Minimal FastAPI service for the committed stationary LSTM.

Three endpoints (decision D12): ``/health``, ``/model-info``, ``/predict``.
The caller sends recent **raw daily rows**; the service turns them into model
input with ``src.feature_eng.prepare_model_input`` — the same function training
and evaluation use — so there is no second feature implementation.

The model has no demonstrated predictive edge (D24/D25). The response says so
in a fixed ``statement`` and a ``caveats`` list, returns a log return rather
than a price headline, and never returns a confidence interval.

The contract is docs/SERVING_DESIGN.md.
"""
from __future__ import annotations

import json
import logging
import os
from contextlib import asynccontextmanager
from datetime import date as date_type
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import AliasChoices, BaseModel, ConfigDict, Field, model_validator

from config.logging import setup_logging
from src.api.predictor import ArtifactMissing, ServingBundle, load_bundle
from src.api.security import require_api_key
from src.feature_eng import (
    MAX_HISTORY_ROWS,
    MIN_HISTORY_ROWS,
    RAW_PRICE_COLUMNS,
    InputError,
    prepare_model_input,
)

setup_logging(base_log_dir="logs", level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent.parent
RESULTS_DIR = BASE_DIR / "results"
PRIMARY_RESULTS = RESULTS_DIR / "eval_V2.json"
BACKTEST_RESULTS = RESULTS_DIR / "backtest.json"

STALE_AFTER_DAYS = 7

STATEMENT = (
    "This model has no demonstrated predictive edge: its log-return accuracy is "
    "indistinguishable from a zero-return benchmark and the economic test finds "
    "no value over buy-and-hold. See docs/RESULTS.md."
)

CAVEATS = [
    "No demonstrated predictive edge: log-return R2 is indistinguishable from "
    "zero and the economic test finds no value over buy-and-hold "
    "(docs/RESULTS.md).",
    "The output is a single next-trading-day log return, not a price forecast; "
    "the implied price is persistence-equivalent.",
    "Metrics come from a ~210-row trending hold-out and are not a claim about "
    "future performance.",
    "Serving history shorter than ~400 rows differs from the full-history "
    "feature frame in the MACD EMA seed (1.6e-4 at 89 rows, 1.1e-8 at 200).",
]

HOLDOUT_METRIC_KEYS = [
    "n", "rmse", "mae", "r2_zero", "r2_histmean", "dir_acc",
    "dm_p_one_sided", "boot_r2_lo", "boot_r2_hi", "std_pred", "std_actual", "corr",
]

# --- Schemas ---

# The sample CSV header is Date,Gold_IRR,USD_IRR,Ounce_USD,Oil_USD. The JSON
# contract historically used `date`; both spellings are accepted so a caller can
# post a CSV row without renaming. The four price fields already have the same
# name in both forms. A request carrying both date aliases with different values
# is rejected rather than silently choosing one.
FIELD_ALIASES = {
    "date": ("date", "Date"),
    "Gold_IRR": ("Gold_IRR",),
    "USD_IRR": ("USD_IRR",),
    "Ounce_USD": ("Ounce_USD",),
    "Oil_USD": ("Oil_USD",),
}


class DailyRow(BaseModel):
    """One raw daily observation, in the units of the raw dataset."""

    model_config = ConfigDict(populate_by_name=True)

    date: date_type = Field(validation_alias=AliasChoices(*FIELD_ALIASES["date"]))
    Gold_IRR: float = Field(validation_alias=AliasChoices(*FIELD_ALIASES["Gold_IRR"]))
    USD_IRR: float = Field(validation_alias=AliasChoices(*FIELD_ALIASES["USD_IRR"]))
    Ounce_USD: float = Field(validation_alias=AliasChoices(*FIELD_ALIASES["Ounce_USD"]))
    Oil_USD: float = Field(validation_alias=AliasChoices(*FIELD_ALIASES["Oil_USD"]))

    @model_validator(mode="before")
    @classmethod
    def _reject_conflicting_aliases(cls, data: Any) -> Any:
        """Accept both date aliases, but not with two different values."""
        if not isinstance(data, dict):
            return data
        for field, aliases in FIELD_ALIASES.items():
            present = [alias for alias in aliases if alias in data]
            if len(present) > 1:
                first = data[present[0]]
                if any(data[alias] != first for alias in present[1:]):
                    shown = ", ".join(f"{alias}={data[alias]!r}" for alias in present)
                    raise ValueError(f"conflicting values for {field}: {shown}")
        return data


class PredictRequest(BaseModel):
    rows: List[DailyRow]


class HealthResponse(BaseModel):
    status: bool
    model_loaded: bool
    timestamp: str


# --- State and lifespan ---

state: Dict[str, Any] = {
    "bundle": None,
    "status": "startup",
    "results": {},
    "results_error": None,
}


def _read_json(path: Path) -> Optional[Dict[str, Any]]:
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _rel(path: Path) -> str:
    """Path relative to the repo root when possible, else absolute."""
    try:
        return str(Path(path).relative_to(BASE_DIR))
    except ValueError:
        return str(path)


def _load_results() -> None:
    """Read the committed evaluation and backtest results, once, at startup."""
    try:
        state["results"] = {
            "eval_V2": _read_json(PRIMARY_RESULTS),
            "backtest": _read_json(BACKTEST_RESULTS),
        }
        missing = [p.name for p, v in ((PRIMARY_RESULTS, state["results"]["eval_V2"]),
                                       (BACKTEST_RESULTS, state["results"]["backtest"]))
                   if v is None]
        if missing:
            state["results_error"] = f"missing results file(s): {', '.join(missing)}"
            logger.warning("Results files missing: %s", ", ".join(missing))
    except (OSError, json.JSONDecodeError) as exc:
        state["results_error"] = f"could not read results: {exc}"
        logger.error("Could not read results: %s", exc)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load the model once; never prevent the server from starting."""
    _load_results()
    try:
        state["bundle"] = load_bundle()
        state["status"] = "ready"
        logger.info("Serving %s", state["bundle"].metadata["artifact"])
    except ArtifactMissing as exc:
        state["status"] = "model_missing"
        logger.warning("%s. Server starts; /predict returns 503.", exc)
    except Exception as exc:  # keep /health alive for diagnosis
        state["status"] = "failed"
        logger.error("Failed to load model: %s", exc)

    yield

    state["bundle"] = None
    state["status"] = "shutdown"


app = FastAPI(
    title="Gold in IRR — honest next-day return model",
    description=(
        "Serves the committed stationary LSTM (seed 42, V2). The model has no "
        "demonstrated predictive edge; see docs/RESULTS.md."
    ),
    version="3.0.0",
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


# --- Endpoints ---


@app.get("/health", response_model=HealthResponse)
def health_check():
    """Liveness plus whether the artifacts were loaded. No auth, no model call."""
    is_ready = state["status"] == "ready"
    return HealthResponse(
        status=is_ready,
        model_loaded=is_ready,
        timestamp=datetime.now().isoformat(),
    )


def _require_bundle() -> ServingBundle:
    bundle = state["bundle"]
    if bundle is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "model_not_loaded",
                "message": f"model artifacts not loaded (status: {state['status']})",
            },
        )
    return bundle


def _metric_summary(block: Dict[str, Any]) -> Dict[str, Any]:
    """Selected metrics, with undefined (NaN) values as null, not NaN."""
    out = {}
    for model, metrics in block.items():
        row = {}
        for k in HOLDOUT_METRIC_KEYS:
            v = metrics.get(k)
            row[k] = v if not (isinstance(v, float) and not np.isfinite(v)) else None
        out[model] = row
    return out


@app.get("/model-info")
def get_model_info(_: None = Depends(require_api_key)):
    """Artifact metadata and the committed metrics, both read from disk."""
    bundle = _require_bundle()
    results = state["results"]
    eval_v2 = results.get("eval_V2") or {}
    backtest = results.get("backtest") or {}

    evaluation = None
    if eval_v2:
        evaluation = {
            "source": _rel(PRIMARY_RESULTS),
            "variant": eval_v2.get("metadata", {}).get("variant"),
            "walkforward": _metric_summary(eval_v2.get("walkforward", {})),
            "holdout": _metric_summary(eval_v2.get("holdout", {})),
            "edge_verdict": eval_v2.get("edge_verdict"),
        }

    economic = None
    if backtest:
        economic = {
            "source": _rel(BACKTEST_RESULTS),
            "verdict": backtest.get("verdict"),
            "costs": backtest.get("metadata", {}).get("costs"),
            "period": backtest.get("metadata", {}).get("period"),
        }

    return {
        "model_id": bundle.model_id,
        "metadata": bundle.metadata,
        "metadata_source": _rel(bundle.metadata_path),
        "input_contract": {
            "method": "POST /predict",
            "body": {"rows": "list of daily rows, oldest first"},
            "required_columns": RAW_PRICE_COLUMNS,
            "units": {
                "Gold_IRR": "Rial per gram, 18k (geram18)",
                "USD_IRR": "Rial per USD",
                "Ounce_USD": "USD per ounce",
                "Oil_USD": "USD per barrel",
            },
            "min_rows": MIN_HISTORY_ROWS,
            "max_rows": MAX_HISTORY_ROWS,
            "sequence_length": bundle.sequence_length,
            "n_features": bundle.n_features,
            "feature_columns": bundle.feature_columns,
            "target": "next_trading_day_log_return",
        },
        "evaluation": evaluation,
        "economic": economic,
        "results_error": state["results_error"],
        "statement": STATEMENT,
    }


@app.post("/predict")
def predict(request: PredictRequest, _: None = Depends(require_api_key)):
    """
    Predict the next trading day's log return from recent raw daily rows.

    Synchronous on purpose: FastAPI runs plain ``def`` endpoints in its
    threadpool, so the blocking Keras call never sits on the event loop.
    """
    bundle = _require_bundle()

    frame = pd.DataFrame([
        {
            "Date": row.date,
            "Gold_IRR": row.Gold_IRR,
            "USD_IRR": row.USD_IRR,
            "Ounce_USD": row.Ounce_USD,
            "Oil_USD": row.Oil_USD,
        }
        for row in request.rows
    ])

    try:
        model_input = prepare_model_input(frame, seq_len=bundle.sequence_length)
    except InputError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": exc.code, "message": exc.message},
        ) from exc

    log_return = bundle.predict_log_return(model_input.X)
    simple_return = float(np.expm1(log_return))

    warnings: List[str] = []
    age_days = (datetime.now(timezone.utc).date() - model_input.last_date.date()).days
    if age_days > STALE_AFTER_DAYS:
        warnings.append(
            f"stale_input: last date {model_input.last_date.date()} is {age_days} "
            f"days old (limit {STALE_AFTER_DAYS})"
        )

    return {
        "prediction": {
            "target": "next_trading_day_log_return",
            "log_return": log_return,
            "simple_return": simple_return,
            "persistence_log_return": 0.0,
            "implied_next_price_persistence_equivalent": float(
                model_input.last_close * np.exp(log_return)
            ),
        },
        "model": bundle.metadata,
        "model_metadata_source": _rel(bundle.metadata_path),
        "input": {
            "last_date": str(model_input.last_date.date()),
            "rows_used": model_input.n_rows_input,
            "feature_rows": model_input.n_feature_rows,
            "sequence_length": bundle.sequence_length,
            "last_close_irr": model_input.last_close,
        },
        "warnings": warnings,
        "caveats": CAVEATS,
        "statement": STATEMENT,
        "timestamp": datetime.now().isoformat(),
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
