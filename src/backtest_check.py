"""
Stage 4 "economic reality" check: long/flat rules on the saved Stage 3 hold-out.

Protocol: docs/BACKTEST_PROTOCOL.md. No training: the committed seed-42 artifact
predicts the 210 hold-out rows by inference; S0-S3 pay the pre-registered costs.
Usage: python -m src.backtest_check
"""
from __future__ import annotations

import json
import logging
import os
import subprocess
from datetime import datetime, timezone

import joblib
import numpy as np
import pandas as pd

from src.eval_data import (
    PURGE_ROWS, SEQ_LEN, build_feature_frame, build_prices, build_sequences,
    load_global_series, load_raw_prices, split_fit_val, split_holdout,
)
from src.eval_metrics import dispersion, r2_vs_zero, rmse
from src.feature_eng import STATIONARY_FEATURE_COLUMNS

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS_DIR = os.path.join(ROOT, "results")
MODEL_DIR = os.path.join(ROOT, "models")
MODEL_PATH = os.path.join(MODEL_DIR, "gold_lstm_stationary_v2.keras")
SCALER_X_PATH = os.path.join(MODEL_DIR, "scaler_X_stationary_v2.pkl")
SCALER_Y_PATH = os.path.join(MODEL_DIR, "scaler_y_stationary_v2.pkl")
META_PATH = os.path.join(MODEL_DIR, "gold_lstm_stationary_v2.metadata.json")

COSTS = {"C0": 0.0, "C1": 0.0035, "C2": 0.0075, "C3": 0.015}
ANN_DAYS, BLOCK_LEN, N_BOOT, BOOT_SEED = 252, 10, 10_000, 20261116

LOGGER = logging.getLogger("stage4")
LOGGER.addHandler(logging.NullHandler())


def _git_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, text=True
        ).strip()
    except Exception:
        return "unknown"


def _setup_logging() -> logging.Logger:
    os.makedirs(RESULTS_DIR, exist_ok=True)
    LOGGER.setLevel(logging.INFO)
    if not any(isinstance(h, logging.FileHandler) for h in LOGGER.handlers):
        fmt = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
        fh = logging.FileHandler(os.path.join(RESULTS_DIR, "backtest.log"),
                                 mode="w", encoding="utf-8")
        sh = logging.StreamHandler()
        fh.setFormatter(fmt)
        sh.setFormatter(fmt)
        LOGGER.addHandler(fh)
        LOGGER.addHandler(sh)
    return LOGGER


def load_artifact():
    """Load the committed model and scalers. Inference only; no fitting."""
    import tensorflow as tf

    with open(META_PATH, encoding="utf-8") as f:
        meta = json.load(f)
    model = tf.keras.models.load_model(MODEL_PATH, compile=False)
    return model, joblib.load(SCALER_X_PATH), joblib.load(SCALER_Y_PATH), meta


def predict_holdout(frame, holdout_idx, model, sx, sy, meta):
    """Mirror evaluate.train_predict_lstm's test path exactly, without fitting."""
    feature_cols = list(meta["feature_columns"])
    if feature_cols != list(STATIONARY_FEATURE_COLUMNS):
        raise ValueError("artifact feature list does not match the frozen Stage 3 set")
    if int(meta["sequence_length"]) != SEQ_LEN:
        raise ValueError("artifact sequence length does not match the Stage 3 protocol")
    X_all = sx.transform(frame[feature_cols].values)
    y_all = sy.transform(frame[["Target_Next_LogRet"]].values).ravel()
    X_test, _, valid = build_sequences(
        X_all, y_all, frame["segment"].values, holdout_idx, SEQ_LEN
    )
    pred = sy.inverse_transform(model.predict(X_test, verbose=0).reshape(-1, 1)).ravel()
    return pd.Series(pred, index=frame.index[valid])


def positions_from_threshold(pred, threshold: float) -> np.ndarray:
    """Long (1) iff the prediction is strictly above the fixed threshold."""
    return (np.asarray(pred, dtype=float) > float(threshold)).astype(float)


def delay_positions(p, days: int = 1) -> np.ndarray:
    """Shift the position series forward, starting flat."""
    p = np.asarray(p, dtype=float)
    out = np.zeros_like(p)
    if days < len(p):
        out[days:] = p[:-days]
    return out


def equity_curve(positions, returns, cost: float):
    """Pre-registered accounting: cost on turnover, then the day's return."""
    p, r = np.asarray(positions, float), np.asarray(returns, float)
    if p.shape != r.shape:
        raise ValueError(f"shape mismatch: positions {p.shape}, returns {r.shape}")
    eq, net, prev = np.empty(len(p) + 1), np.empty(len(p)), 0.0
    eq[0] = 1.0
    for t in range(len(p)):
        factor = (1.0 + p[t] * r[t]) * (1.0 - cost * abs(p[t] - prev))
        eq[t + 1], net[t], prev = eq[t] * factor, factor - 1.0, p[t]
    return eq, net


def strategy_metrics(positions, eq, net) -> dict:
    p = np.asarray(positions, dtype=float)
    running_max = np.maximum.accumulate(eq)
    return {
        "total_return": float(eq[-1] - 1.0), "equity_multiple": float(eq[-1]),
        "annualized_return": float(eq[-1] ** (ANN_DAYS / len(net)) - 1.0),
        "annualized_vol": float(np.std(net, ddof=1) * np.sqrt(ANN_DAYS)),
        "max_drawdown": float(np.min(eq / running_max - 1.0)),
        "position_changes": int(np.sum(np.abs(np.diff(np.concatenate(([0.0], p)))))),
        "share_long": float(np.mean(p)), "n_days": int(len(net)),
    }


def block_bootstrap_mean_diff(diff, block_len=BLOCK_LEN, n_boot=N_BOOT, seed=BOOT_SEED) -> dict:
    """Moving-block bootstrap 95% percentile CI for the mean of a daily series."""
    d = np.asarray(diff, dtype=float)
    n, rng = len(d), np.random.default_rng(seed)
    n_blocks, starts = int(np.ceil(n / block_len)), np.arange(n - block_len + 1)
    means = np.empty(n_boot)
    for b in range(n_boot):
        idx = rng.choice(starts, size=n_blocks, replace=True)
        means[b] = np.concatenate([d[s:s + block_len] for s in idx])[:n].mean()
    return {"mean_diff": float(d.mean()), "ci_low": float(np.percentile(means, 2.5)),
            "ci_high": float(np.percentile(means, 97.5)),
            "block_len": int(block_len), "n_boot": int(n_boot)}


def _run_strategies(gold_ret, usd_ret, p2, p3, cost):
    series = {"S0": (np.ones(len(gold_ret)), gold_ret),
              "S1": (np.ones(len(usd_ret)), usd_ret),
              "S2": (p2, gold_ret), "S3": (p3, gold_ret)}
    rows, nets = {}, {}
    for name, (p, r) in series.items():
        eq, net = equity_curve(p, r, cost)
        rows[name], nets[name] = strategy_metrics(p, eq, net), net
    boot = {f"{name}_vs_S0": block_bootstrap_mean_diff(nets[name] - nets["S0"])
            for name in ("S2", "S3")}
    return rows, nets, boot


def run() -> dict:
    raw = load_raw_prices()
    global_df = load_global_series(raw)
    prices, _ = build_prices(raw, global_df, "V2")
    frame = build_feature_frame(prices, "stationary", "V2")
    pre, holdout = split_holdout(frame)
    fit_idx, val_idx = split_fit_val(np.arange(len(pre)), purge=PURGE_ROWS)
    model, sx, sy, meta = load_artifact()

    fit_start, fit_end = pre.index[fit_idx[0]], pre.index[fit_idx[-1]]
    val_start, val_end = pre.index[val_idx[0]], pre.index[val_idx[-1]]
    if [str(fit_start.date()), str(fit_end.date())] != meta["training_window"]:
        raise ValueError("artifact training window does not match the Stage 3 split")
    if [str(val_start.date()), str(val_end.date())] != meta["validation_window"]:
        raise ValueError("artifact validation window does not match the Stage 3 split")

    pred = predict_holdout(frame, np.arange(len(pre), len(frame)), model, sx, sy, meta)
    if len(pred) != len(holdout):
        raise ValueError(f"artifact predicted {len(pred)} of {len(holdout)} hold-out rows")
    y = holdout.loc[pred.index, "Target_Next_LogRet"]
    gold_ret = (prices["Gold_IRR"].shift(-1) / prices["Gold_IRR"] - 1.0).loc[pred.index]
    usd_ret = (prices["USD_IRR"].shift(-1) / prices["USD_IRR"] - 1.0).loc[pred.index]
    if not np.allclose(np.exp(y.values) - 1.0, gold_ret.values, atol=1e-10):
        raise ValueError("simple gold return does not match the saved log target")
    if gold_ret.isna().any() or usd_ret.isna().any():
        raise ValueError("hold-out return series has NaNs")

    mu_train = float(pre.iloc[fit_idx]["Target_Next_LogRet"].mean())
    p2, p3 = positions_from_threshold(pred, mu_train), positions_from_threshold(pred, 0.0)
    table, boots, nets = {}, {}, {}
    for label, cost in COSTS.items():
        table[label], nets[label], boots[label] = _run_strategies(
            gold_ret.values, usd_ret.values, p2, p3, cost
        )

    delay = {}
    for name, p in (("S2", p2), ("S3", p3)):
        p_delay = delay_positions(p)
        delay[name] = {}
        for label, cost in COSTS.items():
            eq, net = equity_curve(p_delay, gold_ret.values, cost)
            row = strategy_metrics(p_delay, eq, net)
            row["boot_vs_S0"] = block_bootstrap_mean_diff(net - nets[label]["S0"])
            delay[name][label] = row

    gold_usd = prices["Gold_IRR"] / prices["USD_IRR"]
    q_ret = (gold_usd.shift(-1) / gold_usd - 1.0).loc[pred.index]
    eq_q, net_q = equity_curve(np.ones(len(q_ret)), q_ret.values, 0.0)
    gold_usd_row = strategy_metrics(np.ones(len(q_ret)), eq_q, net_q)

    with open(os.path.join(RESULTS_DIR, "eval_V2.json"), encoding="utf-8") as f:
        saved = json.load(f)["holdout"]["lstm_stationary"]
    artifact_diag = {
        "n": int(len(pred)), "mean_pred": float(pred.mean()),
        "share_pred_gt_zero": float(np.mean(pred.values > 0)),
        "share_pred_gt_mu_train": float(np.mean(pred.values > mu_train)),
        "rmse": rmse(y.values, pred.values), "r2_zero": r2_vs_zero(y.values, pred.values),
        **dispersion(y.values, pred.values),
    }
    stage3_saved = {k: saved[k] for k in (
        "n", "rmse", "r2_zero", "std_pred", "std_actual", "corr", "dir_acc", "up_rate"
    )}

    verdict = {}
    for name in ("S2", "S3"):
        b = boots["C2"][f"{name}_vs_S0"]
        verdict[name] = {
            "cost": "C2 (0.75% per side, 1.5% round trip)",
            "mean_diff": b["mean_diff"], "ci_low": b["ci_low"], "ci_high": b["ci_high"],
            "adds_value": bool(b["mean_diff"] > 0 and b["ci_low"] > 0),
        }
    finding = ("added value over buy-and-hold"
               if any(v["adds_value"] for v in verdict.values())
               else "no added value over buy-and-hold")
    next_price = prices.index[prices.index.get_indexer([pred.index[-1]])[0] + 1]

    return {
        "metadata": {
            "stage": "4", "protocol": "docs/BACKTEST_PROTOCOL.md",
            "git_commit": _git_commit(),
            "run_date_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "artifact": os.path.relpath(MODEL_PATH, ROOT),
            "artifact_git_commit": meta["git_commit"], "artifact_seed": meta["seed"],
            "n_rows": int(len(pred)),
            "period": [str(pred.index[0].date()), str(pred.index[-1].date())],
            "traded_through": str(next_price.date()), "annualization_days": ANN_DAYS,
            "costs": COSTS,
            "bootstrap": {"method": "moving-block percentile", "block_len": BLOCK_LEN,
                          "n_boot": N_BOOT, "seed": BOOT_SEED},
            "mu_train": mu_train,
            "fit_window": [str(fit_start.date()), str(fit_end.date())],
            "validation_window": [str(val_start.date()), str(val_end.date())],
            "artifact_audit": {
                "holdout_feature_rows_in_fit_or_val": 0,
                "validation_labels_in_holdout_period": 1,
                "note": "one label (2025-10-01 return) in val_loss early stopping; "
                        "see docs/EVAL_PROTOCOL.md §11 D-1",
            },
        },
        "prediction_diagnostics": {"artifact_seed_42": artifact_diag,
                                   "stage3_saved_5seed": stage3_saved},
        "strategies": table, "bootstrap": boots, "delay_one_day": delay,
        "gold_in_usd": gold_usd_row,
        "verdict": {"rule": "docs/BACKTEST_PROTOCOL.md §7",
                    "strategies": verdict, "finding": finding,
                    "s3_equals_buy_and_hold": bool(np.all(p3 == 1.0))},
    }


def main():
    _setup_logging()
    LOGGER.info("Stage 4 backtest start; git=%s; protocol=docs/BACKTEST_PROTOCOL.md", _git_commit())
    out = run()
    path = os.path.join(RESULTS_DIR, "backtest.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)
    m = out["metadata"]
    LOGGER.info("Hold-out %s..%s, n=%d, traded through %s; mu_train=%.6f",
                m["period"][0], m["period"][1], m["n_rows"], m["traded_through"], m["mu_train"])
    for label in COSTS:
        s = out["strategies"][label]
        LOGGER.info("%s: total S0=%.4f S2=%.4f S3=%.4f; long S2=%.3f S3=%.3f",
                    label, s["S0"]["total_return"], s["S2"]["total_return"],
                    s["S3"]["total_return"], s["S2"]["share_long"], s["S3"]["share_long"])
    for name in ("S2", "S3"):
        v = out["verdict"]["strategies"][name]
        LOGGER.info("Verdict %s: diff=%.6f CI=[%.6f, %.6f] adds_value=%s",
                    name, v["mean_diff"], v["ci_low"], v["ci_high"], v["adds_value"])
    LOGGER.info("Finding: %s", out["verdict"]["finding"])
    LOGGER.info("Wrote %s", path)


if __name__ == "__main__":
    main()
