# Project State

**Date:** 2026-11-18
**Stage:** Stages 3, 4, 5a, 5b and 6 complete. GATE 3 accepted ("no demonstrated edge" final);
GATE 4 accepted (D29: no added value over buy-and-hold, no re-runs, seed-42 artifact served);
GATE 5a accepted (D31); GATE 5b accepted (D33: Docker is the only deployment deliverable).
Stage 6 release fixes applied. No merge, no push, no release tag.
**Branch:** `refactor/honest-portfolio`
**Baseline tag:** `legacy-pre-refactor` → `d1670cc` (annotated)
**Pre-refactor description:** `docs/AUDIT_REPORT.md` (2026-11-13)
**Data-quality authority:** `docs/DATA_INTEGRITY.md` (includes "Stage 1b" and "Stage 2a — Applied fix")
**Evaluation authority:** `docs/EVAL_PROTOCOL.md` (pre-registered) and `docs/RESULTS.md` (measured)
**Serving authority:** `docs/SERVING_DESIGN.md`

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
- Quantified the shift impact (scratch copy): shifting the Iranian series by −1/+1 does not improve any baseline (persistence R² −0.80 across all three; ridge R² −0.83 to −0.86) and the −1 shift destroys the contemporaneous global-gold correlation (+0.165 → −0.049).
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

### Stage 3 — honest modeling and evaluation (`798981a`, `cb75162`, `37585ac`, `8d7715e`, `64c9798`, `5f4abaa`)

- **Protocol pre-registered before any model fit.** `docs/EVAL_PROTOCOL.md` (`798981a`) fixes the task, information timing, 23-feature set, V1/V2/V3 variants, five expanding folds with 30-row purge / 5-row embargo, six models, metrics, the edge rule and cost sanity. One **pre-run** amendment (`cb75162`): the hold-out is all rows from 2025-10-01 (210 rows), not the literal last 180 rows, which begin 2025-11-05 and would skip October. No post-run deviations.
- **Data.** Iranian series from the untracked local snapshot (1,424 rows, 2021-06-14 → 2026-06-13). One complete Yahoo `GC=F`/`BZ=F` pull for all variants (cached at `data/raw/global_yahoo.csv`), because the CSV lacks 110 corrected-date global bars (83 Thursdays). V2 relabels 503 merged block dates +1 before the global merge; V3 drops the block and keeps LSTM sequences inside segments. Fresh oil matches the CSV 911/911; fresh ounce differs by a median 0.33% in level / 0.018% in log return (corr 0.993).
- **Features.** 23 stationary features, single source of truth in `src/feature_eng.py::add_stationary_features` (gold/USD/ounce/oil return lags, RSI 14, MACD/price, Bollinger %B and bandwidth 20, price/SMA−1 7/20/60, RV 5/20). No raw price level, no calendar dummy.
- **Models.** Persistence, historical mean, ridge-own (4 gold lags), ridge-full (23 features), stationary LSTM 64→32→16 (5 seeds), legacy-spec LSTM on the old 15 raw-level features (3 seeds, V2 only). Four fixed configurations, no tuning; 109 LSTM fits.
- **Run.** `.venv/bin/python -m src.evaluate --variant all --artifact`, **1,259.6 s (21.0 min)**, inside the 90-minute budget. Tests: **35 passed** (15 protocol tests + 6 date-shift + 14 pipeline).
- **Verdict: no demonstrated edge.** V2 stationary LSTM: walk-forward RMSE 0.018214 vs persistence 0.018350 (R² +0.0148, DM p 0.2251, bootstrap CI [−0.0272, +0.0561]); hold-out 0.026543 vs 0.026545 (R² +0.0001, DM p 0.4984, CI [−0.0577, +0.0630]). Ridge-own beats persistence only on the walk-forward (0.018299, p 0.3264); hold-out 0.026704 (worse). Ridge-full is worse in both. The historical mean is the only significant walk-forward DM (p 0.0055, CI [+0.0032, +0.0338]) but fails on the hold-out (p 0.2428, CI [−0.0116, +0.0287]).
- **Sensitivity.** V1 vs V2 changes no conclusion (largest relative move: LSTM walk-forward RMSE −0.24%; baselines and ridge-own identical). V3 changes no conclusion; it is a different period/sample (300 walk-forward test rows, LSTM coverage 271/300) and makes ridge-full worse (WF R² −0.2555), not better. The block was a data-integrity defect, not the source of the model's failure.
- **Legacy vs stationary.** Legacy LSTM WF RMSE 0.018243 / R² +0.0116; HO 0.026631 / R² −0.0065. Stationary is slightly better; both are near persistence. Feature design alone does not create an edge.
- **Cost sanity.** At 1.5% round-trip cost the break-even directional accuracy is 108.9% (WF) / 95.4% (HO); at 3% it is 167.8% / 140.9%. Observed accuracy is ~51–57%.
- **Artifact.** `models/gold_lstm_stationary_v2.keras` + `models/scaler_X_stationary_v2.pkl` + `models/scaler_y_stationary_v2.pkl` + `models/gold_lstm_stationary_v2.metadata.json`, trained on V2 pre-hold-out rows (fit 2021-08-28 → 2024-12-31, validation 2025-02-08 → 2025-09-30, seed 42). Not wired into the API or Streamlit; `models/gold_lstm_v2.keras` remains for the API.
- **Results files.** `results/eval_V1.json`, `results/eval_V2.json`, `results/eval_V3.json`, `results/eval_summary.csv`, `results/run.log`. Full tables and interpretation in `docs/RESULTS.md`.

### Stage 4 — economic reality (`1e3e634`, `0cc0647`, `9b9caca`, `cf09f8d`, `3b5ac3a`)

- **Protocol pre-registered** in `docs/BACKTEST_PROTOCOL.md` (`0cc0647`) before any backtest result: hold-out only, seed-42 artifact by inference, S0–S3, four cost scenarios, moving-block bootstrap, fixed decision rule.
- **Prediction source.** Stage 3 saved aggregate metrics only; no per-row predictions. Stage 4 evaluates the committed seed-42 artifact by inference, with no training. Per-seed and 5-seed backtest tables are not recoverable and are dropped (D27).
- **Artifact audit.** Fit 2021-08-28 → 2024-12-31 (951), validation 2025-02-08 → 2025-09-30 (173), hold-out 2025-10-01 → 2026-06-11 (210). No hold-out feature row is in fit or validation; scalers are fit only through 2024-12-31. One validation label (2025-09-30 target = 2025-10-01 return, +2.15%, 0.69% of validation loss with the artifact's predictions; 0.50% was `label² / Σy²`) entered early stopping; recorded as `docs/EVAL_PROTOCOL.md` §11 D-1 and Errata, not fixed (D28).
- **Run.** `.venv/bin/python -m src.backtest_check`, code `9b9caca`, 2026-11-16, inference only. Two inference-only passes (development + final) produced identical results; Stage 3 scored the hold-out three times and predicted it once unscored. Total six prediction passes, three scored.
- **Verdict: no added value over buy-and-hold.** At C2 (0.75%/side): S0 +56.71%, S1 +47.89%, S2 +1.13%, S3 +36.90%. S2 diff −22.45 bp/day, CI [−45.45, −7.89] (significantly worse); S3 diff −7.56 bp/day, CI [−23.96, +2.01] (no value). At C0: S0 +57.89%, S1 +49.00%, S2 +12.37%, S3 +52.12%.
- **Prediction spread.** Seed-42 hold-out `std_pred` 0.002482 vs `std_actual` 0.026456 (9.4%), corr +0.031, RMSE 0.026540, R² +0.000367. The Stage 3 5-seed headline is `std_pred` 0.003304, corr +0.0381, RMSE 0.026543, R² +0.000119. Seed 42 is typical, not stronger; the model is still near-constant.
- **Gold in USD.** +5.97% over the traded period vs +57.89% nominal gold; USD/IRR +49.0%. No inflation series exists; gold-in-USD is the currency-neutral proxy, not a real return.
- **`trading_bot/` removed** with `git rm`; no kept code imported it; the tag preserves it (D26). `src/backtest_check.py` + 9 tests; **44 tests pass**.
- **Results files.** `results/backtest.json`, `results/backtest.log`. Full tables and plain-language reading in `docs/RESULTS.md` §11.

### Stage 5a — serving (`1768b2e`, `f587864`, `1bd4a5b`, `f749791`, `e9d65e0`)

- **Design first.** `docs/SERVING_DESIGN.md` committed at `1768b2e` before any serving code: input contract, the 89-row minimum with its derivation, error codes, output contract, timing, auth, concurrency and the four-tab UI.
- **One feature path.** `src/feature_eng.py::prepare_model_input` is the only raw-row adapter; it validates the contract and calls `add_stationary_features`, the function training and evaluation already use. Measured parity: **0.0** max absolute difference over 696 row-comparisons at 24 sample positions and 5 post-block positions of the full series; served prediction equals the evaluation-primitive prediction exactly (max diff 0.0 over 5 positions).
- **API.** `src/api/` rewritten around the seed-42 artifact: raw rows in, log return out, metadata and metrics read from `models/gold_lstm_stationary_v2.metadata.json` and `results/*.json`. The `(30, 15)` contract, `FeatureBuilder`, the rate limiter and every price-level metric reference are gone.
- **Auth.** `API_KEY` compared with `hmac.compare_digest`; `/health` open; `API_KEY` unset → 503 on protected endpoints. No rate limiter (documented omission).
- **UI.** `streamlit_app.py` rewritten as Findings / Data / Model demo / About, all numbers read from files, model load cached, missing artifacts rendered as a message.
- **Tests.** 35 new (`test_serving_parity.py` 8, `test_api_contract.py` 19, `test_streamlit_app.py` 8). **79 passed** in total (30 `tests/` + 14 `test_pipeline.py` + 35 new).
- **Footprint.** Streamlit + TensorFlow 2.20 + model + one prediction: **689 MB** peak RSS, **3.12 s** from import to prediction. Full AppTest run (all four tabs): **699 MB**, 3.2 s. Direct requirements total **2,345 MB** installed (TensorFlow alone 1,858 MB).
- **Not changed:** `results/`, `models/`, `docs/EVAL_PROTOCOL.md`, `docs/BACKTEST_PROTOCOL.md`, `Dockerfile`, `README.md`. No retraining, no new seeds.

### Stage 5b — reproducibility, packaging, CI and README (`e6f8210` … `13ce2c6`, `9aab948`)

- **Release plan first.** `docs/RELEASE_PLAN.md` committed at `e6f8210` before any Stage 5b
  change: deliverables, acceptance commands and the README outline.
- **One test command.** Root `test_pipeline.py` moved to `tests/test_pipeline.py` (`d59dc34`);
  plain `pytest` now collects **83 passed**. The old "44" was 30 tests under `tests/` plus 14
  in the root file; plain `pytest` saw only 30 because `pytest.ini` sets `testpaths = tests`.
  No test was added or removed by the move.
- **Dependencies split** (`60e9870`): `requirements.txt` is the serving path with
  `tensorflow-cpu==2.20.0`; `requirements-dev.txt` adds pytest, httpx, yfinance, curl_cffi,
  matplotlib and seaborn. Python **3.12** is pinned in the Dockerfile and CI.
- **Makefile** (`13ce2c6`): `install`, `test`, `check`, `evaluate`, `backtest`, `api`, `app`,
  `docker-build`, `docker-run`, `fetch-data`, all documented in the README.
  `scripts/fetch_data.py` is the TGJU/Yahoo entry point.
- **Per-row predictions** (`539f92b`): opt-in `--save-predictions` plus `--out-dir`. A scratch
  run in a temporary directory (one seed, one epoch) wrote 2,760 walk-forward and 1,050 hold-out rows and
  did not touch `results/`. `docs/RESULTS.md` §12 records that the headline numbers predate the
  flag.
- **Docker** (`361b195`, `9aab948`): single image, Python 3.12 slim bookworm pinned by digest,
  non-root UID 10001, healthcheck on `/health`, API default and Streamlit from the same image.
  No raw data, tests, notebooks or legacy artifacts. Compose keeps one service and documents
  port/auth/healthcheck. The legacy managed-runtime port configuration is gone.
- **CI** (`eed9ee0`): push/PR workflow, Python 3.12, pip cache, `requirements-dev.txt`,
  `make check`.
- **Hygiene** (`1cf8285`): MIT `LICENSE` (data excluded), `results/predictions/` ignored,
  notebooks moved to `notebooks/exploratory/` with cleared outputs and a banner, legacy model
  removed, absolute notebook path replaced.
- **README** (`369f151`): rewritten from scratch, 319 lines, 58 marked numbers checked against
  `results/*.json`; `docs/README_CLAIMS.md` records every claim and its verification.
- **Absolute paths in the run logs.** `results/run.log` and `results/backtest.log` contained
  the reference machine's absolute paths (`Wrote <REPO>/results/eval_V2.json`). Stage 5b left
  them alone; Stage 6 replaced only the path string with `<REPO>` (D34), with a masked-diff
  and digit-checksum proof in the Stage 6 section. Nothing secret was in them.

## Next

**Owner merge and tag.** GATE 5b is accepted (D33). The branch is complete and is **not**
merged or pushed. The owner merges without squashing after the Stage 6 report and an
independent review, then tags the release. No release tag has been created.

### README checklist for Stage 5b (owner-mandated, D29) — all present

- [x] **Touch count.** Six prediction passes over the hold-out, three of them scored; the
      pre-registered "touched once" was not literally met.
- [x] **Validation/hold-out overlap (D-1).** One validation label is the 2025-10-01 hold-out
      return (`docs/EVAL_PROTOCOL.md` §11 D-1, D28); recorded, not fixed, and its direction
      favors the model slightly.
- [x] **Nominal vs USD gold.** +57.89% nominal gold in IRR vs +5.97% gold in USD over the
      traded period (`results/backtest.json`); USD/IRR +49.00%.
- [x] **Hold-out shape.** ~210 rows of a trending nominal series; the metrics are not a claim
      about future performance.

## Blockers

None. G1-final is resolved by D19; O1–O8 are resolved as D10–D17; Stages 3, 4, 5a, 5b and 6
are complete. The remaining items are the owner's merge/tag and the TODOs listed in the
Stage 6 verification block.

## Known stale artifacts

Resolved in Stage 5b:

- `README.md` was rewritten from measured results; it no longer describes removed components or
  quotes pre-refactor metrics.
- `models/gold_lstm_v2.keras` and the untracked `models/scaler_X.pkl` / `scaler_y.pkl` were
  removed; the only tracked artifacts are the stationary model, its metadata and its two
  scalers. The legacy files remain reachable at the tag.
- `notebooks/` moved to `notebooks/exploratory/`, outputs cleared, a banner added and the
  absolute local path replaced.
- `.streamlit/config.toml` no longer pins a legacy managed-runtime port or disables CORS/XSRF;
  it carries the theme only.

Untracked local directories (`mlruns/`, `mlflow/`, `logs/`, `data/raw/`, `data/processed/`,
`data/*.db`) remain on disk and are ignored. They are not part of the repository.

---

## Verified environment facts

Everything below was produced by a command in this session. Nothing here is copied from the README.

| Fact | How verified |
|---|---|
| Interpreter is Python 3.12.3 at `.venv/bin/python` | `.venv/bin/python -V` |
| `pytest` was **not installed** in `.venv` through Stage 4; **9.2.0** was installed in Stage 5a | `.venv/bin/python -c "import pytest; print(pytest.__version__)"` |
| `yfinance` is **not installed** in `.venv` | `.venv/bin/python -c "import yfinance"` → `ModuleNotFoundError` |
| `curl_cffi` is **not installed** in `.venv` | `ModuleNotFoundError`; live fetches used `urllib` instead |
| Raw dataset has **1,424** data rows | `wc -l data/raw/final_gold_dataset.csv` → 1,425 incl. header |
| Processed dataset has **1,394** data rows | `wc -l data/processed/advanced_gold_features.csv` → 1,395 incl. header |
| Repository had **129** commits at the start of Stage 0 (**138** at the end of Stage 2b) | `git rev-list --count HEAD` |
| `.env` exists, is untracked, and is ignored at `.gitignore:28` | `git ls-files .env` (empty), `git check-ignore -v .env` |
| `.github/workflows/ci.yml` exists (Stage 5b); there was no CI before | `ls .github/workflows` |
| `Makefile` exists with 10 documented targets (Stage 5b); none before | `make help` |
| `scripts/` exists: `fetch_data.py` and `check_readme_numbers.py` | `ls scripts` |
| `docs/` contained only `AUDIT_REPORT.md` before Stage 0 | `ls docs` |
| `docker-compose.yml` now defines exactly **one** service, `api` (was `ml-stack` before Stage 2b) | `grep -n "^  [a-z]" docker-compose.yml` |
| **Four** model files are tracked: the stationary artifact + metadata + both stationary scalers; the old `gold_lstm_v2.keras` was removed in Stage 5b | `git ls-files models/` |
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

### Stage 3 verified facts

| Fact | How verified |
|---|---|
| Protocol committed before any model fit; one pre-run hold-out amendment | `git log -- docs/EVAL_PROTOCOL.md` (`798981a`, `cb75162`); no `results/` before `798981a` |
| Feature frame: **1,364** rows for V1/V2; **860** for V3 | `results/eval_V1.json` / `eval_V3.json` metadata; run log |
| Hold-out: **210** rows, **2025-10-01 → 2026-06-11** | `results/eval_V2.json` metadata |
| Walk-forward: **5** folds; pooled **n=552** (V1/V2), **300** (V3) | `results/eval_summary.csv` |
| V2 stationary LSTM WF: RMSE **0.018214** vs persistence **0.018350**, R² **+0.0148**, DM p **0.2251**, boot R² **[−0.0272, +0.0561]** | `results/eval_V2.json` / `eval_summary.csv` |
| V2 stationary LSTM HO: RMSE **0.026543** vs persistence **0.026545**, R² **+0.0001**, DM p **0.4984**, boot R² **[−0.0577, +0.0630]** | same |
| V2 ridge-own: WF RMSE **0.018299** (R² +0.0056, p 0.3264); HO RMSE **0.026704** (worse) | same |
| V2 ridge-full: WF RMSE **0.018846** (R² −0.0548); HO RMSE **0.026798** (R² −0.0192) | same |
| V2 historical mean: WF p **0.0055**, R² **+0.0175**, CI **[+0.0032, +0.0338]**; HO p **0.2428**, CI **[−0.0116, +0.0287]** | same |
| V2 legacy LSTM: WF RMSE **0.018243**, R² **+0.0116**; HO RMSE **0.026631**, R² **−0.0065** | same |
| V1 vs V2: baselines and ridge-own identical; LSTM WF RMSE **0.018258 → 0.018214** (−0.24%); HO **0.026575 → 0.026543** (−0.12%) | `eval_V1.json` vs `eval_V2.json` |
| V3: WF **n=300**, LSTM coverage **271/300**; HO **n=210**; ridge-full WF R² **−0.2555**; no edge | `eval_V3.json` |
| Edge verdict: **no demonstrated edge** (all three eligible models fail) | `results/eval_V2.json` → `edge_verdict` |
| Cost break-even: **108.9% / 95.4%** at 1.5%, **167.8% / 140.9%** at 3% | `eval_V2.json` → `cost_sanity` |
| Run time **1,259.6 s (21.0 min)**; **109** LSTM fits | run log; `results/eval_*.json` metadata |
| Tests: **35 passed** (15 protocol + 6 date-shift + 14 pipeline) | pytest output, `docs/RESULTS.md` §9 |
| Artifact: 35,489 params, input `(None, 30, 23)`, seed 42 | `models/gold_lstm_stationary_v2.keras` + metadata |

### Stage 4 verified facts

| Fact | How verified |
|---|---|
| Protocol committed before any backtest result | `git log -- docs/BACKTEST_PROTOCOL.md` (`0cc0647`); code commit `9b9caca` |
| Hold-out predictions: seed-42 artifact only, inference; no training | `src/backtest_check.py`; `results/backtest.json` metadata |
| Seed-42 HO: RMSE **0.026540**, R² **+0.000367**, corr **+0.0312**, std_pred **0.002482** vs std_actual **0.026456** | `results/backtest.json` |
| Stage 3 5-seed HO: RMSE **0.026543**, R² **+0.000119**, corr **+0.0381**, std_pred **0.003304** | `results/eval_V2.json` |
| S0/S1/S2/S3 at C2: **+56.71% / +47.89% / +1.13% / +36.90%** | `results/backtest.json` |
| S2 vs S0 at C2: **−22.45 bp/day**, CI **[−45.45, −7.89]**; S3: **−7.56 bp/day**, CI **[−23.96, +2.01]** | same |
| Gold in USD **+5.97%** vs nominal gold **+57.89%**; USD/IRR **+49.00%** | same |
| Finding: **no added value over buy-and-hold** | same → `verdict` |
| `trading_bot/` removed; no kept imports | `git ls-files | grep trading_bot` empty; grep of `src/`, `tests/`, `streamlit_app.py` |
| Tests: **44 passed** (9 backtest + 35 existing) | pytest output |

> **The "44 vs 30" ambiguity, resolved in Stage 5b.** The 44 was the count from the explicit
> command `pytest tests/ test_pipeline.py`: **30** tests collected under `tests/` plus **14** in
> the root `test_pipeline.py`. Plain `pytest` collected only **30**, because `pytest.ini` sets
> `testpaths = tests`. Stage 5b moved the root file to `tests/test_pipeline.py`, so plain
> `pytest` now collects every module: **83 passed** (79 before the two new Stage 5b test files).
> No test was added or removed by the move.

### Stage 5a verified facts

| Fact | How verified |
|---|---|
| Design note committed before serving code | `git log -- docs/SERVING_DESIGN.md` → `1768b2e`; code commits follow |
| Minimum rows **89** = (60 − 1) + 30 | derived from `price_sma_60` and `sequence_length`; 88-row tail → 29 feature rows, 89 → 30 |
| Feature parity: **0.0** max abs difference | 24 sample positions, 696 row-comparisons, plus 5 post-block positions of the full series |
| Prediction parity: **0.0** max abs difference | 5 positions, served vs `build_sequences` + scalers + model |
| No lookahead | rows after t multiplied by 1.7 / 0.6 leave the prediction for t unchanged; a change at t does move it |
| API serves the seed-42 artifact, metadata-driven | `/model-info` metadata equals the file; metrics equal `results/eval_V2.json` |
| Validation codes | 8 rejected classes return their documented 422 code; missing/wrong key 401; no key 503 |
| No confidence field | every response key walked; no `confidence`/`interval`/`bound` |
| Streamlit: four tabs, no exception | `AppTest` run, all tab text asserted |
| Suite: **79 passed** | 30 `tests/` + 14 `test_pipeline.py` + 35 new |

## Stage 2b acceptance outputs

All commands run in this session on `refactor/honest-portfolio` at `66b2353` (docs commit follows).

### 1. Tests

`pytest` was **not installed in `.venv`** at the time (verified: `ModuleNotFoundError`). A throwaway environment was used and nothing was installed into the repo. The equivalent command now is:

```bash
.venv/bin/python -m pip install pytest          # pytest 9.2.0, already in requirements-dev.txt
PYTHONPATH="$PWD/.venv/lib/python3.12/site-packages:$PWD" \
  .venv/bin/python -m pytest tests/ test_pipeline.py -q
```

```
platform linux -- Python 3.12.3, pytest-9.2.0, pluggy-1.7.0
rootdir: <REPO>
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


## Stage 5a acceptance outputs

All commands run on `refactor/honest-portfolio` at `e9d65e0`, 2026-11-17, Python 3.12.3.

`pytest 9.2.0` was **installed into `.venv`** for this stage (it was absent; Stage 2b used a
scratch environment). `requirements.txt` already lists `pytest`; nothing else was installed.

### 1. Full test suite

```bash
.venv/bin/python -m pytest tests/ test_pipeline.py -q
```

```
collected 79 items
======================= 79 passed, 20 warnings in 11.23s =======================
```

Breakdown: 30 existing `tests/` + 14 `test_pipeline.py` + 8 `test_serving_parity.py`
+ 19 `test_api_contract.py` + 8 `test_streamlit_app.py`.

### 2. API

```bash
API_KEY=demo-key .venv/bin/python -m uvicorn src.api.main:app --host 127.0.0.1 --port 8013
```

```
INFO:     Started server process [80409]
INFO:     Waiting for application startup.
... src.api.predictor - INFO - Loaded models/gold_lstm_stationary_v2.keras (35489 params) ...
... src.api.main - INFO - Serving models/gold_lstm_stationary_v2.keras
INFO:     Application startup complete.
```

`/health` (no key):

```
{"status":true,"model_loaded":true,"timestamp":"2026-11-17T13:28:30.525328"}
```

`/model-info` without a key → `401`. With the key (trimmed to the contract and the headline
numbers, all read from the files):

```json
{
 "model_id": "gold_lstm_stationary_v2",
 "metadata_source": "models/gold_lstm_stationary_v2.metadata.json",
 "input_contract": {"min_rows": 89, "max_rows": 5000, "sequence_length": 30,
                    "n_features": 23, "target": "next_trading_day_log_return"},
 "holdout_lstm": {"n": 210, "rmse": 0.02654343629055195, "r2_zero": 0.00011901387468038482,
                  "dir_acc": 0.5142857142857142, "dm_p_one_sided": 0.4984040692302986,
                  "boot_r2_lo": -0.05772243482018194, "boot_r2_hi": 0.06298942977793245,
                  "std_pred": 0.0033038654010531425, "std_actual": 0.026455760242444695,
                  "corr": 0.03811900797197325},
 "edge": "no demonstrated edge",
 "economic": "no added value over buy-and-hold"
}
```

`/predict` with the 200-row sample (a scratch payload file):

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
  "warnings": ["stale_input: last date 2026-06-13 is 157 days old (limit 7)"],
  "statement": "This model has no demonstrated predictive edge: its log-return accuracy is
                indistinguishable from a zero-return benchmark and the economic test finds no
                value over buy-and-hold. See docs/RESULTS.md."
}
```

`/predict` with 40 rows → `422`:

```
{"detail":{"code":"too_few_rows","message":"need at least 89 rows, got 40"}}
```

`/predict` with a wrong key → `401`:

```
{"detail":{"code":"invalid_api_key","message":"Invalid or missing API key"}}
```

### 3. Streamlit

```bash
.venv/bin/streamlit run streamlit_app.py --server.headless true --server.port 8513
```

It binds the port given on the command line (`HTTP 200` on `:8513`). The printed URL at the
time came from a `[browser] serverPort` key in `.streamlit/config.toml`; that key has since
been removed, so the command-line port is authoritative.

`AppTest`:

```
exceptions: 0
tabs: ['Findings', 'Data', 'Model demo', 'About']
metrics: [('Model prediction', '-0.05%'), ('Persistence', '+0.00%'), ('Realized', 'n/a')]
```

### 4. Parity

```
sample feature parity: positions=24 rows=696 max_abs_diff=0.000e+00
prediction parity: n=5 max_abs_diff=0.000e+00
full-series feature parity (5 post-block positions): max_abs_diff=0.000e+00
```

```
tests/test_serving_parity.py ........                                     [100%]
```

### 5. Footprint

| Stage | Peak RSS | Time |
|---|---|---|
| bare Python | 9.6 MB | 0.01 s |
| + `streamlit` | 54.9 MB | 0.23 s |
| + `tensorflow` (2.20.0) | 656.4 MB | 2.76 s |
| + model and scalers | 668.2 MB | 2.68 s |
| + one prediction from 200 rows | 689.0 MB | 3.12 s |
| full `AppTest` run, all four tabs | 699.1 MB | 3.22 s |

Installed size of the direct `requirements.txt` packages: **2,345.5 MB**, of which
TensorFlow is **1,857.9 MB**. `.venv/lib/python3.12/site-packages` totals 3,234.9 MB (it also
contains packages unrelated to this repo, e.g. MLflow). TensorFlow 2.20.0 metadata says
`Requires-Python: >=3.9`; the installed wheel is `cp312-cp312-manylinux_2_17_x86_64`.
`yfinance` and `curl_cffi` are listed in `requirements.txt` but are **not installed** in this
`.venv`; they are imported lazily by `src/data_loader.py`.

**Footprint read.** The 699 MB peak was compared with a ~1 GB per-app reference limit (not
verifiable from the repository; an assumption). It is **plausibly within** that limit but with
little headroom, and the larger risk is the install: a 1.86 GB unpacked TensorFlow plus the
rest of the stack. This is a measurement, not a deployment plan; no framework change was made.

> **Superseded in Stage 5b.** The "~1 GB, could not verify" assumption above was replaced by the
> official limits quoted in *Stage 5b acceptance outputs* §2 (690 MB minimum, 2.7 GB maximum, as
> of February 2024), and the footprint was re-measured. The conclusion did not change.

## Stage 5b acceptance outputs

All commands run on `refactor/honest-portfolio`, 2026-11-17, Python 3.12.3.

### 1. Tests and the README check

```bash
.venv/bin/python -m pytest
.venv/bin/python scripts/check_readme_numbers.py
```

```
collected 83 items
======================= 83 passed, 20 warnings in 11.66s =======================
README number check passed: 58 marked numbers match results/*.json
```

Breakdown: 65 pre-existing tests under `tests/`, plus the 14 moved from the root
`test_pipeline.py`, plus 2 prediction-export tests and 2 README-number tests. The move added no
test. `pytest.ini` (`testpaths = tests`) now covers everything.

### 2. Dependencies and footprint

The clean-venv install of `requirements.txt` **failed on network timeouts**, not on dependency
resolution:

```bash
python3 -m venv /tmp/rt-venv2
/tmp/rt-venv2/bin/pip install -r requirements.txt
```

```
ReadTimeoutError: HTTPSConnectionPool(host='files.pythonhosted.org', port=443): Read timed out.
INSTALL_SECONDS=959.92          # first attempt
INSTALL_SECONDS=393.60          # retry with PIP_DEFAULT_TIMEOUT=120
```

A resumable `wget` of the same wheel (`tensorflow_cpu-2.20.0-cp312...whl`, 259.0 MB) reached
**82.9 MB at roughly 11 KB/s** before it was stopped. The clean-venv installed size and the
`tensorflow-cpu` import time therefore **could not be measured**. The Docker build uses the same
wheel and hit the same limit (below).

Measured instead in the existing `.venv`, which has `tensorflow 2.20.0` (the CPU-only build on
this host: `pip show tensorflow` lists no NVIDIA dependency). These are **not** `tensorflow-cpu`
numbers and are labelled as such:

| Stage | Peak RSS | Time |
|---|---:|---:|
| numpy + pandas | 94.9 MB | 0.28 s |
| + streamlit | 125.2 MB | 0.18 s |
| + tensorflow 2.20.0 | 640.7 MB | 2.07 s |
| + model and scalers | 654.2 MB | 0.23 s |
| + one prediction from the 200-row sample | 674.5 MB | 0.34 s |
| full `AppTest` run, all four tabs | **686.8 MB** | **3.04 s** |

`/usr/bin/time -v` reports 690,812 KB (674.5 MB) maximum RSS for the prediction run and
703,284 KB (686.8 MB) for the AppTest. The served log return matches the API exactly
(`-0.00045206`). Installed size in the existing `.venv`: `tensorflow` is **1,769.6 MB**
apparent; `site-packages` totals **3,085.0 MB** but includes unrelated packages (MLflow). This
is not a clean runtime total.

**Reference managed-runtime limits** (vendor documentation, "Resource limits", as of February
2024): CPU **0.078–2 cores**, memory **690 MB minimum, 2.7 GB maximum**, storage **50 GB
maximum**. Read: a 686.8 MB peak sits **just under** the documented 690 MB floor, with
essentially no headroom; the 1.77 GB TensorFlow install is the larger practical risk. This is
recorded as a footprint measurement only; Docker is the only deployment deliverable (D33).

### 3. Docker (the primary deliverable)

The image **was built and run**. This took three attempts; the first two are recorded because
the timing is part of the evidence:

| Attempt | Dockerfile | Result |
|---|---|---|
| 1 | plain `pip install` | failed after **2,383 s (39m43s)**: `error: incomplete-download … 123.4 MB/259.0 MB`, "Download failed after 6 attempts because not enough bytes were received" |
| 2 | `--timeout 120 --retries 20 --resume-retries 50` | **succeeded in 4,224.88 s (70.4 min)** |

```
docker build -t gold-irr-honest-forecasting .
BUILD_SECONDS=4224.88
#20 naming to docker.io/library/gold-irr-honest-forecasting:latest done
#20 DONE 64.8s
```

Every second of that is the one `pip install` layer; the build cache grew 4.252 GB → 6.493 GB
while it landed and the remaining COPY layers each took 0.1 s. The build did not fail on the
Dockerfile: it failed on a slow `files.pythonhosted.org`, and the retry flags fixed it. This is
the same network limit that stopped the clean-venv measurement in §2, which is why the
`tensorflow-cpu` install could not be timed in a venv but did complete inside the build.

**Image**

```
$ docker images gold-irr-honest-forecasting
gold-irr-honest-forecasting:latest   59b76cee5177   2.99GB   (140MB unique, 2.85GB shared)

$ docker history (layers over 50 MB)
2240.0 MB  RUN pip install --no-cache-dir ... -r requirements.txt
  85.3 MB  debian bookworm base
sum of all layers: 2,385,392,490 bytes = 2.39 GB
```

`docker image inspect .Size` reports 603,725,822 bytes, which does not match either figure; on
this Docker Desktop version it counts only layers not shared with other local images. The
number a user sees in `docker images` is **2.99 GB on disk**, and the layer sum is 2.39 GB.
The image is large because TensorFlow is: the single `pip install` layer is 2,240 MB of the
2,385 MB total. Nothing else in the build contributes more than 85 MB.

Manifest `sha256:3c8148b0b11ef523ab2111913481086b2b712ef72b6c492f39d7722bc8e01cf4`,
config `sha256:b4e9e8fa4bb1aa91d36b1f6f22848d701e0fff8e5e4325130b99aa152dd9db10`,
base `python:3.12-slim-bookworm@sha256:935c3c5b…` (Python 3.12.16).

**Run, health and prediction**

```
$ docker run -d --name gold-irr-gate -p 18080:8000 -e API_KEY=demo-key gold-irr-honest-forecasting
2feaa39e6aec…
$ docker ps
Up 25 seconds (healthy)   ports=8501/tcp, 0.0.0.0:18080->8000/tcp

$ curl -sS localhost:18080/health
{"status":true,"model_loaded":true,"timestamp":"2026-11-17T12:40:27.593028"}
```

The `HEALTHCHECK` itself passed five consecutive times (`docker inspect .State.Health.Log`,
exit code 0 each, `/health` JSON in the output), so `healthy` is the container's own verdict,
not a container that merely started.

`POST /predict` with the committed 200-row sample:

```json
"prediction": {
  "target": "next_trading_day_log_return",
  "log_return": -0.00045206130016595125,
  "simple_return": -0.00045195913585182153,
  "persistence_log_return": 0.0,
  "implied_next_price_persistence_equivalent": 172130169.0211332
},
"input": {"last_date": "2026-06-13", "rows_used": 200, "feature_rows": 141,
          "sequence_length": 30, "last_close_irr": 172208000.0},
"warnings": ["stale_input: last date 2026-06-13 is 157 days old (limit 7)"]
```

`log_return` is **bit-identical** to the host run and to the value in the README
(`-0.00045206130016595125`), so the image reproduces the committed serving output, not just
something plausible. The response also carries the `model` block (`git_commit 8d7715e`, seed 42)
and four `caveats`; the README shows a trimmed example.

Failure paths inside the container:

```
wrong key   → HTTP 401
40 rows     → HTTP 422 {"detail":{"code":"too_few_rows","message":"need at least 89 rows, got 40"}}
```

**Non-root and contents**

```
$ docker exec gold-irr-gate id
uid=10001(appuser) gid=10001(appuser) groups=10001(appuser)

$ docker inspect --format 'User={{.Config.User}} Cmd={{.Config.Cmd}}'
User=appuser Cmd=[uvicorn src.api.main:app --host 0.0.0.0 --port 8000]

$ ls /app
config  data  logs  models  requirements.txt  results  src  streamlit_app.py
/app/data/sample/gold_sample.csv, /app/data/sample/README.md   (nothing else under data)
/app/results: backtest.json backtest.log eval_V1.json eval_V2.json eval_V3.json
              eval_summary.csv run.log
```

Absent, checked by `ls` inside the image: `data/raw`, `data/processed`, `tests`, `notebooks`,
`results/predictions`, `.env`, and the legacy `models/gold_lstm_v2.keras`.

**Streamlit from the same image** (the second service, started by overriding the command):

```
$ docker run -d -p 18501:8501 gold-irr-honest-forecasting \
    streamlit run streamlit_app.py --server.port 8501 --server.address 0.0.0.0 --server.headless true
$ curl -o /dev/null -w '%{http_code} %{time_total}' localhost:18501/
200 0.020436
```

It prints `Local URL: http://localhost:8501` — the legacy configured port came from the removed
`.streamlit/config.toml` keys and is gone. Both containers were stopped and removed after the
evidence was captured; the image is left in place.

**One precision note.** The `results/predictions` line in `.dockerignore` was added while this
build was already running, so this image was built from the earlier context. It changes nothing
here: `results/predictions/` did not exist on disk (the smoke run wrote to a temporary
directory) and the
`ls` above confirms it is not in the image. The next build picks up the rule.

### 4. CI

The YAML parses:

```
parsed OK; top-level keys: ['name', True, 'permissions', 'jobs']
jobs: ['check']
steps: ['actions/checkout@v4', 'actions/setup-python@v5', 'Install dependencies', 'Run checks']
runs-on: ubuntu-latest
python: 3.12
```

(`on` is read as the boolean `True` by PyYAML 1.1; GitHub's parser treats it as the event key.)

Local replay, in order:

* `python -m pip install --upgrade pip` → installed pip **26.3**.
* `make check` → **83 passed** and **58 marked numbers** (above).
* `python -m pip install -r requirements-dev.txt` **could not be replayed in a clean
  environment**: it includes `-r requirements.txt`, so it hits the same `tensorflow-cpu`
  download. In the existing `.venv`, the dev-only `yfinance` and `curl_cffi` are absent; the
  tests do not import them (the loader imports them lazily).

The workflow itself was **not executed on GitHub** from this environment.

### 5. Repository size

```bash
git ls-files | wc -l
git ls-files '*.py' | wc -l
git ls-files '*.py' | xargs cat | wc -l
git diff legacy-pre-refactor --stat | tail -1
```

```
tracked files:        71
tracked Python files: 33
Python LOC:           5,849
vs legacy tag:        148 files changed, 14430 insertions(+), 53841 deletions(-)
```

Read: the branch is smaller than the legacy state in tracked content because the 2.6 MB
`models/gold_lstm_v2.keras` duplicate, notebook outputs and stale artifacts are gone; the
insertion count is inflated by the three new documentation files (`README.md`,
`docs/RELEASE_PLAN.md`, `docs/README_CLAIMS.md`) and the split requirement files, not by new
pipeline code. The counts are measured after the Stage 5b documentation commits.

### 6. TODOs left for the owner

* `LICENSE`: replace `<TODO: copyright holder>`.
* `README.md`: author, contact, citation, and the TGJU permission status are marked `TODO`.
* The image exists only in this machine's Docker daemon. Push it to a registry if the release
  should ship one; nothing here does that.
* CI has never executed on GitHub (no remote push). The YAML and every command were replayed
  locally; the first real run is the owner's.
* Merge the branch after review, without squashing. No release tag exists.

## Stage 6 acceptance outputs

All commands run on `refactor/honest-portfolio`, 2026-11-18, Python 3.12.3. Stage 6 is limited
to release fixes: no retraining, no re-scoring, no changes to committed numeric results (the
only `results/` change is the path redaction in D34).

### 1. API field names and tests

`POST /predict` now accepts the sample CSV header verbatim. `src/api/main.py` declares
`date` with `pydantic.AliasChoices("date", "Date")` and a before-validator rejects `date` /
`Date` with different values. The four price fields already matched the CSV.

Four tests were added to `tests/test_api_contract.py` (none removed):

* `test_sample_csv_header_is_accepted_verbatim` — posts
  `json.loads(pd.read_csv(...).to_json(orient="records"))` with keys
  `Date,Gold_IRR,USD_IRR,Ounce_USD,Oil_USD`; asserts 200 and
  `log_return == -0.00045206130016595125`.
* `test_lowercase_date_form_still_works` — the old `date` form returns the same value.
* `test_conflicting_date_aliases_are_rejected` — both aliases with different values → 422.
* `test_matching_date_aliases_are_accepted` — both with the same value → 200.

**Sample parity proof:** the verbatim-header request returned HTTP 200 with
`log_return = -0.00045206130016595125`, exactly the committed Stage 5a/5b parity value. The
full suite is **87 passed** (83 before Stage 6).

### 2. README example

The README's "predict from the sample" script reads the CSV with pandas and posts the rows
without renaming. It was executed against a local server on 2026-11-18; the captured
`log_return` is `-0.00045206130016595125`, `rows_used` 200, `feature_rows` 141, and the
stale warning says 158 days. `make check` re-ran and the 58 marked numbers still match.

### 3. Log redaction proof (D34)

`results/run.log` and `results/backtest.log` had the absolute repository path replaced by
`<REPO>`; nothing else changed.

| File | Lines before/after | Path replacements | Digit SHA-256 before = after |
|---|---:|---:|---|
| `results/run.log` | 87 / 87 | 6 | `4a3e59bb4515a494d173f9881a1a18a46e915743b6e588e8b4e7bd03ab76994b` |
| `results/backtest.log` | 10 / 10 | 1 | `eec5f611e4779e78d16faf09a50dd501accca5f66267d9309f6f3f0d03149ddc` |

Proof:

* Masking the old path to `<REPO>` on both sides gives an empty diff (`diff -u` on the
  masked files → no output).
* Replacing `<REPO>` back with the old path reconstructs the pre-edit bytes exactly
  (`after.replace(b"<REPO>", old_path) == before` → True for both files).
* The digit-only SHA-256 is identical before and after (table above).
* `grep -c "/home/"` → 0 in both files after the edit.
* `git diff --word-diff` shows only the path strings changing; every timestamp, metric and
  line count is unchanged.

### 4. Deployment-reference grep

Tracked-tree grep after the cleanup found no match for the vendor name, the platform port,
or the vendor's cloud product name. The only matches for the `host` substring are
`files.pythonhosted.org` in the README/STATE network notes — the Python package index, not a
managed app. Docker is the only deployment deliverable (D33).

### 5. Docker rebuild and run

The image was rebuilt because `src/` and `results/` are copied into it. The dependency layer
was cached; the rebuild took **1 s** (`BUILD_SECONDS=1`). The image is
`gold-irr-honest-forecasting:latest`, ID `38287aaa10d8`, **2.99 GB** on disk
(`docker image inspect .Size` = **603,727,316 bytes**); the `pip install` layer remains
2.24 GB.

```
$ docker run -d --name gold-irr-stage6 -p 18081:8000 -e API_KEY=demo-key gold-irr-honest-forecasting
$ curl -sS http://127.0.0.1:18081/health
{"status":true,"model_loaded":true,"timestamp":"2026-11-18T08:00:13.729150"}
```

`POST /predict` with the 200-row sample posted with the CSV's original header
(`Date,Gold_IRR,USD_IRR,Ounce_USD,Oil_USD`):

```json
{
  "prediction": {
    "target": "next_trading_day_log_return",
    "log_return": -0.00045206130016595125,
    "simple_return": -0.00045195913585182153,
    "persistence_log_return": 0.0,
    "implied_next_price_persistence_equivalent": 172130169.0211332
  },
  "input": {"last_date": "2026-06-13", "rows_used": 200, "feature_rows": 141,
            "sequence_length": 30, "last_close_irr": 172208000.0},
  "warnings": ["stale_input: last date 2026-06-13 is 158 days old (limit 7)"]
}
```

Wrong key:

```text
HTTP 401 {"detail": {"code": "invalid_api_key", "message": "Invalid or missing API key"}}
```

The container's own `HEALTHCHECK` reports `Status: healthy` with a successful `/health`
probe; it runs as `uid=10001(appuser)`. The rebuilt image contains the new code
(`grep AliasChoices /app/src/api/main.py` matches) and the redacted logs
(`grep -c "/home/"` → 0). The container was stopped and removed; the image is kept.

### 6. Final verification

The absolute root path in the raw `make check` output is shown as `<REPO>`; the run itself
used the local path.

```text
$ make check
.venv/bin/python -m pytest -q
============================= test session starts ==============================
platform linux -- Python 3.12.3, pytest-9.2.0, pluggy-1.7.0
rootdir: <REPO>
configfile: pytest.ini
testpaths: tests
plugins: anyio-3.7.1, Faker-40.43.0
collected 87 items

tests/test_api_contract.py .......................                       [ 26%]
tests/test_backtest_check.py .........                                   [ 36%]
tests/test_data_loader_date_shift.py ......                              [ 43%]
tests/test_eval_protocol.py ...............                              [ 60%]
tests/test_pipeline.py ..............                                    [ 77%]
tests/test_predictions_export.py ..                                      [ 79%]
tests/test_readme_numbers.py ..                                          [ 81%]
tests/test_serving_parity.py ........                                    [ 90%]
tests/test_streamlit_app.py ........                                     [100%]

======================= 87 passed, 23 warnings in 19.31s =======================
.venv/bin/python scripts/check_readme_numbers.py
README number check passed: 58 marked numbers match results/*.json
```

**Test count:** 87 passed (83 before Stage 6; four API tests added, none removed).

**`git status`:** clean after the Stage 6 commits.

**Branch log** (the commit adding this block is the next one; this is its parent history):

```text
5bc9516 docs(readme): record the Stage 6 Docker rebuild measurement
383000d chore(results): redact absolute paths from the committed run logs
833fe0d docs: remove managed-deployment references
5917b80 docs(decisions): record GATE 5b acceptance and the Docker-only decision
d293c75 docs(readme): add a runnable sample prediction and exact field names
15f4cda fix(api): accept the sample CSV header verbatim
2423b80 docs: add the Stage 6 release-fix plan
```

**Remaining TODOs for the owner:**

* `LICENSE`: replace `<TODO: copyright holder>`.
* `README.md`: author, contact, citation, and TGJU permission status are `TODO`.
* TGJU permission: confirm whether redistribution is allowed; the 200-row sample is bundled
  pending that answer.
* Registry push: the image exists only in this machine's Docker daemon.
* GitHub push and the first CI run: CI has never executed on GitHub.
* Merge `refactor/honest-portfolio` without squashing, then tag. No merge, push or tag was
  done in Stage 6.

## Not verified in this session

Stated plainly so nobody mistakes these for measured facts:

- Model architecture (64→32→16, 33,441 params), the log-return R² of −0.0016, and the Diebold–Mariano result are **audit-reported**. Stage 3 re-derives the first two.
- `python -m unittest test_pipeline` reportedly runs 14 tests successfully (audit §5.6). Not re-run here.
- The old `trading_bot/` backtest was not re-executed; only its committed JSON was read before the directory was removed. The Stage 4 backtest in `results/backtest.json` was executed in this session.
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

# Tests (pytest 9.2.0 is installed in .venv as of Stage 5a; requirements.txt lists it)
.venv/bin/python -m pytest tests/ test_pipeline.py -q

# Stage 3 evaluation (writes results/ and the primary artifact; needs the local raw snapshot)
.venv/bin/python -m src.evaluate --variant all --artifact

# API — needs the committed artifact and a key
API_KEY=demo-key .venv/bin/python -m uvicorn src.api.main:app --host 127.0.0.1 --port 8000
curl -sS http://127.0.0.1:8000/health
curl -sS -H "X-API-Key: demo-key" http://127.0.0.1:8000/model-info

# POST /predict takes raw rows; build a payload from the bundled sample
PAYLOAD=$(mktemp)
.venv/bin/python -c "import json,pandas as pd; d=pd.read_csv('data/sample/gold_sample.csv'); \
print(json.dumps({'rows':[{'date':str(r.Date),'Gold_IRR':float(r.Gold_IRR),'USD_IRR':float(r.USD_IRR), \
'Ounce_USD':float(r.Ounce_USD),'Oil_USD':float(r.Oil_USD)} for r in d.itertuples()]}))" > "$PAYLOAD"
curl -sS -X POST http://127.0.0.1:8000/predict -H "Content-Type: application/json" \
  -H "X-API-Key: demo-key" -d @"$PAYLOAD"
rm -f "$PAYLOAD"

# Streamlit (offline; sample + committed artifacts only)
.venv/bin/streamlit run streamlit_app.py

# Regenerate features from the corrected data (writes to data/processed/, ignored)
.venv/bin/python src/feature_eng.py
```

`requirements.txt` lists `pytest` for a fresh environment. A `Makefile` provides `make test`,
`make check`, `make evaluate`, `make backtest`, `make api` and `make app`. Data files are **not**
in a fresh clone: `data/sample/` is, and the full series must be fetched or supplied locally.


---

## Stage 6 review — final verification (2026-11-18)

**Branch:** `refactor/honest-portfolio` · **HEAD at the start of this block:** `d4d9353`
**Scope:** the Stage 6 review fixes. No evaluation or backtest run, no retraining, no merge,
push or tag. `results/` was not written.

### Commands and results

| Check | Command | Result |
|---|---|---|
| Test suite (snapshot present) | `make check` | **91 passed, 0 skipped, 91 collected**; README number check: **58 marked numbers match `results/*.json`** |
| Test suite (clean clone) | `pytest -q` with the two `data/raw/*.csv` files moved aside | **88 passed, 3 skipped**; the skips are `tests/test_serving_parity.py:128`, `tests/test_serving_parity.py:229` and `tests/test_api_contract.py:238` |
| D-1 share | `python scripts/d1_share.py` | exact **0.691161%**, zero-prediction **0.498226%**, reviewer ratio **0.861932** |
| Global grid | `python scripts/global_grid_audit.py` | V1 **35.80%** zero / **19.08%** multi-day; V2 **36.02%** / **18.93%**; V3 **36.01%** / **19.00%** |
| Alignment script | `python scripts/align_gold_ounce.py --live` | the four B2.2 correlations reproduced to four decimals (see `docs/REVIEW_FIXES.md`) |
| Docker build | `docker build -t gold-irr-honest-forecasting .` | succeeded with the dependency layer cached; image `fb0788de3bd`, **2.99 GB**, 603,728,251 bytes |
| Docker health | `curl /health` | 200 `{"status":true,"model_loaded":true,...}` |
| Docker predict | 200 sample rows with the CSV header `Date,Gold_IRR,USD_IRR,Ounce_USD,Oil_USD`, `X-API-Key` | 200, `log_return -0.00045206130016595125`, `rows_used 200`, `feature_rows 141` |
| Docker auth | the same request without the key | **401** `{"code":"invalid_api_key",...}` |
| `results/` unchanged | `git diff --exit-code HEAD -- results/`; `git diff --stat 5c2208e^..HEAD -- results/` | no output; empty diff |

### Remaining TODOs for the owner (untouched)

| File:line | Placeholder |
|---|---|
| `LICENSE:3` | `Copyright (c) 2026 <TODO: copyright holder>` |
| `README.md:404` | Author / maintainer |
| `README.md:405` | Contact |
| `README.md:406` | How to cite |
| `README.md:407` | Data permission status (TGJU) |

The verification did not edit any of these.
