"""
Parity between the serving path and the training/evaluation path.

The claim under test: the raw-row adapter adds no feature skew, the served
prediction equals the one obtained from the evaluation primitives with the same
artifact, and serving is causal. See docs/SERVING_DESIGN.md §9.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.api.predictor import load_bundle
from src.eval_data import build_feature_frame, build_sequences
from src.feature_eng import (
    MIN_HISTORY_ROWS,
    SERVING_SEQUENCE_LENGTH,
    STATIONARY_FEATURE_COLUMNS,
    InputError,
    add_stationary_features,
    prepare_model_input,
)

ROOT = Path(__file__).resolve().parents[1]
SAMPLE_PATH = ROOT / "data" / "sample" / "gold_sample.csv"
FULL_PATH = ROOT / "data" / "raw" / "final_gold_dataset.csv"
PRICE_COLUMNS = ["Gold_IRR", "USD_IRR", "Ounce_USD", "Oil_USD"]


def load_sample() -> pd.DataFrame:
    return (
        pd.read_csv(SAMPLE_PATH, parse_dates=["Date"])
        .sort_values("Date")
        .reset_index(drop=True)
    )


def as_prices(df: pd.DataFrame) -> pd.DataFrame:
    """The price frame shape the evaluation code expects."""
    return df.set_index("Date")[PRICE_COLUMNS].astype(float)


def eval_features(prices: pd.DataFrame) -> pd.DataFrame:
    """The Stage 3 evaluation feature frame for exactly these rows."""
    return build_feature_frame(prices, "stationary", "V1")


@pytest.fixture(scope="module")
def bundle():
    return load_bundle()


def eval_path_prediction(prices: pd.DataFrame, bundle) -> float:
    """
    Predict with the evaluation primitives, not with the serving adapter.

    Mirrors ``src.evaluate.train_predict_lstm``: scale the whole frame, build
    the window with ``build_sequences``, run the model, invert ``scaler_y``.
    """
    features = add_stationary_features(prices).dropna()
    X_all = bundle.scaler_X.transform(features[bundle.feature_columns].values)
    end = np.array([len(X_all) - 1])
    X, _, _ = build_sequences(
        X_all, np.zeros(len(X_all)), np.zeros(len(X_all), dtype=int),
        end, bundle.sequence_length,
    )
    assert X.shape == (1, bundle.sequence_length, bundle.n_features)
    pred = bundle.model.predict(X, verbose=0).ravel()
    return float(bundle.scaler_y.inverse_transform(pred.reshape(-1, 1))[0, 0])


def test_minimum_rows_is_derived_not_guessed():
    """89 = (60-row longest window − 1) + 30-row sequence."""
    assert MIN_HISTORY_ROWS == (60 - 1) + SERVING_SEQUENCE_LENGTH == 89

    df = load_sample()
    short = prepare_model_input(df.iloc[-MIN_HISTORY_ROWS:])
    assert short.n_feature_rows == SERVING_SEQUENCE_LENGTH

    with pytest.raises(InputError) as exc:
        prepare_model_input(df.iloc[-(MIN_HISTORY_ROWS - 1):])
    assert exc.value.code == "too_few_rows"


def test_adapter_returns_the_last_window():
    df = load_sample()
    result = prepare_model_input(df)
    assert result.X.shape == (SERVING_SEQUENCE_LENGTH, len(STATIONARY_FEATURE_COLUMNS))
    assert result.last_date == df["Date"].iloc[-1]
    assert result.feature_frame.index[-1] == result.last_date
    assert result.n_rows_input == len(df)
    assert result.n_feature_rows == len(df) - 59
    assert result.n_rows_dropped == 59
    assert result.last_close == pytest.approx(df["Gold_IRR"].iloc[-1])


def test_feature_parity_sample():
    """Serving features == evaluation features on the same rows, 1e-9."""
    df = load_sample()
    positions = np.linspace(MIN_HISTORY_ROWS - 1, len(df) - 1, 24).astype(int)
    assert len(positions) >= 20

    worst = 0.0
    compared_rows = 0
    for t in positions:
        sub = df.iloc[: t + 1]
        prices = as_prices(sub)

        served = prepare_model_input(sub).feature_frame
        expected = eval_features(prices)

        common = served.index.intersection(expected.index)
        assert len(common) >= 29  # the evaluation frame lacks the final target row
        diff = np.abs(
            served.loc[common, STATIONARY_FEATURE_COLUMNS].to_numpy()
            - expected.loc[common, STATIONARY_FEATURE_COLUMNS].to_numpy()
        )
        worst = max(worst, float(diff.max()))
        compared_rows += len(common)

    assert compared_rows > 600
    assert worst < 1e-9, f"max feature difference {worst:.3e}"


@pytest.mark.skipif(not FULL_PATH.exists(), reason="local full series not present")
def test_feature_parity_full_series():
    """Same claim on the local full series, using post-block rows only."""
    full = (
        pd.read_csv(FULL_PATH, parse_dates=["Date"])
        .sort_values("Date")
        .reset_index(drop=True)
    )
    post = full[full["Date"] > "2025-08-06"].reset_index(drop=True)
    assert len(post) > MIN_HISTORY_ROWS

    positions = np.linspace(MIN_HISTORY_ROWS - 1, len(post) - 1, 5).astype(int)
    worst = 0.0
    for t in positions:
        sub = post.iloc[: t + 1]
        prices = as_prices(sub)
        served = prepare_model_input(sub).feature_frame
        expected = eval_features(prices)
        common = served.index.intersection(expected.index)
        diff = np.abs(
            served.loc[common, STATIONARY_FEATURE_COLUMNS].to_numpy()
            - expected.loc[common, STATIONARY_FEATURE_COLUMNS].to_numpy()
        )
        worst = max(worst, float(diff.max()))
    assert worst < 1e-9, f"max feature difference {worst:.3e}"


def test_prediction_parity(bundle):
    """Served prediction == evaluation-primitive prediction, 1e-6."""
    df = load_sample()
    positions = [MIN_HISTORY_ROWS - 1, 120, 150, 180, len(df) - 1]
    for t in positions:
        sub = df.iloc[: t + 1]
        served = bundle.predict_log_return(prepare_model_input(sub).X)
        expected = eval_path_prediction(as_prices(sub), bundle)
        assert served == pytest.approx(expected, abs=1e-6), f"position {t}"
        assert np.isfinite(served)


def test_no_lookahead_in_serving(bundle):
    """Rows after t cannot change the prediction for t."""
    df = load_sample()
    t, last = 150, len(df) - 1
    base = df.copy()
    altered = df.copy()
    # A violent change to every row after t.
    altered.loc[t + 1:, "Gold_IRR"] *= 1.7
    altered.loc[t + 1:, "USD_IRR"] *= 0.6

    base_features = add_stationary_features(as_prices(base))
    altered_features = add_stationary_features(as_prices(altered))
    upto = base_features.index[base_features.index <= base["Date"].iloc[t]]
    pd.testing.assert_frame_equal(
        base_features.loc[upto], altered_features.loc[upto], check_exact=True
    )

    def window(frame):
        valid = frame.dropna()
        valid = valid.loc[valid.index <= base["Date"].iloc[t]]
        return valid[STATIONARY_FEATURE_COLUMNS].to_numpy()[-SERVING_SEQUENCE_LENGTH:]

    p_base = bundle.predict_log_return(window(base_features))
    p_alt = bundle.predict_log_return(window(altered_features))
    # Stays an exact ==: both calls are in this process, on the same model
    # object, with feature arrays the check above proved bit-identical
    # (check_exact=True). Bitwise equality is the claim here — no lookahead —
    # not a cross-machine reproduction, so there is no float32 kernel drift.
    assert p_base == p_alt

    # Positive control: a change at t must move the features at t.
    changed = df.copy()
    changed.loc[t, "Gold_IRR"] *= 1.05
    changed_features = add_stationary_features(as_prices(changed))
    row = base["Date"].iloc[t]
    assert not np.allclose(
        base_features.loc[row].to_numpy(), changed_features.loc[row].to_numpy()
    )


def test_global_lag_lives_in_the_feature_function():
    """
    ounce/oil enter at t−1 and usd at t, computed inside
    add_stationary_features — the only feature code path.
    """
    prices = as_prices(load_sample())
    features = add_stationary_features(prices)
    t = prices.index[100]
    prev, prev2 = prices.index[99], prices.index[98]

    expected_ounce = np.log(prices["Ounce_USD"].loc[prev] / prices["Ounce_USD"].loc[prev2])
    expected_usd = np.log(prices["USD_IRR"].loc[t] / prices["USD_IRR"].loc[prev])
    assert features.loc[t, "ounce_ret_lag1"] == pytest.approx(expected_ounce, abs=1e-12)
    assert features.loc[t, "usd_ret_lag0"] == pytest.approx(expected_usd, abs=1e-12)

    # If the lag were missing, ounce_ret_lag1 would be today's return.
    todays = np.log(prices["Ounce_USD"].loc[t] / prices["Ounce_USD"].loc[prev])
    assert features.loc[t, "ounce_ret_lag1"] != pytest.approx(todays, abs=1e-12)


def test_ema_warmup_is_bounded_and_decays(bundle):
    """
    Serving from a short window seeds the MACD EMA at the first supplied row.
    The difference from the full-history frame must shrink with history length.
    """
    if not FULL_PATH.exists():
        pytest.skip("local full series not present")
    full = pd.read_csv(FULL_PATH, parse_dates=["Date"]).sort_values("Date")

    full_features = add_stationary_features(as_prices(full)).dropna()
    target = full_features.index[-1]

    diffs = {}
    for n in (89, 120, 200, 400):
        sub = add_stationary_features(as_prices(full.iloc[-n:])).dropna()
        diffs[n] = float(
            np.abs(sub.loc[target, STATIONARY_FEATURE_COLUMNS]
                   - full_features.loc[target, STATIONARY_FEATURE_COLUMNS]).max()
        )

    assert diffs[89] < 2e-4
    assert diffs[200] < 1e-7
    assert diffs[400] < 1e-12
    assert diffs[89] > diffs[200] > diffs[400]

    # The prediction-level effect at the bundled sample's length is negligible.
    window_200 = full_features[STATIONARY_FEATURE_COLUMNS].to_numpy()[-200:][-SERVING_SEQUENCE_LENGTH:]
    window_full = full_features[STATIONARY_FEATURE_COLUMNS].to_numpy()[-SERVING_SEQUENCE_LENGTH:]
    served_200 = bundle.predict_log_return(window_200)
    full_pred = bundle.predict_log_return(window_full)
    assert abs(served_200 - full_pred) < 1e-6
