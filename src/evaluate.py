"""
Stage 3 evaluation entry point.

Usage:
    python -m src.evaluate --variant V2
    python -m src.evaluate --variant all --artifact

The protocol is docs/EVAL_PROTOCOL.md.  Results are written to results/ as
JSON/CSV plus a log; the primary artifact is written to models/.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import subprocess
import time
from datetime import datetime, timezone

import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler

from src.eval_data import (
    LEGACY_FEATURE_COLUMNS,
    N_FOLDS,
    PURGE_ROWS,
    EMBARGO_ROWS,
    SEQ_LEN,
    build_feature_frame,
    build_prices,
    build_sequences,
    load_global_series,
    load_raw_prices,
    make_folds,
    split_fit_val,
    split_holdout,
)
from src.eval_metrics import evaluate_predictions, cost_sanity
from src.feature_eng import STATIONARY_FEATURE_COLUMNS

RESULTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "results")
MODELS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "models")
OWN_FEATURE_COLUMNS = ["gold_ret_lag1", "gold_ret_lag2", "gold_ret_lag3", "gold_ret_lag5"]
PRIMARY_VARIANT = "V2"
PRIMARY_SEED = 42


def _git_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            text=True,
        ).strip()
    except Exception:
        return "unknown"


def _setup_logging(out_dir: str = RESULTS_DIR) -> logging.Logger:
    """Attach the run.log handler. Called from main(), never on import."""
    os.makedirs(out_dir, exist_ok=True)
    logger = logging.getLogger("stage3")
    logger.setLevel(logging.INFO)
    if not any(isinstance(h, logging.FileHandler) for h in logger.handlers):
        fmt = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
        fh = logging.FileHandler(os.path.join(out_dir, "run.log"), mode="w", encoding="utf-8")
        fh.setFormatter(fmt)
        sh = logging.StreamHandler()
        sh.setFormatter(fmt)
        logger.addHandler(fh)
        logger.addHandler(sh)
    return logger


# A NullHandler keeps imported functions quiet; main() replaces it with the
# file/stream handlers above. Importing this module must not touch run.log.
LOGGER = logging.getLogger("stage3")
LOGGER.addHandler(logging.NullHandler())


def _set_seeds(seed: int):
    import random
    os.environ["PYTHONHASHSEED"] = str(seed)
    random.seed(seed)
    np.random.seed(seed)
    import tensorflow as tf
    tf.random.set_seed(seed)
    tf.keras.utils.set_random_seed(seed)


def _fit_scalers(frame, feature_cols, fit_idx):
    sx = StandardScaler()
    sy = StandardScaler()
    sx.fit(frame.iloc[fit_idx][feature_cols].values)
    sy.fit(frame.iloc[fit_idx][["Target_Next_LogRet"]].values)
    return sx, sy


def fit_predict_ridge(frame, feature_cols, fit_idx, test_idx, alpha=1.0):
    sx = StandardScaler()
    X_fit = sx.fit_transform(frame.iloc[fit_idx][feature_cols].values)
    X_test = sx.transform(frame.iloc[test_idx][feature_cols].values)
    y_fit = frame.iloc[fit_idx]["Target_Next_LogRet"].values
    model = Ridge(alpha=alpha)
    model.fit(X_fit, y_fit)
    pred = model.predict(X_test)
    return pd.Series(pred, index=frame.index[test_idx])


def fit_predict_histmean(frame, train_idx, test_idx):
    mean = float(frame.iloc[train_idx]["Target_Next_LogRet"].mean())
    pred = pd.Series(mean, index=frame.index[test_idx])
    return pred, mean


def train_predict_lstm(frame, feature_cols, fit_idx, val_idx, test_idx,
                       seed: int, epochs: int = 60, seq_len: int = SEQ_LEN,
                       return_model: bool = False):
    """Train one LSTM seed and return its predictions on ``test_idx``."""
    import tensorflow as tf
    from src.model_builder import LSTMModelBuilder

    _set_seeds(seed)
    sx, sy = _fit_scalers(frame, feature_cols, fit_idx)
    X_all = sx.transform(frame[feature_cols].values)
    y_all = sy.transform(frame[["Target_Next_LogRet"]].values).ravel()
    segments = frame["segment"].values

    X_fit, y_fit, _ = build_sequences(X_all, y_all, segments, fit_idx, seq_len)
    X_val, y_val, _ = build_sequences(X_all, y_all, segments, val_idx, seq_len)
    X_test, _, test_valid = build_sequences(X_all, y_all, segments, test_idx, seq_len)
    if len(X_fit) == 0 or len(X_val) == 0 or len(X_test) == 0:
        LOGGER.warning("LSTM seed %s skipped: fit=%d val=%d test=%d",
                       seed, len(X_fit), len(X_val), len(X_test))
        tf.keras.backend.clear_session()
        return None

    builder = LSTMModelBuilder(
        lstm_units_1=64, lstm_units_2=32, dense_units=16,
        dropout_rate=0.3, learning_rate=1e-3, random_state=seed,
    )
    model = builder.build_model((seq_len, len(feature_cols)))
    callbacks = builder.get_callbacks(
        early_stopping_config={"monitor": "val_loss", "patience": 10,
                               "restore_best_weights": True, "verbose": 0},
        reduce_lr_config={"monitor": "val_loss", "factor": 0.5, "patience": 5,
                          "min_lr": 1e-5, "verbose": 0},
    )
    model.fit(
        X_fit, y_fit,
        validation_data=(X_val, y_val),
        epochs=epochs, batch_size=16, callbacks=callbacks, verbose=0,
    )
    pred_scaled = model.predict(X_test, verbose=0).ravel()
    pred = sy.inverse_transform(pred_scaled.reshape(-1, 1)).ravel()
    out = pd.Series(pred, index=frame.index[test_valid], name=f"lstm_seed_{seed}")
    if return_model:
        return out, model, sx, sy
    tf.keras.backend.clear_session()
    return out


def _seed_average(frame, feature_cols, fit_idx, val_idx, test_idx, seeds, epochs):
    preds = []
    for seed in seeds:
        p = train_predict_lstm(frame, feature_cols, fit_idx, val_idx, test_idx,
                               seed=seed, epochs=epochs)
        if p is not None:
            preds.append(p)
    if not preds:
        return pd.Series(dtype=float), []
    aligned = pd.concat(preds, axis=1)
    return aligned.mean(axis=1), preds


def _date_positions(target_frame, dates):
    """Map dates to integer positions in target_frame; drop missing."""
    pos = target_frame.index.get_indexer(pd.DatetimeIndex(dates))
    return pos[pos >= 0]


def _write_predictions(out_dir, variant, sample, predictions, y_true):
    """Write per-row predictions for one variant and sample (opt-in)."""
    rows = []
    for model, pred in predictions.items():
        if pred is None or len(pred) == 0:
            continue
        idx = pred.index
        for date, actual, forecast in zip(idx, y_true.loc[idx].values, pred.values):
            rows.append({
                "variant": variant,
                "sample": sample,
                "model": model,
                "date": str(pd.Timestamp(date).date()),
                "y_true": float(actual),
                "y_pred": float(forecast),
            })
    if not rows:
        return
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f"{variant}_{sample}.csv")
    pd.DataFrame(rows).to_csv(path, index=False)
    LOGGER.info("Wrote %s (%d rows)", path, len(rows))


def _metrics_row(variant, model, sample, y, pred, hist_pred):
    m = evaluate_predictions(y, pred, hist_pred)
    return {
        "variant": variant,
        "model": model,
        "sample": sample,
        "n": m["n"],
        "rmse": m["rmse"],
        "mae": m["mae"],
        "r2_zero": m["r2_zero"],
        "r2_histmean": m["r2_histmean"],
        "dir_acc": m["dir_acc"],
        "up_rate": m["up_rate"],
        "always_up_acc": m["always_up_acc"],
        "dir_minus_always_up": m["dir_minus_always_up"],
        "binom_p_vs_baserate": m["binom_p_vs_baserate"],
        "binom_p_vs_50": m["binom_p_vs_50"],
        "dm_stat": m["dm_stat"],
        "dm_p_one_sided": m["dm_p_one_sided"],
        "dm_p_two_sided": m["dm_p_two_sided"],
        "dm_lag": m["dm_lag"],
        "dm_n": m["dm_n"],
        "boot_r2_lo": m["boot_r2_lo"],
        "boot_r2_hi": m["boot_r2_hi"],
        "boot_rmse_diff_lo": m["boot_rmse_diff_lo"],
        "boot_rmse_diff_hi": m["boot_rmse_diff_hi"],
        "std_pred": m["std_pred"],
        "std_actual": m["std_actual"],
        "corr": m["corr"],
    }


def run_variant(variant: str, args, global_df: pd.DataFrame, raw: pd.DataFrame,
                out_dir: str = RESULTS_DIR):
    t0 = time.time()
    LOGGER.info("=" * 72)
    LOGGER.info("Variant %s", variant)
    prices, n_shifted = build_prices(raw, global_df, variant)
    LOGGER.info("%s prices: %d rows, %s..%s, relabelled=%d",
                variant, len(prices), prices.index.min().date(),
                prices.index.max().date(), n_shifted)

    stat = build_feature_frame(prices, "stationary", variant)
    feature_cols = list(stat.attrs["feature_columns"])
    pre, holdout = split_holdout(stat)
    folds = make_folds(pre, N_FOLDS, purge=PURGE_ROWS, embargo=EMBARGO_ROWS)
    LOGGER.info("%s stationary frame: %d rows; pre=%d holdout=%d (%s..%s); folds=%d",
                variant, len(stat), len(pre), len(holdout),
                holdout.index.min().date(), holdout.index.max().date(), len(folds))
    for f in folds:
        LOGGER.info("  fold %d: train %s..%s (%d), test %s..%s (%d)",
                    f["fold"], f["train_start"].date(), f["train_end"].date(),
                    len(f["train_idx"]), f["test_start"].date(),
                    f["test_end"].date(), len(f["test_idx"]))

    legacy_frame = None
    legacy_cols = None
    if variant == "V2" and not args.skip_legacy:
        legacy_frame = build_feature_frame(prices, "legacy", variant)
        legacy_cols = list(legacy_frame.attrs["feature_columns"])
        LOGGER.info("V2 legacy frame: %d rows (old 15 raw-level features)", len(legacy_frame))

    # Per-model pooled walk-forward predictions and per-fold metrics.
    model_names = ["persistence", "histmean", "ridge_own", "ridge_full", "lstm_stationary"]
    if legacy_frame is not None:
        model_names.append("lstm_legacy")
    wf_preds = {m: [] for m in model_names}
    wf_hist = []
    wf_y = []
    fold_metrics = {m: [] for m in model_names}
    coverage = {m: 0 for m in model_names}

    for f in folds:
        fit_idx, val_idx = split_fit_val(f["train_idx"], purge=PURGE_ROWS)
        test_idx = f["test_idx"]
        y_test = stat.iloc[test_idx]["Target_Next_LogRet"]
        hist_pred, _ = fit_predict_histmean(stat, f["train_idx"], test_idx)
        wf_hist.append(hist_pred)
        wf_y.append(y_test)

        wf_preds["persistence"].append(pd.Series(0.0, index=y_test.index))
        wf_preds["histmean"].append(hist_pred)
        wf_preds["ridge_own"].append(
            fit_predict_ridge(stat, OWN_FEATURE_COLUMNS, fit_idx, test_idx))
        wf_preds["ridge_full"].append(
            fit_predict_ridge(stat, feature_cols, fit_idx, test_idx))

        seeds = list(range(args.seeds))
        p_lstm, _ = _seed_average(stat, feature_cols, fit_idx, val_idx, test_idx,
                                  seeds, args.epochs)
        wf_preds["lstm_stationary"].append(p_lstm)

        if legacy_frame is not None:
            lfit = _date_positions(legacy_frame, stat.index[fit_idx])
            lval = _date_positions(legacy_frame, stat.index[val_idx])
            ltest = _date_positions(legacy_frame, y_test.index)
            p_leg, _ = _seed_average(legacy_frame, legacy_cols, lfit, lval, ltest,
                                     list(range(args.legacy_seeds)), args.epochs)
            wf_preds["lstm_legacy"].append(p_leg)

        # Per-fold metrics on each model's own coverage.
        for m in model_names:
            if not wf_preds[m]:
                continue
            p = wf_preds[m][-1]
            if p is None or len(p) == 0:
                continue
            yy = y_test.loc[p.index]
            hp = hist_pred.loc[p.index]
            fold_metrics[m].append(_metrics_row(variant, m, f"fold_{f['fold']}",
                                                yy.values, p.values, hp.values))
        LOGGER.info("  fold %d done (fit=%d val=%d test=%d)", f["fold"],
                    len(fit_idx), len(val_idx), len(test_idx))

    y_wf = pd.concat(wf_y).sort_index()
    hist_wf = pd.concat(wf_hist).sort_index()
    walkforward = {}
    pooled = {}
    for m in model_names:
        preds = [p for p in wf_preds[m] if p is not None and len(p) > 0]
        if not preds:
            continue
        p = pd.concat(preds).sort_index()
        p = p[~p.index.duplicated(keep="first")]
        y = y_wf.loc[p.index]
        h = hist_wf.loc[p.index]
        pooled[m] = p
        walkforward[m] = _metrics_row(variant, m, "walkforward", y.values, p.values, h.values)
        walkforward[m]["per_fold"] = fold_metrics[m]
        coverage[m] = len(p)
        LOGGER.info("  WF %-16s n=%4d rmse=%.6f r2=%+.4f dm_p=%.4f dir=%.4f",
                    m, len(p), walkforward[m]["rmse"], walkforward[m]["r2_zero"],
                    walkforward[m]["dm_p_one_sided"], walkforward[m]["dir_acc"])

    if args.save_predictions:
        _write_predictions(os.path.join(out_dir, "predictions"), variant,
                           "walkforward", pooled, y_wf)

    # ---------------- Hold-out: touched once, after all walk-forward numbers.
    holdout_idx = np.arange(len(pre), len(stat))
    fit_idx, val_idx = split_fit_val(np.arange(len(pre)), purge=PURGE_ROWS)
    y_hold = holdout["Target_Next_LogRet"]
    hist_mean_hold = float(pre["Target_Next_LogRet"].mean())
    hist_hold = pd.Series(hist_mean_hold, index=y_hold.index)
    holdout_preds = {
        "persistence": pd.Series(0.0, index=y_hold.index),
        "histmean": hist_hold,
        "ridge_own": fit_predict_ridge(stat, OWN_FEATURE_COLUMNS, fit_idx, holdout_idx),
        "ridge_full": fit_predict_ridge(stat, feature_cols, fit_idx, holdout_idx),
    }
    p_lstm, _ = _seed_average(stat, feature_cols, fit_idx, val_idx, holdout_idx,
                              list(range(args.seeds)), args.epochs)
    holdout_preds["lstm_stationary"] = p_lstm
    if legacy_frame is not None:
        lfit = _date_positions(legacy_frame, stat.index[fit_idx])
        lval = _date_positions(legacy_frame, stat.index[val_idx])
        ltest = _date_positions(legacy_frame, y_hold.index)
        p_leg, _ = _seed_average(legacy_frame, legacy_cols, lfit, lval, ltest,
                                 list(range(args.legacy_seeds)), args.epochs)
        holdout_preds["lstm_legacy"] = p_leg

    holdout_metrics = {}
    for m, p in holdout_preds.items():
        if p is None or len(p) == 0:
            continue
        yy = y_hold.loc[p.index]
        hh = hist_hold.loc[p.index]
        holdout_metrics[m] = _metrics_row(variant, m, "holdout",
                                          yy.values, p.values, hh.values)
        LOGGER.info("  HO %-16s n=%4d rmse=%.6f r2=%+.4f dm_p=%.4f dir=%.4f",
                    m, len(p), holdout_metrics[m]["rmse"], holdout_metrics[m]["r2_zero"],
                    holdout_metrics[m]["dm_p_one_sided"], holdout_metrics[m]["dir_acc"])

    if args.save_predictions:
        _write_predictions(os.path.join(out_dir, "predictions"), variant,
                           "holdout", holdout_preds, y_hold)

    # ---------------- Cost sanity (per sample, primary variant only in RESULTS).
    cost = {
        "walkforward": cost_sanity(y_wf.values),
        "holdout": cost_sanity(y_hold.values),
    }

    # ---------------- Edge verdict (V2 stationary models only).
    edge = None
    if variant == PRIMARY_VARIANT:
        edge = _edge_verdict(walkforward, holdout_metrics)

    elapsed = time.time() - t0
    result = {
        "metadata": {
            "stage": "3",
            "protocol": "docs/EVAL_PROTOCOL.md",
            "git_commit": _git_commit(),
            "run_date_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "variant": variant,
            "primary": variant == PRIMARY_VARIANT,
            "data_source": "data/raw/final_gold_dataset.csv (untracked) + cached Yahoo global series",
            "n_prices": int(len(prices)),
            "n_shifted_dates": int(n_shifted),
            "n_feature_rows": int(len(stat)),
            "n_pre_holdout": int(len(pre)),
            "n_holdout": int(len(holdout)),
            "holdout_start": str(holdout.index.min().date()),
            "holdout_end": str(holdout.index.max().date()),
            "feature_spec": "stationary",
            "feature_columns": feature_cols,
            "legacy_feature_columns": legacy_cols,
            "n_folds": len(folds),
            "fold_scheme": "expanding, initial_train_frac=0.50, purge=30, embargo=5",
            "folds": [
                {"fold": f["fold"],
                 "train_start": str(f["train_start"].date()),
                 "train_end": str(f["train_end"].date()),
                 "test_start": str(f["test_start"].date()),
                 "test_end": str(f["test_end"].date()),
                 "n_train": int(len(f["train_idx"])),
                 "n_test": int(len(f["test_idx"]))}
                for f in folds
            ],
            "seq_len": SEQ_LEN,
            "seeds_stationary": args.seeds,
            "seeds_legacy": args.legacy_seeds if legacy_frame is not None else 0,
            "epochs": args.epochs,
            "configurations_tried": 1,
            "ridge_alpha": 1.0,
            "compute_seconds": round(elapsed, 1),
        },
        "walkforward": walkforward,
        "holdout": holdout_metrics,
        "cost_sanity": cost,
        "edge_verdict": edge,
    }
    LOGGER.info("Variant %s finished in %.1f s", variant, elapsed)
    return result


def _edge_verdict(wf, ho):
    eligible = ["ridge_own", "ridge_full", "lstm_stationary"]
    criteria = {}
    any_edge = False
    for m in eligible:
        if m not in wf or m not in ho:
            continue
        c = {
            "wf_rmse_below_persistence": wf[m]["rmse"] < wf["persistence"]["rmse"],
            "wf_dm_p_one_sided_lt_005": wf[m]["dm_p_one_sided"] < 0.05,
            "ho_rmse_below_persistence": ho[m]["rmse"] < ho["persistence"]["rmse"],
            "ho_dm_p_one_sided_lt_005": ho[m]["dm_p_one_sided"] < 0.05,
            "wf_boot_r2_lo_gt_zero": wf[m]["boot_r2_lo"] > 0,
            "ho_boot_r2_lo_gt_zero": ho[m]["boot_r2_lo"] > 0,
        }
        c["passes"] = all(c.values())
        criteria[m] = c
        any_edge = any_edge or c["passes"]
    return {
        "rule": "docs/EVAL_PROTOCOL.md §8",
        "eligible_models": eligible,
        "criteria": criteria,
        "edge_demonstrated": bool(any_edge),
        "finding": "edge demonstrated" if any_edge else "no demonstrated edge",
    }


def _write_summary(all_results, out_dir: str = RESULTS_DIR):
    rows = []
    for res in all_results:
        for sample in ("walkforward", "holdout"):
            for model, m in res[sample].items():
                row = {k: v for k, v in m.items() if k != "per_fold"}
                row["sample"] = sample
                rows.append(row)
    if not rows:
        return
    cols = [
        "variant", "model", "sample", "n", "rmse", "mae", "r2_zero", "r2_histmean",
        "dir_acc", "up_rate", "always_up_acc", "dir_minus_always_up",
        "binom_p_vs_baserate", "binom_p_vs_50", "dm_stat", "dm_p_one_sided",
        "dm_p_two_sided", "dm_lag", "dm_n", "boot_r2_lo", "boot_r2_hi",
        "boot_rmse_diff_lo", "boot_rmse_diff_hi", "std_pred", "std_actual", "corr",
    ]
    df = pd.DataFrame(rows)
    df = df[[c for c in cols if c in df.columns]]
    path = os.path.join(out_dir, "eval_summary.csv")
    df.to_csv(path, index=False)
    LOGGER.info("Wrote %s (%d rows)", path, len(df))


def _save_artifact(variant, raw, global_df, args):
    """Train the primary stationary LSTM on V2 pre-hold-out and save model+scalers."""
    prices, _ = build_prices(raw, global_df, variant)
    frame = build_feature_frame(prices, "stationary", variant)
    feature_cols = list(frame.attrs["feature_columns"])
    pre, holdout = split_holdout(frame)
    fit_idx, val_idx = split_fit_val(np.arange(len(pre)), purge=PURGE_ROWS)
    holdout_idx = np.arange(len(pre), len(frame))
    LOGGER.info("Artifact: training on %s..%s (fit=%d, val=%d), holdout starts %s",
                pre.index[fit_idx[0]].date(), pre.index[fit_idx[-1]].date(),
                len(fit_idx), len(val_idx), holdout.index.min().date())
    out = train_predict_lstm(frame, feature_cols, fit_idx, val_idx, holdout_idx,
                             seed=PRIMARY_SEED, epochs=args.epochs, return_model=True)
    if out is None:
        raise RuntimeError("artifact training failed")
    _, model, sx, sy = out
    model_path = os.path.join(MODELS_DIR, "gold_lstm_stationary_v2.keras")
    sx_path = os.path.join(MODELS_DIR, "scaler_X_stationary_v2.pkl")
    sy_path = os.path.join(MODELS_DIR, "scaler_y_stationary_v2.pkl")
    model.save(model_path)
    joblib.dump(sx, sx_path)
    joblib.dump(sy, sy_path)
    meta = {
        "stage": "3",
        "artifact": os.path.relpath(model_path, os.path.dirname(MODELS_DIR)),
        "scalers": [
            os.path.relpath(sx_path, os.path.dirname(MODELS_DIR)),
            os.path.relpath(sy_path, os.path.dirname(MODELS_DIR)),
        ],
        "variant": variant,
        "feature_spec": "stationary",
        "feature_columns": feature_cols,
        "sequence_length": SEQ_LEN,
        "architecture": "LSTM(64)-LSTM(32)-Dense(16)-Dense(1)",
        "training_window": [str(pre.index[fit_idx[0]].date()), str(pre.index[fit_idx[-1]].date())],
        "validation_window": [str(pre.index[val_idx[0]].date()), str(pre.index[val_idx[-1]].date())],
        "pre_holdout_window": [str(pre.index.min().date()), str(pre.index.max().date())],
        "holdout_window": [str(holdout.index.min().date()), str(holdout.index.max().date())],
        "seed": PRIMARY_SEED,
        "git_commit": _git_commit(),
        "date_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "note": "Not wired into the API or Streamlit in Stage 3.",
    }
    meta_path = os.path.join(MODELS_DIR, "gold_lstm_stationary_v2.metadata.json")
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)
    LOGGER.info("Artifact saved: %s + scalers + %s", model_path, meta_path)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Stage 3 honest evaluation")
    parser.add_argument("--variant", default="V2", choices=["V1", "V2", "V3", "all"])
    parser.add_argument("--seeds", type=int, default=5, help="stationary LSTM seeds")
    parser.add_argument("--legacy-seeds", type=int, default=3, help="legacy LSTM seeds")
    parser.add_argument("--epochs", type=int, default=60)
    parser.add_argument("--skip-legacy", action="store_true")
    parser.add_argument("--artifact", action="store_true",
                        help="train and save the primary V2 artifact")
    parser.add_argument("--save-predictions", action="store_true",
                        help="write per-row OOS and hold-out predictions to "
                             "<out-dir>/predictions/ (opt-in; not run for the "
                             "committed results)")
    parser.add_argument("--out-dir", default=RESULTS_DIR,
                        help="where JSON/CSV/log/predictions are written "
                             "(default: results/). Use a scratch dir to avoid "
                             "overwriting committed results.")
    args = parser.parse_args(argv)

    out_dir = os.path.abspath(args.out_dir)
    _setup_logging(out_dir)
    os.makedirs(out_dir, exist_ok=True)
    LOGGER.info("Stage 3 evaluation start; git=%s; args=%s", _git_commit(), vars(args))
    raw = load_raw_prices()
    global_df = load_global_series(raw)
    LOGGER.info("Raw prices: %d rows %s..%s; global series: %d rows %s..%s",
                len(raw), raw.index.min().date(), raw.index.max().date(),
                len(global_df), global_df.index.min().date(), global_df.index.max().date())

    variants = ["V1", "V2", "V3"] if args.variant == "all" else [args.variant]
    all_results = []
    t0 = time.time()
    for v in variants:
        res = run_variant(v, args, global_df, raw, out_dir=out_dir)
        all_results.append(res)
        path = os.path.join(out_dir, f"eval_{v}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(res, f, indent=2, default=_json_default)
        LOGGER.info("Wrote %s", path)

    _write_summary(all_results, out_dir=out_dir)

    if args.artifact:
        if "V2" not in variants:
            LOGGER.warning("--artifact requires V2; running it now")
        _save_artifact("V2", raw, global_df, args)

    LOGGER.info("Stage 3 evaluation complete in %.1f s", time.time() - t0)


def _json_default(o):
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, (np.bool_,)):
        return bool(o)
    if isinstance(o, (pd.Timestamp,)):
        return str(o)
    return str(o)


if __name__ == "__main__":
    main()
