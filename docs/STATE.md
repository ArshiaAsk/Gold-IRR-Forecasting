# Project State

**Date:** 2026-11-14
**Stage:** Stages 0–2b complete. The data correction is applied; the repo is cut down to the kept code and a minimal API. **Stopped at the end of Stage 2b, before Stage 3.**
**Branch:** `refactor/honest-portfolio`
**Baseline tag:** `legacy-pre-refactor` → `d1670cc` (annotated)
**Pre-refactor description:** `docs/AUDIT_REPORT.md` (2026-11-13)
**Data-quality authority:** `docs/DATA_INTEGRITY.md` (includes "Stage 1b" and "Stage 2a — Applied fix")

---

## Done

### Stage 0
- Read `docs/AUDIT_REPORT.md` in full (512 lines). It is the only trustworthy description of the pre-refactor state; the current `README.md` is not.
- Confirmed the working tree had uncommitted changes before starting (`.gitignore` modified, `docs/` untracked) and asked the owner how to proceed. Owner chose: tag `d1670cc` exactly as-is and carry both items into Stage 0.
- Created annotated tag `legacy-pre-refactor` at `d1670cc` and branch `refactor/honest-portfolio`.
- Wrote `docs/PLAN.md` (Stages 1–5, checklist, deliverables, runnable acceptance criteria, two gates).
- Wrote `docs/DECISIONS.md` (D1–D6 accepted, O1–O8 open).
- Wrote this file.
- Committed `docs/AUDIT_REPORT.md` plus the three new docs; committed the `.gitignore` change separately.

### Stage 1
- Traced the date path end to end: TGJU JSON array → positional column map → `Date_G` → `pd.to_datetime(...).dt.date` → outer merge of the two Iranian series → `how='left'` merge with Yahoo → `ffill`. Quoted with line numbers in `docs/DATA_INTEGRITY.md` §2.
- **Refuted H1 (uniform one-day backward shift).** Each Iranian series, counted on its own axis before any merge, is 84–89% Saturday–Wednesday. `geram18` alone: Sat 631, Sun 634, Mon 637, Tue 631, Wed 646, Thu 274, Fri 101 over 3,554 rows.
- **Found the cause of the puzzle: the audit's weekday table is mislabelled by one weekday.** The counts are right; the labels are rotated. Reproduced the audit's exact row from an off-by-one `dayofweek` label list.
- Refuted H2 (Jalali conversion) with an independent implementation: 7,556 `Date_J → Date_G` conversions, 0 mismatches, four Nowruz boundaries and the 1403 leap day correct. The pipeline never reads `Date_J` anyway.
- Refuted H3 (parsing) and H5 (timezone): explicit and implicit `to_datetime` formats are identical on 3,775 records; there are no timestamps and no timezone call in `src/` or `api_layer/`.
- Refuted H4 as the cause of the weekday pattern, but verified a different merge defect: 588 of 1,424 rows (41.3%) carry a forward-filled global price, 473 of them on Saturdays/Sundays; 317 Yahoo dates are dropped by `how='left'`.
- **Discovered a real defect the audit missed:** a contiguous 21-month block (2023-10-27 → 2025-08-06, 503 rows, 36.1% of the modelled frame) in which Thursday rows vanish and Friday rows appear, identically in both Iranian series. The post-weekend return moves from Saturday to Friday inside the block. Lag-1 alignment against `GC=F` peaks at +0.231 inside the block vs +0.552 at lag 0 outside. Interpreted as a one-day-early label — **INFERRED, not proven**. *(The alignment evidence was strengthened in Stage 1b; see below and Contradictions item 8.)*
- Quantified the shift impact (scratch copy, `/tmp/s1`): shifting the Iranian series by −1/+1 does not improve any baseline (persistence R² −0.80 across all three; ridge R² −0.83 to −0.86) and the −1 shift destroys the contemporaneous global-gold correlation (+0.165 → −0.049).
- Confirmed the unit finding: values are Rial (gold/USD/ounce identity holds to 1.010 median, IQR 0.994–1.023); every "Toman" label is 10× wrong.
- Wrote `docs/DATA_INTEGRITY.md`. Committed docs only.

### Stage 1b (G1 option c)
- Recorded O1–O8 as accepted decisions **D10–D17** and G1 option (c) as **D18** in `docs/DECISIONS.md`.
- **Tested the Jalali date field** (`src/data_loader.py:70` discards it; it is index 7 of the raw row). Wrote an independent converter from the jalaali-js algorithm, validated it on 14 known dates (five Nowruz boundaries, leap Esfand 30 of 1403) and a 73,349-day round trip over 1900–2100 with 0 mismatches.
- **The Jalali field is not an independent witness.** It agrees with `Date_G` in **11,331 of 11,331** records — 3,554 `geram18` live, 4,002 `price_dollar_rl` live, 3,775 cached `price_dollar_rl` — inside the block (502) and outside it (3,052 / 3,500 / 3,273) alike. TGJU emits both fields from one record, so a one-day-early label shifts both and the offset stays 0. **Verdict: UNKNOWN — the source cannot speak.**
- Confirmed the cached Feb-2026 snapshot and the Nov-2026 live fetch have **identical block dates and identical prices** (502/502). TGJU has not corrected or revised the block in nine months.
- **Alignment test, identical row set.** Using only Iranian rows with a Yahoo bar on both `d` and `d+1` — so the return vector is the same under both shifts and only the matched ounce date moves — the block's same-day correlation goes **+0.1119 → +0.3803** under a +1 relabel (n=235). The clean post-block period goes the other way, **+0.3577 → −0.1262** (n=238). Pre-block is flat (+0.034 / +0.045). **Verdict: VERIFIED — the block's Iranian rows are one day early relative to the global series.**
- Supporting: the block's Friday rows carry the weekend move (median |return| 1.179%, mean 1.622%, zero-change share 0.00 — the largest of any weekday, where outside the block Saturday is largest at 0.871% and Thursday is the 60%-zero carry-over day). All four holiday dates present in the block carry real moves (−0.149%, +3.77%, −3.46%, +0.69%); under +1 they become empty, matching the outside-block behaviour. The identity-dispersion test agrees but is weak (sd −3.5% in block, +25% post-block).
- Checked the counter-signal: the block's Wednesday has no Thursday-style carry-overs. Not a contradiction — TGJU's Thursday practice changed (zero-change share 0.82–1.00 in 2013–2014 and 2020–2023, but 0.00 in 2025 and 0.05 in 2026), so a real Thursday in 2023–2025 would not be a zero-change row.
- Verified the relabel is mechanically safe: 502 rows, **0 date collisions**, row count unchanged (3,554 / 4,002), index stays unique, no price changes.
- **Applied the decision rule: branch (b).** Source 1 is UNKNOWN and source 2 is VERIFIED, so they do not agree. Branch (a) as worded ("use the Jalali-derived dates for the whole series") is also a literal no-op, because those dates are byte-identical to the ones in use.
- Also resolved **O6** in code: `signal_history.jsonl` has 7 records, six with `pct/log = 100.0` and only the 2026-02-08 record at 10,000.0. That value is float32 ×100 applied twice (442.9512939 vs recorded 442.9512978, relative diff 8.6e-9), and the same record's `reasoning` string says "4.43%". Not an edit — a one-off double-scaling bug.
- Appended "Stage 1b" to `docs/DATA_INTEGRITY.md`; updated `docs/DECISIONS.md` and this file. Committed docs only.

### Stage 2a — data correction applied (`d5b8dcd`, `75c927e`)
- Recorded the owner's G1-final call as **D19**: apply the +1 relabel, as a reversible loader transform. Rationale in `docs/DECISIONS.md`: the Jalali field cannot witness the defect (TGJU emits both fields from one record), so its silence is uninformative; the alignment test is the independent evidence.
- Added `apply_block_date_shift()` to `src/data_loader.py`, called from `DataLoader.get_tgju_history()` after date parsing and **before** the gold/USD merge. Window (`2023-10-27 → 2025-08-06`), `+1` day and an enable flag live in `config/settings.py` (`DATE_SHIFT_*`), default enabled. The number of relabelled rows is logged on every run.
- The helper only changes the `Date` label. It copies the frame, leaves prices untouched, and raises `ValueError` on any date collision instead of silently corrupting the merge.
- Added `tests/test_data_loader_date_shift.py` (6 tests): exact rows, flag off, row count, uniqueness, first/last day and the days around them, collision refusal.
- Verified on `data/raw/final_gold_dataset.csv` (no network): **503 rows relabelled, 0 collisions, 1,424 → 1,424 rows, prices identical**; weekday histogram Thu 137 → 220, Fri 90 → 4; features regenerate **1,424 → 1,394** rows. Block alignment on local data: **+0.1833 → +0.3722** under +1, post-block **+0.4126 → −0.0990**. Details and caveats in `docs/DATA_INTEGRITY.md` → "Stage 2a — Applied fix".
- `yfinance` and `curl_cffi` are now imported inside the fetch methods, so the module and its offline tests import without the network stack.

### Stage 2b — scope reduction (`147d58b`, `5c6a74a`, `66b2353`)
- Deleted **75 tracked paths**: `api_layer/`, `src/mlops/`, `src/monitoring/`, `monitoring/`, `examples/`, `example_usage.py`, `supervisord.conf`, `start.sh`, `quick-start.sh`, empty `main.py`, `setup.py`, `src/api/client_example.py`, stale `outputs/`, `notebooks/catboost_info/`, and the 7 tests that exercised removed modules. All reachable at `legacy-pre-refactor`.
- Grepped kept code before deleting: only `streamlit_app.py` imported `api_layer` (guarded try/except) and only `src/api/main.py` imported `src.mlops` (rewritten). `src/monitoring/` and `monitoring/` were imported by nothing. The Streamlit guarded import was reduced to the kept predictor.
- Minimal API (`src/api/main.py`): exactly `/health`, `/model-info`, `/predict`. No MLOps wiring, no Prometheus, no ONNX, no audit store. Starts even when artifacts are absent; `/health` returns 200 and reports `model_loaded`. `/predict` validates the real `(30, 15)` schema with pydantic v2. Removed `/predict-with-confidence` and the artificial Gaussian interval in `src/api/predictor.py`.
- API auth is unchanged and environment-driven: **`API_KEY`** holds the key, **`API_KEY_REQUIRED`** (default `true`) toggles it. If auth is required and `API_KEY` is unset, protected endpoints return 503 with a clear message. Header name is `X-API-Key` (override with `API_KEY_HEADER_NAME`).
- Docker reduced to one process (`uvicorn` on 8000); `start.sh`/`supervisord.conf` are gone. `docker-compose.yml` has a single `api` service.
- Untracked `data/raw/final_gold_dataset.csv`, `data/processed/advanced_gold_features.csv` and `data/mlops_audit.db` (kept on disk). Added `data/sample/gold_sample.csv`, the last 200 rows (2025-10-14 → 2026-06-13), with a README noting that full redistribution awaits TGJU permission (D14/O5).
- `.gitignore` now covers `data/raw`, `data/processed`, `*.db`, `mlruns/`, `logs/`, `outputs/`, caches, and allows `data/sample/*.csv`. The global `*.csv` rule and the self-ignoring `.dockerignore` entry were removed.
- `requirements.txt` rebuilt from actual imports: adds `yfinance`, `curl_cffi`, `requests`, `pytest`; removes `mlflow`, `evidently`, `onnxruntime`, `tf2onnx`, `schedule`, `prometheus-*`, `aiofiles`, `psutil`. TensorFlow/Keras pins kept. Notebook-only libraries are listed as optional comments.
- **Scalers are not committed** (`models/scaler_X.pkl`, `models/scaler_y.pkl` are untracked and ignored). **Stage 3 regenerates the model and both scalers and commits them together**, so the committed model and scalers always come from the same training run.

## Next

**Stage 3 — honest modeling and evaluation.** Normalize the raw-level features (D16), use walk-forward validation, report persistence/ridge/LSTM side by side, and run the **three-variant sensitivity analysis required by D19: raw, corrected, block excluded**, on identical folds. The README must report all three. Regenerate and commit model + scalers together.

## Blockers

None. G1-final is resolved by D19; O1–O8 are resolved as D10–D17.

## Known stale artifacts

- `README.md` is still the pre-refactor document. It describes components deleted in Stage 2b, quotes metrics that contradict the artifacts, and labels Rial as Toman. **Do not quote it.** Stage 5 rewrites it; Stage 3 supplies the numbers, including the three data variants required by D19.
- `models/gold_lstm_v2.keras` is the pre-refactor model. It is still tracked so the API has something to load, but Stage 3 replaces it and commits the new model together with its scalers.
- `notebooks/` are kept as history. They import `catboost`, `lightgbm`, `xgboost` and `statsmodels`, which are **not** installed by `requirements.txt` (listed there as optional comments).

---

## Verified environment facts

Everything below was produced by a command in this session. Nothing here is copied from the README.

| Fact | How verified |
|---|---|
| Interpreter is Python 3.12.3 at `.venv/bin/python` | `.venv/bin/python -V` |
| `pytest` is **not installed** in `.venv` | `.venv/bin/python -c "import pytest"` → `ModuleNotFoundError` |
| `yfinance` is **not installed** in `.venv` | `.venv/bin/python -c "import yfinance"` → `ModuleNotFoundError` |
| `curl_cffi` is **not installed** in `.venv` | `ModuleNotFoundError`; live fetches used `urllib` instead |
| Raw dataset has **1,424** data rows | `wc -l data/raw/final_gold_dataset.csv` → 1,425 incl. header |
| Processed dataset has **1,394** data rows | `wc -l data/processed/advanced_gold_features.csv` → 1,395 incl. header |
| Repository had **129** commits at the start of Stage 0 (**138** at the end of Stage 2b) | `git rev-list --count HEAD` |
| `.env` exists, is untracked, and is ignored at `.gitignore:28` | `git ls-files .env` (empty), `git check-ignore -v .env` |
| `.github/` does not exist (no CI) | `ls -d .github` |
| `Makefile` does not exist | `ls Makefile` |
| `scripts/` does not exist | `ls -d scripts` |
| `docs/` contained only `AUDIT_REPORT.md` before Stage 0 | `ls docs` |
| `docker-compose.yml` now defines exactly **one** service, `api` (was `ml-stack` before Stage 2b) | `grep -n "^  [a-z]" docker-compose.yml` |
| Model file is tracked; both scalers are **not** | `git ls-files models/` → only `models/gold_lstm_v2.keras`; `models/scaler_X.pkl` and `scaler_y.pkl` exist on disk |
| `logs/test_metrics.json` reports price R² 0.9716991951320707, RMSE 4,840,916.90, MAE 2,883,359.74, MAPE 1.7017, log-return RMSE 0.0275036 — and **no** log-return R² field | `cat logs/test_metrics.json` (log file still on disk; `logs/` is ignored) |
| `trading_bot/outputs/backtest_metrics.json` reported −12.034% return, Sharpe −7.361, max drawdown 15.105%, 30 trades, 40% win rate, benchmark +1,184.94%, period 2021-01-27 → 2025-12-20 (1,384 days) | read in Stage 0; the stale `trading_bot/outputs/` was deleted in Stage 2b |
| `trading_bot/outputs/portfolio_log.csv` covered 2021-07-19 → 2026-06-11 (1,394 rows) and ended at 859,421,876.91 IRR — it did **not** match the committed metrics file's period | read in Stage 0; deleted in Stage 2b |
| `README.md:600` contains a leftover AI-chat sentence | `sed -n '598,602p' README.md` |
| Undeclared third-party imports existed before Stage 2b: `yfinance` (2 files), `curl_cffi` (2), `pytest` (2), `requests` (5, commented line) | `grep -rl` per module; **fixed** — `requirements.txt` rebuilt in Stage 2b |
| `python-dotenv` is imported nowhere (0 files) | `grep -rl "import dotenv"` |

### Stage 1 verified facts

| Fact | How verified |
|---|---|
| Weekday counts of the raw dataset are **Sat 237 · Sun 236 · Mon 241 · Tue 243 · Wed 240 · Thu 137 · Fri 90** | `docs/DATA_INTEGRITY.md` §4.1 |
| Sat–Wed share: **84.1%** merged, **84.3%** `geram18` alone, **85.1%** `price_dollar_rl` alone, **89.4% / 88.8%** over full source history | §4 |
| Yahoo `GC=F` has **0** Saturday and **0** Sunday bars | §4.4 |
| `Date_J → Date_G` conversions: **7,556 rows, 0 mismatches** | §6 |
| `geram18` has **3,554** rows (2013-07-22 → 2026-11-12); `price_dollar_rl` has **4,002** (2011-11-26 → 2026-11-12) | §3.1 |
| Block 2023-10-27 → 2025-08-06: **503 rows**, Thursday count **0** for 21 consecutive months, Friday 3–5/month | §7 |
| Block rows by split: **train 337, val 166, test 0** | §7.3 |
| Split boundaries: train 2021-07-19 → 2024-12-24, val 2024-12-25 → 2025-10-01, test 2025-10-02 → 2026-06-11 (209 rows, 180 windows) | §7.3 |
| `ffill` fills **7** gold rows, **24** USD rows, **588** ounce rows (41.3%); **317** Yahoo dates dropped by `how='left'` | §8 |
| Genuine TGJU carry-overs in gold: **104** rows, **85** of them Thursday | §8 |
| `Gold_IRR / (0.75·Ounce/31.1035·USD_IRR)` median **1.010**, IQR **0.994–1.023** | §10 |
| Shift −1/0/+1 leaves persistence R² at **−0.80** and ridge R² at **−0.83…−0.86** | §9.2 |
| Contemporaneous `Gold~Ounce` correlation: **+0.165** at shift 0, **−0.049** at shift −1 | §9.1 |

### Stage 1b verified facts

| Fact | How verified |
|---|---|
| Jalali↔Gregorian: **11,331 records, 0 non-zero offsets** (11,331 = 3,554 + 4,002 + 3,775) | `DATA_INTEGRITY.md` "Stage 1b" B1.3 |
| Jalali offset inside block **0** for 502/502 rows, in all three datasets | B1.3 |
| Cached (2026-02) and live (2026-11) block: **502/502 identical dates and prices** | B1.4 |
| Converter: 14 known dates + **73,349-day round trip, 0 mismatches** | B1.2 |
| Block `Gold~Ounce` corr, identical rows: **+0.1119 (shift 0) vs +0.3803 (shift +1)**, n=235 | B2.2 |
| Post-block `Gold~Ounce` corr, identical rows: **+0.3577 (shift 0) vs −0.1262 (shift +1)**, n=238 | B2.2 |
| Block Friday: median abs return **1.179%**, zero-change share **0.00**, n=86 | B2.5 |
| Relabel +1: **0 collisions**, 502 rows moved, row count 3,554 / 4,002 unchanged | B5 |
| `signal_history.jsonl`: 7 records, **6 at ratio 100.0**, 1 at **10,000.0** | read in Stage 1b from `api_layer/cache/signal_history.jsonl` (deleted in Stage 2b); see D15 |

## Stage 2b acceptance outputs

All commands run in this session on `refactor/honest-portfolio` at `66b2353` (docs commit follows).

### 1. Tests

`pytest` is **not installed in `.venv`** (verified: `ModuleNotFoundError`). A scratch environment was used and nothing was installed into the repo:

```bash
python3 -m venv /tmp/pytest-scratch
/tmp/pytest-scratch/bin/pip install pytest          # pytest 9.2.0
PYTHONPATH="$PWD/.venv/lib/python3.12/site-packages:$PWD" \
  /tmp/pytest-scratch/bin/python -m pytest tests/ test_pipeline.py -q
```

```
platform linux -- Python 3.12.3, pytest-9.2.0, pluggy-1.7.0
rootdir: /home/arshiaask/projects/Gold_Usd_Oil_IRR
configfile: pytest.ini
plugins: anyio-3.7.1, Faker-40.43.0
collected 20 items

tests/test_data_loader_date_shift.py ......                              [ 30%]
test_pipeline.py ..............                                          [100%]

============================== 20 passed in 9.69s ==============================
```

No import errors, no collection errors.

### 2. Minimal API

```bash
.venv/bin/python -m uvicorn src.api.main:app --host 127.0.0.1 --port 8013
curl -sS -w "\nHTTP %{http_code}\n" http://127.0.0.1:8013/health
```

```
{"status":true,"model_loaded":true,"timestamp":"2026-11-14T17:38:16.608376"}
HTTP 200
```

`model_loaded` is `true` here because the scalers exist on disk in this working tree. They are **not tracked**, so a fresh clone reports:

```
WARNING - Model artifacts missing (scaler_X.pkl, scaler_y.pkl). Server starts; /predict returns 503.
status: model_missing predictor: None
```

Verified by pointing the path constants at an absent directory and entering the lifespan. In both cases `/health` returns **200**.

`/model-info` (auth disabled) returned `input_shape (None, 30, 15)`, `output_shape (None, 1)`, `total_parameters 33441`. `/predict` with a 1x2 payload returned **422**; with a valid `(30, 15)` payload returned **200** and a prediction. With auth on and `API_KEY` unset, `/predict` returns **503** (`API key authentication is enabled but API_KEY is not configured`).

### 3. Size

| Metric | Before Stage 2b (`75c927e`) | After (`66b2353`) |
|---|---|---|
| `git ls-files \| wc -l` | **117** | **44** |
| tracked Python files | 71 | 26 |
| Python LOC (`git ls-files '*.py' \| xargs cat \| wc -l`) | **11,367** | **5,301** |
| deleted paths vs `75c927e` | — | **75** (5,469 Python LOC) |

### 4. Deleted paths, grouped by reason

| Reason | Paths |
|---|---|
| Live bot / dashboard / caches (14) | `api_layer/api_config.py`, `cache/latest_*.json` (4), `cache/raw_response_20260207_130227.json`, `cache/signal_history.jsonl`, `dashboard.py`, `data_fetcher.py`, `live_feature_engineering.py`, `live_predictor.py`, `live_signal_generator.py`, `setup_and_test.py`, `trading_bot.py` |
| MLOps modules (19) | `src/mlops/`: `__init__`, `ab_testing`, `alerting`, `api_integration`, `audit_store`, `background_tasks`, `drift_detector`, `experiment_tracker`, `metrics_exporter`, `model_governance`, `model_registry`, `model_validator`, `onnx_exporter`, `optimized_predictor`, `phase5_integration`, `prediction_router`, `retraining_pipeline`, `scheduler`, `worker` |
| Monitoring (8) | `src/monitoring/` (3), `monitoring/` (5: alert rules, Prometheus, Grafana provisioning/dashboard) |
| Supervisor / startup (3) | `supervisord.conf`, `start.sh`, `quick-start.sh` |
| Examples / orphans (8) | `examples/` (4), `example_usage.py`, empty `main.py`, `setup.py`, `src/api/client_example.py` |
| Generated artifacts (13) | `outputs/*.png` (7), `notebooks/catboost_info/` (6) |
| Tests of deleted code (7) | `test_data_fetcher`, `test_live_predictor`, `test_live_signal_generator`, `test_mlops_api_integration`, `test_mlops_background_tasks`, `test_mlops_endpoints`, `test_phase5_mlops` |
| Untracked, kept on disk (3) | `data/raw/final_gold_dataset.csv`, `data/processed/advanced_gold_features.csv`, `data/mlops_audit.db` |

### 5. Diff against the legacy tag

```bash
git diff legacy-pre-refactor --stat | tail -1
```

```
 95 files changed, 2782 insertions(+), 47968 deletions(-)
```

### 6. Nothing remains under `api_layer/` or `src/mlops/`

```bash
git ls-files | grep -E 'api_layer|src/mlops|src/monitoring|monitoring/'   # no output
find api_layer src/mlops                                                  # No such file or directory
```


## Not verified in this session

Stated plainly so nobody mistakes these for measured facts:

- Model architecture (64→32→16, 33,441 params), the log-return R² of −0.0016, and the Diebold–Mariano result are **audit-reported**. Stage 3 re-derives the first two.
- `python -m unittest test_pipeline` reportedly runs 14 tests successfully (audit §5.6). Not re-run here.
- The backtest has not been re-executed; only the committed JSON was read.
- The **mechanism** of the 2023-10 block is still **inferred**, not observed at the source. Stage 1b verifies that the block's rows are one day early relative to `GC=F`; it does not observe TGJU's internal intent. No external archive of an individual date inside the block was available.
- `Ounce_USD` matches Yahoo `GC=F` on only 38/835 overlapping dates (max diff 53.4 on ≈ $4,000). Cause **unknown**; most likely a different Yahoo vintage. Does not affect any date conclusion.

---

## Contradictions found between the audit and the repo

1. **`.agents/` documentation does not exist.** A prior session's memory asserted that `.agents/STATE.md`, `ROADMAP.md`, `CONVENTIONS.md`, `DECISIONS.md`, `LOG.md` and a root `CLAUDE.md` were created at `d1670cc`. They are absent from the working tree and from all git history (`git log --all -- .agents` → empty). The audit was right; the memory was stale and has been corrected.
2. **`docs/` is no longer empty.** The audit describes it as `EMPTY`, which was accurate when written; it now contains `AUDIT_REPORT.md` plus the Stage 0–1 docs. Timing difference, not an error.
3. **The test inventory was wrong in both the audit and this file.** The audit says `tests/` holds "8 test modules (2 sources deleted, .pyc only)". At `d1670cc` there are **7** `test_*.py` sources (verified with `git ls-tree --name-only d1670cc tests/`), plus `conftest.py` and `__init__.py`; no test bytecode is tracked. Stage 1's "6 live test modules, not 8" was also off by one. Corrected here. All 7 tested removed modules and were deleted in Stage 2b.
4. **Committed backtest metrics and the committed portfolio log disagree.** `backtest_metrics.json` says 2021-01-27 → 2025-12-20 / 1,384 days; `portfolio_log.csv` runs 2021-07-19 → 2026-06-11 / 1,394 rows. Confirmed here. The log matches the audit's *fresh* run (−14.06%, final 859.4M), so the JSON is the stale artifact.
5. **The audit's weekday table is mislabelled.** It prints `Fri 237 · Sat 236 · Sun 241 · Mon 243 · Tue 240 · Wed 137 · Thu 90`. The real mapping is `Sat 237 · Sun 236 · Mon 241 · Tue 243 · Wed 240 · Thu 137 · Fri 90` — the same counts, rotated by one weekday. Reproduced exactly by an off-by-one label list. The audit's central data-quality finding was an artefact of its own analysis. See `docs/DATA_INTEGRITY.md` §5.
6. **The audit missed the 2023-10 → 2025-08 block** — a 36% sub-period with a different weekly shape, present identically in both source series. See `docs/DATA_INTEGRITY.md` §7.
7. **Stage 1 overstated the Jalali field's evidential value.** §6 correctly used `Date_J → Date_G` agreement to refute a conversion bug, but the agreement also means the field cannot detect a date that is wrong in both columns. Stage 1b extends the check to 11,331 records and concludes the field is not an independent witness. Nothing in §6 is wrong; the implication that it could confirm the block is.
8. **Stage 1's block-alignment test was weaker than it looked.** §7.2 reported the block peaking at lag −1 (+0.231) only slightly ahead of lag 0 (+0.164). That test let the matched row set change between shifts. Stage 1b holds the row set fixed and gets +0.112 → +0.380, with the post-block going +0.358 → −0.126. The Stage 1b result supersedes §7.2 as the alignment evidence; §7.2 is left as written.
9. **Two orphan files the audit did not mention.** `logs/baseline_metrics.json` refers to a baseline-evaluation script that is not in the repo, and `setup.py` declares a package that nothing installs or imports. Both were removed in Stage 2b. Neither affected any published number.
10. **No contradiction in the audit's account of the MLOps layer.** Every module in `src/mlops/` was imported only by `src/api/main.py` and its own tests; deleting the layer required rewriting the API but broke nothing in the training, feature or evaluation path. The audit's "never completed a cycle" description is consistent with what was removed.

No contradiction was found in the audit's dependency claims, its `.env` finding, its "no CI" finding, its account of the loader/merge/ffill, or its README-quote evidence.

---

## How to run (verified commands only)

```bash
# Interpreter used by this project
.venv/bin/python -V                       # Python 3.12.3

# Inspect the frozen pre-refactor state
git show legacy-pre-refactor:README.md
git ls-tree -r --name-only legacy-pre-refactor | head

# Re-derive the row counts (data files are on disk but untracked)
wc -l data/raw/final_gold_dataset.csv data/processed/advanced_gold_features.csv

# Re-derive the weekday table (the audit's version is mislabelled)
.venv/bin/python -c "import pandas as pd; d=pd.read_csv('data/raw/final_gold_dataset.csv',index_col='Date',parse_dates=True); print(d.index.day_name().value_counts())"

# Tests. pytest is not installed in .venv; use a scratch environment.
python3 -m venv /tmp/pytest-scratch && /tmp/pytest-scratch/bin/pip install pytest
PYTHONPATH="$PWD/.venv/lib/python3.12/site-packages:$PWD" \
  /tmp/pytest-scratch/bin/python -m pytest tests/ test_pipeline.py -q

# Minimal API
.venv/bin/python -m uvicorn src.api.main:app --host 127.0.0.1 --port 8000
curl -sS http://127.0.0.1:8000/health

# Regenerate features from the corrected data (writes to data/processed/, ignored)
.venv/bin/python src/feature_eng.py
```

`pytest` is not a dependency of the runtime venv; `requirements.txt` lists it for a fresh environment. There is still no `Makefile` (`make test` is a Stage 5 deliverable). Data files are **not** in a fresh clone: `data/sample/` is, and the full series must be fetched or supplied locally.

