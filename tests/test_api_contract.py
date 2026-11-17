"""
The HTTP contract: auth, validation codes, output shape, and that /model-info
reports what the committed files say.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from src.api.main import MAX_HISTORY_ROWS, app
from src.feature_eng import MIN_HISTORY_ROWS

ROOT = Path(__file__).resolve().parents[1]
SAMPLE_PATH = ROOT / "data" / "sample" / "gold_sample.csv"
FULL_PATH = ROOT / "data" / "raw" / "final_gold_dataset.csv"
METADATA_PATH = ROOT / "models" / "gold_lstm_stationary_v2.metadata.json"
RESULTS_PATH = ROOT / "results" / "eval_V2.json"
TEST_KEY = "stage-5a-test-key"

FORBIDDEN_KEY_PARTS = ("confidence", "interval", "ci_low", "ci_high", "lower_bound", "upper_bound")


def sample_rows() -> list:
    df = pd.read_csv(SAMPLE_PATH)
    return [
        {
            "date": str(row.Date),
            "Gold_IRR": float(row.Gold_IRR),
            "USD_IRR": float(row.USD_IRR),
            "Ounce_USD": float(row.Ounce_USD),
            "Oil_USD": float(row.Oil_USD),
        }
        for row in df.itertuples()
    ]


def walk_keys(obj):
    if isinstance(obj, dict):
        for key, value in obj.items():
            yield key
            yield from walk_keys(value)
    elif isinstance(obj, list):
        for value in obj:
            yield from walk_keys(value)


@pytest.fixture(scope="module")
def client():
    previous = os.environ.get("API_KEY")
    os.environ["API_KEY"] = TEST_KEY
    with TestClient(app) as test_client:
        yield test_client
    if previous is None:
        os.environ.pop("API_KEY", None)
    else:
        os.environ["API_KEY"] = previous


@pytest.fixture(scope="module")
def headers():
    return {"X-API-Key": TEST_KEY}


def test_health_is_unauthenticated(client):
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["model_loaded"] is True
    assert body["status"] is True


def test_model_info_requires_key(client):
    assert client.get("/model-info").status_code == 401
    assert client.get("/model-info", headers={"X-API-Key": "wrong"}).status_code == 401


def test_model_info_matches_the_files(client, headers):
    response = client.get("/model-info", headers=headers)
    assert response.status_code == 200
    body = response.json()

    with open(METADATA_PATH, "r", encoding="utf-8") as f:
        metadata = json.load(f)
    assert body["metadata"] == metadata
    assert body["metadata_source"] == "models/gold_lstm_stationary_v2.metadata.json"
    assert body["model_id"] == "gold_lstm_stationary_v2"

    contract = body["input_contract"]
    assert contract["min_rows"] == MIN_HISTORY_ROWS
    assert contract["max_rows"] == MAX_HISTORY_ROWS
    assert contract["sequence_length"] == metadata["sequence_length"]
    assert contract["feature_columns"] == metadata["feature_columns"]

    with open(RESULTS_PATH, "r", encoding="utf-8") as f:
        results = json.load(f)
    served = body["evaluation"]["holdout"]["lstm_stationary"]
    for key in ("n", "rmse", "r2_zero", "dir_acc"):
        assert served[key] == pytest.approx(results["holdout"]["lstm_stationary"][key], rel=1e-12)
    assert body["evaluation"]["edge_verdict"]["edge_demonstrated"] is False

    with open(ROOT / "results" / "backtest.json", "r", encoding="utf-8") as f:
        backtest = json.load(f)
    assert body["economic"]["verdict"]["finding"] == backtest["verdict"]["finding"]


def test_predict_returns_a_log_return(client, headers):
    response = client.post("/predict", json={"rows": sample_rows()}, headers=headers)
    assert response.status_code == 200
    body = response.json()

    prediction = body["prediction"]
    assert prediction["target"] == "next_trading_day_log_return"
    assert np.isfinite(prediction["log_return"])
    assert prediction["persistence_log_return"] == 0.0
    assert prediction["simple_return"] == pytest.approx(
        float(np.expm1(prediction["log_return"])), abs=1e-12
    )

    assert body["input"]["rows_used"] == 200
    assert body["input"]["last_date"] == "2026-06-13"
    assert body["model"]["seed"] == 42
    assert "no demonstrated predictive edge" in body["statement"].lower()
    assert body["caveats"]


def test_output_has_no_confidence_field(client, headers):
    response = client.post("/predict", json={"rows": sample_rows()}, headers=headers)
    assert response.status_code == 200
    for key in walk_keys(response.json()):
        lowered = str(key).lower()
        for part in FORBIDDEN_KEY_PARTS:
            assert part not in lowered, f"forbidden key {key!r}"


def test_stale_input_warns_but_succeeds(client, headers):
    response = client.post("/predict", json={"rows": sample_rows()}, headers=headers)
    assert response.status_code == 200
    warnings = response.json()["warnings"]
    assert any(w.startswith("stale_input") for w in warnings)


def _payload(rows):
    return {"rows": rows}


@pytest.mark.parametrize(
    "mutate, code",
    [
        (lambda rows: rows[: MIN_HISTORY_ROWS - 1], "too_few_rows"),
        (lambda rows: rows + rows[:1], "duplicate_dates"),
        (lambda rows: list(reversed(rows)), "unsorted_dates"),
        (lambda rows: _set(rows, 5, "Gold_IRR", -1.0), "non_positive_price"),
        (lambda rows: _set(rows, 5, "Oil_USD", 0.0), "non_positive_price"),
        (lambda rows: _set(rows, 5, "Gold_IRR", float("nan")), "non_finite_value"),
        (lambda rows: _set(rows, 5, "Gold_IRR", rows[5]["Gold_IRR"] * 10), "implausible_jump"),
        (lambda rows: [], "empty_rows"),
    ],
)
def test_validation_codes(client, headers, mutate, code):
    rows = mutate(sample_rows())
    response = client.post("/predict", json=_payload(rows), headers=headers)
    assert response.status_code == 422, response.text
    assert response.json()["detail"]["code"] == code


def _set(rows, index, column, value):
    out = [dict(r) for r in rows]
    out[index][column] = value
    return out


def test_too_many_rows(client, headers):
    rows = sample_rows()
    oversized = rows + [dict(rows[0]) for _ in range(MAX_HISTORY_ROWS + 1 - len(rows))]
    response = client.post("/predict", json=_payload(oversized), headers=headers)
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "too_many_rows"


def test_wrong_type_is_a_schema_error(client, headers):
    rows = sample_rows()
    rows[3]["Gold_IRR"] = "not-a-number"
    response = client.post("/predict", json=_payload(rows), headers=headers)
    assert response.status_code == 422
    assert "detail" in response.json()


@pytest.mark.skipif(not FULL_PATH.exists(), reason="local full series not present")
def test_block_dates_are_rejected(client, headers):
    full = pd.read_csv(FULL_PATH).sort_values("Date")
    window = full[full["Date"] <= "2025-08-20"].tail(120)
    rows = [
        {
            "date": str(row.Date),
            "Gold_IRR": float(row.Gold_IRR),
            "USD_IRR": float(row.USD_IRR),
            "Ounce_USD": float(row.Ounce_USD),
            "Oil_USD": float(row.Oil_USD),
        }
        for row in window.itertuples()
    ]
    response = client.post("/predict", json=_payload(rows), headers=headers)
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "block_dates_unsupported"


def test_missing_key_is_401(client):
    response = client.post("/predict", json={"rows": sample_rows()})
    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "invalid_api_key"


def test_unconfigured_key_fails_closed(client):
    previous = os.environ.pop("API_KEY", None)
    try:
        response = client.post("/predict", json={"rows": sample_rows()})
        assert response.status_code == 503
        assert response.json()["detail"]["code"] == "api_key_not_configured"
        assert client.get("/health").status_code == 200
    finally:
        if previous is not None:
            os.environ["API_KEY"] = previous
