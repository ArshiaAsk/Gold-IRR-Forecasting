# Backtest Protocol — Stage 4 "economic reality" (pre-registered)

**Status:** written and committed **before** any backtest result was computed. The commit that
adds this file precedes `src/backtest_check.py` and `results/backtest.*`.
**Branch:** `refactor/honest-portfolio` · **Baseline tag:** `legacy-pre-refactor`
**Purpose:** quantify what a daily long/flat rule driven by the Stage 3 model would have earned
on the hold-out, after costs, against simple benchmarks — so the README can state the economic
conclusion with numbers.
**Related:** `docs/EVAL_PROTOCOL.md` (Stage 3, including its §11 D-1 deviation),
`docs/RESULTS.md` (measured Stage 3 results).

This document is deliberately rigid. The strategies, costs, metrics, bootstrap and decision
rule below are fixed now. Anything changed after a result is seen goes under **Deviations** at
the end, with its own commit; nothing is changed silently.

---

## 1. Purpose (what this is and is not)

This is **not** a search for a profitable strategy. It is an accounting exercise: take the
predictions the Stage 3 model already produced, apply a simple long/flat rule, charge realistic
costs, and compare the result with buy-and-hold gold and buy-and-hold USD. The question is
whether the rule **adds value over buy-and-hold after costs** — not whether some other rule,
threshold, horizon or model could.

The GATE 3 decision makes this final: **"no demonstrated edge"** is the verdict for this
project. No model tuning, new features or new architectures are tried here. Any extra search
after seeing the hold-out would be post-hoc and is out of scope.

---

## 2. Sample and prediction source

### 2.1 Sample

- **Hold-out only:** all 210 feature rows dated **2025-10-01 → 2026-06-11** in the V2
  (date-corrected) frame, the same rows as the Stage 3 hold-out.
- **Traded returns:** 210 close-to-close returns, from the **2025-10-01 close** to the
  **2026-06-13 close** (the last hold-out row's target is the 2026-06-13 price). The
  2025-09-30 → 2025-10-01 return is not traded; it is the last pre-hold-out target.
- **Prices:** `Gold_IRR` and `USD_IRR` from the same V2 construction as Stage 3
  (`src.eval_data.build_prices(raw, global_df, "V2")`), not a new data pull. The repository's
  untracked snapshot is the input (D14); `data/raw/global_yahoo.csv` is the cached global
  series.
- No walk-forward period is used. No other sample is used.

### 2.2 Predictions: the committed seed-42 artifact only

Stage 3 saved **aggregate metrics only**. `results/eval_V1.json`, `eval_V2.json` and
`eval_V3.json` contain RMSE, R², DM p-values, bootstrap CIs, `std_pred`, `std_actual` and
`corr`, but **no per-row prediction series**. The only persisted model is the committed
artifact:

```
models/gold_lstm_stationary_v2.keras
models/scaler_X_stationary_v2.pkl
models/scaler_y_stationary_v2.pkl
models/gold_lstm_stationary_v2.metadata.json
```

Therefore:

- **Only the seed-42 artifact is evaluated.** Predictions are produced by **inference only**
  (`model.predict` on the 210 hold-out windows). No fitting, no re-tuning, no new seed.
- **Per-seed tables and the 5-seed mean are not recoverable and are dropped.** The Stage 3
  hold-out headline is a 5-seed average; its per-seed predictions were never written to disk.
  Reproducing them would require re-running the fits, which is prohibited. This is a recorded
  deviation from the Stage 4 instruction, not a silent omission.
- **Seed 42 was fixed before the Stage 3 run**, not chosen after seeing hold-out results:
  `PRIMARY_SEED = 42` is in `src/evaluate.py`, committed at `8d7715e` before the results commit
  (`64c9798`). This is not best-seed selection. It is also the model Stage 5a will serve.

### 2.3 Artifact audit (done 2026-11-16, before inference)

From `models/gold_lstm_stationary_v2.metadata.json` and `src/evaluate.py::_save_artifact`:

| Item | Value |
|---|---|
| Variant / feature spec | V2 (corrected) / 23 stationary features |
| Fitting rows | 2021-08-28 → 2024-12-31, **951 rows** |
| Early-stopping validation | 2025-02-08 → 2025-09-30, **173 rows** |
| Pre-hold-out frame | 2021-08-28 → 2025-09-30, **1,154 rows** |
| Hold-out | 2025-10-01 → 2026-06-11, **210 rows** |
| Seed | 42 |
| Artifact git commit | `8d7715e` |

- **No hold-out feature row** is in the fitting or validation rows (0 of 210).
- **Scalers** are fit only on the 951 fitting rows, then applied unchanged to validation and
  hold-out rows.
- **One validation label is a hold-out-period return.** The last validation row is 2025-09-30;
  its target is the 2025-10-01 return. That label (+2.1548%, log) entered `val_loss` early
  stopping, i.e. epoch selection only. It is 1 of 173 validation labels and 0.4982% of the
  validation MSE about zero. Model weights are not fit on it. Full record:
  `docs/EVAL_PROTOCOL.md` §11 **D-1**. The same one-label overlap applies to the Stage 3
  stationary-LSTM hold-out headline (5-seed mean), not only to this artifact.
- No re-training or re-splitting is performed to "fix" this. The artifact is used as committed.

### 2.4 Hold-out touch count (verified from `results/run.log`)

`results/run.log` contains **exactly one** `Stage 3 evaluation start` line:
2026-11-14 18:03:57, `variant=all`, `seeds=5`, `legacy_seeds=3`, `epochs=60`,
`skip_legacy=False`, `artifact=True`; it ends at 18:24:57. There is no later evaluation run:
`git log` shows one results commit (`64c9798`) and one log commit (`5f4abaa`).

Within that single run the hold-out was:

- **scored three times** — once per pre-registered variant V1, V2, V3, each on the same 210
  rows;
- **predicted once more, unscored**, by the `--artifact` path (the seed-42 model predicts the
  hold-out, but `_save_artifact` discards the predictions);
- **18 LSTM hold-out fits** in total (V1: 5 stationary; V2: 5 stationary + 3 legacy; V3: 5
  stationary) plus 1 artifact fit = **19 LSTM fits that produced hold-out predictions**.

This stage adds **one inference-only pass** (0 fits) of the seed-42 artifact.

So the pre-registered promise "touched once" is **not literally true**: the hold-out was
scored three times in one run, predicted once more by the artifact code, and is now predicted
once more by inference. What did *not* happen is a result-dependent re-run: V1/V2/V3 were
pre-registered sensitivity variants, not repeated attempts to find a better number, and no
evaluation was re-run after its result was seen. The count is stated here and in
`docs/RESULTS.md`.

---

## 3. Strategies (long/flat only; no shorting)

Retail shorting of Iranian gold is not available, so every strategy is long or flat. No
leverage, no USD hedge inside S2/S3, no intraday trading.

| ID | Strategy | Position rule |
|---|---|---|
| **S0** | Buy-and-hold gold (Rial) | long every day: `p_t = 1` for all `t` |
| **S1** | Buy-and-hold USD (Rial) | long `USD_IRR` every day: `p_t = 1` for all `t` |
| **S2** | LSTM, mean-return threshold | long next day iff `ŷ_t > μ_train`, else flat |
| **S3** | LSTM, zero threshold | long next day iff `ŷ_t > 0`, else flat |

- `ŷ_t` is the artifact's predicted **log** return for the row dated `t`.
- `μ_train` is the mean of `Target_Next_LogRet` over the artifact's **951 fitting rows**
  (2021-08-28 → 2024-12-31). It is a fixed training statistic, not re-estimated on the
  hold-out. (It is not the mean of the validation or pre-hold-out frame.)
- S0/S1 are the benchmarks and are always displayed next to S2/S3.
- **Per-seed S2/S3 and the 5-seed mean are not reported** — see §2.2. Only seed 42 exists.
- For each rule, report the **share of days long** and the **number of position changes**. If
  the near-constant prediction makes S3 long on all 210 days (i.e. S3 equals S0 before costs),
  that is stated explicitly.

---

## 4. Execution timing

The prediction for the row dated `d` is made **after the close of `d`** (the model's features
at `d` use data through the `d` close, and the target is `d → d+1`). The position for the
`d → d+1` return is therefore decided at the `d` close.

- **Primary:** trade at the **close of `d`**. The position earns the full `d → d+1` return;
  the cost is charged at the `d` close on the notional traded.
- **Sensitivity:** **one-day execution delay**. The position that the signal at `d` would have
  taken is instead taken at the close of `d+1`, so it earns the `d+1 → d+2` return and misses
  the first day. Implemented as `p^delay_t = p_{t-1}` with `p^delay_0 = 0`; costs are
  recomputed on the delayed position series. The delay shifts the position by exactly one day.

No other timing convention is tried. There is no open-price or next-open execution.

---

## 5. Costs

Cost is charged **per position change**, on the notional traded, at the close where the change
happens. A flat → long or long → flat change costs `c` of notional; flat → flat costs zero.
There is no separate spread, slippage, tax or borrow cost beyond `c`.

| Scenario | Per side | Round trip | Origin |
|---|---:|---:|---|
| C0 | 0.00% | 0.00% | frictionless reference |
| C1 | 0.35% | 0.70% | half the old backtest's per-side cost; low-cost-venue reference |
| C2 | 0.75% | 1.50% | the 1.5% round-trip cost in the Stage 3 break-even analysis (`docs/RESULTS.md` §5) |
| C3 | 1.50% | 3.00% | the 3.0% round-trip cost in the same analysis |

The **old** `trading_bot/` backtest used `COMMISSION_RATE = 0.005` plus
`SLIPPAGE_RATE = 0.002` = **0.7% per side (1.4% round trip)**
(`legacy-pre-refactor:trading_bot/config/backtest_config.py:21-22`). That 0.7%/side setting is
between C1 and C2 and is not one of the four scenarios; it is quoted only as the origin of C1.

Cost convention for the equity path (pre-registered):

```
p_{-1} = 0
turnover_t = |p_t - p_{t-1}|
net_factor_t = (1 + p_t * r_{t+1}) * (1 - c * turnover_t)
E_t = E_{t-1} * net_factor_t,   E_{-1} = 1
r_net,t = net_factor_t - 1
```

`r_{t+1} = Gold_{t+1}/Gold_t - 1` is the **simple** return; the model predicts a log return, but
the accounting is in simple returns. S0/S1 also pay one entry cost at `t=0` (because
`p_{-1}=0`), so all four strategies face the same entry convention.

The **gold-in-USD reference** is not a traded strategy and is reported **gross** (no cost); it is
a currency conversion, not a trade.

---

## 6. Metrics

For every strategy × cost scenario:

- **Total return** `E_N - 1`
- **Final equity multiple** `E_N`
- **Annualised return** `E_N^(252/N) - 1`, with `N = 210` return observations and 252
  trading days/year
- **Annualised volatility** `std(r_net,t, ddof=1) * sqrt(252)`
- **Maximum drawdown** `min_t (E_t / max_{s<=t} E_s - 1)`, with `E_{-1}=1` in the running max
- **Number of position changes** `sum_t turnover_t` (includes the first entry)
- **Share of days long** `mean(p_t)`

**Bootstrap.** For S2 and S3 versus S0, report the difference in mean daily net return
`Δ = mean_t(r_net,S - r_net,S0)` at each cost, with a **moving-block bootstrap 95% CI**:
block length **10**, **10,000** resamples, blocks drawn with replacement and truncated to
`N = 210`, percentile interval (2.5%, 97.5%), seed **20261116**. The bootstrap resamples the
paired daily difference series, so the same blocks are used for both strategies.

**Gold in USD.** `q_t = Gold_IRR_t / USD_IRR_t`, buy-and-hold, gross. Report the same
return/vol/drawdown/multiple metrics. This is the currency-neutral reference.

**No inflation series exists in the repository.** Nominal Rial returns are inflated by Iranian
currency devaluation; the gold-in-USD series is the available currency-neutral proxy, **not**
an inflation-adjusted real return. No CPI series is invented or imported.

---

## 7. Decision rule (fixed now)

A strategy **"adds value"** only if, at **C2 = 0.75% per side (1.5% round trip)**:

1. its mean daily net return is higher than S0's (`Δ > 0`), **and**
2. the 95% block-bootstrap CI for `Δ` **excludes zero** (`CI_low > 0`).

Otherwise the stated finding is **"no added value over buy-and-hold"**. This applies to S2 and
S3; S0 and S1 are benchmarks, not candidates. A higher total return with a CI that includes
zero is **not** added value. A lower total return is not added value even if the CI is entirely
below zero (that would be evidence of destruction, not value).

This rule is about **economic value on this sample**, not about the statistical edge rule in
`docs/EVAL_PROTOCOL.md` §8. Passing it would not overturn the Stage 3 verdict; failing it is
the expected outcome.

---

## 8. Caveats fixed in advance

- The hold-out is **~210 rows** in a **strongly trending nominal series** (the nominal Rial
  gold price rises over the traded period; the measured change is reported in
  `docs/RESULTS.md`). The power to detect a small timing edge is low. Results describe **this
  sample**, not the future.
- A long/flat rule in a rising market inherits the trend. S0 is therefore a hard benchmark, and
  a rule that is long most of the time will look similar to S0 before costs.
- The near-constant prediction (Stage 3 `std_pred` 0.003304 vs `std_actual` 0.026456) means S2
  and S3 can differ from each other and from S0 only through the few days on which the
  prediction crosses the threshold. This is reported, not corrected.
- Costs are the dominant term: the average absolute daily move is 1.65% on the hold-out
  (`docs/RESULTS.md` §5), so a 1.5% round trip is roughly one day's average move. A daily rule
  cannot pay that unless it is right on almost every day.
- No claim is made about inflation-adjusted returns, other assets, other periods or other
  execution venues.

---

## 9. Outputs

- `src/backtest_check.py`, entry point `python -m src.backtest_check` (target ≤ 250 lines).
- `results/backtest.json` — machine-readable: metadata, prediction diagnostics, the full
  strategy × cost table, bootstrap CIs, gold-in-USD reference, delay sensitivity.
- `results/backtest.log` — short run log.
- `docs/RESULTS.md` — "Economic reality" section with the tables, the verdict under §7 and the
  plain-language reading.
- Tests: cost charged exactly on each position change (flat → flat charges nothing); no
  lookahead in the position at `t`; S0 equity equals the compounded product of daily returns;
  the delay sensitivity shifts the position by exactly one day.

---

## 10. Deviations

**None at pre-registration.** The prediction-source amendment (seed-42 artifact only; per-seed
and 5-seed tables dropped; touch count stated in §2.4) was agreed by the owner **before** this
file was committed and before any backtest result existed. Any change made after seeing a
result is appended here with its own commit.
