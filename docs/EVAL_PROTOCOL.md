# Evaluation Protocol — Stage 3 (pre-registered)

**Status:** pre-registered before any model was run. Committed before `results/` existed.
**Branch:** `refactor/honest-portfolio` · **Data-quality authority:** `docs/DATA_INTEGRITY.md`
**Purpose:** decide, with a rule fixed in advance, whether any model has out-of-sample edge on
next-day gold log returns — and make a negative result as credible as a positive one.

This document is deliberately rigid. Everything below is fixed before the first fit. Any
change made after seeing a result is recorded under **Deviations** at the end, with the reason,
in a separate commit.

---

## 1. Task

Predict the **next-trading-day log return of `Gold_IRR` (TGJU `geram18`, Rial)**:

```
y_t = ln(Gold_{t+1} / Gold_t)
```

Prediction time is **after the Iranian close of day `d`**. The target is the return from the
close of `d` to the close of the next trading day in the series. No intraday data is used.

The series is the local snapshot `data/raw/final_gold_dataset.csv` (1,424 rows,
2021-06-14 → 2026-06-13). It is untracked (D14); the 200-row `data/sample/` file is not used
for modelling.

---

## 2. Information timing

### 2.1 Global bars (Yahoo `GC=F`, `BZ=F`)

The Yahoo bar dated `d` closes at the US close, **after** the Iranian session of day `d`.
Therefore, at prediction time after the Iranian close of `d`, the last **completed** global
bar is the bar of `d-1`. The primary specification uses global features lagged by **one
trading day only**. No same-day global bar is used in the headline.

This is verified from the data, not assumed. The Stage 1b identical-row-set test
(`docs/DATA_INTEGRITY.md`, B2.2) matched the same Iranian return vector against `GC=F` at
`d` and `d+1`:

| Period | corr with `GC=F` at `d` | corr with `GC=F` at `d+1` | n |
|---|---:|---:|---:|
| block (2023-10-27 → 2025-08-06) | +0.1119 | **+0.3803** | 235 |
| post-block (2025-08-21 →) | **+0.3577** | −0.1262 | 238 |

The block's Iranian rows align with the **same calendar day's** global bar once relabelled
`+1`, and the clean post-block rows already align with the same calendar day. Conclusion:
the Iranian row of date `d` corresponds to global date `d`; the global bar of `d` is not
finished at the Iranian close of `d`; the last usable global bar is `d-1`. Global features are
therefore lagged one trading day in the primary spec.

A same-day variant (`GLOBAL_LAG=0`) may be run **only** as a clearly labelled sensitivity
analysis, never as the headline.

### 2.2 USD_IRR

`Gold_IRR` and `USD_IRR` are both TGJU Iranian closes stamped on the same Iranian date and
published together after the same session. The same-day USD log return is therefore equally
available at the close of `d` as the gold close itself. The primary spec uses `USD_IRR` at
**lag 0** (plus its own lags). This is stated explicitly because it is the one series where a
same-day value is legitimate.

### 2.3 Global series construction (needed for V2)

The committed CSV stores the Yahoo columns only on the original Iranian dates. The corrected
block (V2) needs global bars on dates that are absent from the CSV: of the 503 merged block
rows, **110** have a corrected date `d+1` that is not an original Iranian date (83 of them are
Thursdays, the day the block omits). A date-label-only shift would keep the old, mis-paired
global values and would not correct the block.

To avoid mixing vintages, **all three variants use one global series** pulled from Yahoo for
the same period (`GC=F`, `BZ=F`), merged onto the Iranian dates with the loader's
`how='left'` + `ffill` rule. The Iranian series (`Gold_IRR`, `USD_IRR`) is unchanged from the
local CSV. The fresh oil series matches the CSV exactly on 911/911 overlapping dates; the fresh
ounce series differs by a median 0.33% in level and 0.018% in log return (corr 0.993), which is
the stale-vintage effect already noted in `docs/DATA_INTEGRITY.md` ("Not verified in this
session", last bullet). Using one complete vintage is more honest than using the CSV's ounce on
some rows and a different vintage on the 110 rows where the CSV has no corrected-date bar.

For **V2**, the Iranian block dates are relabelled `+1` **before** the merge, so each block row
is paired with the global bar of its true date. This is the loader's behaviour
(`src/data_loader.py`), not a date-label-only cosmetic shift.

---

## 3. Features — stationary only, one implementation

All features are computed by one function, `src/feature_eng.py::add_stationary_features`, used
by both training and serving. The final list is frozen here. **No raw price-level feature is
included.** All rolling windows use data up to and including row `t`; the target is `y_t`.

| # | Feature | Definition | Window | One-line justification |
|---|---|---|---|---|
| 1 | `gold_ret_lag1` | `ln(Gold_t/Gold_{t-1})` | 1 | Own return at the prediction close; momentum/reversal. |
| 2 | `gold_ret_lag2` | `ln(Gold_{t-1}/Gold_{t-2})` | 1 | One-day reversal. |
| 3 | `gold_ret_lag3` | `ln(Gold_{t-2}/Gold_{t-3})` | 1 | Two-day reversal. |
| 4 | `gold_ret_lag5` | `ln(Gold_{t-4}/Gold_{t-5})` | 1 | Weekly momentum. |
| 5 | `usd_ret_lag0` | `ln(USD_t/USD_{t-1})` | 1 | Same-day FX move, legitimately available at the close. |
| 6 | `usd_ret_lag1` | `ln(USD_{t-1}/USD_{t-2})` | 1 | FX momentum. |
| 7 | `usd_ret_lag2` | `ln(USD_{t-2}/USD_{t-3})` | 1 | FX reversal. |
| 8 | `usd_ret_lag5` | `ln(USD_{t-4}/USD_{t-5})` | 1 | Weekly FX momentum. |
| 9 | `ounce_ret_lag1` | `ln(Ounce_{t-1}/Ounce_{t-2})` | 1 | Last completed global gold bar (one trading day lag). |
| 10 | `ounce_ret_lag2` | `ln(Ounce_{t-2}/Ounce_{t-3})` | 1 | Global gold momentum. |
| 11 | `ounce_ret_lag5` | `ln(Ounce_{t-4}/Ounce_{t-5})` | 1 | Weekly global gold momentum. |
| 12 | `oil_ret_lag1` | `ln(Oil_{t-1}/Oil_{t-2})` | 1 | Last completed oil bar. |
| 13 | `oil_ret_lag5` | `ln(Oil_{t-4}/Oil_{t-5})` | 1 | Weekly oil momentum. |
| 14 | `rsi_14` | RSI(14) on `Gold_IRR`, simple-average gains/losses (same formula as legacy) | 14 | Bounded oscillator; stationary by construction. |
| 15 | `macd_norm` | `(EMA12 - EMA26) / Gold_t` | 12, 26 | Price-normalised MACD; removes the price level. |
| 16 | `macd_signal_norm` | `EMA9(MACD) / Gold_t` | 9 | Price-normalised signal line. |
| 17 | `bb_pctb_20` | `(Gold_t - lower20)/(upper20 - lower20)`, `upper/lower = SMA20 ± 2·sd20` | 20 | Position inside the band, dimensionless. |
| 18 | `bb_bandwidth_20` | `(upper20 - lower20)/SMA20` | 20 | Band width / volatility regime, dimensionless. |
| 19 | `price_sma_7` | `Gold_t/SMA7_t - 1` | 7 | Short-term trend, price-normalised. |
| 20 | `price_sma_20` | `Gold_t/SMA20_t - 1` | 20 | Medium-term trend, price-normalised. |
| 21 | `price_sma_60` | `Gold_t/SMA60_t - 1` | 60 | Long-term trend, price-normalised. |
| 22 | `rv_5` | `sd(gold log return)` over the last 5 rows | 5 | Short-term realised volatility. |
| 23 | `rv_20` | `sd(gold log return)` over the last 20 rows | 20 | Medium-term realised volatility. |

**Calendar features: none.** Justification: the only calendar effect documented in this
dataset is the weekend carry (Saturday/Friday), and it is already reflected in the lagged
returns and realised volatility. Day-of-week dummies would additionally encode the
2023-10 → 2025-08 block's anomalous weekday pattern, i.e. the regime we are trying to avoid
learning. They are excluded rather than risk a block-identity shortcut.

The legacy-spec LSTM (model f) deliberately uses the **old 15 raw-level features** from
`config.data.FEATURE_COLUMNS` (`SMA_7`, `MACD`, `MACD_Signal`, `Bollinger_Upper`,
`Bollinger_Lower`, plus the old same-day global returns and lags). It is a feature-design
comparison, not an information-timing-honest spec, and is labelled as such everywhere.

Warm-up rows with NaN features or NaN target are dropped before any split. No imputation is
used for features; the only fill in the pipeline is the loader's `ffill` on the raw price
frame, as before.

---

## 4. Data variants

All three are evaluated and reported. V2 is the primary specification.

| Variant | Construction | Role |
|---|---|---|
| **V1 raw** | Iranian dates unchanged (`relabel` flag off); global series merged on the raw dates. | Sensitivity: the uncorrected data. |
| **V2 corrected** | Iranian block dates `2023-10-27 → 2025-08-06` relabelled `+1` before the global merge; prices untouched. | **Primary.** The loader's corrected output. |
| **V3 block excluded** | V1 frame; all rows in `2023-10-27 → 2025-08-06` dropped after feature/target computation. | Sensitivity: does the block drive the conclusion? |

**V3 gap handling, explicitly.** Features and the target are computed on the full V1 series so
that every rolling window is defined on consecutive trading rows; the block rows are then
dropped. This means the first post-block rows' features use block **prices** in their rolling
windows (not block date labels); recomputing features after dropping the block would leave no
post-block data before the hold-out. This limitation is reported. In addition:

- the last pre-block row is dropped, because its target is the first block row;
- the frame carries a `segment` column (pre-block / post-block);
- LSTM sequences are built **within** a segment and never cross the gap;
- the first 30 post-block rows cannot produce sequences of their own but can serve as context
  for later sequences; the effective scored post-block rows are reported.

---

## 5. Validation

### 5.1 Hold-out

The final hold-out is **all rows dated 2025-10-01 or later** — 210 rows in this snapshot,
which is the requested "~180 rows, 2025-10 onward" (the old test split was 2025-10-02 →
2026-06-11, 209 rows). It is touched **once**, at the end, after every walk-forward number is
written. For V3 the block is absent and the same date cutoff is used. No scaler, fold boundary,
early-stopping epoch or model choice uses hold-out rows.

*Pre-run amendment 1 (before any model fit, 2026-11-14): the first draft said "the final 180
rows". A data-shape check showed those begin 2025-11-05, which would skip October. The
2025-10-01 cutoff matches the requested period and gives 210 rows; it is used from here on.*

### 5.2 Walk-forward

- Expanding-window, strictly chronological, no shuffling.
- For each variant, the **pre-hold-out** rows are split into **K = 5** contiguous test blocks
  after an initial **50%** training segment. Test blocks are approximately equal-sized.
  Fold `k` trains on all rows before its test block and tests on that block. This keeps five
  non-empty folds in V3 despite the excluded block. Fold date ranges are reported per variant.
- **Purge:** the last **30** training rows (the LSTM sequence length) are dropped before
  fitting, so no training target or feature window touches the test block.
- **Embargo:** the first **5** test rows are not scored, to avoid near-duplicate windows at the
  boundary. Reported row counts reflect this.
- Within each fold's training part, the last **15%** (at least 30 rows) is used only for LSTM
  early stopping; a 30-row purge separates the fitting rows from this validation part. Ridge,
  persistence and the historical mean are fit on the fitting rows only, so every model sees the
  same fitting sample.
- **Scalers:** `StandardScaler` for `X` and `y` is fit **only** on the fitting rows of that
  fold. It is then applied unchanged to validation and test rows.
- The legacy-spec LSTM on V2 uses the **same date ranges** as the V2 stationary folds and
  hold-out, so the comparison is on identical dates, not merely identical row counts.
- The final artifact is trained on the V2 pre-hold-out rows with the same 85/15 internal split
  and a fixed seed (42). It is not tuned on the hold-out.

### 5.3 Compute budget

Target **under 90 minutes** of CPU compute for the full protocol. The budgeted work is 5 folds
× (5 stationary seeds + 3 legacy seeds) × 3 variants = **120 LSTM fits**, plus the final
artifact. If the 5-seed stationary run would exceed the budget, the pre-registered fallback is
to reduce the stationary LSTM to **3 seeds**; this is recorded as a deviation and the reduced
seed count is stated in every results table.

---

## 6. Models — nothing more

| ID | Model | Specification |
|---|---|---|
| a | Zero-return persistence | `ŷ_t = 0` for every test row. The benchmark. |
| b | Historical-mean drift | `ŷ_t = mean(y)` on the training part of the fold; for the hold-out, the mean of all pre-hold-out targets. |
| c | Ridge, own returns only | `Ridge(alpha=1.0)` on features 1–4 (`gold_ret_lag1..5`), standardised. |
| d | Ridge, full stationary set | `Ridge(alpha=1.0)` on all 23 features, standardised. |
| e | Stationary LSTM | The project's 64→32→16 LSTM (`src/model_builder.py`), dropout 0.3, Adam lr 1e-3, batch 16, max 60 epochs, early stopping patience 10, ReduceLROnPlateau patience 5 / factor 0.5 / min_lr 1e-5, sequence length 30, on the 23 stationary features. **5 seeds** (fallback 3). Predictions are the seed-average; seed dispersion is reported. |
| f | Legacy-spec LSTM | Same architecture and training schedule, on the **old 15 raw-level features**, V2 only, **3 seeds**. Included only to show the effect of feature design; not eligible for the edge verdict. |

**Hyperparameters and multiple testing.** There is **no hyperparameter search**. One fixed
configuration is used for each ridge and each LSTM architecture; ridge `alpha=1.0`; the LSTM
schedule above. Seeds are repetitions, not configurations. The number of configurations tried
is therefore **1 per model family** (2 ridge, 2 LSTM architectures), and this is reported in
`docs/RESULTS.md`. If any tuning is added later, it must happen inside training folds, the
number of configurations must be recorded, and the hold-out must remain untouched.

---

## 7. Metrics

For **every model and every variant**, on the pooled walk-forward out-of-sample predictions and
on the hold-out:

1. **RMSE** and **MAE** of log returns.
2. **OOS R² vs zero-return persistence** (Campbell–Thompson):
   `1 - Σ(y-ŷ)² / Σy²`.
3. **OOS R² vs the historical-mean benchmark**:
   `1 - Σ(y-ŷ)² / Σ(y-ŷ_histmean)²`.
4. **Directional accuracy**, the **up-day base rate** in the evaluation sample, a one-sided
   binomial test against that base rate (not 50%), and the difference from the always-up
   predictor (whose accuracy is the base rate). A two-sided binomial p vs 50% is reported only
   as a supplementary column, clearly labelled.
5. **Diebold–Mariano vs persistence**: squared-error loss differential, Newey–West HAC variance
   with lag `L = max(1, floor(4·(n/100)^(2/9)))`, Harvey–Leybourne–Newbold small-sample
   correction, one-sided p for "model better" and two-sided p.
6. **Moving-block bootstrap** 95% percentile CI (block length **20**, **2,000** replications,
   fixed seed **12345**) on OOS R² vs persistence and on `RMSE_model − RMSE_persistence`.
7. **Prediction dispersion**: `sd(ŷ)`, `sd(y)`, `corr(ŷ, y)`, so a near-constant predictor is
   visible rather than hidden by an aggregate score.

Price-level metrics are **not** headline and are not reported. If any are ever shown, they are
labelled "persistence-equivalent".

Per-fold metrics are also written to JSON so a single lucky fold cannot masquerade as a result.

---

## 8. Pre-registered rule for "does the model have edge"

Apply to the **primary specification: V2, stationary features**. A model has demonstrated edge
only if it satisfies **all** of the following:

1. pooled walk-forward OOS RMSE is **lower** than zero-return persistence, **and**
2. the one-sided DM test vs persistence has **p < 0.05** on the pooled walk-forward OOS
   predictions, **and**
3. the same two conditions hold on the **hold-out** (RMSE lower and one-sided DM p < 0.05),
   **and**
4. the moving-block bootstrap 95% CI on OOS R² vs persistence has a **lower bound > 0** on both
   the pooled walk-forward sample and the hold-out.

The eligible models are `ridge-own`, `ridge-full` and the stationary LSTM (seed-average). The
legacy-spec LSTM and the V1/V3 variants are not eligible for the edge verdict; they are
sensitivity analyses. If no eligible model meets all four conditions, the stated finding is
**"no demonstrated edge"**. This rule is fixed now and is not changed after seeing the numbers.

Multiple-comparison disclosure: three eligible models are checked. A Bonferroni-adjusted
threshold would be 0.05/3 ≈ 0.017; the pre-registered rule uses 0.05, and the adjusted p-values
are reported alongside it so a reader can apply the stricter threshold.

---

## 9. Cost sanity (no trading simulation)

No backtest is run in Stage 3. For each evaluation sample, report the **break-even directional
accuracy** needed to cover round-trip costs of **1.5%** and **3.0%**, given the observed mean
absolute daily log move `E|y|`:

```
break-even accuracy = 0.5 · (1 + cost / E|y|)
```

This is a sanity check, not a strategy: it assumes one position per day, symmetric moves, no
slippage, no compounding and no position sizing. If the break-even accuracy exceeds the
observed directional accuracy (or 100%), the cost hurdle is stated plainly.

---

## 10. Outputs and reproducibility

- One entry point: `python -m src.evaluate --variant V2` (and `V1`, `V3`; `--all` runs all
  three). It writes machine-readable JSON/CSV to `results/` and a log.
- The primary artifact (`models/gold_lstm_stationary_v2.keras`) and its two scalers are
  committed together with a metadata JSON (feature list, training window, data variant, git
  commit, date, seed). It is **not** wired into the API or Streamlit in Stage 3.
- Tests must pass before the results are committed:
  no feature at row `t` uses data after `t`; target alignment; scaler fit only on training
  rows; fold windows do not cross boundaries; relabel behaviour in each variant.
- Every number in `docs/RESULTS.md` must appear in a committed `results/` file or in the pasted
  console log. No number is estimated.

---

## 11. Deviations

**One post-run deviation, found on 2026-11-16 during the Stage 4 artifact audit.** The only
change made before the run was the pre-run hold-out amendment recorded in §5.1 (`cb75162`), made
before any model fit. The global-series construction in §2.3 was part of the pre-registration,
not a post-hoc change. The implementation file names and the `make eval` /
`scripts/check_eval.py` substitution are recorded in `docs/RESULTS.md` §8 and `docs/PLAN.md`
Stage 3.

### D-1 — one validation label is a hold-out return (found 2026-11-16, not fixed)

§5.1 promised that "no scaler, fold boundary, early-stopping epoch or model choice uses hold-out
rows." That promise is violated by **one label** at the hold-out boundary.

- **What happened.** The pre-hold-out frame ends on **2025-09-30**. `split_fit_val` puts the
  last 173 pre-hold-out rows (2025-02-08 → 2025-09-30) in the LSTM early-stopping tail. The
  target of the last of those rows is the **2025-10-01 return** — the first return of the
  hold-out period. The gap between the validation tail and the hold-out is therefore **0 rows**,
  one row short of the 1 row needed to keep the label out.
- **What it did not touch.** No hold-out **feature row** appears in the fitting rows or the
  validation rows (0 of 210). The scalers are fit only on the 951 fitting rows
  (2021-08-28 → 2024-12-31). The model weights are not fit on the leaked label; the only channel
  is `val_loss` early stopping (`restore_best_weights=True`), i.e. epoch selection.
- **Size.** 1 of 173 validation labels (0.58%). The label is +2.1548% (log return). Its squared
  value is **0.4982%** of the validation MSE measured about zero. The validation set's mean is
  +0.3147% and its standard deviation 2.2995%.
- **Scope.** The same `split_fit_val(np.arange(len(pre)))` call produced the hold-out models for
  all three variants, so the same single label was in the early-stopping tails of every
  stationary-LSTM and legacy-LSTM hold-out fit in Stage 3 (18 LSTM fits), not only in the final
  seed-42 artifact.
- **Fold boundaries are clean.** Checked read-only on the five V2 stationary folds: the last
  validation target is 36 rows before the first test row (purge 30 + embargo 5 + 1), so **0 of 5**
  fold boundaries are affected.
- **Direction and bound.** Hold-out information can only make the model look better, not worse;
  the leaked label is a large positive move (+2.15%) and the hold-out is a rising sample. The
  effect is confined to epoch selection and is far too small to create the observed null's
  opposite: the stationary LSTM's hold-out R² is +0.0001 with a 95% CI of
  [−0.0577, +0.0630], and it fails the DM condition (p = 0.4984) and the bootstrap condition by
  wide margins. **The verdict "no demonstrated edge" is unchanged.**
- **What was not done.** No re-run, no retraining, no re-split. Fixing the boundary would require
  a new artifact and a new hold-out evaluation, which the GATE 3 decision rules out. Stage 4's
  backtest uses the committed seed-42 artifact as-is and records the overlap again in
  `docs/BACKTEST_PROTOCOL.md` and `docs/RESULTS.md`.

---

## Errata (append-only)

Corrections to the pre-registered text above. The body is not rewritten. Each entry states what
was wrong, the corrected value with its denominator, and the command that reproduces it.

### E-1 — D-1 share of validation loss (2026-11-18)

§11 D-1 says the label's squared value is **0.4982%** of the validation MSE measured about zero.
That figure is `label² / Σy²`: the share the label would have under a zero prediction. It is not
the share of the loss the model actually minimised.

| Quantity | Formula (173 validation labels) | Value |
|---|---|---:|
| zero-prediction approximation (the 0.4982% figure) | `label² / Σy²` | 0.4982% |
| reviewer's "0.86" | `label² / mean(y²)` = `173 · label² / Σy²` | 86.19% |
| exact share of validation loss | `(y − ŷ)² / Σ(y − ŷ)²` | **0.6912%** |

The denominator in the first row is the **sum of squared targets**, `Σy²`; in the second it is
the **mean squared target**, `mean(y²) = Σy² / 173`, so the ratio is 173 times the first. The
reviewer's stated formula `label² / (173 · mean(y²))` is algebraically the first row (0.4982%);
the "0.86" comes from dropping the 173. `0.8619` is a fraction (86.19%), not 0.86% of the loss.
Neither the first nor the second row is a share of the loss.

Early stopping minimises `val_loss = (1/173) Σ(y − ŷ)²`, so the label's share of that loss is its
squared error over the total squared error, using the model's predictions: **0.6912%**. This is
the seed-42 artifact's share (`python scripts/d1_share.py`, one inference pass, no training, no
hold-out scoring). The Stage 3 five-seed fits used the same label, but their per-seed validation
losses were not saved, so their exact shares are not recoverable.

The conclusion was re-checked against the corrected number, not assumed: 0.69% is still small,
the only channel is epoch selection, and the hold-out inputs are unchanged (R² +0.000119,
DM p = 0.4984, 95% CI [−0.0577, +0.0630]). The direction of any effect is optimistic for the
model by construction, not by measurement.

### E-2 — global series forward-filled onto the Iranian grid (2026-11-18)

§2.3 describes the global construction but does not state how much of the daily global variation
is lost or aggregated by the join. Measured on the full training frame
(`python scripts/global_grid_audit.py`, `docs/GLOBAL_GRID_AUDIT.md`):

| Variant | comparable rows | exactly zero (ffill) | span > 1 global day |
|---|---:|---:|---:|
| V1 | 1,363 | 488 (35.80%) | 260 (19.08%) |
| V2 | 1,363 | 491 (36.02%) | 258 (18.93%) |
| V3 | 858 | 309 (36.01%) | 163 (19.00%) |

The cause is the grid mismatch: the price frame has one row per Iranian date (Sat-Thu), the
Yahoo series trades Mon-Fri, and `iran.join(global, how="left").ffill()` picks up a Friday bar
only when Friday is an Iranian row. About 36% of the global returns are therefore exactly zero
by construction, and about 19% aggregate more than one global session. The bundled sample shows
the same zero share (36.18% ounce, 36.68% oil).

The effect on any reported metric was **not measured**. No sensitivity run was performed; it is
future work. This entry records the mechanism and its size, and makes no claim about direction.
