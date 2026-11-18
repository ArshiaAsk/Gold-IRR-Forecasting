#!/usr/bin/env python3
"""
Recompute the D-1 share of validation loss contributed by the one label whose
target is the first hold-out return.

Read-only diagnostic: it loads the committed artifact and scalers, rebuilds the
V2 validation sequences, and runs one inference pass over the 173 validation
rows. It does not fit anything, does not score the hold-out and does not write
to the repository.

The three numbers in circulation are:

* ``0.4982%`` = label^2 / sum(y^2) = label^2 / (173 * mean(y^2)).
  The zero-prediction approximation of the label's share of the *total*
  validation squared error.
* ``0.8619`` = label^2 / mean(y^2), i.e. 86.19%.
  The label's squared error relative to the average per-row squared error;
  this is 173x the total-loss share, not a share of the loss. The review's
  "0.86" is this ratio (0.86 as a fraction, not 0.86% of the loss).
* the exact share = (y_label - yhat_label)^2 / sum_i (y_i - yhat_i)^2.
  This is the right measure of influence on early stopping, because
  ``val_loss = (1/173) sum (y - yhat)^2`` and the label is one of the 173 terms.

Usage:
    python scripts/d1_share.py
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import joblib
import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from src.eval_data import (  # noqa: E402
    PURGE_ROWS,
    SEQ_LEN,
    build_feature_frame,
    build_prices,
    build_sequences,
    load_global_series,
    load_raw_prices,
    split_fit_val,
    split_holdout,
)
from src.feature_eng import STATIONARY_FEATURE_COLUMNS  # noqa: E402

MODELS = REPO / "models"
MODEL = MODELS / "gold_lstm_stationary_v2.keras"
SCALER_X = MODELS / "scaler_X_stationary_v2.pkl"
SCALER_Y = MODELS / "scaler_y_stationary_v2.pkl"


def main() -> int:
    for path in (MODEL, SCALER_X, SCALER_Y):
        if not path.exists():
            print(f"{path} is missing; the committed artifact is required.")
            return 2

    try:
        raw = load_raw_prices()
    except FileNotFoundError as exc:
        print(f"{exc}\nThe untracked full snapshot is required (see docs/DATA_MANIFEST.md).")
        return 2

    prices, _ = build_prices(raw, load_global_series(raw), "V2")
    frame = build_feature_frame(prices, "stationary", "V2")
    pre, _ = split_holdout(frame)
    fit_idx, val_idx = split_fit_val(np.arange(len(pre)), purge=PURGE_ROWS)

    scaler_x = joblib.load(SCALER_X)
    scaler_y = joblib.load(SCALER_Y)
    x_all = scaler_x.transform(frame[STATIONARY_FEATURE_COLUMNS].values)
    y_all = scaler_y.transform(frame[["Target_Next_LogRet"]].values).ravel()
    x_val, y_val, valid = build_sequences(
        x_all, y_all, frame["segment"].values, val_idx, SEQ_LEN
    )

    import keras

    model = keras.models.load_model(str(MODEL), compile=False)
    pred = model.predict(x_val, verbose=0).ravel()

    y_true = scaler_y.inverse_transform(y_val.reshape(-1, 1)).ravel()
    y_pred = scaler_y.inverse_transform(pred.reshape(-1, 1)).ravel()
    squared = (y_true - y_pred) ** 2

    label = float(y_true[-1])
    prediction = float(y_pred[-1])
    exact = float(squared[-1] / squared.sum())
    zero_approx = float(label ** 2 / (y_true ** 2).sum())
    ratio_to_mean = float(label ** 2 / (y_true ** 2).mean())

    print(f"validation sequences: {len(y_true)} "
          f"({frame.index[valid[0]].date()} -> {frame.index[valid[-1]].date()})")
    last = int(valid[-1])
    target_date = frame.index[last + 1].date() if last + 1 < len(frame) else "n/a"
    print(f"last validation row: {frame.index[last].date()}; target date: {target_date}")
    print(f"label:               {label:+.9f}  ({label * 100:+.4f}%)")
    print(f"artifact prediction: {prediction:+.9f}")
    print(f"squared error:       {squared[-1]:.12f}")
    print(f"total squared error: {squared.sum():.12f}")
    print(f"mean squared error:  {squared.mean():.12f}")
    print()
    print(f"exact share of total validation loss: {exact:.6%}")
    print(f"zero-prediction approximation:        {zero_approx:.6%}  (label^2 / sum y^2)")
    print(f"reviewer ratio:                       {ratio_to_mean:.6f}  "
          f"(= {ratio_to_mean:.2%} of the mean per-row squared error; "
          f"{len(y_true)}x the total-loss share)")
    print()
    print("The exact share is the right measure of influence on early stopping:")
    print("val_loss = (1/173) * sum (y - yhat)^2, so the label's share of the mean is")
    print("its squared error divided by the total squared error.")

    results_path = REPO / "results" / "eval_V2.json"
    if results_path.exists():
        with open(results_path, "r", encoding="utf-8") as handle:
            holdout = json.load(handle)["holdout"]["lstm_stationary"]
        print()
        print("hold-out verdict inputs (unchanged by the D-1 correction):")
        print(f"  n={holdout['n']}  R2={holdout['r2_zero']:+.4f}  "
              f"DM p={holdout['dm_p_one_sided']:.4f}  "
              f"bootstrap CI=[{holdout['boot_r2_lo']:+.4f}, {holdout['boot_r2_hi']:+.4f}]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
