"""
Data construction, variants, feature frames and walk-forward folds for Stage 3.

The protocol is docs/EVAL_PROTOCOL.md.  This module deliberately does not
contain model code; it only turns the raw snapshot into the three pre-registered
variants and produces chronological folds.
"""
from __future__ import annotations

import json
import os
import urllib.request
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from config.settings import config
from src.data_loader import apply_block_date_shift
from src.feature_eng import (
    FeatureEngineer,
    STATIONARY_FEATURE_COLUMNS,
    add_stationary_features,
)
from src.utils import logger

# Frozen protocol constants (docs/EVAL_PROTOCOL.md §5).
N_FOLDS = 5
INITIAL_TRAIN_FRAC = 0.50
PURGE_ROWS = 30
EMBARGO_ROWS = 5
HOLDOUT_START = pd.Timestamp("2025-10-01")
SEQ_LEN = 30
VAL_FRAC = 0.15
MIN_VAL_ROWS = 30

LEGACY_FEATURE_COLUMNS = list(config.data.FEATURE_COLUMNS)

# The global series is cached locally because data/raw is untracked (D14).
GLOBAL_CACHE = os.path.join(config.paths.DATA_RAW_DIR, "global_yahoo.csv")


def load_raw_prices() -> pd.DataFrame:
    """Load the local merged Iranian snapshot (untracked, 1,424 rows)."""
    path = config.paths.raw_data_path
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"{path} is missing. Stage 3 needs the local full series; it is not "
            "redistributed in the repository (D14)."
        )
    df = pd.read_csv(path, index_col="Date", parse_dates=True)
    df.index = pd.to_datetime(df.index).normalize()
    df = df.sort_index()
    required = ["Gold_IRR", "USD_IRR", "Ounce_USD", "Oil_USD"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"raw snapshot missing columns: {missing}")
    if df.index.duplicated().any():
        raise ValueError("raw snapshot has duplicate dates")
    return df[required].astype(float)


def _fetch_yahoo(ticker: str, period1: int, period2: int) -> pd.Series:
    url = (
        f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
        f"?period1={period1}&period2={period2}&interval=1d&events=history"
    )
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    payload = json.loads(urllib.request.urlopen(req, timeout=30).read())
    result = payload["chart"]["result"][0]
    ts = result["timestamp"]
    closes = result["indicators"]["quote"][0]["close"]
    dates = [datetime.fromtimestamp(t, timezone.utc).date() for t in ts]
    s = pd.Series(closes, index=pd.to_datetime(dates), name=ticker)
    s = s.dropna().sort_index()
    s = s[~s.index.duplicated(keep="last")]
    return s


def load_global_series(raw: pd.DataFrame) -> pd.DataFrame:
    """
    One complete Yahoo global series for all variants.

    The committed CSV stores Yahoo columns only on the original Iranian dates.
    V2 needs global bars on dates absent from the CSV (110 block rows, 83 of
    them Thursdays), so a single complete vintage is used everywhere.  The
    fetch is cached in data/raw/global_yahoo.csv (untracked).
    """
    if os.path.exists(GLOBAL_CACHE):
        g = pd.read_csv(GLOBAL_CACHE, index_col="Date", parse_dates=True)
        g.index = pd.to_datetime(g.index).normalize()
        return g.sort_index().astype(float)

    start = raw.index.min() - pd.Timedelta(days=10)
    end = raw.index.max() + pd.Timedelta(days=2)
    period1 = int(pd.Timestamp(start, tz="UTC").timestamp())
    period2 = int(pd.Timestamp(end, tz="UTC").timestamp())
    gold = _fetch_yahoo("GC=F", period1, period2).rename("Ounce_USD")
    oil = _fetch_yahoo("BZ=F", period1, period2).rename("Oil_USD")
    g = pd.concat([gold, oil], axis=1).sort_index()
    g = g.ffill().dropna()
    os.makedirs(os.path.dirname(GLOBAL_CACHE), exist_ok=True)
    g.to_csv(GLOBAL_CACHE, index_label="Date")
    logger.info("Cached global Yahoo series: %d rows -> %s", len(g), GLOBAL_CACHE)
    return g


def build_prices(raw: pd.DataFrame, global_df: pd.DataFrame, variant: str):
    """
    Build a price frame for V1/V2/V3.

    V2 relabels the Iranian block dates +1 *before* the global merge, so each
    block row is paired with the global bar of its true date.  V1/V3 keep the
    raw dates.  The global merge and ffill/dropna mirror src/data_loader.py.
    """
    if variant not in {"V1", "V2", "V3"}:
        raise ValueError(f"unknown variant {variant!r}")
    iran = raw[["Gold_IRR", "USD_IRR"]].copy()
    n_shifted = 0
    if variant == "V2":
        tmp = iran.reset_index()
        if "Date" not in tmp.columns:
            tmp = tmp.rename(columns={tmp.columns[0]: "Date"})
        tmp, n_shifted = apply_block_date_shift(
            tmp,
            window_start=config.data.DATE_SHIFT_WINDOW_START,
            window_end=config.data.DATE_SHIFT_WINDOW_END,
            days=config.data.DATE_SHIFT_DAYS,
            enabled=True,
        )
        iran = tmp.set_index("Date").sort_index()
        if iran.index.duplicated().any():
            raise ValueError("V2 relabel produced duplicate dates")

    prices = iran.join(global_df, how="left").sort_index()
    prices = prices.ffill().dropna()
    return prices, n_shifted


def build_feature_frame(prices: pd.DataFrame, spec: str, variant: str) -> pd.DataFrame:
    """
    Compute features and the next-day target, then apply the V3 block exclusion.

    V3 drops rows inside the block *after* feature/target computation, drops the
    last pre-block row whose target is in the block, and records a segment id so
    LSTM sequences never cross the gap.  See docs/EVAL_PROTOCOL.md §4.
    """
    if spec not in {"stationary", "legacy"}:
        raise ValueError(f"unknown feature spec {spec!r}")

    if spec == "stationary":
        X = add_stationary_features(prices)
        target = np.log(prices["Gold_IRR"]).diff().shift(-1).rename("Target_Next_LogRet")
        frame = X.join(target).dropna(subset=STATIONARY_FEATURE_COLUMNS + ["Target_Next_LogRet"])
        feature_cols = STATIONARY_FEATURE_COLUMNS
    else:
        engineer = FeatureEngineer()
        frame = engineer.create_features(prices)
        feature_cols = LEGACY_FEATURE_COLUMNS
        frame = frame[feature_cols + ["Target_Next_LogRet"]].dropna()

    frame = frame.copy()
    frame["segment"] = 0

    if variant == "V3":
        start = pd.Timestamp(config.data.DATE_SHIFT_WINDOW_START)
        end = pd.Timestamp(config.data.DATE_SHIFT_WINDOW_END)
        next_date = pd.Series(frame.index, index=frame.index).shift(-1)
        in_block = (frame.index >= start) & (frame.index <= end)
        target_in_block = next_date.between(start, end)
        keep = ~(in_block | target_in_block)
        frame = frame.loc[keep].copy()
        # Rows are either before the block or after it; the gap itself is gone.
        frame["segment"] = np.where(frame.index < start, 0, 1)

    frame = frame.sort_index()
    if frame.index.duplicated().any():
        raise ValueError(f"{variant}/{spec} feature frame has duplicate dates")
    frame.attrs["feature_columns"] = feature_cols
    return frame


def split_holdout(frame: pd.DataFrame, start: pd.Timestamp = HOLDOUT_START):
    """Rows from ``start`` onward are the untouched hold-out; the rest is walk-forward."""
    pre = frame.loc[frame.index < start].copy()
    holdout = frame.loc[frame.index >= start].copy()
    if len(pre) < 300 or len(holdout) < 100:
        raise ValueError(
            f"frame too short for hold-out at {start.date()}: pre={len(pre)} holdout={len(holdout)}"
        )
    return pre, holdout


def make_folds(pre: pd.DataFrame, n_folds: int = N_FOLDS,
               initial_frac: float = INITIAL_TRAIN_FRAC,
               purge: int = PURGE_ROWS, embargo: int = EMBARGO_ROWS):
    """
    Expanding-window chronological folds.

    The first ``initial_frac`` of pre-hold-out rows is the initial training
    segment; the remainder is split into n_folds contiguous test blocks.  The
    last ``purge`` training rows and the first ``embargo`` test rows are
    excluded, as pre-registered.
    """
    n = len(pre)
    initial = int(n * initial_frac)
    blocks = np.array_split(np.arange(initial, n), n_folds)
    folds = []
    for k, block in enumerate(blocks, start=1):
        test_idx = block[embargo:]
        train_end = int(block[0]) - purge
        train_idx = np.arange(0, train_end)
        if len(test_idx) < 10 or len(train_idx) < 100:
            logger.warning("Fold %d skipped: train=%d test=%d", k, len(train_idx), len(test_idx))
            continue
        folds.append({
            "fold": k,
            "train_idx": train_idx,
            "test_idx": test_idx,
            "train_start": pre.index[train_idx[0]],
            "train_end": pre.index[train_idx[-1]],
            "test_start": pre.index[test_idx[0]],
            "test_end": pre.index[test_idx[-1]],
            "purge": purge,
            "embargo": embargo,
        })
    if not folds:
        raise ValueError("no usable walk-forward folds")
    return folds


def split_fit_val(train_idx: np.ndarray, val_frac: float = VAL_FRAC,
                  min_val: int = MIN_VAL_ROWS, purge: int = PURGE_ROWS):
    """
    Split a fold's training rows into fitting rows and an early-stopping
    validation tail.  A purge of ``purge`` rows separates the two.
    """
    n_val = max(min_val, int(len(train_idx) * val_frac))
    n_val = min(n_val, max(1, len(train_idx) // 3))
    val_idx = train_idx[-n_val:]
    fit_idx = train_idx[:-(n_val + purge)]
    if len(fit_idx) < 100:
        raise ValueError(f"not enough fitting rows: {len(fit_idx)}")
    return fit_idx, val_idx


def build_sequences(X_all: np.ndarray, y_all: np.ndarray, segments: np.ndarray,
                    end_idx: np.ndarray, seq_len: int = SEQ_LEN):
    """
    Build (seq_len, n_features) windows ending at each requested row.

    A window is skipped if it would start before row 0 or if it would cross a
    segment boundary (V3's excluded block).  Windows may include rows before the
    requested end index; those rows are causal context and are not targets.
    """
    Xs, ys, valid = [], [], []
    for i in end_idx:
        i = int(i)
        start_i = i - seq_len + 1
        if start_i < 0:
            continue
        if segments[start_i] != segments[i]:
            continue
        Xs.append(X_all[start_i:i + 1])
        ys.append(y_all[i])
        valid.append(i)
    if not Xs:
        return (np.empty((0, seq_len, X_all.shape[1])), np.empty((0,)),
                np.empty((0,), dtype=int))
    return np.asarray(Xs), np.asarray(ys), np.asarray(valid, dtype=int)
