# Forecasting Iranian Gold (IRR): an end-to-end pipeline and an honest negative result

This repository builds a complete, reproducible pipeline for one narrow question: can a
recurrent model predict the **next trading day's log return** of 18-karat gold priced in
Iranian rial? It covers data acquisition and repair, a frozen stationary feature set, an LSTM,
a pre-registered walk-forward and hold-out evaluation, an economic long/flat check, a FastAPI
service and a Streamlit demo. The answer is **no**: the model has no demonstrated predictive
edge, and a rule driven by its predictions adds no value over buy-and-hold gold after costs.
The nominal gains that make the chart look impressive are mostly rial devaluation, not
forecasting skill. The pipeline is the deliverable; the negative result is the finding.

## Headline results

All numbers below are read from `results/eval_V2.json` and `results/backtest.json`. The
evaluation protocol was committed before any model was fit (`docs/EVAL_PROTOCOL.md`); the
economic protocol was committed before any backtest result (`docs/BACKTEST_PROTOCOL.md`).

### Predictive accuracy, V2, log returns

Walk-forward pools five expanding folds (n = <!-- num:int@eval_V2.walkforward.lstm_stationary.n -->552<!-- /num -->);
the hold-out is <!-- num:int@eval_V2.holdout.lstm_stationary.n -->210<!-- /num --> rows from
2025-10-01 to 2026-06-11. R² is measured against a zero-return benchmark; the DM p-value is
one-sided against persistence (lower is better for the model).

| Model | WF RMSE | WF R² | WF DM p | HO RMSE | HO R² | HO DM p |
|---|---:|---:|---:|---:|---:|---:|
| Persistence (zero return) | <!-- num:eval_V2.walkforward.persistence.rmse -->0.018350<!-- /num --> | 0.0000 | — | <!-- num:eval_V2.holdout.persistence.rmse -->0.026545<!-- /num --> | 0.0000 | — |
| Historical mean | <!-- num:eval_V2.walkforward.histmean.rmse -->0.018188<!-- /num --> | <!-- num:eval_V2.walkforward.histmean.r2_zero -->0.0175<!-- /num --> | <!-- num:eval_V2.walkforward.histmean.dm_p_one_sided -->0.0055<!-- /num --> | <!-- num:eval_V2.holdout.histmean.rmse -->0.026457<!-- /num --> | <!-- num:eval_V2.holdout.histmean.r2_zero -->0.0066<!-- /num --> | <!-- num:eval_V2.holdout.histmean.dm_p_one_sided -->0.2428<!-- /num --> |
| Ridge, own lags | <!-- num:eval_V2.walkforward.ridge_own.rmse -->0.018299<!-- /num --> | <!-- num:eval_V2.walkforward.ridge_own.r2_zero -->0.0056<!-- /num --> | <!-- num:eval_V2.walkforward.ridge_own.dm_p_one_sided -->0.3264<!-- /num --> | <!-- num:eval_V2.holdout.ridge_own.rmse -->0.026704<!-- /num --> | <!-- num:eval_V2.holdout.ridge_own.r2_zero -->-0.0120<!-- /num --> | <!-- num:eval_V2.holdout.ridge_own.dm_p_one_sided -->0.7966<!-- /num --> |
| Ridge, all 23 features | <!-- num:eval_V2.walkforward.ridge_full.rmse -->0.018846<!-- /num --> | <!-- num:eval_V2.walkforward.ridge_full.r2_zero -->-0.0548<!-- /num --> | <!-- num:eval_V2.walkforward.ridge_full.dm_p_one_sided -->0.8595<!-- /num --> | <!-- num:eval_V2.holdout.ridge_full.rmse -->0.026798<!-- /num --> | <!-- num:eval_V2.holdout.ridge_full.r2_zero -->-0.0192<!-- /num --> | <!-- num:eval_V2.holdout.ridge_full.dm_p_one_sided -->0.7018<!-- /num --> |
| **Stationary LSTM** | <!-- num:eval_V2.walkforward.lstm_stationary.rmse -->0.018214<!-- /num --> | <!-- num:eval_V2.walkforward.lstm_stationary.r2_zero -->0.0148<!-- /num --> | <!-- num:eval_V2.walkforward.lstm_stationary.dm_p_one_sided -->0.2251<!-- /num --> | <!-- num:eval_V2.holdout.lstm_stationary.rmse -->0.026543<!-- /num --> | <!-- num:eval_V2.holdout.lstm_stationary.r2_zero -->0.0001<!-- /num --> | <!-- num:eval_V2.holdout.lstm_stationary.dm_p_one_sided -->0.4984<!-- /num --> |

The LSTM's walk-forward R² of <!-- num:eval_V2.walkforward.lstm_stationary.r2_zero -->0.0148<!-- /num -->
has a block-bootstrap 95% interval of
[<!-- num:eval_V2.walkforward.lstm_stationary.boot_r2_lo -->-0.0272<!-- /num -->,
<!-- num:eval_V2.walkforward.lstm_stationary.boot_r2_hi -->0.0561<!-- /num -->]; on the hold-out it is
[<!-- num:eval_V2.holdout.lstm_stationary.boot_r2_lo -->-0.0577<!-- /num -->,
<!-- num:eval_V2.holdout.lstm_stationary.boot_r2_hi -->0.0630<!-- /num -->]. Both include zero.

Directional accuracy tells the same story. Walk-forward the LSTM is right
<!-- num:pct@eval_V2.walkforward.lstm_stationary.dir_acc -->56.16%<!-- /num --> of the time, while
always predicting "up" is right <!-- num:pct@eval_V2.walkforward.lstm_stationary.always_up_acc -->56.34%<!-- /num -->.
On the hold-out both are <!-- num:pct@eval_V2.holdout.lstm_stationary.dir_acc -->51.43%<!-- /num -->:
the model has no directional skill at all.

### Economic reality, hold-out, after costs

A long/flat rule driven by the served seed-42 artifact, 210 trading days, no shorting
anywhere. S0 is buy-and-hold gold in rial; S1 is buy-and-hold USD in rial (the devaluation
reference); S2 is long when the prediction exceeds the training mean; S3 is long when the
prediction is positive.

| Strategy | 0% per side | 0.75% per side |
|---|---:|---:|
| S0 buy-and-hold gold (IRR) | <!-- num:pct@backtest.strategies.C0.S0.total_return -->+57.89%<!-- /num --> | <!-- num:pct@backtest.strategies.C2.S0.total_return -->+56.71%<!-- /num --> |
| S1 buy-and-hold USD (IRR) | <!-- num:pct@backtest.strategies.C0.S1.total_return -->+49.00%<!-- /num --> | <!-- num:pct@backtest.strategies.C2.S1.total_return -->+47.89%<!-- /num --> |
| S2 long if prediction > training mean | <!-- num:pct@backtest.strategies.C0.S2.total_return -->+12.37%<!-- /num --> | <!-- num:pct@backtest.strategies.C2.S2.total_return -->+1.13%<!-- /num --> |
| S3 long if prediction > 0 | <!-- num:pct@backtest.strategies.C0.S3.total_return -->+52.12%<!-- /num --> | <!-- num:pct@backtest.strategies.C2.S3.total_return -->+36.90%<!-- /num --> |

At the pre-registered decision cost of 0.75% per side, S2 loses
<!-- num:bp@backtest.bootstrap.C2.S2_vs_S0.mean_diff -->-22.45<!-- /num --> bp/day against buy-and-hold,
95% CI [<!-- num:bp@backtest.bootstrap.C2.S2_vs_S0.ci_low -->-45.45<!-- /num -->,
<!-- num:bp@backtest.bootstrap.C2.S2_vs_S0.ci_high -->-7.89<!-- /num -->] — significantly worse.
Even at zero cost S2 is worse: <!-- num:bp@backtest.bootstrap.C0.S2_vs_S0.mean_diff -->-17.83<!-- /num --> bp/day,
CI [<!-- num:bp@backtest.bootstrap.C0.S2_vs_S0.ci_low -->-40.54<!-- /num -->,
<!-- num:bp@backtest.bootstrap.C0.S2_vs_S0.ci_high -->-3.08<!-- /num -->]. S3 is indistinguishable
from buy-and-hold at 0.75% per side:
<!-- num:bp@backtest.bootstrap.C2.S3_vs_S0.mean_diff -->-7.56<!-- /num --> bp/day,
CI [<!-- num:bp@backtest.bootstrap.C2.S3_vs_S0.ci_low -->-23.96<!-- /num -->,
<!-- num:bp@backtest.bootstrap.C2.S3_vs_S0.ci_high -->2.01<!-- /num -->], and it does not beat it.

Over the same period gold in USD returned
<!-- num:pct@backtest.gold_in_usd.total_return -->+5.97%<!-- /num --> while gold in rial returned
+57.89% and USD/IRR rose +49.00%. Most of the rial gain is the rial, not the metal.

## How to read the results

**The benchmark is zero return.** A log return is close to unpredictable, so "predict zero"
is a strong baseline. `r2_zero` compares the model's squared error with that baseline;
persistence therefore scores exactly 0. A positive R² means only that the model is slightly
better than assuming no change — not that it is useful.

**Walk-forward** fits on an expanding window and tests on the next block, five times, with a
30-row purge and a 5-row embargo between fit and test. Scalers are fit only on each fold's
fitting rows. The pooled out-of-sample set is 552 rows. This is the closest thing to an
honest simulation of repeated deployment.

**The hold-out** is the final 210 rows (2025-10-01 to 2026-06-11), never used for fitting or
model selection. It is scored once in the protocol. In practice it was predicted six times
across the project (see Limitations); three of those passes were scored, and none was re-run
after seeing its result.

**Diebold–Mariano** tests whether the model's squared-error loss is lower than persistence's,
with a HAC variance and the Harvey–Leybourne–Newbold small-sample correction. A p-value above
0.05 means the difference is not distinguishable from noise.

**The bootstrap** resamples blocks of the loss differential and reports a 95% interval for R².
An interval that contains zero is the formal version of "no demonstrated edge".

**Why the historical mean looked significant in walk-forward and not on the hold-out.** The
historical mean predicts a constant positive return. In the walk-forward period the up-rate
was 56.3%, so a positive constant reduces squared error and the DM test is significant
(p = 0.0055). On the hold-out the up-rate fell to 51.4%, the volatility rose, and the same
constant has no significant advantage (p = 0.2428). That is nominal drift, not skill: the
benchmark was flattered by the direction the series happened to move, and the effect did not
survive a different sample.

**Break-even costs.** At a 1.5% round trip, a daily directional rule would need
<!-- num:pct@eval_V2.cost_sanity.walkforward.breakeven_acc_0_015 -->108.9%<!-- /num --> accuracy
in walk-forward and <!-- num:pct@eval_V2.cost_sanity.holdout.breakeven_acc_0_015 -->95.4%<!-- /num -->
on the hold-out just to break even. At a 3% round trip it needs
<!-- num:pct@eval_V2.cost_sanity.walkforward.breakeven_acc_0_030 -->167.8%<!-- /num --> and
<!-- num:pct@eval_V2.cost_sanity.holdout.breakeven_acc_0_030 -->140.9%<!-- /num -->. Observed
accuracy is 51–57%. Costs are larger than any effect the model could plausibly have.

## What is in the repository

```
src/            data loader, features, evaluation, backtest, API, model code
config/         settings (paths, tickers, the date-repair window) and logging
models/         seed-42 stationary LSTM + two scalers + metadata
results/        committed evaluation and backtest JSON/CSV plus run logs
data/sample/    the last 200 rows, the only data redistributed
docs/           audit, protocols, results, decisions, serving design, this stage's plan
scripts/        data fetch and the README-numbers check
tests/          the full test suite (pytest)
notebooks/exploratory/  early sketches; outputs cleared, not the final evaluation
```

Python **3.12**. The runtime needs only `requirements.txt`; development, training and data
fetching need `requirements-dev.txt`. The Docker image is the only deployment artifact; no
live demo is provided.

### Quickstart

```bash
python -m venv .venv && . .venv/bin/activate
make install       # runtime + development requirements into .venv
make test          # full suite: 91 collected (88 pass + 3 skip without the full series)
make check         # the test suite, then the README-numbers check
make api           # FastAPI on :8000 (sets API_KEY=demo-key)
make app           # Streamlit on :8501
make docker-build  # single image, API + Streamlit
make docker-run    # API on :8000
```

`make check` is exactly what CI runs: `pytest`, then `scripts/check_readme_numbers.py`, which
re-reads every number marked in this file from `results/*.json` and fails on drift.

`make test` collects 91 tests. In a clean clone, 88 pass and 3 skip because they need the
untracked full series (`data/raw/final_gold_dataset.csv`); with that file present, all 91 pass.
The 3 skips are the full-series feature-parity check, the EMA warm-up check and the block-date
rejection check.

`make evaluate` re-runs the pre-registered Stage 3 protocol. It retrains 109 LSTMs and took
1,259.6 s (21.0 min) on the reference machine; it needs the full local dataset, which is not
in the repository. `make backtest` re-runs the inference-only economic check.

`make fetch-data` calls the TGJU and Yahoo scrapers and writes `data/raw/final_gold_dataset.csv`.
It needs `yfinance` and `curl_cffi` (installed by `requirements-dev.txt`), may break if TGJU
changes its endpoint, and writes to a gitignored directory.

### Docker

The image is the only deployment artifact: one Python 3.12 slim image, non-root UID 10001,
`HEALTHCHECK` on `/health`, API on 8000 by default and Streamlit from the same image by
overriding the command.

```bash
docker build -t gold-irr-honest-forecasting .
docker run --rm -p 8000:8000 -e API_KEY=demo-key gold-irr-honest-forecasting
docker run --rm -p 8501:8501 gold-irr-honest-forecasting \
  streamlit run streamlit_app.py --server.port 8501 --server.address 0.0.0.0
```

Measured on the reference machine: the image is **2.99 GB** on disk, of which the single
`pip install` layer is 2,240 MB — almost all of it TensorFlow. The build took **4,224.9 s
(70.4 min)** because the connection to `files.pythonhosted.org` dropped the 259 MB
`tensorflow-cpu` wheel; the Dockerfile retries and resumes, so a fast connection should be
much quicker. A Stage 6 rebuild that changed only application files reused the cached
dependency layer and took **1 s**; the image ID changed and the size stayed **2.99 GB** on
disk (`docker image inspect` reports 603,727,316 bytes). The running container reports
`healthy` and returns `-0.00045206130016595125` for the bundled sample as shipped,
bit-identical to the value from a local run. That identity is a property of this sample file,
not of any refreshed series: replacing only the sample's `Ounce_USD` column with the complete
global series changes the prediction to `-0.0004350765375420451` (difference +1.70e-05),
because the sample carries a June-2026 ounce vintage (see `data/sample/README.md`).

The image contains the model, scalers, metadata, `results/` JSON and the 200-row sample. It
does not contain `data/raw`, `data/processed`, tests, notebooks or `.env`.

### API

Three endpoints. The caller sends recent **raw daily rows**; the service runs the same feature
function training used. Prices are in **Rial**; `Gold_IRR` is 18-karat gold per gram
(`geram18`), `USD_IRR` is rial per dollar, `Ounce_USD` is dollars per ounce, `Oil_USD` is Brent
in dollars. Set `API_KEY` in the environment; `/health` is open and the other two fail closed
with 503 when the key is unset. There is no rate limiter, deliberately.

The accepted field names are the sample CSV header verbatim:

| Field | Accepted JSON names | Unit |
|---|---|---|
| date | `date`, `Date` | Gregorian date, `YYYY-MM-DD` |
| Gold_IRR | `Gold_IRR` | Rial per gram, 18k |
| USD_IRR | `USD_IRR` | Rial per USD |
| Ounce_USD | `Ounce_USD` | USD per ounce |
| Oil_USD | `Oil_USD` | USD per barrel |

`date` and `Date` are the same field (`pydantic.AliasChoices`); both spellings are accepted,
so a row parsed from `data/sample/gold_sample.csv` can be posted without renaming. Supplying
both with different values is a 422.

`GET /health`:

```json
{"status":true,"model_loaded":true,"timestamp":"2026-11-18T11:25:58.972087"}
```

`GET /model-info` (trimmed) returns the artifact metadata, the input contract and the committed
metrics. The contract is `min_rows: 89`, `max_rows: 5000`, `sequence_length: 30`,
`n_features: 23`, target `next_trading_day_log_return`.

`POST /predict` with the 200-row sample, posted exactly as the CSV parses it:

```bash
.venv/bin/python - <<'PY'
import json, urllib.request
import pandas as pd

rows = json.loads(pd.read_csv("data/sample/gold_sample.csv").to_json(orient="records"))
request = urllib.request.Request(
    "http://localhost:8000/predict",
    data=json.dumps({"rows": rows}).encode(),
    headers={"Content-Type": "application/json", "X-API-Key": "demo-key"},
)
with urllib.request.urlopen(request) as response:
    print(json.dumps(json.load(response), indent=2))
PY
```

Output, captured on 2026-11-18 against a local server (trimmed to the fields shown; the full
response also carries the model metadata, four caveats and a timestamp):

```json
{
  "prediction": {
    "target": "next_trading_day_log_return",
    "log_return": -0.00045206130016595125,
    "simple_return": -0.00045195913585182153,
    "persistence_log_return": 0.0,
    "implied_next_price_persistence_equivalent": 172130169.02113324
  },
  "input": {"last_date": "2026-06-13", "rows_used": 200, "feature_rows": 141,
            "sequence_length": 30, "last_close_irr": 172208000.0},
  "warnings": ["stale_input: last date 2026-06-13 is 158 days old (limit 7)"],
  "statement": "This model has no demonstrated predictive edge: ..."
}
```

For the bundled sample as shipped, the `log_return` is bit-identical to the value in the
Docker section and to the committed serving output. A refreshed global ounce series changes it
to `-0.0004350765375420451` (difference +1.70e-05); see `data/sample/README.md`. The stale day
count grows with the calendar.

**Why 89 rows minimum.** The longest lookback is the 60-row SMA, which leaves the first feature
row at index 59; the model needs 30 consecutive feature rows, so 59 + 30 = 89. An 88-row
request yields 29 feature rows and is rejected.

**Why 422 for 2023-10-27 .. 2025-08-06.** Those TGJU rows are dated one day early. The V2
training data repairs them by pairing each relabelled Iranian row with the global bar of the
corrected date, which requires the full global vintage. A raw-row request cannot supply that,
so serving those dates would feed V1-style global features to a V2-trained model. The service
rejects them instead:

```json
{"detail":{"code":"block_dates_unsupported","message":"rows dated 2023-10-27..2025-08-06 are not servable: ... Start after 2025-08-06."}}
```

A 40-row request returns `422 too_few_rows`; a wrong key returns `401 invalid_api_key`.

**No confidence interval.** The old service fabricated one by adding Gaussian noise. With no
demonstrated edge, a real interval would be either uninformative or falsely precise, so the
response returns a single log return, the zero-return benchmark beside it, and no interval.

## Data

* **Gold, rial:** TGJU `geram18` (18-karat gold per gram), in **rial**, not toman. Every
  "toman" label in the legacy document was 10× wrong.
* **USD/IRR:** TGJU `price_dollar_rl`.
* **Global gold and oil:** Yahoo Finance `GC=F` (gold ounce) and `BZ=F` (Brent).

**The date defect.** From 2023-10-27 to 2025-08-06 (502 raw rows, 36.1% of the frame, entirely
before the hold-out), Thursday rows vanish and Friday rows appear in both TGJU series. The
Jalali date field cannot witness this: TGJU derives both date columns from one record, and they
agree in all 11,331 records. The evidence is alignment against the global series on a fixed row
set: matching `GC=F` one day later moves the block's same-day correlation from +0.112 to
+0.380, while the same operation outside the block moves it from +0.358 to −0.126. The loader
therefore relabels the block **+1 day** as a reversible transform (`src/data_loader.py`,
`apply_block_date_shift`); prices and row counts are untouched and a date collision raises an
error. The full argument is in `docs/DATA_INTEGRITY.md`.

**The sample.** `data/sample/gold_sample.csv` is the last 200 rows (2025-10-14 to 2026-06-13).
The full series is **not redistributed**: permission from the source is pending. The scrapers
are undocumented and may break without notice.

## Limitations and honesty

* **The hold-out was touched more than once.** The pre-registered protocol says "scored once".
  In total the hold-out was predicted six times — Stage 3 scored it three times (V1, V2, V3)
  and the artifact code predicted it once without scoring; Stage 4 added two inference-only
  passes (a development run and the final run, identical outputs). Three passes were scored.
  No scored pass was re-run after seeing its result, but the literal "touched once" was not met.
* **One validation label is a hold-out return.** The last validation row (2025-09-30) has the
  2025-10-01 return as its target, so one hold-out-period label entered early stopping. It is
  1 of 173 validation labels and **0.69% of the validation loss** — the label's squared error
  over the sum of squared errors, computed with the artifact's own predictions
  (`scripts/d1_share.py`). The 0.50% quoted in earlier drafts was `label² / Σy²`, a
  zero-prediction approximation, not the loss the model minimised; the review's "0.86" was
  `label² / mean(y²)`, which is 173× the zero-prediction share (0.4982%) and not a share of the
  loss. No
  hold-out feature row was in fitting or validation. Any effect on epoch selection is
  optimistic for the model by construction, but at 0.69% it cannot change the verdict: the
  hold-out R² is +0.0001, DM p = 0.4984, 95% CI [−0.0577, +0.0630]. It is recorded, not fixed
  (`docs/EVAL_PROTOCOL.md` §11 D-1 and the Errata at the end of that file).
* **The global series is forward-filled onto the Iranian grid.** The ounce and oil inputs are
  Yahoo daily bars carried onto the Sat-Thu Iranian dates by a left join and forward-fill.
  Measured on the full training frame: **36%** of the global returns are exactly zero because of
  the fill, and **19%** of rows have a return spanning more than one global trading day
  (`scripts/global_grid_audit.py`, `docs/GLOBAL_GRID_AUDIT.md`). The effect of this construction
  on the results was **not measured**; a sensitivity run is future work. It is not claimed to
  help or hurt the model.
* **The hold-out amendment predates the first fit.** The pre-registered protocol was committed
  at 2026-11-14 17:59:11 +03:30 (`bda5992`); the amendment that set the 2025-10-01 cutoff was
  committed at 2026-11-14 18:02:01 +03:30 (`74d9369`), 1 min 56 s before the first model fit,
  which `results/run.log` timestamps at 2026-11-14 18:03:57,480. The reason: the first draft
  said "the final 180 rows", but a data-shape check showed those begin 2025-11-05, which would
  skip October; the 2025-10-01 cutoff matches the requested period and gives 210 rows.
* **The hold-out is ~210 rows in a strongly trending nominal series.** Statistical power is
  low, and the results describe this sample, not future performance. A 210-row window cannot
  rule out small effects, and it does not support the large, tradeable effect the old document
  implied.
* **The served model is the seed-42 artifact.** Stage 3 saved aggregate metrics only, so the
  per-seed and 5-seed backtests are not recoverable without retraining. Seed 42 was fixed
  before the run, not chosen afterwards; its hold-out spread is 9.4% of actual, and its
  correlation is +0.031, so it is typical rather than stronger.
* **Serving has an EMA warm-up caveat.** MACD uses an exponential moving average seeded at the
  first supplied row. A short request therefore differs slightly from the full-history feature
  frame: about 1.6e-4 at 89 rows and 1.1e-8 at 200 rows. The service documents this rather than
  hiding it.
* **There is no inflation series in the repository.** Gold in USD is the available
  currency-neutral proxy, not a real return. It shows +5.97% against +57.89% nominal, but it is
  still not inflation-adjusted.
* **The legacy README's numbers are not carried over.** The pre-refactor document quoted
  metrics that contradicted its own artifacts (price R² presented as skill, a backtest return
  that did not match the shipped files, toman instead of rial, a different architecture). None
  of it is repeated here.
* **The legacy tag exists and is deliberate.** `legacy-pre-refactor` points at the pre-refactor
  state so the removed bot, MLOps layer and old README remain reachable. Nothing in this branch
  depends on them.

## Lessons learned

* **A high price-level R² can be exactly persistence.** The old artifact reported a price R² of
  0.9717, and the persistence baseline scores the same 0.9717 (`docs/AUDIT_REPORT.md` §2.4);
  price levels are so persistent that "tomorrow equals today" scores the same. On log returns,
  which remove the level, this repository's pre-registered evaluation finds no edge. Always
  benchmark against the naive forecast.
* **Directional accuracy can be below "always up".** In this sample the LSTM's 56.16% was
  worse than always predicting up (56.34%) in walk-forward, and on the hold-out both were
  51.43%. A directional metric must be compared with the up-day base rate, not 50%.
* **Raw price levels and distribution shift do not mix.** The legacy feature set used absolute
  prices, MACD in rial and unbounded levels; a 2025 price is far outside the 2021 training
  range. The stationary set removed the levels, and the result was still no edge — which is the
  honest conclusion: feature design alone does not create a signal.
* **Pre-registering the protocol prevented a better-looking story.** The hold-out, the fold
  boundaries, the models and the edge rule were fixed before fitting. The one amendment was
  made before the run. Without that discipline, the walk-forward historical-mean result
  (p = 0.0055) would have been easy to present as a finding.
* **Recount the labels before trusting an audit, including your own.** A weekday table in the
  first audit was rotated by one weekday: the counts were right, the labels were wrong. A
  direct recount showed the market was a normal Saturday–Wednesday week and that the real
  defect was a 21-month block, not a uniform shift. The correction changed the entire data
  plan.
* **Nominal returns are not real returns.** Gold rose 57.89% in rial over the hold-out while it
  rose 5.97% in dollars and USD/IRR rose 49.00%. Reporting only the rial number would have
  described the currency, not the asset.
* **Training–serving parity is testable and worth testing.** Serving calls the same feature
  function as training; a parity test compared 696 row-level feature values and the served
  prediction against the offline path, with a maximum absolute difference of 0.0. The test is
  cheap and it removes a whole class of silent skew.
* **Costs decide the economics, not the R².** At a 1.5% round trip the break-even directional
  accuracy is 108.9% (walk-forward) and 95.4% (hold-out). A model at 51–57% cannot pay for its
  own trading, which is why the economic check is part of the result rather than an appendix.

## License, data terms, citation

The **code** is MIT-licensed; see `LICENSE`. The license **does not cover the data**: TGJU and
Yahoo values remain subject to their sources' terms, and the full series is not redistributed.
The bundled 200-row sample is included for demonstration only, pending permission from the
source.

Citation and contact are placeholders for the repository owner to fill:

* **Author / maintainer:** 
Built by ArshiaAsk as a hands-on project in end-to-end ML engineering and honest model evaluation.
GitHub: [https://github.com/ArshiaAsk]

* **Contact:** 
m.arshiaaskarzadeh@gmail.com
Issues and corrections are welcome, especially anything that contradicts a number
or claim in this repository.

* **How to cite:** If you reference this work, please cite it as:

    @software{gold_irr_honest_forecasting,
      author  = {Askarzadeh, Arshia},
      title   = {Forecasting Iranian Gold (IRR): an end-to-end pipeline and an honest negative result},
      year    = {2026},
      version = {1.0.0},
      url     = {https://github.com/ArshiaAsk/Gold-AI-Bot}
    }
* **Data permission status:** The code is released under the MIT License. **The license does not cover the data.**

- Iranian gold (18-karat gram, IRR) and USD/IRR prices were collected from TGJU;
  gold ounce (GC=F) and Brent (BZ=F) prices come from Yahoo Finance.
- I have not obtained permission from either source to redistribute their data.
  For that reason the full dataset is not included. The repository ships only a
  200-row sample (`data/sample/`), used to demonstrate the API and the app.
- `make fetch-data` downloads the data from the original sources. If you use it, you are
  responsible for complying with their terms of use. The scrapers may break at any time
  if those sites change.
- If you are a rights holder and want the sample removed, contact me and I will remove it.
