# Serving design — Stage 5a

**Status:** design, committed before any serving code (Stage 5a).
**Served artifact:** `models/gold_lstm_stationary_v2.keras` + `models/scaler_X_stationary_v2.pkl`
+ `models/scaler_y_stationary_v2.pkl` + `models/gold_lstm_stationary_v2.metadata.json`
(seed 42, V2, stationary feature spec). Nothing is retrained in this stage.
**Protocol:** `docs/EVAL_PROTOCOL.md`. **Results:** `docs/RESULTS.md`. **Backtest:** `docs/BACKTEST_PROTOCOL.md`.

## 0. What this service is and is not

The model has **no demonstrated predictive edge** (D24/D25). The API and the UI exist to
show that a negative result can still be served honestly: one feature path, no fabricated
confidence, no price headline. Every number the service reports about itself is read from
the committed metadata and result files at startup, never typed into the code.

Non-goals: no retraining, no new seeds, no model selection, no price-level metric, no
confidence interval, no trading signal, no live data feed.

## 1. Input contract — `POST /predict`

### 1.1 Body

Recent **raw daily rows**, exactly as they appear in `data/raw/final_gold_dataset.csv`
(and in the bundled `data/sample/gold_sample.csv`). The CSV header is
`Date,Gold_IRR,USD_IRR,Ounce_USD,Oil_USD`, and those names can be posted verbatim:

```json
{
  "rows": [
    {"Date": "2026-06-11", "Gold_IRR": 108433000.0, "USD_IRR": 1088900.0,
     "Ounce_USD": 4138.7, "Oil_USD": 62.39},
    {"Date": "2026-06-12", "...": "..."}
  ]
}
```

| Field | Accepted JSON names | Unit | Meaning |
|---|---|---|---|
| `date` | `date`, `Date` | `YYYY-MM-DD` | Gregorian calendar date of the row |
| `Gold_IRR` | `Gold_IRR` | Rial per gram | 18-karat gold (`geram18`) |
| `USD_IRR` | `USD_IRR` | Rial per USD | free-market USD (`price_dollar_rl`) |
| `Ounce_USD` | `Ounce_USD` | USD per ounce | `GC=F` close |
| `Oil_USD` | `Oil_USD` | USD per barrel | `BZ=F` close |

`date` and `Date` are the same field, declared with `pydantic.AliasChoices`. The old
lowercase form remains valid; the sample CSV header is valid without renaming. The four
price names are already identical in both forms, so no alias is needed for them. If a row
supplies both `date` and `Date` with different values, the request is rejected with **422**
(pydantic schema error) rather than silently choosing one; supplying both with the same
value is accepted.

The four price columns are the names used by the raw dataset. They are **levels**, not
features: the caller never sends features, so it cannot send a differently-scaled or
differently-lagged feature matrix. `src/feature_eng.py::add_stationary_features` computes
all 23 features inside the service.

Dates must be **strictly increasing** (ascending, no duplicates). Order is a hard
requirement rather than something the service silently sorts, because a silent sort would
hide a caller bug that reorders or duplicates rows.

### 1.2 Minimum number of rows: **89** (derived, not guessed)

The longest lookback in the frozen feature set is `price_sma_60`
(`src/feature_eng.py:93`), a 60-row rolling mean. Row *i* of the input (0-based) is the
first row with a complete 60-row window, so the first row with a non-NaN feature vector is
index **59**. The model consumes `SEQUENCE_LENGTH = 30` consecutive feature rows
(`models/gold_lstm_stationary_v2.metadata.json`, `src/eval_data.py:33`), so:

```
minimum rows = (60 − 1) + 30 = 89
```

Other warm-ups, all shorter and therefore not binding:

| Feature | Warm-up in raw rows | Source |
|---|---|---|
| `price_sma_60` | 60 | `src/feature_eng.py:93` |
| `rv_20` | 21 (diff, then 20-row std) | `src/feature_eng.py:96` |
| `bb_pctb_20`, `bb_bandwidth_20`, `price_sma_20` | 20 | `src/feature_eng.py:83-92` |
| `rsi_14` | 15 (diff, then 14-row mean) | `src/feature_eng.py:109-119` |
| `price_sma_7` | 7 | `src/feature_eng.py:91` |
| global returns | 5 (`shift(4)` on a diff) | `src/feature_eng.py:68-72` |
| `macd_norm`, `macd_signal_norm` | 1 (EMA, no warm-up) | `src/feature_eng.py:76-81` |

Verified empirically on the local series: an 88-row tail yields 29 valid feature rows, an
89-row tail yields exactly 30. The adapter applies two checks: a fast row-count check
(`n < 89`) and, after computing features, `n_feature_rows >= sequence_length`. The second is
derived from the features actually computed, so a change to the feature set cannot silently
produce a short window.

### 1.3 Maximum number of rows: **5,000**

A documented cap, not a model limit. The local full series is 1,424 rows and the bundled
sample is 200; 5,000 rows is roughly 19 years of daily data and bounds the per-request
work (the request is stateless and recomputes all features). Larger payloads are rejected
with `too_many_rows` rather than truncated, because truncating silently would change which
rows the caller believes were used.

## 2. Validation rules and error codes

Validation runs in this fixed order, so a payload with several defects always reports the
same one:

| # | Rule | HTTP | `detail.code` | Message (fixed) |
|---|---|---|---|---|
| 1 | `rows` present and non-empty | 422 | `empty_rows` | `rows must contain at least 89 daily rows` |
| 2 | fewer than the minimum | 422 | `too_few_rows` | `need at least 89 rows, got N` |
| 3 | more than 5,000 rows | 422 | `too_many_rows` | `at most 5000 rows, got N` |
| 4 | missing price column | 422 | `missing_column` | `missing column(s): ...` |
| 5 | unparseable date | 422 | `invalid_date` | `unparseable date: ...` |
| 6 | duplicate dates | 422 | `duplicate_dates` | `duplicate date(s): ...` |
| 7 | dates not strictly increasing | 422 | `unsorted_dates` | `dates must be strictly increasing; first violation at index i` |
| 8 | NaN / ±inf in any price | 422 | `non_finite_value` | `non-finite value in column C at index i` |
| 9 | price ≤ 0 | 422 | `non_positive_price` | `non-positive price in column C at index i` |
| 10 | implausible daily jump | 422 | `implausible_jump` | `abs log change of C at i is X, above the 0.5 limit` |
| 11 | window overlaps the mis-dated block | 422 | `block_dates_unsupported` | see §2.2 |
| 12 | wrong field type / missing field / conflicting `date` aliases | 422 | `schema` (pydantic) | pydantic's own detail list |
| 13 | model artifacts absent | 503 | `model_not_loaded` | `model artifacts not loaded (status: ...)` |

All semantic errors return `{"detail": {"code": "...", "message": "..."}}`. Pydantic shape
errors (a missing column, a string where a number belongs) keep FastAPI's default 422
list; the tests only assert the codes above.

### 2.1 Implausible daily jumps: **reject** at `|ln(p_t / p_{t−1})| > 0.5`

0.5 is ≈ 64.9% in one day. Measured maxima of the absolute daily log change:

| Series | Bundled sample (200 rows) | Local full series (1,424 rows) |
|---|---|---|
| `Gold_IRR` | 0.1732 | 0.1732 |
| `USD_IRR` | 0.1237 | 0.1777 |
| `Ounce_USD` | 0.1402 | 0.1402 |
| `Oil_USD` | 0.1569 | 0.1569 |

The largest observed move is 0.1777, so the limit has **2.8× headroom** over anything in
the data and still catches the classic unit errors: Toman submitted as Rial (a factor of
10, `ln 10 = 2.303`) and a zero or near-zero price. It is a **rejection**, not a warning,
because a 65% one-day move is far more likely to be a unit/row error than a real return,
and a warning would let the model consume it.

### 2.2 The 2023-10-27 → 2025-08-06 block: **rejected**

V2, the variant the artifact was trained on, relabels that block's dates +1 day *before*
merging the global series, so each block row is paired with the global bar of its true
date (`src/eval_data.py:108-137`, D19/D23). A raw-row API call cannot reproduce that
pairing: it has no global vintage to re-join against, and the row's own `Ounce_USD` /
`Oil_USD` belong to the *raw* date. Serving raw block rows would therefore silently feed
the model V1-style global features while it was trained on V2 — exactly the train/serve
skew this stage exists to remove.

Rule: if any supplied date falls in `[2023-10-27, 2025-08-06]`, the request is rejected
with `block_dates_unsupported`, and the message tells the caller to start after
2025-08-06. The bundled sample (2025-10-14 → 2026-06-13) and all post-block rows are
unaffected. This is a documented limitation, not a hidden fallback.

### 2.3 Staleness: **warning**, not an error

If the last date is more than **7 calendar days** before the current UTC date, the
response carries a `stale_input` warning. Seven days covers the Iranian Saturday–Wednesday
trading week plus a long weekend or holiday cluster. The prediction is still returned: the
caller may legitimately be back-testing, and refusing would make the service unusable for
the demo.

## 3. Output contract

`POST /predict` → 200:

```json
{
  "prediction": {
    "target": "next_trading_day_log_return",
    "log_return": -0.0004520613,
    "simple_return": -0.0004520613,
    "persistence_log_return": 0.0,
    "implied_next_price_persistence_equivalent": 108433000.0
  },
  "model": { "...": "verbatim contents of the metadata JSON" },
  "model_metadata_source": "models/gold_lstm_stationary_v2.metadata.json",
  "input": {
    "last_date": "2026-06-13",
    "rows_used": 200,
    "feature_rows": 141,
    "sequence_length": 30,
    "last_close_irr": 108433000.0
  },
  "warnings": [],
  "caveats": ["..."],
  "statement": "This model has no demonstrated predictive edge ...",
  "timestamp": "2026-11-17T13:00:00"
}
```

| Field | Rule |
|---|---|
| `prediction.log_return` | Model output, inverse-transformed with `scaler_y`. The **only** headline number. |
| `prediction.simple_return` | `exp(log_return) − 1`. |
| `prediction.persistence_log_return` | Always `0.0`: the zero-return benchmark the model must beat. |
| `prediction.implied_next_price_persistence_equivalent` | `last_close × exp(log_return)`, named and documented as persistence-equivalent because the model's prediction is near-constant (`std_pred` 0.0025 vs `std_actual` 0.0265, `docs/RESULTS.md` §11). Not a headline. |
| `model` | Verbatim metadata file contents. Includes `variant`, `seed`, `git_commit`, `architecture`, `training_window`, `holdout_window`, `feature_columns`, `sequence_length`. Nothing here is hardcoded. |
| `input.last_date` | Last **input** date, i.e. the date whose close the prediction starts from. |
| `input.rows_used` / `feature_rows` | Input row count and post-warm-up feature row count. |
| `warnings` | Machine-readable strings, currently only `stale_input: last date ... is N days old`. |
| `caveats` | Fixed list (§3.1). |
| `statement` | One fixed sentence: no demonstrated predictive edge, pointer to `docs/RESULTS.md`. |

**Forbidden fields.** No `confidence_interval`, `confidence`, `ci_low`, `ci_high`,
`lower_bound`, `upper_bound`, or any percentage described as confidence. The old
`/predict-with-confidence` endpoint and its Gaussian interval were fabricated and are not
reintroduced. A test asserts that no response key contains `confidence`/`interval`/`bound`.

### 3.1 Fixed caveats

1. `No demonstrated predictive edge: log-return R² is indistinguishable from zero and the economic test finds no value over buy-and-hold (docs/RESULTS.md).`
2. `Prediction is a single next-trading-day log return, not a price forecast; the implied price is persistence-equivalent.`
3. `Metrics were computed on a ~210-row trending hold-out; they are not a claim about future performance.`
4. `The bundled sample is 200 rows; serving history shorter than ~400 rows differs from the full-history feature frame in the MACD EMA seed (measured: 1.6e-4 at 89 rows, 1.1e-8 at 200).`

## 4. Timing and the global-feature lag

`add_stationary_features` (`src/feature_eng.py:25`) applies the global lag **inside the
shared function**:

```python
out['ounce_ret_lag1'] = ounce_ret.shift(1)   # line 68
out['oil_ret_lag1']    = oil_ret.shift(1)    # line 71
```

The global bars dated *t* are not complete at the Iranian close of *t*, so the last usable
global bar is *t−1* (`docs/EVAL_PROTOCOL.md` §2.1). Because the shift lives inside the one
function that training, evaluation and serving all call, the API cannot bypass it: there is
no code path that builds global features separately. `tests/test_serving_parity.py`
asserts the served features equal the evaluation features, which covers the shift
implicitly and explicitly (a test shifts the global columns by one day and shows the
features change).

**What "next trading day" means.** The prediction attached to the last input row *t* is
the log return from the close of *t* to the close of the next row in the series. The
service does not know the next row's calendar date (Iranian holidays are irregular and the
service has no calendar), so it does not invent one. It returns `input.last_date = t` and
the label `next_trading_day_log_return`; the caller supplies the date of the next row when
it becomes available.

## 5. Authentication

- Header: `X-API-Key` (overridable with `API_KEY_HEADER_NAME`).
- Secret: environment variable **`API_KEY`**. Never read from a file in the repo, never
  logged, never echoed.
- Comparison: `hmac.compare_digest(provided, expected)` — constant-time, no `==`.
- `/health` is **unauthenticated** and returns only liveness plus `model_loaded`.
- If `API_KEY` is unset, `/predict` and `/model-info` return **503
  `api_key_not_configured`**: the service fails closed rather than running open. The
  Streamlit app does not use the API at all (it loads the artifact in-process), so the
  demo needs no key.
- **No rate limiter.** Deliberate omission for a demo service with no public traffic. The
  old token-bucket middleware and its `RATE_LIMIT_*` variables are removed rather than
  left switched off, so nobody mistakes the service for rate-limited.

## 6. Concurrency

- `lifespan` loads the model, both scalers and the metadata **once** at startup; `/health`
  reports `model_loaded`. A failed load leaves the server up and `/predict` returns 503.
- `/predict` and `/model-info` are plain `def` endpoints, so FastAPI runs them in its
  threadpool instead of on the event loop. `model.predict` is blocking and must not run on
  the loop (audit finding 4.1).
- A single `threading.Lock` guards the `model.predict` call. Keras inference is not
  documented as thread-safe under concurrent calls on one model object, and serialising
  one forward pass costs microseconds.

## 7. Streamlit app

One file, four tabs, no network, no data beyond `data/sample/` and the committed artifacts.

| Tab | Content | Source |
|---|---|---|
| **Findings** | Headline hold-out table (persistence, histmean, ridge_own, ridge_full, lstm_stationary, lstm_legacy), V1/V2/V3 sensitivity table, legacy-vs-stationary comparison, economic-reality table (C0–C3 × S0–S3) and the verdict | `results/eval_V1.json`, `eval_V2.json`, `eval_V3.json`, `backtest.json` |
| **Data** | Gold in IRR, USD/IRR and gold in USD over the sample; devaluation note | `data/sample/gold_sample.csv` |
| **Model demo** | Pick a sample date with ≥89 rows of history; run the model through `add_stationary_features`; show prediction vs persistence vs realized next-day return; prominent caveat | sample + artifact |
| **About** | Units (Rial, `geram18`), data-source caveat (TGJU permission pending, 200-row sample only), links to the docs | static text + metadata |

Rules:
- No hardcoded metric appears in the file. Every number on **Findings** is read from the
  JSON files; a missing file renders a message, not a stack trace.
- The model load is wrapped in `@st.cache_resource`; a missing artifact renders
  "Model artifacts are missing" with the expected paths.
- The **Model demo** tab states that the realized return is retrospective and that the
  model has no demonstrated edge. It shows no confidence interval.
- Charts use `plotly`, already a dependency.

## 8. Known limitations (all measured, none hidden)

| Limitation | Measurement | Consequence |
|---|---|---|
| EMA warm-up: `macd_norm`/`macd_signal_norm` are seeded at the first supplied row | Max feature difference vs a 2021-seeded full-history frame: 1.6e-4 at 89 rows, 1.1e-8 at 200 rows, 5e-16 at 400. Prediction difference: 5.6e-5 at 89 rows, 3.3e-9 at 200 rows | Serving from 89 rows is *structurally* valid but not bit-identical to full history. The bundled 200-row sample is at the 1e-8 level. Documented in caveat 4; the parity test proves code equivalence on identical rows and separately bounds this effect. |
| Block window unsupported | §2.2 | 503-row window cannot be served from raw rows |
| No rate limiting | §5 | Do not expose publicly |
| No live feed | — | Caller supplies rows |

## 9. How parity is proven

`tests/test_serving_parity.py`:

1. **Feature parity (1e-9).** For ≥20 positions in the sample and a few in the local full
   series, the adapter's feature matrix equals the evaluation frame produced by
   `build_feature_frame(prices, "stationary", "V1")` on the **same input rows** — same rows
   in, same numbers out, so the adapter adds no skew. (V1 and V2 agree outside the block;
   block rows are rejected by the API and excluded from this test. The evaluation frame
   ends one row earlier than the adapter because it needs a next-day target, so the
   comparison is on the common dates. `build_feature_frame` is called directly on the
   price frame, so the test does not need the untracked global cache.)
2. **Prediction parity (1e-6).** The served prediction equals
   `train_predict_lstm`'s inference path — `scaler_X.transform` → model → `scaler_y
   .inverse_transform` — with the same artifact and the same 30-row window.
3. **No lookahead.** Changing rows after *t* leaves the prediction for *t* unchanged;
   appending rows after *t* likewise.
4. **Warm-up bound.** The difference from the full-history frame is asserted to shrink
   with history length at the measured magnitudes above.
