#!/usr/bin/env python3
"""
Measure how the Yahoo global series lands on the Sat-Thu Iranian grid.

Read-only: it loads the untracked raw snapshot and the cached Yahoo series,
rebuilds each variant's price frame exactly as ``src.eval_data.build_prices``
does, and counts two things for every consecutive pair of Iranian rows:

* **forward-filled zero** - the join found no new Yahoo bar at the later row,
  so ``ffill`` repeated the previous close and the global return computed on
  the Iranian grid is exactly 0.0 by construction (not because the market did
  not move);
* **multi-day span** - the two rows use Yahoo bars more than one trading day
  apart, so the "daily" global return on the Iranian grid aggregates several
  global sessions.

The join is ``iran.join(global, how="left").ffill()``, so a Yahoo bar dated on
a day the Iranian grid does not contain (most Fridays) is never picked up; the
next Iranian row jumps from the older bar to the current one.  That is why the
span is measured between the bars actually used, not between calendar dates.

No model is loaded and nothing is written to the repository.

Usage:
    python scripts/global_grid_audit.py            # full snapshot + sample
    python scripts/global_grid_audit.py --sample-only
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from src.eval_data import (  # noqa: E402
    build_feature_frame,
    build_prices,
    load_global_series,
    load_raw_prices,
)

SAMPLE = REPO / "data" / "sample" / "gold_sample.csv"


def _used_bars(prices_index: pd.DatetimeIndex,
               global_index: pd.DatetimeIndex) -> pd.Series:
    """
    Date of the Yahoo bar actually carried by each row of the price frame.

    The left join only matches exact dates; ``ffill`` then repeats the last
    exact match.  So the bar used at row ``t`` is the latest date <= t that is
    present in both grids.
    """
    common = prices_index.intersection(global_index)
    pos = np.searchsorted(common.values, prices_index.values, side="right") - 1
    return pd.Series(common.values[pos], index=prices_index)


def audit(frame_index: pd.DatetimeIndex, segments: np.ndarray,
          prices_index: pd.DatetimeIndex,
          global_index: pd.DatetimeIndex) -> dict:
    used = _used_bars(prices_index, global_index).loc[frame_index].values
    same_segment = segments[1:] == segments[:-1]
    bar_pos = global_index.get_indexer(pd.DatetimeIndex(used))
    zero = (used[1:] == used[:-1])[same_segment]
    span = np.diff(bar_pos)[same_segment]
    n = int(same_segment.sum())
    return {
        "rows": len(frame_index),
        "comparable": n,
        "ffill_zero": int(zero.sum()),
        "ffill_zero_share": float(zero.mean()) if n else float("nan"),
        "multi_day": int((span > 1).sum()),
        "multi_day_share": float((span > 1).mean()) if n else float("nan"),
        "mean_span": float(span.mean()) if n else float("nan"),
    }


def _print(label: str, r: dict) -> None:
    print(f"{label:<22} rows={r['rows']:>4} comparable={r['comparable']:>4} "
          f"ffill_zero={r['ffill_zero']:>4} ({r['ffill_zero_share']:.2%}) "
          f"span>1={r['multi_day']:>4} ({r['multi_day_share']:.2%}) "
          f"mean_span={r['mean_span']:.3f}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sample-only", action="store_true",
                        help="skip the untracked full snapshot and audit the sample only")
    args = parser.parse_args()

    sample = pd.read_csv(SAMPLE, parse_dates=["Date"])
    sample_ret = {c: np.log(sample[c]).diff() for c in ("Ounce_USD", "Oil_USD")}
    n_sample = len(sample) - 1

    if not args.sample_only:
        try:
            raw = load_raw_prices()
        except FileNotFoundError as exc:
            print(f"{exc}\nUse --sample-only to audit the bundled sample.")
            return 2
        global_df = load_global_series(raw)
        gidx = pd.DatetimeIndex(global_df.index)
        print("Global bars:", len(gidx), gidx.min().date(), "->", gidx.max().date())
        for variant in ("V1", "V2", "V3"):
            prices, _ = build_prices(raw, global_df, variant)
            frame = build_feature_frame(prices, "stationary", variant)
            _print(variant, audit(pd.DatetimeIndex(frame.index),
                                  frame["segment"].values,
                                  pd.DatetimeIndex(prices.index), gidx))
        print()
        print("sample (200 rows): exact-zero returns "
              f"ounce {float((sample_ret['Ounce_USD'] == 0.0).sum()) / n_sample:.2%}, "
              f"oil {float((sample_ret['Oil_USD'] == 0.0).sum()) / n_sample:.2%}; "
              "multi-day span not measurable (its global vintage is not the cache)")
    else:
        print("sample (200 rows), exact-zero returns "
              f"ounce {float((sample_ret['Ounce_USD'] == 0.0).sum()) / n_sample:.2%}, "
              f"oil {float((sample_ret['Oil_USD'] == 0.0).sum()) / n_sample:.2%} "
              "(multi-day span needs the untracked Yahoo cache)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
