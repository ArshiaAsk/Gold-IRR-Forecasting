# Results — Honest Modeling and Evaluation (Stage 3) and Economic Reality (Stage 4)

**Status:** Stage 3 complete; **GATE 3 accepted**, "no demonstrated edge" is final. Stage 4
"economic reality" complete; **stopped at GATE 4**. `trading_bot/` removed (preserved in
`legacy-pre-refactor`). No README, API, Streamlit or Dockerfile changes; Stage 5 not started.
**Stage 3 protocol:** `docs/EVAL_PROTOCOL.md`, committed at `798981a` **before any model fit**;
one pre-run hold-out amendment at `cb75162` (see §8), and one post-run deviation found in the
Stage 4 audit (`docs/EVAL_PROTOCOL.md` §11 D-1, summarized in §2.2 and §11.10).
**Stage 3 run:** 2026-11-14, code commit `8d7715e`, 1,259.6 s (21.0 min) on 8 CPU cores.
**Stage 3 results:** `results/eval_V1.json`, `results/eval_V2.json`, `results/eval_V3.json`,
`results/eval_summary.csv`, `results/run.log` (results commit `64c9798`; log commit `5f4abaa`).
**Stage 4 protocol:** `docs/BACKTEST_PROTOCOL.md`, committed at `0cc0647` before the backtest.
**Stage 4 run:** 2026-11-16, code commit `9b9caca`, inference only (no training).
**Stage 4 results:** `results/backtest.json`, `results/backtest.log`.
**Artifact:** `models/gold_lstm_stationary_v2.keras` + two scalers + metadata (seed 42; not
wired into the API or Streamlit until Stage 5a).

---

## 0. Headline

**The pre-registered verdict is "no demonstrated edge."**

The primary specification is V2 (corrected dates), stationary features, five expanding
walk-forward folds and a 2025-10-01 hold-out touched once. The stationary LSTM's point estimate
is a hair below zero-return persistence in both samples, but it is statistically
indistinguishable from persistence:

| V2 stationary LSTM | n | RMSE | Persistence RMSE | OOS R² vs zero | DM p (1-sided) | Bootstrap 95% CI on R² |
|---|---:|---:|---:|---:|---:|---|
| Walk-forward | 552 | 0.018214 | 0.018350 | +0.0148 | 0.2251 | [−0.0272, +0.0561] |
| Hold-out | 210 | 0.026543 | 0.026545 | +0.0001 | 0.4984 | [−0.0577, +0.0630] |

It meets the RMSE condition in both samples (by 0.7% walk-forward and 0.008% hold-out) but fails
the DM significance condition and the bootstrap-CI condition in both. Ridge-own beats
persistence on the walk-forward only; ridge-full is worse than persistence in both. **The only
model with a significant walk-forward DM vs persistence is the historical-mean drift**
(p = 0.0055, R² = +0.0175, CI [+0.0032, +0.0338]); it fails on the hold-out (p = 0.2428, CI
[−0.0116, +0.0287]). That is the nominal uptrend, not timing skill.

The V1/V2/V3 sensitivity analysis changes no conclusion. The legacy-spec LSTM is not better than
the stationary LSTM. At 1.5% round-trip cost the break-even directional accuracy is **108.9%
(walk-forward) / 95.4% (hold-out)**; at 3% it is **167.8% / 140.9%**. The observed accuracy is
~51–57%, so the cost hurdle is far out of reach.

---

## 1. What was run

### 1.1 Data construction

- **Iranian series:** the local snapshot `data/raw/final_gold_dataset.csv` (1,424 rows,
  2021-06-14 → 2026-06-13, Rial). It is untracked (D14).
- **Global series:** one complete Yahoo `GC=F` / `BZ=F` pull for the same period, cached at
  `data/raw/global_yahoo.csv` (untracked), merged onto the Iranian dates with the loader's
  `how='left'` + `ffill` rule. This was required because the CSV stores global bars only on the
  original Iranian dates and V2 needs bars on 110 corrected dates that are absent from the CSV
  (83 of them Thursdays). Using one complete vintage avoids mixing vintages. Fresh oil matches
  the CSV exactly on 911/911 overlapping dates; fresh ounce differs by a median 0.33% in level
  and 0.018% in log return (corr 0.993), the stale-vintage effect already noted in
  `docs/DATA_INTEGRITY.md`.
- **V1 raw:** Iranian dates unchanged; global series merged on the raw dates.
- **V2 corrected (primary):** Iranian block dates 2023-10-27 → 2025-08-06 relabelled +1
  **before** the global merge; 503 merged rows moved; prices untouched.
- **V3 block excluded:** V1 features/target computed on the full series, then all block rows
  dropped; the last pre-block row (target in the block) also dropped; a `segment` column keeps
  LSTM sequences from crossing the gap.

### 1.2 Feature set

The frozen 23-feature stationary set from `src/feature_eng.py::add_stationary_features`
(`docs/EVAL_PROTOCOL.md` §3): gold-return lags 1/2/3/5, USD-return lags 0/1/2/5 (same-day USD is
allowed because the TGJU USD close is available with the gold close), ounce-return lags 1/2/5
(global bars lagged one trading day), oil-return lags 1/5, RSI(14), price-normalised MACD and
signal, Bollinger %B and bandwidth (20), price/SMA−1 (7/20/60), and realised volatility (5/20).
No raw price level and no calendar dummy.

### 1.3 Validation

- **Hold-out:** all rows dated 2025-10-01 or later — 210 feature rows, 2025-10-01 → 2026-06-11.
  Touched once, after all walk-forward numbers.
- **Walk-forward:** five expanding chronological folds; initial 50% training segment; the
  remaining pre-hold-out rows split into five contiguous test blocks; 30-row purge and 5-row
  embargo; scalers fit only on the fitting rows of each fold. The final 15% of each fold's
  training part is used only for LSTM early stopping, separated by a 30-row purge.
- **V3 folds:** the same five-fold scheme on the 650 pre-hold-out V3 rows. V3 fold 5 spans the
  excluded block (2023-10-02 → 2025-09-30) because the block rows are gone; its 60 test rows are
  the last pre-block rows plus the post-block rows before the hold-out.
- **V2 legacy spec:** the same V2 date ranges as the stationary folds and hold-out, so the
  comparison is on identical dates.

Fold date ranges (V2; V1 is the same with the raw block dates one day earlier inside the block):

| Fold | Train (expanding) | Test | n train | n test |
|---:|---|---|---:|---:|
| 1 | 2021-08-28 → 2023-08-07 | 2023-09-21 → 2024-02-04 | 547 | 111 |
| 2 | 2021-08-28 → 2023-12-30 | 2024-02-13 → 2024-07-08 | 663 | 111 |
| 3 | 2021-08-28 → 2024-05-29 | 2024-07-17 → 2024-11-28 | 779 | 110 |
| 4 | 2021-08-28 → 2024-10-24 | 2024-12-07 → 2025-04-27 | 894 | 110 |
| 5 | 2021-08-28 → 2025-03-12 | 2025-05-04 → 2025-09-30 | 1009 | 110 |

### 1.4 Models and configurations tried

Six models: zero-return persistence; historical-mean drift; ridge on the four gold-own return
lags (`alpha=1.0`); ridge on all 23 stationary features (`alpha=1.0`); the project's 64→32→16
LSTM on the stationary features (5 seeds, seed-average prediction); and the legacy-spec LSTM on
the old 15 raw-level features, V2 only (3 seeds). The LSTM schedule is fixed: dropout 0.3, Adam
1e-3, batch 16, max 60 epochs, early stopping patience 10, ReduceLROnPlateau 5 / 0.5 / 1e-5,
sequence length 30.

**Configurations tried: four fixed configurations** (ridge-own, ridge-full, stationary LSTM,
legacy LSTM); **no hyperparameter search**, so there is no tuning-induced multiple testing.
Seeds are repetitions, not configurations: 5 stationary seeds and 3 legacy seeds. The run
executed **109 LSTM fits** (75 stationary walk-forward, 15 legacy walk-forward, 15 stationary
hold-out, 3 legacy hold-out, 1 final artifact) and 36 ridge fits. Compute time **1,259.6 s
(21.0 min)**, inside the 90-minute budget; the 5-seed stationary run did not need the
pre-registered fallback to 3 seeds.

---

## 2. V2 — primary specification

### 2.1 Walk-forward out-of-sample (pooled across five folds, n = 552)

| Model | RMSE | MAE | R² vs zero | R² vs hist-mean | Dir acc | Up rate | Binom p vs base rate | DM p (1-sided) | Bootstrap R² 95% CI | sd(pred) | corr(pred, actual) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|
| persistence | 0.018350 | 0.012728 | 0.0000 | −0.0178 | 0.0091 | 0.5634 | 1.0000 | — | [0.0000, 0.0000] | 0.000000 | — |
| hist-mean | 0.018188 | 0.012603 | +0.0175 | 0.0000 | 0.5634 | 0.5634 | 0.5178 | **0.0055** | [+0.0032, +0.0338] | 0.000205 | +0.0521 |
| ridge-own | 0.018299 | 0.012660 | +0.0056 | −0.0122 | 0.5688 | 0.5634 | 0.4157 | 0.3264 | [−0.0166, +0.0292] | 0.001799 | −0.0042 |
| ridge-full | 0.018846 | 0.013030 | −0.0548 | −0.0737 | 0.5598 | 0.5634 | 0.5856 | 0.8596 | [−0.1638, +0.0439] | 0.005997 | +0.0504 |
| LSTM stationary | 0.018214 | 0.012555 | +0.0148 | −0.0028 | 0.5616 | 0.5634 | 0.5519 | 0.2251 | [−0.0272, +0.0561] | 0.002485 | +0.0492 |
| LSTM legacy | 0.018243 | 0.012603 | +0.0116 | −0.0060 | 0.5489 | 0.5634 | 0.7674 | 0.1337 | [−0.0102, +0.0363] | 0.001724 | +0.0304 |

### 2.2 Hold-out (2025-10-01 → 2026-06-11, n = 210)

| Model | RMSE | MAE | R² vs zero | R² vs hist-mean | Dir acc | Up rate | Binom p vs base rate | DM p (1-sided) | Bootstrap R² 95% CI | sd(pred) | corr(pred, actual) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|
| persistence | 0.026545 | 0.016507 | 0.0000 | −0.0067 | 0.0238 | 0.5143 | 1.0000 | — | [0.0000, 0.0000] | 0.000000 | — |
| hist-mean | 0.026457 | 0.016780 | +0.0066 | 0.0000 | 0.5143 | 0.5143 | 0.5278 | 0.2428 | [−0.0116, +0.0287] | 0.000000 | +0.0000 |
| ridge-own | 0.026704 | 0.016953 | −0.0120 | −0.0188 | 0.5000 | 0.5143 | 0.6857 | 0.7966 | [−0.0327, +0.0119] | 0.002091 | −0.0763 |
| ridge-full | 0.026798 | 0.017833 | −0.0192 | −0.0260 | 0.4571 | 0.5143 | 0.9578 | 0.7018 | [−0.1345, +0.0593] | 0.006544 | +0.0753 |
| LSTM stationary | 0.026543 | 0.017082 | +0.0001 | −0.0066 | 0.5143 | 0.5143 | 0.5278 | 0.4984 | [−0.0577, +0.0630] | 0.003304 | +0.0381 |
| LSTM legacy | 0.026631 | 0.016977 | −0.0065 | −0.0132 | 0.4762 | 0.5143 | 0.8797 | 0.7153 | [−0.0326, +0.0257] | 0.002646 | −0.0112 |

The LSTM's hold-out R² is +0.000119 and its RMSE advantage is 0.000002 — a point estimate
indistinguishable from zero, not a usable edge.

**One-label caveat (found 2026-11-16, not fixed).** The stationary LSTM's early-stopping
validation tail ends on 2025-09-30, and its target is the 2025-10-01 return — the first return
of the hold-out period. That is 1 of 173 validation labels (+2.15% log, about 0.50% of the
validation MSE about zero), used only for epoch selection. No hold-out feature row is in the
fitting or validation rows, and the scalers are fit only through 2024-12-31. The same overlap
applies to the seed-42 artifact used in Stage 4, so it affects the Stage 3 headline numbers and
the backtest alike. The direction, if any, favors the model slightly; it cannot change the
verdict. Full record: `docs/EVAL_PROTOCOL.md` §11 D-1.

### 2.3 Per-fold stability (V2, stationary LSTM and ridge-full)

| Fold | LSTM RMSE | LSTM R² | LSTM DM p | ridge-full RMSE | ridge-full R² |
|---:|---:|---:|---:|---:|---:|
| 1 | 0.012846 | +0.0076 | 0.3483 | 0.013171 | −0.0431 |
| 2 | 0.019745 | −0.0029 | 0.5517 | 0.020929 | −0.1268 |
| 3 | 0.014351 | +0.0368 | 0.1884 | 0.014079 | +0.0730 |
| 4 | 0.023376 | −0.0039 | 0.5299 | 0.024746 | −0.1251 |
| 5 | 0.018773 | +0.0514 | 0.0132 | 0.018834 | +0.0452 |

The LSTM is positive in three folds and negative in two. Fold 5 alone would look significant
(p = 0.0132); the pooled result (p = 0.2251) does not. This is exactly why the protocol uses
pooled walk-forward **and** hold-out rather than a best fold.

### 2.4 V1 (raw) — full tables

V1 has no legacy-spec LSTM (that model is V2 only). Walk-forward (n = 552):

| Model | RMSE | MAE | R² vs zero | R² vs hist-mean | Dir acc | Up rate | Binom p vs base | DM p (1-sided) | Bootstrap R² 95% CI | sd(pred) | corr |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|
| persistence | 0.018350 | 0.012728 | 0.0000 | −0.0178 | 0.0091 | 0.5634 | 1.0000 | — | [0.0000, 0.0000] | 0.000000 | — |
| hist-mean | 0.018188 | 0.012603 | +0.0175 | 0.0000 | 0.5634 | 0.5634 | 0.5178 | 0.0055 | [+0.0032, +0.0338] | 0.000205 | +0.0521 |
| ridge-own | 0.018299 | 0.012660 | +0.0056 | −0.0122 | 0.5688 | 0.5634 | 0.4157 | 0.3264 | [−0.0166, +0.0292] | 0.001799 | −0.0042 |
| ridge-full | 0.018839 | 0.013062 | −0.0540 | −0.0728 | 0.5562 | 0.5634 | 0.6509 | 0.8671 | [−0.1548, +0.0419] | 0.005946 | +0.0493 |
| LSTM stationary | 0.018258 | 0.012594 | +0.0100 | −0.0076 | 0.5489 | 0.5634 | 0.7674 | 0.3287 | [−0.0349, +0.0546] | 0.003155 | +0.0576 |

Hold-out (n = 210):

| Model | RMSE | MAE | R² vs zero | R² vs hist-mean | Dir acc | Up rate | Binom p vs base | DM p (1-sided) | Bootstrap R² 95% CI | sd(pred) | corr |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|
| persistence | 0.026545 | 0.016507 | 0.0000 | −0.0067 | 0.0238 | 0.5143 | 1.0000 | — | [0.0000, 0.0000] | 0.000000 | — |
| hist-mean | 0.026457 | 0.016780 | +0.0066 | 0.0000 | 0.5143 | 0.5143 | 0.5278 | 0.2428 | [−0.0116, +0.0287] | 0.000000 | +0.0000 |
| ridge-own | 0.026704 | 0.016953 | −0.0120 | −0.0188 | 0.5000 | 0.5143 | 0.6857 | 0.7966 | [−0.0327, +0.0119] | 0.002091 | −0.0763 |
| ridge-full | 0.026764 | 0.017791 | −0.0166 | −0.0234 | 0.4619 | 0.5143 | 0.9438 | 0.6747 | [−0.1312, +0.0639] | 0.006475 | +0.0786 |
| LSTM stationary | 0.026575 | 0.017054 | −0.0023 | −0.0090 | 0.5286 | 0.5143 | 0.3652 | 0.5283 | [−0.0683, +0.0657] | 0.003238 | +0.0243 |

### 2.5 V3 (block excluded) — full tables

V3 has no legacy-spec LSTM. Walk-forward (n = 300; the LSTM covers 271 rows because the first
29 post-block rows lack a 30-row same-segment context):

| Model | RMSE | MAE | R² vs zero | R² vs hist-mean | Dir acc | Up rate | Binom p vs base | DM p (1-sided) | Bootstrap R² 95% CI | sd(pred) | corr |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|
| persistence | 0.021282 | 0.013113 | 0.0000 | −0.0062 | 0.1100 | 0.4833 | 1.0000 | — | [0.0000, 0.0000] | 0.000000 | — |
| hist-mean | 0.021216 | 0.013289 | +0.0062 | 0.0000 | 0.4833 | 0.4833 | 0.5228 | 0.1419 | [−0.0078, +0.0197] | 0.000587 | −0.1188 |
| ridge-own | 0.021249 | 0.013376 | +0.0031 | −0.0031 | 0.4267 | 0.4833 | 0.9786 | 0.4168 | [−0.0168, +0.0357] | 0.002231 | +0.0191 |
| ridge-full | 0.023846 | 0.014973 | −0.2555 | −0.2633 | 0.4467 | 0.4833 | 0.9081 | 0.9716 | [−0.4209, −0.0143] | 0.011818 | +0.0933 |
| LSTM stationary | 0.021475 | 0.013229 | +0.0061 | +0.0024 | 0.4059 | 0.4649 | 0.9781 | 0.3012 | [−0.0166, +0.0411] | 0.001646 | +0.0280 |

Hold-out (n = 210):

| Model | RMSE | MAE | R² vs zero | R² vs hist-mean | Dir acc | Up rate | Binom p vs base | DM p (1-sided) | Bootstrap R² 95% CI | sd(pred) | corr |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|
| persistence | 0.026545 | 0.016507 | 0.0000 | −0.0065 | 0.0238 | 0.5143 | 1.0000 | — | [0.0000, 0.0000] | 0.000000 | — |
| hist-mean | 0.026460 | 0.016749 | +0.0064 | 0.0000 | 0.5143 | 0.5143 | 0.5278 | 0.2250 | [−0.0098, +0.0262] | 0.000000 | +0.0000 |
| ridge-own | 0.026829 | 0.017082 | −0.0215 | −0.0281 | 0.5095 | 0.5143 | 0.5823 | 0.8567 | [−0.0525, +0.0149] | 0.003004 | −0.0638 |
| ridge-full | 0.027296 | 0.018633 | −0.0574 | −0.0642 | 0.4810 | 0.5143 | 0.8498 | 0.8426 | [−0.2674, +0.0854] | 0.009681 | +0.0950 |
| LSTM stationary | 0.026676 | 0.017421 | −0.0099 | −0.0164 | 0.5476 | 0.5143 | 0.1848 | 0.6357 | [−0.0829, +0.0501] | 0.003307 | +0.0045 |

---

## 3. V1 / V2 / V3 sensitivity — does the correction change a conclusion?

### 3.1 V1 vs V2

V1 and V2 share the same Iranian target and the same fold rows; they differ in the global
pairing inside the block (V2 re-pairs it). The baselines and ridge-own are identical by
construction. The full-feature models move only marginally:

| V2 vs V1 | Walk-forward RMSE | Hold-out RMSE | Walk-forward R² | Hold-out R² |
|---|---|---|---:|---:|
| persistence | 0.018350 vs 0.018350 | 0.026545 vs 0.026545 | 0.0000 vs 0.0000 | 0.0000 vs 0.0000 |
| hist-mean | 0.018188 vs 0.018188 | 0.026457 vs 0.026457 | +0.0175 vs +0.0175 | +0.0066 vs +0.0066 |
| ridge-own | 0.018299 vs 0.018299 | 0.026704 vs 0.026704 | +0.0056 vs +0.0056 | −0.0120 vs −0.0120 |
| ridge-full | 0.018846 vs 0.018839 | 0.026798 vs 0.026764 | −0.0548 vs −0.0540 | −0.0192 vs −0.0166 |
| LSTM stationary | 0.018214 vs 0.018258 | 0.026543 vs 0.026575 | +0.0148 vs +0.0100 | +0.0001 vs −0.0023 |

The largest relative move is the stationary LSTM's walk-forward RMSE: −0.24%. Every difference
is far inside the bootstrap CI. **V1 vs V2 changes no conclusion.** The block correction is a
data-integrity fix, not a performance fix.

### 3.2 V3 block excluded

V3 removes 503 of 1,364 feature rows and leaves 650 pre-hold-out rows. Its walk-forward test
period is therefore mostly 2022–2023, a different regime; its RMSE is not directly comparable to
V1/V2. The V3 hold-out is the same 2025-10-01 → 2026-06-11 period, so that column is comparable.

| V3 vs V2 | Walk-forward (V3 n=300) | Hold-out (n=210) |
|---|---:|---:|
| persistence RMSE | 0.021282 vs 0.018350 | 0.026545 vs 0.026545 |
| hist-mean RMSE | 0.021216 vs 0.018188 | 0.026460 vs 0.026457 |
| ridge-own RMSE | 0.021249 vs 0.018299 | 0.026829 vs 0.026704 |
| ridge-full RMSE | 0.023846 vs 0.018846 | 0.027296 vs 0.026798 |
| LSTM stationary RMSE | 0.021475 vs 0.018214 | 0.026676 vs 0.026543 |
| LSTM stationary n | 271 vs 552 | 210 vs 210 |
| LSTM stationary R² | +0.0061 vs +0.0148 | −0.0099 vs +0.0001 |

The V3 walk-forward up-day rate is 48.3% (below 50%), and persistence's directional accuracy is
11.0% because it matches the many exact zero returns in the pre-block data. The hist-mean's
directional accuracy is exactly the up rate (48.3%). No model has a significant DM vs
persistence. **V3 changes no conclusion**, and it makes the full-feature ridge worse, not better.
V3 is a sensitivity check, not a clean block ablation: it also removes 36% of the rows and
changes the training period, so the sample-size and regime effects are confounded with the block
exclusion.

**V3 LSTM coverage:** 271 of 300 walk-forward test rows. The 29 missing rows are the first
post-block rows, which have fewer than 30 same-segment rows of context. The hold-out coverage is
210/210. This was anticipated in the protocol.

---

## 4. Legacy-spec vs stationary-spec (V2)

The legacy spec uses the old 15 raw-level features (`SMA_7`, `MACD`, `Bollinger_Upper/Lower`,
etc.) and same-day global returns. It is **not** information-timing-honest; it is included only
to show the effect of feature design.

| V2 LSTM | Walk-forward RMSE | Walk-forward R² | Walk-forward DM p | Hold-out RMSE | Hold-out R² | Hold-out DM p |
|---|---:|---:|---:|---:|---:|---:|
| stationary (23 features) | **0.018214** | **+0.0148** | 0.2251 | **0.026543** | **+0.0001** | 0.4984 |
| legacy (15 raw-level) | 0.018243 | +0.0116 | 0.1337 | 0.026631 | −0.0065 | 0.7153 |

The legacy spec is not better. It is slightly worse on the hold-out (R² −0.0065 vs +0.0001) and
essentially tied on the walk-forward. Its hold-out directional accuracy is 47.6%, below the
51.4% up rate (i.e. worse than always-up). Both predictors are near-constant: prediction sd is
0.0017–0.0033 against an actual sd of 0.0182–0.0265.

This is consistent with the audit's old log-return result (R² −0.0016, corr −0.017, directional
55.4%, DM p 0.79 on the old test split). The old model's price-level R² of 0.97 was
persistence-equivalent; the log-return predictability is near zero in both feature designs.
**Feature design alone does not create an edge.**

---

## 5. Cost sanity — break-even directional accuracy

`break-even accuracy = 0.5 · (1 + cost / E|y|)`, with `E|y|` the mean absolute daily log move.
This is a sanity check, not a backtest: one position per day, symmetric moves, no slippage, no
compounding.

| Variant / sample | E\|y\| | Break-even at 1.5% | Break-even at 3.0% | Observed dir. accuracy |
|---|---:|---:|---:|---:|
| V2 walk-forward | 0.012728 | **1.0892 (108.9%)** | **1.6785 (167.8%)** | 0.5616 (LSTM) |
| V2 hold-out | 0.016507 | **0.9543 (95.4%)** | **1.4087 (140.9%)** | 0.5143 (LSTM) |
| V1 walk-forward | 0.012728 | 1.0892 | 1.6785 | 0.5489 (LSTM) |
| V1 hold-out | 0.016507 | 0.9543 | 1.4087 | 0.5286 (LSTM) |
| V3 walk-forward | 0.013113 | 1.0720 | 1.6439 | 0.4059 (LSTM, n=271) |
| V3 hold-out | 0.016507 | 0.9543 | 1.4087 | 0.5476 (LSTM) |

At 1.5% round-trip cost the break-even accuracy is 95–109%; at 3% it is 141–168%. The observed
directional accuracy is 51–57% (and equals or is below the up-day base rate in the primary
spec). The 1.5% cost is roughly the entire average absolute daily move (1.27% walk-forward,
1.65% hold-out); the 3% cost is larger than the average move. A daily strategy at these costs
would need to be right on almost every day just to break even. No trading simulation is run in
Stage 3.

---

## 6. Edge verdict under the pre-registered rule

Rule (`docs/EVAL_PROTOCOL.md` §8): an eligible V2 stationary model must beat persistence on OOS
RMSE **and** have a one-sided DM p < 0.05, on **both** the pooled walk-forward and the hold-out,
**and** a bootstrap 95% CI on OOS R² with a lower bound > 0 on both samples.

| Criterion | ridge-own | ridge-full | LSTM stationary |
|---|---|---|---|
| WF RMSE < persistence | ✅ (0.018299 < 0.018350) | ❌ (0.018846) | ✅ (0.018214) |
| WF DM p < 0.05 | ❌ (0.3264) | ❌ (0.8596) | ❌ (0.2251) |
| HO RMSE < persistence | ❌ (0.026704) | ❌ (0.026798) | ✅ (0.026543 vs 0.026545) |
| HO DM p < 0.05 | ❌ (0.7966) | ❌ (0.7018) | ❌ (0.4984) |
| WF bootstrap R² lower bound > 0 | ❌ (−0.0166) | ❌ (−0.1638) | ❌ (−0.0272) |
| HO bootstrap R² lower bound > 0 | ❌ (−0.0327) | ❌ (−0.1345) | ❌ (−0.0577) |
| **Passes all** | **No** | **No** | **No** |

**Verdict: no demonstrated edge.** The historical-mean drift is not an eligible model under the
rule (it is the benchmark), but it is worth naming: it is the only model with a significant
walk-forward DM vs persistence (p = 0.0055, CI [+0.0032, +0.0338]), and it fails on the hold-out
(p = 0.2428, CI [−0.0116, +0.0287]). That is the nominal uptrend, not timing skill.

Multiple-comparison disclosure: three eligible models were checked. A Bonferroni threshold would
be 0.05/3 ≈ 0.0167; no model meets even the unadjusted 0.05 DM condition together with the other
criteria.

---

## 7. What the numbers do and do not show

### 7.1 Sample size and statistical power

The walk-forward has 552 out-of-sample rows (V1/V2) and the hold-out has 210. The DM test on 210
rows has limited power: only a large, consistent improvement would be detectable. The bootstrap
CIs are wide — the stationary LSTM's hold-out R² CI is [−0.058, +0.063]. **"No demonstrated
edge" is not "proven no edge."** We cannot rule out a small edge. What the data do rule out is
an edge large enough to matter at 1.5–3% costs: the observed accuracy is 51–57%, while the
break-even accuracy is 95–168%. The result is informative about the cost hurdle, not about
whether a tiny, statistically undetectable edge exists.

### 7.2 The regime problem in Iran, 2021–2026

The sample spans the 2021–2022 gold rally, the 2023-10 → 2025-08 block, currency/devaluation
episodes, and the 2025-10 → 2026-06 hold-out. The relationship between global gold, USD/IRR and
Iranian gold is not stable. The V3 sensitivity makes this visible: excluding the block changes
the walk-forward period and the sample size, and the full-feature ridge goes from R² −0.055 (V2)
to −0.255 (V3), while the historical mean's DM p goes from 0.0055 to 0.1419. That is regime
sensitivity confounded with sample size, not a clean block effect. The hold-out is a different
period from the training data; the LSTM's near-zero predictions and 0.038 correlation with
actuals show it has not learned a stable mapping.

### 7.3 The nominal series trends upward — why directional accuracy is misleading

The gold price in Rial trends strongly upward over this sample. The up-day base rate is **56.3%
in the walk-forward** and **51.4% in the hold-out**. A constant-up predictor therefore gets
56.3% / 51.4% directional accuracy without any timing skill. The historical-mean model's
directional accuracy is exactly the base rate (0.5634 / 0.5143), and its binomial p vs the base
rate is 0.518 / 0.528 — not significant. The stationary LSTM's 0.5616 / 0.5143 is at or below
the base rate (p vs base rate 0.552 / 0.528). Ridge-own's 0.5688 walk-forward is slightly above
the base rate, but its p vs base rate is 0.416. Comparing any of these to 50% would falsely
suggest skill. Comparing to the base rate and always-up shows none. The only significant DM vs
persistence is the historical mean's walk-forward drift (p = 0.0055), and that is the uptrend,
not timing; it fails on the hold-out.

### 7.4 What the block correction did and did not do

V1 vs V2 changes the global pairing inside the block but leaves the Iranian target and the fold
rows unchanged. The results are nearly identical: the stationary LSTM's walk-forward RMSE moves
from 0.018258 to 0.018214 (−0.24%), the hold-out from 0.026575 to 0.026543 (−0.12%); ridge-own
and the baselines are identical. The edge verdict is unchanged. **The block was a real
data-integrity defect, but it was not the source of the model's failure.** This contradicts the
implicit hope that correcting the block would produce a signal. The correction should be judged
on data-quality grounds, not on model performance.

### 7.5 What would have to be true for an edge

A stable, economically motivated relationship between the global and Iranian series; a larger
sample with more independent regimes; a lower-cost trading venue; or a different target
(volatility, relative value, a longer horizon) where the signal-to-noise ratio is higher. None
of these is tested here. This is a negative result about **next-day directional return
prediction at daily frequency**, not a claim that gold/USD/oil information is never useful.

---

## 8. Protocol deviations

**One pre-run amendment, no post-run deviations.**

- **Hold-out definition (pre-run, `cb75162`).** The first draft said "the final 180 rows". A
  data-shape check showed those begin 2025-11-05 and would skip October. The hold-out is
  therefore all rows dated 2025-10-01 or later — 210 rows, matching the requested "~180 rows,
  2025-10 onward". The amendment was made **before any model fit**; no result was seen.
- **Implementation file names.** The old `docs/PLAN.md` Stage 3 text named
  `src/features_stationary.py`, `src/walkforward.py`, `scripts/run_eval.py` and `reports/`.
  The implementation uses `src/feature_eng.py::add_stationary_features`, `src/eval_data.py`,
  `src/eval_metrics.py`, `src/evaluate.py` and `results/`. This is the owner's Stage 3
  instruction ("e.g. `src/evaluate.py` plus whatever modules you need"), recorded here so the
  plan and the tree agree.
- **`make eval` / `scripts/check_eval.py`.** These were in the old Stage 3 acceptance text but
  belong to Stage 5 (Makefile and scripts). The runnable entry point is
  `python -m src.evaluate --variant all --artifact`; it exits 0 and writes the committed
  JSON/CSV/log.
- **Global series vintage.** The protocol §2.3 fixed the use of one complete Yahoo pull for all
  variants because the CSV lacks 110 corrected-date global bars. This is a data-construction
  decision, not a post-hoc deviation.
- **Optional same-day global sensitivity was not run.** The protocol allowed it as a labelled
  sensitivity only; it is not part of the headline, and the one-day global lag is the
  pre-registered primary spec. Its absence does not affect the edge verdict.

---

## 9. Reproduce

```bash
# Single variant (the entry point requested by the Stage 3 instruction)
.venv/bin/python -m src.evaluate --variant V2

# Full protocol (writes results/ and the primary artifact)
.venv/bin/python -m src.evaluate --variant all --artifact

# Tests (pytest is not installed in .venv; use a scratch environment)
PYTHONPATH="$PWD/.venv/lib/python3.12/site-packages:$PWD" \
  /tmp/pytest-scratch/bin/python -m pytest tests/ test_pipeline.py -q
```

Inputs: the untracked local snapshot `data/raw/final_gold_dataset.csv` and the cached
`data/raw/global_yahoo.csv`. The repository does not redistribute the full raw series (D14).
Outputs: `results/eval_V1.json`, `results/eval_V2.json`, `results/eval_V3.json`,
`results/eval_summary.csv`, `results/run.log`; `models/gold_lstm_stationary_v2.keras`,
`models/scaler_X_stationary_v2.pkl`, `models/scaler_y_stationary_v2.pkl`,
`models/gold_lstm_stationary_v2.metadata.json`.

Tests: **35 passed** (15 new protocol tests + 6 date-shift tests + 14 pipeline tests).

---

## 10. Raw outputs

V2 console output (from `results/run.log`):

```text
Variant V2
V2 prices: 1424 rows, 2021-06-14..2026-06-13, relabelled=503
V2 stationary frame: 1364 rows; pre=1154 holdout=210 (2025-10-01..2026-06-11); folds=5
  fold 1: train 2021-08-28..2023-08-07 (547), test 2023-09-21..2024-02-04 (111)
  fold 2: train 2021-08-28..2023-12-30 (663), test 2024-02-13..2024-07-08 (111)
  fold 3: train 2021-08-28..2024-05-29 (779), test 2024-07-17..2024-11-28 (110)
  fold 4: train 2021-08-28..2024-10-24 (894), test 2024-12-07..2025-04-27 (110)
  fold 5: train 2021-08-28..2025-03-12 (1009), test 2025-05-04..2025-09-30 (110)
  WF persistence      n= 552 rmse=0.018350 r2=+0.0000 dm_p=nan dir=0.0091
  WF histmean         n= 552 rmse=0.018188 r2=+0.0175 dm_p=0.0055 dir=0.5634
  WF ridge_own        n= 552 rmse=0.018299 r2=+0.0056 dm_p=0.3264 dir=0.5688
  WF ridge_full       n= 552 rmse=0.018846 r2=-0.0548 dm_p=0.8595 dir=0.5598
  WF lstm_stationary  n= 552 rmse=0.018214 r2=+0.0148 dm_p=0.2251 dir=0.5616
  WF lstm_legacy      n= 552 rmse=0.018243 r2=+0.0116 dm_p=0.1337 dir=0.5489
  HO persistence      n= 210 rmse=0.026545 r2=+0.0000 dm_p=nan dir=0.0238
  HO histmean         n= 210 rmse=0.026457 r2=+0.0066 dm_p=0.2428 dir=0.5143
  HO ridge_own        n= 210 rmse=0.026704 r2=-0.0120 dm_p=0.7966 dir=0.5000
  HO ridge_full       n= 210 rmse=0.026798 r2=-0.0192 dm_p=0.7018 dir=0.4571
  HO lstm_stationary  n= 210 rmse=0.026543 r2=+0.0001 dm_p=0.4984 dir=0.5143
  HO lstm_legacy      n= 210 rmse=0.026631 r2=-0.0065 dm_p=0.7153 dir=0.4762
Variant V2 finished in 612.1 s
```

V1 and V3 walk-forward / hold-out summary lines:

```text
Variant V1
  WF persistence      n= 552 rmse=0.018350 r2=+0.0000 dm_p=nan dir=0.0091
  WF histmean         n= 552 rmse=0.018188 r2=+0.0175 dm_p=0.0055 dir=0.5634
  WF ridge_own        n= 552 rmse=0.018299 r2=+0.0056 dm_p=0.3264 dir=0.5688
  WF ridge_full       n= 552 rmse=0.018839 r2=-0.0540 dm_p=0.8671 dir=0.5562
  WF lstm_stationary  n= 552 rmse=0.018258 r2=+0.0100 dm_p=0.3287 dir=0.5489
  HO persistence      n= 210 rmse=0.026545 r2=+0.0000 dm_p=nan dir=0.0238
  HO histmean         n= 210 rmse=0.026457 r2=+0.0066 dm_p=0.2428 dir=0.5143
  HO ridge_own        n= 210 rmse=0.026704 r2=-0.0120 dm_p=0.7966 dir=0.5000
  HO ridge_full       n= 210 rmse=0.026764 r2=-0.0166 dm_p=0.6747 dir=0.4619
  HO lstm_stationary  n= 210 rmse=0.026575 r2=-0.0023 dm_p=0.5283 dir=0.5286
Variant V1 finished in 357.5 s

Variant V3
  WF persistence      n= 300 rmse=0.021282 r2=+0.0000 dm_p=nan dir=0.1100
  WF histmean         n= 300 rmse=0.021216 r2=+0.0062 dm_p=0.1419 dir=0.4833
  WF ridge_own        n= 300 rmse=0.021249 r2=+0.0031 dm_p=0.4168 dir=0.4267
  WF ridge_full       n= 300 rmse=0.023846 r2=-0.2555 dm_p=0.9716 dir=0.4467
  WF lstm_stationary  n= 271 rmse=0.021475 r2=+0.0061 dm_p=0.3012 dir=0.4059
  HO persistence      n= 210 rmse=0.026545 r2=+0.0000 dm_p=nan dir=0.0238
  HO histmean         n= 210 rmse=0.026460 r2=+0.0064 dm_p=0.2250 dir=0.5143
  HO ridge_own        n= 210 rmse=0.026829 r2=-0.0215 dm_p=0.8567 dir=0.5095
  HO ridge_full       n= 210 rmse=0.027296 r2=-0.0574 dm_p=0.8426 dir=0.4810
  HO lstm_stationary  n= 210 rmse=0.026676 r2=-0.0099 dm_p=0.6357 dir=0.5476
Variant V3 finished in 273.9 s
```

Edge verdict (from `results/eval_V2.json`):

```json
{
  "rule": "docs/EVAL_PROTOCOL.md §8",
  "eligible_models": [
    "ridge_own",
    "ridge_full",
    "lstm_stationary"
  ],
  "criteria": {
    "ridge_own": {
      "wf_rmse_below_persistence": true,
      "wf_dm_p_one_sided_lt_005": false,
      "ho_rmse_below_persistence": false,
      "ho_dm_p_one_sided_lt_005": false,
      "wf_boot_r2_lo_gt_zero": false,
      "ho_boot_r2_lo_gt_zero": false,
      "passes": false
    },
    "ridge_full": {
      "wf_rmse_below_persistence": false,
      "wf_dm_p_one_sided_lt_005": false,
      "ho_rmse_below_persistence": false,
      "ho_dm_p_one_sided_lt_005": false,
      "wf_boot_r2_lo_gt_zero": false,
      "ho_boot_r2_lo_gt_zero": false,
      "passes": false
    },
    "lstm_stationary": {
      "wf_rmse_below_persistence": true,
      "wf_dm_p_one_sided_lt_005": false,
      "ho_rmse_below_persistence": true,
      "ho_dm_p_one_sided_lt_005": false,
      "wf_boot_r2_lo_gt_zero": false,
      "ho_boot_r2_lo_gt_zero": false,
      "passes": false
    }
  },
  "edge_demonstrated": false,
  "finding": "no demonstrated edge"
}
```

Tests:

```text
platform linux -- Python 3.12.3, pytest-9.2.0, pluggy-1.7.0
collected 35 items
tests/test_data_loader_date_shift.py ......                              [ 17%]
tests/test_eval_protocol.py ...............                              [ 60%]
test_pipeline.py ..............                                          [100%]
============================= 35 passed in 10.16s ==============================
```

---

## 11. Economic reality (Stage 4)

**Protocol:** `docs/BACKTEST_PROTOCOL.md` (`0cc0647`), pre-registered before any backtest
result. **Run:** `python -m src.backtest_check`, code `9b9caca`, 2026-11-16, inference only
(no training). **Results:** `results/backtest.json`, `results/backtest.log`.

### 11.1 What was tested

- **Hold-out only:** 210 rows, 2025-10-01 → 2026-06-11; 210 close-to-close returns through the
  2026-06-13 close.
- **Predictions:** the committed **seed-42 artifact only**, by inference. Stage 3 saved
  aggregate metrics but no per-row predictions, so per-seed and 5-seed tables are not
  recoverable without retraining; they are dropped. Seed 42 was fixed before the Stage 3 run
  (`PRIMARY_SEED = 42`, `8d7715e`), not chosen after seeing the hold-out.
- **Strategies (long/flat, no shorting):** S0 buy-and-hold gold (Rial); S1 buy-and-hold USD
  (Rial); S2 long iff `ŷ > μ_train`; S3 long iff `ŷ > 0`. `μ_train = 0.1561%` is the mean log
  return over the 951 fitting rows (2021-08-28 → 2024-12-31).
- **Costs per side:** C0 0%, C1 0.35% (0.7% round trip), C2 0.75% (1.5% round trip), C3 1.5%
  (3% round trip). C2 is the pre-registered decision cost. The old `trading_bot/` backtest used
  0.7% per side (1.4% round trip); C1 is half that, and C2/C3 follow the Stage 3 break-even
  analysis (§5).
- **Annualisation:** 252 days. **Bootstrap:** moving-block, block 10, 10,000 draws, seed
  20261116, percentile 95% CI.

### 11.2 Is the model still near-constant?

| Hold-out statistic | Stage 3 5-seed mean | seed-42 artifact |
|---|---:|---:|
| n | 210 | 210 |
| RMSE | 0.026543 | 0.026540 |
| R² vs zero | +0.000119 | +0.000367 |
| corr(pred, actual) | +0.0381 | +0.0312 |
| std(pred) | 0.003304 | 0.002482 |
| std(actual) | 0.026456 | 0.026456 |
| mean(pred) | — | +0.0621% |
| share pred > 0 | — | 59.0% |
| share pred > `μ_train` | — | 33.8% |

The model is still **near-constant**: prediction sd is **9.4%** of actual sd for seed 42 and
**12.5%** for the 5-seed mean; correlation is +0.031 / +0.038. Seed 42 is **typical, not
materially stronger**: its RMSE is 0.012% lower than the 5-seed mean (0.026540 vs 0.026543) and
its R² is +0.000367 vs +0.000119, but its correlation is lower (+0.031 vs +0.038) and its
predictions are less dispersed. All of these are statistically indistinguishable from zero; the
backtest must not be read as a better model than the Stage 3 evaluation.

Because the prediction varies slightly, S3 is **not** identical to buy-and-hold: it is long on
124 of 210 days (59.0%), and S2 on 71 of 210 (33.8%). Each rule changes position 14 times.

### 11.3 Total return by strategy and cost

| Strategy | C0 0% | C1 0.35%/side | C2 0.75%/side | C3 1.5%/side |
|---|---:|---:|---:|---:|
| S0 buy-and-hold gold (Rial) | +57.89% | +57.34% | +56.71% | +55.52% |
| S1 buy-and-hold USD (Rial) | +49.00% | +48.48% | +47.89% | +46.77% |
| S2 LSTM `> μ_train` | +12.37% | +6.99% | +1.13% | -9.06% |
| S3 LSTM `> 0` | +52.12% | +44.83% | +36.90% | +23.11% |

The final equity multiple is 1 + the percentage (e.g. S3 at C2 = 1.3690).

### 11.4 Full metrics at 0% and 0.75%/side

At **C0 (0%)**:

| Strategy | Total | Ann. return | Ann. vol | Max DD | Changes | Share long | Multiple |
|---|---:|---:|---:|---:|---:|---:|---:|
| S0 | +57.89% | +73.00% | +41.61% | -19.47% | 1 | +100.0% | 1.5789 |
| S1 | +49.00% | +61.38% | +30.12% | -13.63% | 1 | +100.0% | 1.4900 |
| S2 | +12.37% | +15.02% | +30.16% | -24.43% | 14 | +33.8% | 1.1237 |
| S3 | +52.12% | +65.43% | +33.85% | -23.56% | 14 | +59.0% | 1.5212 |

At **C2 (0.75% per side, 1.5% round trip)**:

| Strategy | Total | Ann. return | Ann. vol | Max DD | Changes | Share long | Multiple |
|---|---:|---:|---:|---:|---:|---:|---:|
| S0 | +56.71% | +71.44% | +41.59% | -19.47% | 1 | +100.0% | 1.5671 |
| S1 | +47.89% | +59.92% | +30.08% | -13.63% | 1 | +100.0% | 1.4789 |
| S2 | +1.13% | +1.36% | +30.50% | -25.56% | 14 | +33.8% | 1.0113 |
| S3 | +36.90% | +45.78% | +34.12% | -24.70% | 14 | +59.0% | 1.3690 |

### 11.5 Bootstrap: difference in mean daily net return vs S0

| Cost | S2 diff (bp/day) | 95% CI | S3 diff (bp/day) | 95% CI |
|---|---:|---|---:|---|
| C0 | -17.83 | [-40.54, -3.08] | -2.93 | [-18.31, +6.96] |
| C1 | -19.99 | [-42.97, -5.31] | -5.09 | [-20.82, +4.55] |
| C2 | -22.45 | [-45.45, -7.89] | -7.56 | [-23.96, +2.01] |
| C3 | -27.06 | [-50.87, -12.29] | -12.19 | [-29.82, -2.38] |

1 bp = 0.01%. S2 is significantly worse than S0 at every cost, including 0%. S3 is not
distinguishable from S0 at C0–C2; at C3 it is significantly worse.

### 11.6 One-day execution delay

| Rule | C0 primary | C0 delay | C2 primary | C2 delay |
|---|---:|---:|---:|---:|
| S2 | +12.37% | +8.96% | +1.13% | -1.94% |
| S3 | +52.12% | +53.84% | +36.90% | +38.46% |

At C2 with the delay, S2's mean difference vs S0 is -23.93 bp/day, CI [-50.66, -5.19]; S3's is
-6.90 bp/day, CI [-24.20, +4.11]. The delay does not change the verdict. S3's total is slightly
higher with the delay (+38.46% vs +36.90% at C2) because the shifted series trades a different
set of days; the difference is small and the comparison with S0 is still statistically
indistinguishable.

### 11.7 Gold in USD (currency-neutral reference)

| Series | Total | Ann. return | Ann. vol | Max DD | Multiple |
|---|---:|---:|---:|---:|---:|
| Gold in USD (`Gold_IRR / USD_IRR`), gross | +5.97% | +7.20% | +26.95% | -23.78% | 1.0597 |
| S0 nominal gold (Rial), gross | +57.89% | +73.00% | +41.61% | -19.47% | 1.5789 |
| S1 USD (Rial), gross | +49.00% | +61.38% | +30.12% | -13.63% | 1.4900 |

Nominal gold rose 57.9% while gold in USD rose 6.0%; the gap is the Rial's devaluation
(USD/IRR +49.0%). **No inflation series exists in the repository.** Gold-in-USD is the available
currency-neutral proxy, **not** an inflation-adjusted real return. The nominal strategy numbers
are inflated by devaluation and must not be read as real purchasing-power gains.

### 11.8 Verdict under the pre-registered rule

Rule (`docs/BACKTEST_PROTOCOL.md` §7): at C2 (0.75%/side, 1.5% round trip), a strategy adds
value only if its mean daily net return is higher than S0's **and** the 95% block-bootstrap CI
for the difference excludes zero.

| Candidate | Mean diff (bp/day) | 95% CI (bp/day) | Adds value? |
|---|---:|---|---|
| S2 | -22.45 | [-45.45, -7.89] | **No** — significantly worse |
| S3 | -7.56 | [-23.96, +2.01] | **No** — CI includes zero |

**Finding: no added value over buy-and-hold.** S2 destroys value; S3's point estimate is
negative and its CI includes zero. Neither passes.

### 11.9 Plain-language reading

- **Why daily trading cannot pay 1.5% round-trip costs.** Each rule changes position 14 times
  (about seven round trips). At C2 the simple sum is 14 × 0.75% ≈ 10.5% of notional; the
  compounded effect is larger (15.2 points for S3, 11.2 for S2) because each cost is charged on
  the then-current equity. S3 falls from +52.12% gross to +36.90% net; S2 from +12.37% to
  +1.13%. At C3, S2 turns negative (-9.06%) and S3 keeps only +23.11%. The average absolute
  daily move on the hold-out is 1.65% (§5), so a 1.5% round trip is about **one day's average
  move**; a rule that trades 14 times pays that average move seven times over.
- **What the nominal uptrend does to any long-biased rule.** S0 is a hard benchmark. S3 is long
  59% of days and ends 5.8 points behind S0 gross (52.12% vs 57.89%); costs take another 15.2
  points. S2 is long only 34% and ends 45.5 points behind gross; it is significantly worse than
  S0 even before costs. Any long-biased rule inherits the trend; none of this is timing skill.
- **What the numbers cannot tell us.** Whether another threshold, horizon, asset or venue would
  work (not tested; post-hoc search is out of scope); whether the model has a tiny, undetectable
  edge (Stage 3 says "no demonstrated edge", not "proven no edge"); whether inflation-adjusted
  returns are positive (no CPI series; gold-in-USD is the proxy); anything about future
  performance. The sample is 210 rows in one strongly trending regime, so the power to detect a
  small edge is low.

### 11.10 The one-label overlap and the touch count

- The Stage 3 stationary LSTM hold-out headline and the seed-42 artifact both used an
  early-stopping validation tail whose last label is the 2025-10-01 return (1 of 173 labels,
  +2.15%, about 0.50% of validation MSE). No hold-out feature row is in fitting or validation,
  and the scalers are fit only through 2024-12-31. The overlap can only favor the model
  slightly; it cannot change the verdict. Full record: `docs/EVAL_PROTOCOL.md` §11 D-1.
- **Touch count:** Stage 3 scored the hold-out three times (V1/V2/V3) and the artifact code
  predicted it once without scoring. Stage 4 added two inference-only passes (a development run
  and the final run, identical outputs). Total **six prediction passes, three scored**, none
  re-run after a result. The pre-registered promise was "touched once"; it was **not literally
  met**, though no scored pass was re-run after its result.

### 11.11 Reproduce

```bash
.venv/bin/python -m src.backtest_check
PYTHONPATH="$PWD/.venv/lib/python3.12/site-packages:$PWD" \
  /tmp/pytest-scratch/bin/python -m pytest tests/ test_pipeline.py -q
```

Tests: **44 passed** (9 new backtest tests + 35 existing).

---

## 12. Post-release note (Stage 5b, 2026-11-17)

The headline numbers above **predate** the opt-in `--save-predictions` flag added to
`src/evaluate.py` in Stage 5b. The flag was not used for any committed result: `results/*.json`
still contains aggregate metrics only, and no result file was re-run or overwritten.

- `python -m src.evaluate ... --save-predictions --out-dir <dir>` additionally writes
  `<dir>/predictions/<variant>_<sample>.csv` with `variant, sample, model, date, y_true, y_pred`.
  It is opt-in, and `results/predictions/` is gitignored.
- A scratch smoke run (`--variant V2 --seeds 1 --epochs 1 --skip-legacy --out-dir /tmp/s5b-smoke`)
  verified the flag: 2,760 walk-forward rows (5 models × 552) and 1,050 hold-out rows
  (5 × 210). Its model metrics are **not** comparable to the headline: one seed and one epoch
  are a wiring check, not an evaluation.
- The suite moved to a single command in Stage 5b. The reproduce command in §9 and §11.11 is
  historical; the current command is `python -m pytest` from the repository root, which collects
  every test module under `tests/` (the old root `test_pipeline.py` was moved there).
