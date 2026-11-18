# Global-grid audit

**Date:** 2026-11-18 · **Branch:** `refactor/honest-portfolio` · **Script:**
`scripts/global_grid_audit.py` · **Data:** the untracked full snapshot
(`data/raw/final_gold_dataset.csv`, 1,424 rows) and the cached Yahoo series
(`data/raw/global_yahoo.csv`, 1,265 bars, 2021-06-04 → 2026-06-12). Read-only; no model is
loaded and nothing is written to `results/`.

## What is measured

`src.eval_data.build_prices` does `iran.join(global, how="left").ffill()`: the price frame has
one row per **Iranian** date (Sat-Thu, plus some Fridays in the raw snapshot), and the global
columns are forward-filled onto that grid. A Yahoo bar dated on a day the Iranian grid does not
contain — most Fridays — is never picked up, so the next Iranian row jumps from the older bar to
the current one.

For every consecutive pair of rows inside one segment the script counts:

* **`ffill_zero`** — the later row uses the same Yahoo bar as the earlier row, so the global log
  return on the Iranian grid is exactly `0.0` by construction. (The cached series itself has
  only 0.5% genuinely repeated closes; the rest are forward-fill.)
* **`span>1`** — the two rows use Yahoo bars more than one trading day apart, so the "daily"
  global return aggregates several global sessions.

The bar actually used at a row is the latest date that is present in **both** grids; that is what
the left join + `ffill` carries, and it is why the span is measured between used bars rather than
between calendar dates.

## Output

```
$ python scripts/global_grid_audit.py
Global bars: 1265 2021-06-04 -> 2026-06-12
V1                     rows=1364 comparable=1363 ffill_zero= 488 (35.80%) span>1= 260 (19.08%) mean_span=0.884
V2                     rows=1364 comparable=1363 ffill_zero= 491 (36.02%) span>1= 258 (18.93%) mean_span=0.884
V3                     rows= 860 comparable= 858 ffill_zero= 309 (36.01%) span>1= 163 (19.00%) mean_span=0.881

sample (200 rows): exact-zero returns ounce 36.18%, oil 36.68%; multi-day span not measurable (its global vintage is not the cache)
```

`comparable` excludes the first row and, for V3, the pair that crosses the removed block.
`mean_span` is the mean number of global bars traversed per pair (0 = repeat, 1 = one bar,
2 = two bars, ...).

## Reading the numbers

* About **36%** of the global returns the model sees on the Iranian grid are exactly zero because
  of forward-fill, not because the market was flat.
* About **19%** of the rows have a global return that spans more than one global trading day
  (2 bars: ~15%, more than 2: ~3.6%).
* The shares are almost identical across V1, V2 and V3: the block relabel moves some rows onto
  Fridays, but it does not change the fact that the Iranian grid and the Yahoo grid differ.
* The bundled 200-row sample shows the same zero share (36.18% ounce, 36.68% oil). Its global
  columns come from a different download vintage, so the multi-day span cannot be attributed
  from the sample alone; the full-frame figure is the relevant one.

## What was not measured

The effect of this construction on any reported metric was **not measured**. No model was run,
no feature frame was rebuilt with a different alignment, and no sensitivity analysis was
performed. Whether the forward-fill and the multi-day aggregation help or hurt the model is
unknown; a sensitivity run that rebuilds the features on the global trading calendar (or on a
strictly date-aligned grid) is **future work**. This document records the mechanism and its
size, not a direction.
