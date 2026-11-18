# Gold_Usd_Oil_IRR — Technical Due-Diligence Report

**Audit date:** 2026-11-13 · **HEAD:** d1670cc (2026-06-16) · **Method:** read-only source review + execution in a scratch copy at `/tmp/gold_audit`. No project file was modified.

> **Note:** a prior session's notes point to `.agents/STATE.md` and `CLAUDE.md`; neither exists in this checkout or in git history. Everything below was re-derived from code and artifacts. Where an old audit's artifact survives (`logs/baseline_metrics.json`, generated 2026-10-03), I reproduced its numbers independently and they match.

---

## 1. Executive Summary

- **What it is:** a real, working data pipeline (TGJU + Yahoo Finance scrape → feature engineering → LSTM → FastAPI → SQLite audit → Prometheus metrics) wrapped in a large amount of MLOps scaffolding and a paper "trading bot" that only emits signals.
- **What genuinely works:** the scraper (3,430 gold + 3,878 USD rows fetched 2026-06-14, `logs/bot_2026-06-14.log`), the 15-feature pipeline, the Keras model load/serve path, `/predict` at ~50 ms warm, API-key auth, rate limiting, SQLite prediction audit, Prometheus counters, and the 24 unit tests that actually run.
- **The model has no predictive edge.** On the chronological test split it is a near-constant predictor (predicted log-return std 0.00057 vs actual 0.0275, correlation −0.017). Log-return R² = −0.0016; it is statistically indistinguishable from a random walk (Diebold-Mariano 0.79, p≈0.43).
- **The headline metric is an artifact.** Price-level R² 0.9717 is exactly the persistence baseline (0.9717); predicted price is `today × exp(≈0)`, so the metric measures the price level, not the model.
- **The backtest is not the model.** `USE_REAL_PREDICTIONS=False` (`trading_bot/config/backtest_config.py:108`) and `main_backtest.py:56-62` substitutes a 5-day rolling mean of past returns. Fresh run: −14.06% return, Sharpe −7.53, 31.6% win rate, vs +1,592% buy-and-hold gold.
- **The live bot is numerically broken.** It reports the standardized model output as a return (`api_layer/live_predictor.py:257`), overstating by 16–24×. The README's "+6.38%" is a real log line; the true value is ≈+0.26%.
- **The "95% confidence interval" is fabricated Gaussian noise** (`src/api/predictor.py:193`), independent of input; its width is always 0.5% of price.
- **MLOps is theatre:** retraining gates use placeholder thresholds (RMSE 47,500 vs real 4.8M; validator max 120,000), so no model can ever be promoted; registry is empty, MLflow has 0 runs, daily drift check is a no-op, ONNX export fails.
- **The README is substantially false:** dataset size/date range, architecture, splits, losses, metrics, backtest numbers, API contract, and phase status are all contradicted by artifacts; line 600 is literal leftover chat text.
- **Units are wrong by 10×:** the data is Rial, labeled "Toman" everywhere. 1B IRR initial capital ≈ $555.
- **Verdict:** a competent MLOps scaffold around a model with zero demonstrated alpha, documented dishonestly. It is salvageable as an honest negative-result / data-pipeline portfolio piece, not as a trading product.

---

## 2. Repository Inventory

### 2.1 Tree (depth 3–4, generated artifacts omitted)

```
Gold_Usd_Oil_IRR/
├── src/
│   ├── api/            main.py, predictor.py, security.py, client_example.py
│   ├── mlops/          17 modules (registry, retraining, drift, audit, alerting, AB, ONNX…)
│   ├── monitoring/     prometheus_exporter.py, supervisor_listener.py
│   ├── data_loader.py  TGJU + Yahoo scraper
│   ├── feature_eng.py  indicators + lags + target
│   ├── data_preprocessor.py  split / scale / window
│   ├── model_builder.py      LSTM + trainer
│   ├── model_evaluator.py    metrics + plots
│   └── train_pipeline.py     orchestrator
├── api_layer/          live bot: data_fetcher, live_feature_engineering,
│                       live_predictor, live_signal_generator, trading_bot,
│                       dashboard, api_config; cache/ + logs/
├── trading_bot/        backtesting engine, strategy, risk, config, outputs/
├── config/             settings.py, logging.py
├── monitoring/         prometheus.yml, alert_rules.yml, grafana provisioning + dashboard
├── data/               raw/final_gold_dataset.csv, processed/advanced_gold_features.csv, *.db
├── models/             gold_lstm_v2.keras, scaler_X.pkl, scaler_y.pkl, registry/ (empty)
├── logs/               training logs, test_metrics.json, baseline_metrics.json, bot logs
├── notebooks/          eda_feature_v1.ipynb, model_experiments.ipynb, catboost_info/
├── tests/              8 test modules (2 sources deleted, .pyc only)
├── outputs/            PNG plots
├── docs/               EMPTY
├── main.py             EMPTY (0 bytes)
├── streamlit_app.py, Dockerfile, docker-compose.yml, supervisord.conf,
│   start.sh, quick-start.sh, requirements.txt, setup.py, README.md, .env
```

### 2.2 Components

| Path | Purpose | Stack | LOC | Last modified |
|---|---|---|---|---|
| `src/api/main.py` | FastAPI app, 12 endpoints, MLOps wiring | FastAPI/Pydantic | 777 | 2026-06-14 |
| `src/api/predictor.py` | model load, predict, "MC" CI | Keras | 265 | 2026-06-14 |
| `src/train_pipeline.py` | 5-step training orchestration | Keras | 315 | 2026-06-14 |
| `src/feature_eng.py` | 27 engineered columns | pandas/numpy | 124 | 2026-06-16 |
| `src/data_preprocessor.py` | chronological split, StandardScaler, windows | sklearn | 219 | — |
| `src/model_builder.py` | 2×LSTM + Dense | Keras | 222 | — |
| `src/mlops/*` | 17 modules, ~1,700 LOC | MLflow/Evidently/Prometheus | ~1,700 | 2026-06 |
| `api_layer/*` | live paper bot | pandas/Keras | ~1,700 | 2026-06-16 |
| `trading_bot/*` | backtest engine + risk + plots | pandas | ~1,900 | 2026-06-10 |
| `streamlit_app.py` | HF Spaces UI | Streamlit | 600+ | 2026-06-08 |
| `tests/`, `test_pipeline.py` | tests | pytest/unittest | ~450 | 2026-06 |

**Total Python:** 9,460 LOC (excluding `.venv`).

### 2.3 Dependencies

| File | Notes |
|---|---|
| `requirements.txt` | TF ==2.20.0, keras<3.13, fastapi ==0.104.1, uvicorn ==0.24.0, mlflow ==2.12.1, evidently ==0.4.20, onnxruntime ==1.23.2, tf2onnx, streamlit, schedule. Mostly pinned, but **missing** yfinance, curl_cffi, pytest, requests (all imported). |
| `Dockerfile` | `FROM python:3.10-slim` (unpinned digest), installs requirements + extra mlflow/streamlit, `USER 1000` (non-root — good), entrypoint `start.sh` → supervisord. |
| `docker-compose.yml` | one service `ml-stack`; no prometheus, no grafana, no separate api/worker. |
| CI | **ABSENT** — no `.github/`, no CI config of any kind. |
| `requirements-api.txt` | does not exist (README references it twice). |

**Environment reality (project `.venv`):** TF 2.20.0, Keras 3.12.4, pandas 2.3.3, sklearn 1.9.1. **mlflow MISSING, yfinance MISSING, curl_cffi MISSING, pytest MISSING.** So as shipped, the live fetcher and offline loader cannot even import.

### 2.4 Git history

- 129 commits, 2025-11-26 → 2026-06-16, single branch `main`.
- Evolution: scraping → feature pipeline → API → backtest → live bot → Docker/Streamlit → MLOps/Phase 5. No abandoned branches.
- Large generated files are committed: `data/processed/advanced_gold_features.csv` (708K), `data/raw/final_gold_dataset.csv` (92K), `models/gold_lstm_v2.keras` (436K), `api_layer/cache/raw_response_*.json` (900K), `outputs/*.png` (~1.5MB), `notebooks/*.ipynb` (888K) — despite `.gitignore` listing `*.csv`, `*.png`, `data/*.db`.
- `models/scaler_X.pkl` and `scaler_y.pkl` are **NOT tracked** (`.gitignore` has `*.pkl`). A fresh clone gets the model but not its scalers → `/predict` cannot run.
- `.env` was never committed (good).

### 2.5 Data & artifacts

| File | Size | Date | Origin |
|---|---|---|---|
| `data/raw/final_gold_dataset.csv` | 92K, 1,424 rows | 2026-06-14 | TGJU (`geram18`, `price_dollar_rl`) + Yahoo (`GC=F`, `BZ=F`), merged `how=left`, ffill |
| `data/processed/advanced_gold_features.csv` | 708K, 1,394 rows, 30 cols | 2026-06-15 | `src/feature_eng.py` |
| `models/gold_lstm_v2.keras` | 436K | 2026-06-15 12:33 | `train_pipeline.py` |
| `models/scaler_X.pkl` / `scaler_y.pkl` | 1.4K / 863B | 2026-06-15 12:32 | fitted on train split |
| `logs/test_metrics.json` | — | 2026-06-15 | training run metrics |
| `logs/baseline_metrics.json` | — | 2026-10-03 | orphan: references `scripts/evaluate_baselines.py`, which no longer exists |
| `data/mlops_audit.db` | 32K | — | 0 rows in all tables |
| `mlflow.db`, `data/mlflow.db`, `mlruns/mlflow.db` | 188–565K | — | 2 experiments, 0 runs each |
| `models/registry/versions/` | empty | — | registry empty |
| `api_layer/cache/signal_history.jsonl` | 7 lines | 2026-02-08 → 2026-06-08 | real bot output |

---

## 3. Findings by Phase

**Severity:** C = Critical, H = High, M = Medium, L = Low.
**Label:** VERIFIED (ran/saw), INFERRED (from code), UNKNOWN.

### Phase 1 — Data & Features

| # | Sev | Finding | Evidence | Label |
|---|---|---|---|---|
| 1.1 | H | Gold series is 18-karat gram, **Rial, not Toman**. `TICKER_GOLD="geram18"`; values 10.5M→206.1M Rial; USD 245k→1.86M Rial. Every "Toman" label is off by 10×. | `config/settings.py:49-50`; data min/max | VERIFIED |
| 1.2 | H | Dataset facts contradict README. 1,424 raw / 1,394 processed rows (not 1,385); starts 2021-06-14 / 2021-07-19 (not 2021-01-27); price range 10.5M–206.1M (not 10.7M–11.6M). | `wc -l`, `df.describe()` | VERIFIED |
| 1.3 | M | Calendar is implausible for an Iranian market. 1,424 rows over 1,825 days (78%); weekday counts: Fri 237, Sat 236, Sun 241, Mon 243, Tue 240, Wed 137, Thu 90. Max gap 13 days. No trading-calendar logic anywhere. | `data/raw/...csv`; no calendar code | VERIFIED |
| 1.4 | M | Naive `how='left'` merge + ffill silently forward-fills global ounce/oil across Iranian holidays and local prices across global weekends; stale values become "features". | `src/data_loader.py:146-158` | VERIFIED |
| 1.5 | H | **No leakage in the target.** `Target_Next_LogRet = Gold_LogRet.shift(-1)`; verified `Target[i] == Gold_LogRet[i+1]` exactly. Split is chronological, scaler fit on train only, windows built within splits. This part is correct. | `src/feature_eng.py:89`; `src/data_preprocessor.py:86-120`; reproduced max diff 0.0 | VERIFIED |
| 1.6 | C | **Raw-level, non-stationary features fed to the model.** `SMA_7`, `MACD`, `Bollinger_*` are price levels (10M–200M). Train→test mean shift: SMA_7 +13.3σ, Bollinger_Upper +13.6σ, MACD +6.6σ. StandardScaler fit on train makes test inputs 13σ out of distribution. | `config/settings.py:67-72`; z-shift computation | VERIFIED |
| 1.7 | H | Feature redundancy: SMA_7 vs Bollinger_Upper corr 0.998, Bollinger_Upper vs Lower 0.992, SMA_7 vs Gold_IRR 0.999. | correlation matrix | VERIFIED |
| 1.8 | M | Global features have no useful lead. Contemporaneous corr with gold return: USD +0.572, ounce +0.165, oil +0.042. At lag 1: USD +0.013, ounce −0.049. No predictive lead. | correlation/lead-lag | VERIFIED |
| 1.9 | L | 0 NaNs, 0 duplicate dates, 0 non-positive prices after processing — data cleaning is sound. | pandas audit | VERIFIED |

### Phase 2 — Modeling & Evaluation

| # | Sev | Finding | Evidence | Label |
|---|---|---|---|---|
| 2.1 | C | **Architecture is 64→32→16, not 128→64→32.** Loaded model: lstm_1 64 units (20,480), lstm_2 32 (12,416), dense_1 16 (528), output 17 = 33,441. 128→64→32 would be 125,249. The README's own parameter count disproves its own architecture. | `models/gold_lstm_v2.keras`; `config/settings.py:85-93` | VERIFIED |
| 2.2 | C | **Model has no edge.** Test (180 windows, 2025-10-02→2026-06-11): log-ret RMSE 0.02750, R² −0.0016, corr(pred,actual) −0.017, directional 55.4% (97/175, binomial p=0.173). Persistence RMSE 0.02762. DM(persistence−LSTM)=0.79, n.s. | `eval_audit.py`; matches `logs/test_metrics.json` and `logs/baseline_metrics.json` | VERIFIED |
| 2.3 | C | **Predictions are near-constant and always positive.** mean 0.00217, std 0.00057, min 0.00100, max 0.00347 — vs actual std 0.0275. 55.4% "directional accuracy" is simply the share of up-days; the model always says "up". | `eval_audit.py` | VERIFIED |
| 2.4 | C | **Price-level R² 0.9717 is the random-walk baseline.** `predicted_price = base × exp(pred_ret)`; with pred≈0 this is today's price. Persistence scores the same R² and a better RMSE (4,839,880 vs 4,840,917) and MAPE (1.676% vs 1.702%). | `src/model_evaluator.py:119-123`; reproduced | VERIFIED |
| 2.5 | C | **Reported log-return R² 0.0824 is not produced by this code.** `evaluate_predictions` copies only `log_return_rmse` and `log_return_mae`; the training log shows R² −0.0016. 0.0824 is fabricated or from a different dataset. | `src/model_evaluator.py:126-128`; `logs/training_20260615_123255.log` | VERIFIED |
| 2.6 | C | **"Confidence interval" is fake.** `noise = np.random.normal(0, base_pred*0.005, n)`; no dropout, no MC. Width is always ±~1% of price regardless of input. | `src/api/predictor.py:188-194` | VERIFIED |
| 2.7 | H | Saved artifacts are internally consistent (the one good news): saved scaler mean/scale match a fresh refit to 0.0, feature count 15, and the model reproduces `logs/test_metrics.json` exactly. The model is bad, not mismatched. | `eval_audit.py` scaler check | VERIFIED |
| 2.8 | M | Train loss 0.9636 / val 2.3695 over 16 epochs, 20.7 s; val loss never improved after epoch 1 (early stop). Classic overfit/no-signal. | `logs/training_history.json` | VERIFIED |
| 2.9 | L | RSI is computed with `rolling().mean()` (SMA-style), not Wilder's smoothing; live RSI uses a different (last-14 mean) implementation. Minor but a train/serve skew. | `src/feature_eng.py:19-29`; `api_layer/live_feature_engineering.py:68-85` | VERIFIED |

### Phase 3 — Backtesting

| # | Sev | Finding | Evidence | Label |
|---|---|---|---|---|
| 3.1 | C | **The backtest does not use the LSTM.** `USE_REAL_PREDICTIONS=False`; `Predicted_LogRet` = 5-day rolling mean of past returns shifted 1. The "AI trading strategy" is a momentum heuristic. | `trading_bot/config/backtest_config.py:108`; `main_backtest.py:46-62` | VERIFIED |
| 3.2 | C | **README backtest numbers are fabricated.** Committed file: −12.03%, Sharpe −7.36, maxDD 15.10%, 30 trades, 40% win, benchmark +1,184.9%. Fresh run: −14.06%, −7.53, 15.70%, 38 trades, 31.6%, benchmark +1,591.9%. README: +45.23%, 1.85, −12.4%, 62.5%, 156/97. | `trading_bot/outputs/backtest_metrics.json`; re-run output | VERIFIED |
| 3.3 | M | Committed metrics are stale relative to committed data: metrics say 2021-01-27→2025-12-20 / 1,384 days; `portfolio_log.csv` ends 2026-06-11 / 1,394 days. | files | VERIFIED |
| 3.4 | H | In-sample, full-history backtest (2021-07→2026-06), no train/test separation; `WALK_FORWARD_VALIDATION=False` ("Not implemented yet"). | `backtest_config.py:74`; `main_backtest.py:192` | VERIFIED |
| 3.5 | H | Costs are optimistic for Iranian retail gold: 0.5% commission + 0.2% slippage = 0.7%/side. No bid-ask spread (often 1–3%), no tax, no liquidity limit. | `backtest_config.py:21-22` | VERIFIED |
| 3.6 | M | Benchmark exists but is omitted from README. The strategy loses 12–14% while buy-and-hold gold gains 1,185–1,592%. This is the single most important number and it is hidden. | `performance_metrics.py:198-206` | VERIFIED |
| 3.7 | M | Capital is economically trivial: 1B IRR ≈ $555 at 1.86M Rial/USD. Positions are ~$200. Costs/liquidity at this scale are not representative. | data + config | VERIFIED |
| 3.8 | L | No shorting (SELL is only an exit), close-only execution, 3% stop / 5% TP, 30-day max hold. Reasonable mechanics, but no slippage on stops and no gap handling. | `backtest_engine.py`; `risk_manager.py` | INFERRED |
| 3.9 | L | Sharpe annualizes with 252 days and uses nominal 20% risk-free — defensible in nominal IRR, but never stated; no inflation-adjusted return. | `performance_metrics.py:57,85` | VERIFIED |

### Phase 4 — API & Serving

| # | Sev | Finding | Evidence | Label |
|---|---|---|---|---|
| 4.1 | H | `/predict` is `async def` but calls blocking `model.predict()` — blocks the event loop; no threadpool. With `--workers 2` this is the only concurrency. | `src/api/main.py:299-360`; `supervisord.conf [program:fastapi]` | VERIFIED |
| 4.2 | H | `/predict-from-history` is not "automatic feature engineering". It requires the caller to supply all 15 pre-computed features (Gold_LogRet, SMA_7, MACD…), then takes the last 30 rows. The README's `historical_prices`/`usd_rates` schema returns 422. | `src/api/main.py:73-94, 430-476`; `predictor.py:243-249`; live test 422 | VERIFIED |
| 4.3 | H | README `/predict` contract is wrong. It documents a flat 450-float array; actual schema is 30×15 nested lists. Flat 450 → 422 "too_long". | `src/api/main.py:49-54`; live test | VERIFIED |
| 4.4 | H | **Auth cannot work from `.env`.** No python-dotenv anywhere; `API_KEY` is read from the process env at import. `.env` is never loaded, and its `API_KEY` is a placeholder. With no exported key, every protected endpoint returns 503. | `src/api/security.py:23-24`; grep for dotenv (none); `.env` inspection | VERIFIED |
| 4.5 | M | API key comparison is not constant-time (`api_key != API_KEY_VALUE`). | `src/api/security.py:76` | VERIFIED |
| 4.6 | M | Rate limiter is per-process in-memory, keyed by client IP; `--workers 2` doubles the effective limit and breaks fairness behind a proxy. | `security.py:31-61`; `supervisord` workers=2 | VERIFIED |
| 4.7 | M | `/metrics` is unauthenticated and exempt from rate limiting. | `main.py:238-239` | VERIFIED |
| 4.8 | M | Health check ignores model freshness. `/health` returns `status: true` while `model_fresh: false` (3,632 h old > 720 h limit). | `main.py:284-296, 699-717` | VERIFIED |
| 4.9 | L | CORS is a fixed localhost allowlist (not `*`) — good. Docker runs non-root — good. | `main.py:223-236`; `Dockerfile USER 1000` | VERIFIED |
| 4.10 | L | Pydantic v1 `@validator`/`min_items` are deprecated on Pydantic 2.14 (warnings on startup). | pytest output | VERIFIED |

### Phase 5 — Live Trading Bot (Paper)

| # | Sev | Finding | Evidence | Label |
|---|---|---|---|---|
| 5.1 | C | **Scale bug: standardized output reported as a return.** `pred_log_return = model.predict(...)` is in scaled units; `scaler_y` is never loaded or applied; then ×100. Reproduced: raw 0.035818 → reported 3.58%, true 0.219% (16.3×). README's +6.38% is this bug. | `api_layer/live_predictor.py:257-260`; `api_config.py:51` (only scaler_X); reproduction | VERIFIED |
| 5.2 | C | Confidence 85% is an arbitrary threshold on the mis-scaled value: `abs_return > 0.02 → 0.85`. Every one of the 7 stored signals has confidence exactly 0.85. | `live_predictor.py:286-300`; `signal_history.jsonl` | VERIFIED |
| 5.3 | C | **Stale-history gap corrupts features.** Live features = last 30 rows of a CSV ending 2026-06-13 + one live row dated "now". The "daily" log return becomes a multi-month return; `latest_features.json` contains Gold_LogRet = −2.484 (a −91.7% "daily" move) from a test run. | `live_feature_engineering.py:139-144,174-211`; cache file | VERIFIED |
| 5.4 | H | **Training/serving unit mismatch:** training uses TGJU column index 3 = Close; live `get_latest_price` uses index 0 = Open. | `src/data_loader.py:62-70`; `api_layer/data_fetcher.py:161`; raw response row `['1,609,350','1,572,300','1,624,700','1,622,400',…]` | VERIFIED |
| 5.5 | H | README duplicates the SMA30 value into the SMA7 line. The actual record is `price_vs_sma7 = 29.18%`, `price_vs_sma30 = 48.38%`; README prints 48.38% twice. | `signal_history.jsonl` (2026-02-16) | VERIFIED |
| 5.6 | H | **No broker/exchange integration, no orders, no position/PnL tracking.** `PAPER_TRADING_MODE` appears only in a log string. "Paper mode" is safe only because nothing executes. | `api_layer/trading_bot.py:204`; grep for broker/order/execute | VERIFIED |
| 5.7 | M | Fetcher is undeclared and brittle: yfinance/curl_cffi missing from requirements; TGJU response parsing assumes list rows and positional columns; no Persian-digit handling; cached fallback is 24h stale. | `api_layer/data_fetcher.py:17-18,157-174`; dependency check | VERIFIED |
| 5.8 | M | Signal history is tiny and partly nonsensical: 7 records, 6 BUY / 1 SELL, all 0.85 confidence; first record claims +442.95% predicted return while its own `predicted_log_return` is 0.0443 (internally inconsistent). Duplicate runs produce duplicate signals. | `signal_history.jsonl` | VERIFIED |
| 5.9 | L | Forward check (n=7, not significant): 6 BUYs followed by +0.39…+2.96% next day; the one SELL (2026-06-08) followed by −0.76% / −4.66%. The market was in a broad uptrend; no statistical power. | computed from raw prices | VERIFIED |

### Phase 6 — MLOps Layer

| Feature | Status | Evidence |
|---|---|---|
| Background scheduler (weekly retrain, daily drift) | IMPLEMENTED BUT NON-FUNCTIONAL | `scheduler.py:18-24` schedules Sunday 02:00 + daily 06:00; `initialize_mlops` passes no `daily_drift_data_supplier`, so daily check calls `get_drift_report()` and returns the last (usually None) report (`scheduler.py:50-56`). |
| Filesystem model registry + promotion + rollback | IMPLEMENTED, EMPTY | `model_registry.py` is coherent; `models/registry/versions/` empty, no `metadata.json`. Logs claim "Promoted … version 2" from deleted test runs. |
| Drift detection | IMPLEMENTED, MISAPPLIED | `drift_detector.py` (Evidently → KS+mean-shift fallback). Reference = `X_train` flattened, current = `X_test`; a one-time train/test comparison, not production drift. With raw-level features it will always fire. |
| Retraining + validation/promotion gates | IMPLEMENTED BUT IMPOSSIBLE TO PASS | Placeholder baseline rmse=47,500, r2=0.85 (`retraining_pipeline.py:42-48`); validator `rmse_max=120,000` (`model_validator.py:14-19`). Real price RMSE is 4.8M → every model is rejected. Worse: `_train_and_evaluate` runs `TrainingPipeline`, which **overwrites `models/gold_lstm_v2.keras` and the scalers before any gate** (`train_pipeline.py:103,168`). |
| Prometheus metrics | IMPLEMENTED AND WORKING | `/metrics` returns real histograms/counters (verified); `MetricsExporter` uses its own registry. |
| Grafana dashboards as code | FILES EXIST, NO SERVICE | `monitoring/grafana/...` + dashboard JSON exist; `docker-compose.yml` has no Grafana/Prometheus. `prometheus.yml` targets `api:8000` / `mlops-worker:8001`, which do not exist in compose. |
| SQLite audit persistence | IMPLEMENTED AND WORKING | Live test: 118 prediction rows written; schema for predictions/training_runs/api_events. No WAL/busy_timeout; 2 workers can hit "database is locked". |
| Health checks (disk/memory/freshness/DB) | IMPLEMENTED, FRESHNESS IGNORED | `/health` computes `model_fresh` but does not include it in `overall_ok` (`main.py:290`). |
| Alert hooks (Slack/Telegram/SMTP) | IMPLEMENTED, NEVER EXERCISED | `alerting.py` real; all channel env vars empty; no evidence of a sent alert. |
| Docker Compose stack | BROKEN AS DOCUMENTED | `docker compose config` valid, but only one service `ml-stack`; README claims api/worker/prometheus/grafana. `docker build` attempted, did not finish in ~12 min (Debian apt downloads extremely slow); base `python:3.10-slim` now pulls trixie/python3.13 system packages (unpinned drift). |
| CI/CD, MLflow, A/B testing | ABSENT / DISABLED | No `.github`; mlflow package missing in venv and `MLFLOW_TRACKING_URI` unset → tracker disabled; all 3 MLflow DBs have 0 runs; A/B code exists but `AB_TESTING_ENABLED` defaults false and registry is empty. |
| Reproducibility (seeds, data versioning, one command) | PARTIAL | `np.random.seed(42)` and `tf.random.set_seed(42)` set; no DVC; scalers untracked; no single command retrains end-to-end; `quick-start.sh` only builds Docker. |

**Over-engineering verdict:** ~1,700 LOC of MLOps (registry, canary A/B, governance model cards, ONNX, 5-service supervisor) around a model whose log-return R² is −0.0016 and whose best "feature" is the price level. The machinery is more sophisticated than the signal.

### Phase 7 — Code Quality

| Sev | Finding | Evidence |
|---|---|---|
| H | Feature engineering duplicated with divergent implementations (`src/feature_eng.py` vectorized vs `api_layer/live_feature_engineering.py` scalar; different RSI/SMA/fallbacks). This is the root of the serving skew. | both files |
| H | Broken imports in shipped tests: 3/8 test modules fail collection (yfinance missing; `data_fetcher`/`live_feature_engineering` not importable from repo root). | pytest output |
| M | Dead/abandoned code: `main.py` empty; `docs/` empty; `notebooks/catboost_info/` committed; `test_no_leakage.py` and `test_baselines.py` exist only as `.pyc` (sources deleted); `logs/baseline_metrics.json` references a nonexistent `scripts/` dir. | filesystem |
| M | Artifacts tracked despite `.gitignore` (`*.csv`, `*.png`, `*.pkl`); scalers not tracked. Inconsistent policy. | `git ls-files` |
| M | Stale artifacts presented as current (backtest metrics, README dated Feb 16 while HEAD is Jun 16). | files |
| L | No hardcoded absolute paths in source (good). Type hints are good in `src/mlops/`, inconsistent elsewhere. Logging is duplicated per module with different handlers. | grep |
| L | No lock file / no pinned hash; `keras<3.13` is a range while `tensorflow==2.20.0` is exact. | `requirements.txt` |

**Portfolio first-10-minutes impression:** the README promises a production LSTM trading system; the repo shows an impressive service graph, then collapses the moment you open `test_metrics.json` (log-ret R² −0.0016) or `backtest_metrics.json` (−12% vs +1,185%). A senior reviewer will notice the fake CI (`predictor.py:193`), the 10× unit mislabel, and the fabricated README within minutes.

**Top 10 defects by severity:**

1. No predictive edge; near-constant predictions (C).
2. Raw-level non-stationary features → 13σ test shift (C).
3. Price-level R² is the persistence baseline; reported as model skill (C).
4. Live bot reports standardized output as return (16–24×) (C).
5. Fake Monte-Carlo confidence interval (C).
6. Backtest uses a rolling-mean heuristic, not the model; in-sample (C).
7. MLOps gates use placeholder thresholds; retraining overwrites production before gating (C).
8. README quantitatively fabricated and self-contradictory (C).
9. Rial labeled Toman; $555 capital (H).
10. Training/serving skew: Open vs Close, stale history gap, duplicated feature code (H).

### Phase 8 — Product & Economic Reality

**Is there an edge net of costs?** No evidence. Log-return R² −0.0016, corr −0.017, DM n.s. With 180 test observations, the 95% CI on directional accuracy is roughly ±7%; even a true 55% hit rate would be marginal after 1.4% round-trip costs. The only robust relationship is contemporaneous USD/IRR (0.57); it cannot forecast tomorrow's gold unless USD itself is forecast.

**Domain realities the code ignores:**

- Free-market USD/IRR is the dominant driver; the model includes it but cannot lead it.
- Coin bubble/premium over intrinsic gold value is not modeled; `geram18` is a gram price, not a coin.
- Iranian market calendar, holidays, price limits, and trading halts: no handling.
- Bid-ask spreads and retail access: not modeled (0.2% slippage is optimistic).
- Gold ETF/fund NAV premium on TSE: absent.
- Sanctions/regulatory constraints, data-source fragility (TGJU WAF, HTML/API changes): handled only by a curl_cffi impersonation hack.
- Structural breaks (devaluation): the 2021→2026 20× move means any level-based model is invalid across regimes.

**Plausible product?** A data + monitoring dashboard for Iranian gold/USD (with honest "no forecast" positioning) is plausible; a signal service is not, on this evidence, and publishing trading signals in Iran carries regulatory/licensing exposure. Realistic MVP: 2–4 weeks for a trustworthy data product; the forecasting product needs a genuinely new research effort.

**Recurring cost/effort:** data sources are free but fragile (scraper maintenance ~2–4 h/month); hosting a small API+dashboard ~$5–20/month; monitoring/maintenance ~2–4 h/month. Benefit is currently negative (the strategy loses money vs buy-and-hold).

---

## 4. README Claim Verification Table

| # | Claim (README line) | Where it comes from | Status | Notes |
|---|---|---|---|---|
| 1 | 1,385 daily observations (L66) | `data/processed/...csv` | CONTRADICTED | 1,394 processed / 1,424 raw |
| 2 | Starts 2021-01-27 (L92) | data | CONTRADICTED | 2021-06-14 raw / 2021-07-19 processed |
| 3 | 15 features (L68) | `config/settings.py:62-78` | VERIFIED | exactly 15 used |
| 4 | Price range 10.7M–11.6M Toman (L92) | data | CONTRADICTED | 10.5M–206.1M Rial |
| 5 | LSTM 128→64→32 (L100-106) | model file | CONTRADICTED | 64→32→16 |
| 6 | 33,441 parameters (L108) | model | VERIFIED | but proves 64→32→16 |
| 7 | Adam lr 0.0005, epochs 150, batch 32 (L109-119) | `config/settings.py:91-93` | CONTRADICTED | lr 0.001, epochs 100, batch 16 |
| 8 | Split 940/177/177 (L130-132) | log | CONTRADICTED | 976/209/209 rows; 947/180/180 windows |
| 9 | 20 s, 17/150 epochs (L136-137) | `logs/training_20260615...log` | PARTIAL | 20.7 s true; 16 epochs |
| 10 | Train/val loss 0.8946/1.1533 (L138-139) | `logs/training_history.json` | CONTRADICTED | 0.9636/2.3695 |
| 11 | Price RMSE 1,715,089 / MAE 1,126,082 (L145-146) | `logs/test_metrics.json` | CONTRADICTED | 4,840,917 / 2,883,360 |
| 12 | Price R² 0.9938 (L147) | metrics | CONTRADICTED | 0.9717 = persistence |
| 13 | MAPE 1.42% (L148) | metrics | CONTRADICTED | 1.70% |
| 14 | Log-return R² 0.0824 (L153) | code | CONTRADICTED | −0.0016; code doesn't compute it |
| 15 | Log-return RMSE 0.0340 (L151) | metrics | CONTRADICTED | 0.0275 |
| 16 | `/predict` flat 450 floats (L228) | `main.py:49` | CONTRADICTED | 30×15; flat → 422 |
| 17 | `/predict-from-history` arrays (L269-274) | `main.py:75` | CONTRADICTED | `historical_data: List[Dict]`; arrays → 422 |
| 18 | Response time <100 ms (L594) | live test | VERIFIED (warm) | 48–52 ms warm, 273 ms cold |
| 19 | Backtest +45.23%, Sharpe 1.85, DD −12.4%, 62.5%, 156/97 (L636-641) | `backtest_metrics.json` | CONTRADICTED | −12.03%, −7.36, −15.10%, 40%, 30/12; fresh −14.06% |
| 20 | 97/156 = 62.5% | arithmetic | CONTRADICTED | 97/156 = 62.18% |
| 21 | Live +6.38%, 85%, RSI 96.2, MACD 9,705,105 (L735-744) | `signal_history.jsonl` | VERIFIED (real output) | but output is wrong (scale bug) |
| 22 | Price vs SMA7 +48.38% (L743) | same record | CONTRADICTED | actual 29.18%; 48.38% is SMA30 |
| 23 | "Phase 4 MLOps (Completed)" (L9) | code | CONTRADICTED | gates broken, registry empty, MLflow 0 runs |
| 24 | "Phase 4 … IN PROGRESS" checklist (L806-820) | — | CONTRADICTS L9 | self-contradictory status |
| 25 | Multi-service stack api/worker/prometheus/grafana (L16) | `docker-compose.yml` | CONTRADICTED | one service `ml-stack` |
| 26 | `requirements-api.txt` (L296, L408, L458) | filesystem | CONTRADICTED | file absent |
| 27 | `src.pipeline.train_pipeline` / `src.config.config_settings` (L414-415) | filesystem | CONTRADICTED | actual `src/train_pipeline.py`, `config/settings.py` |
| 28 | Paper mode enforced (L697) | `trading_bot.py` | MISLEADING | no execution code exists at all |
| 29 | "Automatic Feature Engineering" (L177) | `main.py:454` | CONTRADICTED | requires pre-computed features |
| 30 | "Model Version gold_lstm_v2" (L852) | model | VERIFIED | file exists |
| 31 | "Last Updated Feb 16, 2026" (L846) | git | STALE | HEAD 2026-06-16 |
| 32 | "Phase 1-3 complete / production-ready" (L7, L573) | evidence | CONTRADICTED | model has no skill; backtest loses money |

**Leftover AI-chat / copy-paste artifacts:** L600 ("I'll first examine your uploaded files… Now let me provide you with the requested sections formatted as markdown code blocks:"), the `---`/`---` double separator at L560-561, inconsistent heading levels, and the "3.5 Monitoring" / "3 System Architecture" numbering that belongs to a chat response, not a README.

---

## 5. Experiment Results

All runs were in `/tmp/gold_audit` (rsync copy of the repo, no `.venv`/`.git`). Python: project `.venv` (3.12.3, TF 2.20.0). pytest was installed to `/tmp/pytestpkg` (not into the project).

### 5.1 Backtest (fresh run)

```text
$ cd /tmp/gold_audit/trading_bot && MPLBACKEND=Agg python main_backtest.py
📅 Period: 2021-07-19 to 2026-06-11   Duration: 1394 days (5.53 years)
💰 Initial Capital: 1,000,000,000 IRR   Final: 859,421,877 IRR
   Total Return: -14.06 %   CAGR: -2.70 %
📉 Volatility: 3.01 %   Max Drawdown: 15.70 %
   Sharpe: -7.53   Sortino: -4.44   Calmar: -0.17
📈 Total Trades: 38   Winning: 12   Losing: 26   Win Rate: 31.58 %
   Profit Factor: 0.43   Avg Holding: 7.6 days
📊 Strategy: -14.06 %   Benchmark: 1591.94 %   Alpha: -1606.00 %
```

### 5.2 Baselines + LSTM on the exact chronological test split

```text
$ python eval_audit.py
rows=1394 train=976 val=209 test=209
train 2021-07-19..2024-12-24
test  2025-10-02..2026-06-11
[scaler check] max |saved mean - refit mean| = 0.0
saved y mean/std = 0.001622 0.015964  refit = 0.001622 0.015964
[model] input (None, 30, 15) params 33441

model              rmse      mae    r2_sk  r2_zero  dir_acc
lstm            0.02750  0.01696  -0.0016   0.0084   0.5543
ridge_a0.1      0.03602  0.02589  -0.7176  -0.7003   0.4914
ridge_a1.0      0.03460  0.02480  -0.5849  -0.5691   0.4629
ridge_a10.0     0.03030  0.02073  -0.2157  -0.2035   0.4571
ridge_a100.0    0.02801  0.01851  -0.0386  -0.0282   0.5486
persistence     0.02762  0.01674  -0.0101   0.0000   0.0000
momentum        0.03668  0.02285  -0.7816  -0.7637   0.4514

LSTM directional: 97/175 = 0.5543, binomial p=0.1734
persistence DM vs lstm: 0.792
momentum    DM vs lstm: 2.833
ridge(1.0)  DM vs lstm: 3.550
LSTM pred logret: mean=0.002166 std=0.000568 min=0.000997 max=0.003472
actual      logret: mean=0.002765 std=0.027481
corr(pred,actual) = -0.0174
lstm         price RMSE=4,840,917 R2=0.9717 MAPE=1.702%
persistence  price RMSE=4,839,880 R2=0.9717 MAPE=1.676%
```

This reproduces `logs/test_metrics.json` exactly (RMSE 4,840,916.90, MAE 2,883,359.74, R² 0.9717, MAPE 1.7017, log-ret RMSE 0.0275036) and the 2026-10-03 `baseline_metrics.json` (LSTM log-ret R² −0.0016, dir 53.9%).

### 5.3 Data / correlation audit

```text
Gold_IRR min/max: 10,537,000 / 206,141,000   (Rial)
USD_IRR  min/max:    245,190 /   1,864,100   (Rial)
1B IRR in USD at last rate: $555
raw daily ret: mean 0.001951 std 0.018716 frac_pos 0.5032
weekday counts: Mon 243 Tue 240 Wed 137 Thu 90 Fri 237 Sat 236 Sun 241
max gap: 13 days (2025-06-24)
corr(Gold_LogRet, USD_LogRet)   = +0.572
corr(Gold_LogRet, Ounce_LogRet) = +0.165
corr(Gold_LogRet, Oil_LogRet)   = +0.042
lead-lag USD k=1 +0.013, ounce k=1 -0.049
train->test z-shift: SMA_7 +13.3σ, Bollinger_Upper +13.6σ, MACD +6.6σ
```

### 5.4 Live scale-bug reproduction

```text
live-window model raw output (scaled space): 0.035818
live code would report: 3.58%
correct inverse-transformed log return: 0.002194 (0.219%)
ratio (overstatement): 16.3x
```

### 5.5 API (uvicorn on 127.0.0.1:8010, scratch copy)

```text
GET /health -> 200
{"status":true,"model_loaded":true,"checks":{"auth_required":true,
 "disk_ok":true,"memory_ok":true,"model_freshness_hours":3632.07,
 "model_fresh":false,"audit_store_ok":true}}

GET /model-info (no key) -> 401 {"detail":"Invalid or missing API key"}
GET /model-info (key) -> 200, total_parameters 33441, input (None,30,15), onnx_path null

POST /predict x5 (real 30x15 payload):
 run1 0.273 s (cold), run2-5 0.048-0.052 s
 predicted_log_return 0.0021939, predicted_price 179,061,414

POST /predict-with-confidence?n_simulations=100:
 payload A (price 178,669,000): std_dev 990,842  -> 48.8 ms
 payload B (price 144,000,000): std_dev 742,036  -> 50.0 ms
 (width is always ~0.5% of price, independent of features)

Rate limit: 130 rapid requests -> 111x200, 19x429 (120/min)
Audit DB: predictions 118, training_runs 0, api_events 0

README flat-450 payload -> 422 too_long
README history-array payload -> 422 missing historical_data
actual historical_data schema -> 200

ONNX export -> ensure_onnx_artifact returned None ("ONNX export skipped: 'keras_tensor_20'")
```

### 5.6 Tests

```text
$ python -m unittest test_pipeline -v
Ran 14 tests in 4.617s
OK            # synthetic random data only

$ pytest tests/  (project pytest absent; installed to /tmp/pytestpkg)
test_mlops_endpoints.py            1 passed
test_mlops_background_tasks.py     2 passed
test_mlops_api_integration.py      1 passed
test_phase5_mlops.py               6 passed
test_data_fetcher.py               ERROR: No module named 'yfinance'
test_live_predictor.py             ERROR (import path)
test_live_signal_generator.py      ERROR: No module named 'yfinance'
```

### 5.7 Docker

```text
$ docker compose config  -> exit 0
  (warning: `version` attribute is obsolete)
  services: ml-stack   (only one)

$ docker build --progress=plain -t gold-audit-img .
  -> did not complete in ~12 min; Debian apt download of 107 MB was extremely slow.
     Base image `python:3.10-slim` now resolves to Debian trixie and pulls
     python3.13 system packages (unpinned base-image drift).
```

---

## 6. Scorecard

| Dimension | Score | One-line justification |
|---|---|---|
| Data quality | 4/10 | Real scraped data, clean NaNs/dupes; but 10× unit mislabel, implausible calendar, 13-day gaps, ffill across markets, no versioning. |
| Modeling validity | 2/10 | Near-constant predictions; raw-level features 13σ OOD at test; correlation with actual −0.017. |
| Evaluation honesty | 2/10 | Price R² is persistence; log-ret R² hidden; fake CI; README metrics fabricated. |
| Backtest realism | 2/10 | Not the model; in-sample; optimistic costs; hidden buy-and-hold; $555 capital. |
| API/serving quality | 5/10 | Endpoints, validation, auth, audit, rate limit work; blocking async, in-memory limiter, wrong docs, fake CI, no scalers in git. |
| MLOps maturity (real vs claimed) | 3/10 | Real code, but gates impossible to pass, registry empty, 0 MLflow runs, drift no-op, ONNX broken, no Prometheus/Grafana service. |
| Code quality | 4/10 | Clear module layout and some good typing; duplication, dead files, broken test imports, stale artifacts. |
| Documentation accuracy | 1/10 | Most quantitative claims contradicted; leftover chat text; contradictory status. |
| Portfolio value | 3/10 | Impressive surface, collapses under 10 minutes of scrutiny; the honest negative result is the only durable asset. |
| Product/economic viability | 2/10 | No edge, no execution, trivial capital, regulatory exposure, fragile data source. |
| **Overall** | **2.8/10** | A solid MLOps scaffold around a model with no alpha, documented dishonestly. |

---

## 7. Salvage Options

### A) Archive as-is with an honest README — 2–4 hours, risk: low, payoff: low

Rewrite `README.md` to: real dataset (1,424 rows, 2021-06-14→2026-06-13, Rial), real architecture (64→32→16, 33,441), real metrics (price R² 0.9717 = persistence; log-ret R² −0.0016), real backtest (−14.06% vs +1,592%), and a "Known limitations / negative result" section. Delete or quarantine the fabricated numbers and the chat artifact. Payoff: stops the project from being actively misleading; still a weak portfolio piece because the headline result is "no signal".

### B) Refactor into a high-quality portfolio piece — 3–6 days, risk: medium, payoff: high

- **Cut:** the "trading bot" narrative, canary A/B, governance model cards, ONNX, the fake MC CI, the 5-service supervisor, and the duplicated live feature code.
- **Fix:** make the model predict returns with stationary features only (returns, RSI, MACD normalized by price, realized vol); add a proper walk-forward evaluation; always report persistence + ridge baselines; add a Diebold-Mariano test; report log-return R², not price R².
- **Backtest:** run out-of-sample only, with 1.5–3% round-trip costs, and always show buy-and-hold gold and USD benchmarks.
- **MLOps:** keep only what works (FastAPI + SQLite audit + Prometheus + one retrain script with a real baseline and a gate that can pass); delete the rest or mark it "experimental".
- **Repro:** commit scalers, add `make train`, `make test`, `make api`; add a small CI workflow; one-command Docker.
- **Narrative:** "I built an end-to-end pipeline; the LSTM has no edge over a random walk; here is the evidence and what I learned." That is a stronger interview story than the current one.
- **Payoff:** turns the repo from a liability into a credible demonstration of evaluation discipline.

### C) Pivot to a data + monitoring product — 1–2 weeks, risk: medium-high, payoff: medium

Keep the TGJU/Yahoo fetcher, feature store, FastAPI, SQLite audit, Prometheus, and the dashboard. Drop all forecasting claims. Ship an "Iranian gold & USD market monitor": daily gram-18 price, USD/IRR, ounce, oil, spreads, 30-day vol, anomaly alerts, and a public JSON API. Reuse ~60% of the code. Risks: data-source ToS/fragility, sanctions/payment rails, and the fact that a monitoring product has weak willingness-to-pay without proprietary data.

### D) Abandon, extract lessons — 0 hours, risk: none, payoff: learning only

Keep: `src/data_loader.py` (working scraper), `src/feature_eng.py` (clean feature code), `src/model_evaluator.py` (reusable metrics), and the evaluation harness in `eval_audit.py`. Delete the rest. The main lesson is methodological: price-level R² and "always-up" directional accuracy are traps; always compare against persistence and buy-and-hold.

---

## 8. Recommendation

**Recommendation: B — refactor into an honest portfolio piece, with C as an optional stretch.**

**Top reasons:**

1. The engineering scaffolding is real and reusable; the model is not. Refactoring preserves the valuable part.
2. The current README is actively harmful to the author's credibility; an honest negative-result narrative is both more defensible and more impressive to a senior reviewer.
3. The backtest and live-bot bugs are fixable in days, but the absence of alpha is not; pretending otherwise will not survive an interview.

**First 5 concrete actions, in order:**

1. **Freeze the claims:** replace the README with measured numbers and a "Limitations / negative result" section; delete the chat artifact and contradictory phase markers.
2. **Fix the evaluation contract:** report log-return R², RMSE/MAE, directional accuracy with a binomial test, and DM vs persistence; make price-level R² secondary and label it "persistence baseline".
3. **Rebuild features to be stationary** (returns, normalized indicators) and re-run the walk-forward evaluation; if the edge is still zero, say so and stop.
4. **Make the backtest honest:** use the model (or explicitly label it a momentum baseline), out-of-sample only, 1.5–3% costs, and always show buy-and-hold gold and USD.
5. **Fix or remove the live layer:** apply `scaler_y`, use the same Close-price field as training, refuse to run on stale history, and replace the fake CI with a real residual-based interval or delete the endpoint. Delete the unused MLOps modules or mark them "experimental".

---

## 9. Open Questions

1. **Data origin/licensing:** do you have permission to redistribute TGJU data? Is `geram18` the intended product (18k gram) or did you mean a coin (e.g., sekeb, emami)?
2. **Unit convention:** the series is Rial; do you want to keep Rial, or convert to Toman (÷10) everywhere? This changes every number in the README and the $555 capital framing.
3. **The +442.95% signal record:** was `signal_history.jsonl` hand-edited? Its `predicted_log_return` (0.0443) and `predicted_return_pct` (442.95) are inconsistent by 100×.
4. **Intent:** is this a portfolio piece, a real trading tool, or a learning exercise? The answer determines whether B or C is right.
5. **Why the level features?** Was there a reason to feed raw SMA_7/MACD/Bollinger (rather than normalized versions) alongside returns? This is the single largest modeling defect.
6. **The missing `.agents/` audit:** a prior session's `STATE.md`/`ROADMAP.md` are referenced in memory but absent from this checkout. Were they intentionally deleted, or is this a different working copy?
7. **MLflow:** the package is missing from the venv and the DBs have 0 runs — was MLflow ever actually exercised, or only scaffolded?
8. **Deployment target:** the Dockerfile targets a platform-specific Streamlit port, while the README documents a 4-service compose stack. Which is the real target? *(Vendor name and port redacted in Stage 6 per the owner's release instruction; the finding is unchanged.)*

---

**Bottom line:** keep the scraper, the feature code, and the API; delete the fiction. The most valuable thing this repo can become is a rigorous, honest demonstration that an LSTM on 1,394 daily observations does not beat a random walk — provided the author is willing to say so in the README.