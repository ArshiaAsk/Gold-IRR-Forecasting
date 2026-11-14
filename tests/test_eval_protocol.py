"""
Tests for the pre-registered Stage 3 evaluation protocol.

They are deliberately small and synthetic: the point is to prove the
information-timing, alignment, scaler and fold invariants, not to reproduce
the full run.
"""
import numpy as np
import pandas as pd
import pytest

from config.settings import config
from src.eval_data import (
    EMBARGO_ROWS,
    PURGE_ROWS,
    build_feature_frame,
    build_prices,
    make_folds,
    split_fit_val,
    split_holdout,
)
from src.eval_metrics import (
    block_bootstrap,
    cost_sanity,
    diebold_mariano,
    directional_accuracy,
    evaluate_predictions,
    r2_vs_zero,
)
from src.feature_eng import STATIONARY_FEATURE_COLUMNS, add_stationary_features


def _prices(n=320, start="2021-01-04", freq="B", seed=7):
    rng = np.random.default_rng(seed)
    dates = pd.date_range(start, periods=n, freq=freq)
    return pd.DataFrame({
        "Gold_IRR": 10_000_000 * np.exp(np.cumsum(rng.normal(0, 0.010, n))),
        "USD_IRR": 250_000 * np.exp(np.cumsum(rng.normal(0, 0.005, n))),
        "Ounce_USD": 1_900 * np.exp(np.cumsum(rng.normal(0, 0.008, n))),
        "Oil_USD": 75 * np.exp(np.cumsum(rng.normal(0, 0.015, n))),
    }, index=dates)


def _block_prices(seed=11):
    """Business-day frame spanning the real block, with the post-block gap."""
    dates = pd.date_range("2023-01-02", "2025-09-30", freq="B")
    dates = dates[~dates.isin(pd.to_datetime(["2025-08-07", "2025-08-08"]))]
    rng = np.random.default_rng(seed)
    n = len(dates)
    return pd.DataFrame({
        "Gold_IRR": 10_000_000 * np.exp(np.cumsum(rng.normal(0, 0.010, n))),
        "USD_IRR": 250_000 * np.exp(np.cumsum(rng.normal(0, 0.005, n))),
        "Ounce_USD": 1_900 * np.exp(np.cumsum(rng.normal(0, 0.008, n))),
        "Oil_USD": 75 * np.exp(np.cumsum(rng.normal(0, 0.015, n))),
    }, index=dates)


# ---------------------------------------------------------------- timing / target
def test_no_feature_at_t_uses_data_after_t():
    prices = _prices(300)
    base = add_stationary_features(prices)
    t = 150
    perturbed = prices.copy()
    perturbed.iloc[t + 1:] *= 2.0
    after = add_stationary_features(perturbed)
    # Rows up to and including t must be identical; the future is irrelevant.
    np.testing.assert_allclose(
        base.iloc[: t + 1].values,
        after.iloc[: t + 1].values,
        rtol=0, atol=0, equal_nan=True,
    )


def test_target_is_next_day_log_return():
    prices = _prices(300)
    frame = build_feature_frame(prices, "stationary", "V1")
    for i in (0, 10, len(frame) - 2):
        d0, d1 = frame.index[i], frame.index[i + 1]
        expected = np.log(prices.loc[d1, "Gold_IRR"] / prices.loc[d0, "Gold_IRR"])
        assert frame["Target_Next_LogRet"].iloc[i] == pytest.approx(expected, rel=1e-12)


def test_feature_list_has_no_raw_price_level():
    forbidden = {"Gold_IRR", "USD_IRR", "Ounce_USD", "Oil_USD",
                 "SMA_7", "SMA_30", "MACD", "MACD_Signal",
                 "Bollinger_Upper", "Bollinger_Lower"}
    assert not (set(STATIONARY_FEATURE_COLUMNS) & forbidden)
    assert len(STATIONARY_FEATURE_COLUMNS) == len(set(STATIONARY_FEATURE_COLUMNS)) == 23


# ---------------------------------------------------------------- scaler
def test_scaler_fit_only_on_training_rows():
    from src.evaluate import _fit_scalers

    prices = _prices(320)
    frame = build_feature_frame(prices, "stationary", "V1")
    fit_idx = np.arange(0, 120)
    sx, sy = _fit_scalers(frame, STATIONARY_FEATURE_COLUMNS, fit_idx)
    expected = frame.iloc[fit_idx][STATIONARY_FEATURE_COLUMNS].mean().values
    np.testing.assert_allclose(sx.mean_, expected, rtol=1e-12, atol=1e-12)

    changed = frame.copy()
    changed.iloc[120:] *= 100.0
    sx2, _ = _fit_scalers(changed, STATIONARY_FEATURE_COLUMNS, fit_idx)
    np.testing.assert_allclose(sx2.mean_, expected, rtol=1e-12, atol=1e-12)


# ---------------------------------------------------------------- folds
def test_fold_windows_do_not_cross_boundaries():
    prices = _prices(700)
    frame = build_feature_frame(prices, "stationary", "V1")
    folds = make_folds(frame, n_folds=5, purge=PURGE_ROWS, embargo=EMBARGO_ROWS)
    assert len(folds) == 5
    for f in folds:
        train, test = f["train_idx"], f["test_idx"]
        assert np.array_equal(train, np.arange(len(train)))  # expanding prefix
        assert train.max() < test.min()
        assert len(set(train) & set(test)) == 0
        assert test.min() - train.max() - 1 >= PURGE_ROWS + EMBARGO_ROWS
    for a, b in zip(folds, folds[1:]):
        assert a["test_idx"].max() < b["test_idx"].min()


def test_fit_val_split_is_purged():
    train_idx = np.arange(0, 500)
    fit_idx, val_idx = split_fit_val(train_idx, purge=PURGE_ROWS)
    assert len(set(fit_idx) & set(val_idx)) == 0
    assert fit_idx.max() + PURGE_ROWS < val_idx.min()
    assert np.array_equal(val_idx, train_idx[-len(val_idx):])


def test_holdout_is_after_cutoff_and_not_in_folds():
    prices = _prices(700, start="2023-01-02")
    frame = build_feature_frame(prices, "stationary", "V1")
    # The synthetic frame does not reach 2025-10; use a cutoff inside it.
    cutoff = frame.index[int(len(frame) * 0.8)]
    pre, holdout = split_holdout(frame, start=cutoff)
    assert holdout.index.min() >= cutoff
    assert pre.index.max() < cutoff
    folds = make_folds(pre)
    for f in folds:
        assert f["test_idx"].max() < len(pre)


# ---------------------------------------------------------------- variants
def test_variant_relabel_behaviour():
    raw = _block_prices()
    glob = raw[["Ounce_USD", "Oil_USD"]]
    v1, n1 = build_prices(raw, glob, "V1")
    v2, n2 = build_prices(raw, glob, "V2")
    v3, n3 = build_prices(raw, glob, "V3")

    start = pd.Timestamp(config.data.DATE_SHIFT_WINDOW_START)
    end = pd.Timestamp(config.data.DATE_SHIFT_WINDOW_END)
    block_dates = raw.index[(raw.index >= start) & (raw.index <= end)]

    assert n1 == 0 and n3 == 0
    assert n2 == len(block_dates)
    assert v1.index.equals(raw.index)
    assert v3.index.equals(raw.index)
    assert v2.index.is_unique
    # Every block row moved exactly one calendar day; prices did not change.
    for d in block_dates[:5]:
        assert (d + pd.Timedelta(days=1)) in v2.index
        assert v2.loc[d + pd.Timedelta(days=1), "Gold_IRR"] == pytest.approx(
            raw.loc[d, "Gold_IRR"], rel=1e-12)


def test_v3_drops_block_and_records_segments():
    raw = _block_prices()
    glob = raw[["Ounce_USD", "Oil_USD"]]
    v1, _ = build_prices(raw, glob, "V1")
    v3, _ = build_prices(raw, glob, "V3")
    f1 = build_feature_frame(v1, "stationary", "V1")
    f3 = build_feature_frame(v3, "stationary", "V3")

    start = pd.Timestamp(config.data.DATE_SHIFT_WINDOW_START)
    end = pd.Timestamp(config.data.DATE_SHIFT_WINDOW_END)
    assert not ((f3.index >= start) & (f3.index <= end)).any()
    assert len(f3) < len(f1)
    assert set(f3["segment"].unique()) == {0, 1}
    # The last pre-block row is dropped because its target is in the block.
    last_pre = f1.index[f1.index < start].max()
    assert last_pre not in f3.index


# ---------------------------------------------------------------- metrics
def test_diebold_mariano_detects_better_model():
    rng = np.random.default_rng(3)
    y = rng.normal(0, 0.01, 500)
    pred = y + rng.normal(0, 0.0005, 500)
    dm = diebold_mariano(y, pred, np.zeros_like(y))
    assert dm["dm_stat"] < 0
    assert dm["dm_p_one_sided"] < 0.05


def test_block_bootstrap_ci_is_ordered():
    rng = np.random.default_rng(4)
    y = rng.normal(0, 0.01, 400)
    pred = 0.2 * y
    boot = block_bootstrap(y, pred, np.zeros_like(y), n_boot=200)
    assert boot["boot_r2_lo"] <= boot["boot_r2_hi"]
    assert boot["boot_rmse_diff_lo"] <= boot["boot_rmse_diff_hi"]


def test_directional_accuracy_vs_base_rate():
    y = np.array([0.01, -0.01] * 5)
    pred = y.copy()
    out = directional_accuracy(y, pred)
    assert out["dir_acc"] == 1.0
    assert out["up_rate"] == 0.5
    assert out["binom_p_vs_baserate"] < 0.01
    assert out["dir_minus_always_up"] == 0.5


def test_r2_zero_is_zero_for_persistence():
    rng = np.random.default_rng(5)
    y = rng.normal(0, 0.01, 100)
    assert r2_vs_zero(y, np.zeros_like(y)) == pytest.approx(0.0)


def test_cost_sanity_break_even():
    y = np.array([0.01, -0.01] * 10)
    out = cost_sanity(y, costs=(0.015, 0.030))
    assert out["avg_abs_move"] == pytest.approx(0.01)
    assert out["breakeven_acc_0_015"] == pytest.approx(1.25)
    assert out["breakeven_acc_0_030"] == pytest.approx(2.0)


def test_evaluate_predictions_keys():
    rng = np.random.default_rng(6)
    y = rng.normal(0, 0.01, 120)
    pred = 0.1 * y
    out = evaluate_predictions(y, pred, np.full_like(y, y.mean()))
    for key in ("rmse", "mae", "r2_zero", "r2_histmean", "dir_acc",
                "dm_p_one_sided", "boot_r2_lo", "std_pred", "corr"):
        assert key in out
