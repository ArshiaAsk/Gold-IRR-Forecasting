# README claims — source and verification

Every quantitative or status claim in `README.md`, with the committed file it comes from and
the command or read that verified it. Written for Stage 5b (2026-11-17). The automated check
covers the 58 marked numbers (`scripts/check_readme_numbers.py`); this table covers the prose,
the status statements and the numbers that are not in a marked block.

Paths are relative to the repository root. `eval_V2.json` means `results/eval_V2.json`.

## Status and structure

| Claim in README | Source | Verified by |
|---|---|---|
| The pipeline covers data → stationary features → LSTM → API/Streamlit | `src/`, `streamlit_app.py` | read `src/` tree and the app; `make test` exercises the paths |
| The model has no demonstrated predictive edge | `eval_V2.json` → `edge_verdict.edge_demonstrated: false`, `finding` | read the JSON; `docs/RESULTS.md` §6 |
| A prediction-driven rule adds no value over buy-and-hold | `backtest.json` → `verdict.finding` | read the JSON; `docs/RESULTS.md` §11.8 |
| Nominal gains are mostly rial devaluation | `backtest.json` → `strategies.C0.S0/S1.total_return`, `gold_in_usd.total_return` | the three returns compared; §11.7 |
| Protocol committed before fitting / backtest | `docs/EVAL_PROTOCOL.md`, `docs/BACKTEST_PROTOCOL.md` | `git log -- docs/EVAL_PROTOCOL.md docs/BACKTEST_PROTOCOL.md`; results commits follow |
| Python 3.12 | `.venv` | `.venv/bin/python -V` → 3.12.3 |
| Runtime needs only `requirements.txt` | import graph of `src/api`, `src/feature_eng.py`, `streamlit_app.py` | grep of imports; clean-venv install |
| Five expanding folds, 30-row purge, 5-row embargo | `eval_V2.json` → `metadata.folds`, `metadata.fold_scheme` | read the JSON |
| Walk-forward pooled n = 552 | `eval_V2.json` → `walkforward.lstm_stationary.n` | marked block, automated check |
| Hold-out n = 210, 2025-10-01 .. 2026-06-11 | `eval_V2.json` → `metadata.n_holdout`, `holdout_start/end` | read the JSON |
| Up-rate 56.3% walk-forward / 51.4% hold-out | `eval_V2.json` → `walkforward.persistence.up_rate`, `holdout.persistence.up_rate` | read the JSON (0.5634 / 0.5143) |
| The hold-out was predicted six times, three scored | `results/run.log`, `docs/BACKTEST_PROTOCOL.md` §2.4, `docs/DECISIONS.md` D27 | read run.log and D27 |
| One validation label (2025-09-30 target = 2025-10-01 return) entered early stopping | `docs/EVAL_PROTOCOL.md` §11 D-1, `docs/DECISIONS.md` D28 | read both; `backtest.json` → `metadata.artifact_audit.validation_labels_in_holdout_period: 1` |
| That overlap is 1 of 173 labels and ~0.50% of validation MSE | `docs/DECISIONS.md` D28 | read D28 |
| Seed 42 fixed before the run | `src/evaluate.py` `PRIMARY_SEED = 42`; `docs/DECISIONS.md` D27 | read the code and D27 |
| Seed-42 spread is 9.4% of actual, corr +0.031 | `backtest.json` → `prediction_diagnostics.artifact_seed_42` | `std_pred/std_actual` = 0.09381; corr 0.03125 |
| `make evaluate` retrains 109 LSTMs and took 1,259.6 s (21.0 min) | `results/run.log`; `docs/STATE.md` Stage 3 | `grep "complete in" results/run.log` → 1259.6 s; count = 108 run fits + 1 artifact fit |
| Training-serving parity: 696 row comparisons, max abs diff 0.0 | `tests/test_serving_parity.py`; `docs/STATE.md` Stage 5a | run the test; parity output 0.000e+00 |
| EMA warm-up: 1.6e-4 at 89 rows, 1.1e-8 at 200 rows | `docs/SERVING_DESIGN.md` §EMA warm-up | read §286 |
| No inflation series; gold in USD is the proxy | `docs/RESULTS.md` §11.7 | read §11.7 |
| Legacy README numbers are not carried over | `git show legacy-pre-refactor:README.md`; `docs/AUDIT_REPORT.md` | read the audit contradictions (unit, architecture, backtest) |
| Legacy tag exists | `git tag -l` | `git rev-parse --short legacy-pre-refactor` |
| Code is MIT; data excluded | `LICENSE` | read `LICENSE` |
| Full series not redistributed; 200-row sample | `data/sample/gold_sample.csv`, `data/sample/README.md`, D14 | `len=200`, 2025-10-14 .. 2026-06-13; read the sample README |
| Block 2023-10-27 .. 2025-08-06: 502 raw rows, 36.1% of the frame | `docs/DATA_INTEGRITY.md` §7 | read §7 (502 raw / 503 modelled; 36.1%) |
| Jalali field agrees in all 11,331 records | `docs/DATA_INTEGRITY.md` "Stage 1b" | read B1.3 |
| Block correlation +0.112 → +0.380; outside +0.358 → −0.126 | `docs/DATA_INTEGRITY.md` "Stage 1b" B2.2 | read B2.2 |
| The relabel is reversible and price-preserving | `src/data_loader.py::apply_block_date_shift`; `tests/test_data_loader_date_shift.py` | read the function; run the 6 tests |
| Price R² 0.9717 equals persistence | `docs/AUDIT_REPORT.md` §2.4 | read §2.4 (0.9717 both) |
| Old service fabricated a confidence interval | `docs/AUDIT_REPORT.md`; `docs/PLAN.md` Stage 2 | read the audit; the interval code was removed in Stage 2b |
| 89-row minimum = 59 + 30 | `src/feature_eng.py` `MIN_HISTORY_ROWS`; `docs/SERVING_DESIGN.md` | read the constant and the derivation; API test |
| API rejects the block with `422 block_dates_unsupported` | `src/feature_eng.py`; live request | ran the API; response captured below |
| API returns 401 for a wrong key and 422 for 40 rows | `src/api/security.py`, `src/api/main.py` | ran both requests |
| API accepts the sample CSV header verbatim (`Date`, `Gold_IRR`, `USD_IRR`, `Ounce_USD`, `Oil_USD`) | `src/api/main.py` `FIELD_ALIASES`; `tests/test_api_contract.py` | test posts `csv_rows()` with no renaming and asserts 200 + parity |
| Conflicting `date` and `Date` values return 422 | `src/api/main.py` `_reject_conflicting_aliases`; `tests/test_api_contract.py` | test supplies both with different values and asserts 422 |
| API response values (`log_return` etc.) | live run against the 200-row sample, 2026-11-18 | ran the README script; captured output below |
| No confidence field in the response | `src/api/main.py`; `tests/test_api_contract.py` | test walks every key |
| No rate limiter, deliberately | `src/api/security.py` module docstring | read the file |
| Docker is the only deployment artifact (D33) | `docs/DECISIONS.md` D33 | read D33 |
| Image is 2.99 GB on disk; the `pip install` layer is 2,240 MB | live build, 2026-11-17 | `docker images`; `docker history` |
| Build took 4,224.9 s (70.4 min) on the reference machine | live build | `BUILD_SECONDS=4224.88`; `docs/STATE.md` Stage 5b §3 |
| Container reports healthy; prediction bit-identical to a local run | live run, 2026-11-17 | `docker ps` "healthy"; `-0.00045206130016595125` both ways |
| Image excludes `data/raw`, `data/processed`, tests, notebooks, `.env` | live image | `ls` inside the container |
| Non-root UID 10001 | `Dockerfile`; live image | `docker exec id` → `uid=10001(appuser)` |
| Streamlit runs from the same image on 8501 | live run | `curl` → HTTP 200; logs show port 8501 |

## Headline numbers

All marked numbers are checked automatically by `make check`. The table records the source
path for each group.

| README group | Source path(s) | Verified by |
|---|---|---|
| Persistence row (RMSE 0.018350 / 0.026545) | `eval_V2.json` → `walkforward.persistence.rmse`, `holdout.persistence.rmse` | marked blocks; checker |
| Historical mean row (0.018188 / 0.0175 / 0.0055 / 0.026457 / 0.0066 / 0.2428) | `eval_V2.json` → `walkforward.histmean.*`, `holdout.histmean.*` | marked blocks; checker |
| Ridge-own row (0.018299 / 0.0056 / 0.3264 / 0.026704 / −0.0120 / 0.7966) | `eval_V2.json` → `walkforward.ridge_own.*`, `holdout.ridge_own.*` | marked blocks; checker |
| Ridge-full row (0.018846 / −0.0548 / 0.8595 / 0.026798 / −0.0192 / 0.7018) | `eval_V2.json` → `walkforward.ridge_full.*`, `holdout.ridge_full.*` | marked blocks; checker |
| Stationary LSTM row (0.018214 / 0.0148 / 0.2251 / 0.026543 / 0.0001 / 0.4984) | `eval_V2.json` → `walkforward.lstm_stationary.*`, `holdout.lstm_stationary.*` | marked blocks; checker |
| LSTM bootstrap intervals | `eval_V2.json` → `*.lstm_stationary.boot_r2_lo/hi` | marked blocks; checker |
| Directional accuracy 56.16% / 56.34% / 51.43% | `eval_V2.json` → `walkforward.lstm_stationary.dir_acc`, `always_up_acc`, `holdout.lstm_stationary.dir_acc` | marked blocks; checker |
| Economic table C0/C2 (S0–S3) | `backtest.json` → `strategies.C0.*.total_return`, `strategies.C2.*.total_return` | marked blocks; checker |
| S2/S3 differences and CIs (bp/day) | `backtest.json` → `bootstrap.C0/C2.S2_vs_S0`, `S3_vs_S0` | marked blocks; checker |
| Gold in USD +5.97% | `backtest.json` → `gold_in_usd.total_return` | marked block; checker |
| Break-even 108.9% / 95.4% / 167.8% / 140.9% | `eval_V2.json` → `cost_sanity.*.breakeven_acc_0_015/0_030` | marked blocks; checker |

## Claims removed or corrected before publication

| Original intention | Why it was removed or changed |
|---|---|
| "the rial fell 49.00% against the dollar" | Wrong direction. `backtest.json` gives USD/IRR **+49.00%**; the rial's dollar value fell by `1 − 1/1.49 ≈ 32.9%`. The README now says "USD/IRR rose +49.00%". |
| Cite `logs/test_metrics.json` for the 0.9717 price R² | `logs/` is gitignored, so a reader could not verify it from a clone. Replaced with the committed `docs/AUDIT_REPORT.md` §2.4, which records the same value and the persistence comparison. |
| "the model's log-return R² was −0.0016 in the legacy artifact" | Audit-reported only, and the committed legacy metrics file has no log-return R² field. Removed; the README uses this repository's measured Stage 3 numbers instead. |
| "production-ready" / "deployable" / "profitable" | Not supported by the results and explicitly excluded by the brief. |
| A live demo URL | No app was deployed. The README describes the Docker image as the only deployment artifact and does not claim a live URL. |
| A named author, email or citation link | Not supplied. Left as clearly marked `TODO` placeholders. |

## API evidence captured for the README

Run on 2026-11-18 with `API_KEY=demo-key .venv/bin/python -m uvicorn src.api.main:app --port 8022`:

```text
GET /health -> 200 {"status":true,"model_loaded":true,...}
GET /model-info (key) -> 200, min_rows 89, sequence_length 30, n_features 23
POST /predict (200 sample rows, key, posted with the CSV header Date,...) -> 200,
  log_return -0.00045206130016595125, last_date 2026-06-13, rows_used 200,
  feature_rows 141, stale_input warning (158 days)
POST /predict (40 rows, key) -> 422 {"code":"too_few_rows","message":"need at least 89 rows, got 40"}
POST /predict (89 block dates, key) -> 422 {"code":"block_dates_unsupported",...}
GET /model-info (wrong key) -> 401 {"code":"invalid_api_key",...}
```

The `/predict` response in the README is this output, trimmed to the fields shown. The
stale-input day count is a function of the capture date.
