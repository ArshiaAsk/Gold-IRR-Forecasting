# Refactor Plan — Honest Portfolio Piece (B-lite)

**Status:** Stages 0–5b complete; **GATE 5b pending owner review** ·
**Branch:** `refactor/honest-portfolio` · **Baseline tag:** `legacy-pre-refactor` (→ `d1670cc`)
**Source of truth for the "before" state:** `docs/AUDIT_REPORT.md` (2026-11-13, read-only audit of `d1670cc`)

## Stage log

| Stage | Status | Commits | Note |
|---|---|---|---|
| 0 | done | `d061bd7`, `61d130a` | plan, decisions, state, audit committed |
| 1 | done | `14dec06` | data-integrity investigation, read-only |
| 1b | done | `6edf09f` | G1 resolution: Jalali field silent, alignment verified |
| G1-final | done | — | **D19: apply the +1 relabel** (owner) |
| 2a | done | `d5b8dcd`, `75c927e` | reversible date correction + tests + verification |
| 2b | done | `147d58b`, `5c6a74a`, `66b2353` | scope reduction, minimal API, repo hygiene |
| 3 | done | `798981a`, `cb75162`, `37585ac`, `8d7715e`, `64c9798`, `5f4abaa` | no demonstrated edge; GATE 3 accepted; verdict final |
| 4 | done | `1e3e634`, `0cc0647`, `9b9caca`, `cf09f8d`, `3b5ac3a` | economic reality: no added value over buy-and-hold; `trading_bot/` removed |
| 5a | done | `1768b2e`, `f587864`, `1bd4a5b`, `f749791`, `e9d65e0` | serving: API + Streamlit on the seed-42 artifact; one feature function; 79 tests |
| 5b | done | `e6f8210`, `d59dc34`, `60e9870`, `1cf8285`, `361b195`, `eed9ee0`, `539f92b`, `369f151`, `13ce2c6` | reproducibility, Docker, CI, README; 83 tests |

---

## Ground rules (apply to every stage)

1. One logical change per commit. No mixed commits.
2. Nothing is deleted before it is preserved. The pre-refactor state is frozen in the annotated tag `legacy-pre-refactor`. Anything removed from the working tree must remain reachable from that tag.
3. Every number in a doc, README or summary must come from a command run in this session or from a committed artifact that was read. If it cannot be verified, it is omitted — not estimated.
4. No secrets printed or committed. `.env` stays ignored (verified: `.gitignore:28`, and `git ls-files .env` is empty).
5. Stop at every **GATE** and wait for the owner's decision.
6. A contradiction with `docs/AUDIT_REPORT.md` is escalated, never silently resolved.
7. At the end of each stage: update `docs/STATE.md` and `docs/DECISIONS.md`, then stop and report.

---

## Stage 1 — Data integrity investigation (READ-ONLY)

**Goal:** explain the implausible weekday distribution and settle the unit question, without changing any data or source file.

### Why this is first
The audit reports 1,424 raw rows whose weekday counts are `Mon 243 · Tue 240 · Wed 137 · Thu 90 · Fri 237 · Sat 236 · Sun 241`. A Tehran gold/currency market should concentrate on the Iranian working week (Sat–Wed), yet the heavy days here are Fri–Tue. Every downstream result — features, splits, walk-forward folds, backtest dates — inherits whatever is wrong with the date axis. Fixing the model before fixing the calendar would be building on sand.

### Hypotheses to test (none asserted yet)
- **H1 — one-day label shift.** The heavy set `{Fri, Sat, Sun, Mon, Tue}` is exactly the Sat–Wed trading week shifted back one day (`Sat→Fri, Sun→Sat, Mon→Sun, Tue→Mon, Wed→Tue`). Arithmetic: 237+236+241+243+240+137+90 = 1,424. If shifting every date forward by one day moves ≥95% of rows onto Sat–Wed, this is the explanation. *This is a hypothesis, not a finding.*
- **H2 — Jalali↔Gregorian conversion error.** TGJU dates are Jalali; a wrong conversion (or a library that assumes a different epoch) produces a systematic offset that grows or jumps at leap years.
- **H3 — TGJU date parsing.** Persian digits, `YYYY/MM/DD` vs `YYYY-MM-DD`, or a column-position assumption (`src/data_loader.py`).
- **H4 — merge / ffill artifact.** `how='left'` merge of TGJU and Yahoo plus `ffill` (`src/data_loader.py:146-158`) can stamp a global-market row onto an Iranian row's date, mixing two calendars in one series.
- **H5 — timezone / off-by-one.** `Asia/Tehran` vs UTC normalization moving timestamps across midnight.

### Checklist
- [ ] Read `src/data_loader.py` end to end; record exactly how dates are parsed, merged, and forward-filled (with line numbers).
- [ ] Dump 20 consecutive raw TGJU records (date string as received + parsed date) into the report as evidence.
- [ ] Reproduce the weekday table from `data/raw/final_gold_dataset.csv` with a committed script, not a notebook cell.
- [ ] Test H1: shift all dates by +1 day and recount weekdays; report the Sat–Wed share before and after.
- [ ] Test H2: convert a sample of Jalali dates with an independent implementation and compare to the parsed dates.
- [ ] Test H4: count rows whose gold price is unchanged from the previous row (ffill evidence) and cross-tabulate against weekday.
- [ ] Test H5: check whether any date column carries a time component and whether tz conversion is applied.
- [ ] Confirm the unit: `TICKER_GOLD="geram18"` in `config/settings.py`, and verify the magnitude is Rial (not Toman) against the USD series and a known reference rate.
- [ ] Quantify the blast radius: how many rows / what share of the series would move if H1 is true.
- [ ] Write the recommended fix with an explicit risk assessment (what breaks if we re-date the series).

### Deliverables
- `docs/DATA_INTEGRITY.md` — evidence tables, verdict per hypothesis (CONFIRMED / REFUTED / INCONCLUSIVE), recommended fix, risk.
- `scripts/audit_calendar.py` — read-only; reads CSVs, writes nothing, exits 0.

### Acceptance criterion (must be runnable)
```bash
python scripts/audit_calendar.py            # exits 0
git diff --stat legacy-pre-refactor -- data/ src/   # must be empty
grep -c '^|' docs/DATA_INTEGRITY.md         # ≥ 8 (evidence tables present)
```
Additionally: every number printed in `docs/DATA_INTEGRITY.md` appears verbatim in the pasted stdout of `scripts/audit_calendar.py`.

### GATE 1
**Owner decides whether the data is fixed before any modeling work.** Options: (a) fix dates and re-derive everything, (b) keep the data as-is and document the defect as a known limitation, (c) stop and re-source the data. No Stage 2 work starts until this is answered.

### Executed — Stage 1 (`14dec06`) and 1b (`6edf09f`)
- [x] Date path traced with line numbers; H1–H5 tested; H1/H2/H3/H5 refuted, H4 refuted as cause but a separate merge defect verified.
- [x] The audit's weekday table shown to be mislabelled (off-by-one label list).
- [x] A 21-month block (2023-10-27 → 2025-08-06) discovered, present in both TGJU series.
- [x] Jalali field tested: 11,331 records, 0 offsets — it cannot witness the block.
- [x] Alignment against `GC=F`: block +0.1119 → +0.3803 under +1; post-block +0.3577 → −0.1262.
- [x] **GATE 1 answered → D19: apply the relabel** (reversible, loader-level).
- Deviation: `scripts/audit_calendar.py` was not committed (D9); every figure is reproduced by an inlined command in `docs/DATA_INTEGRITY.md`.

---

## Stage 2 — Scope reduction

**Goal:** cut the repo down to what actually works, and make a fresh clone able to run.

### Keep
- `src/data_loader.py`, `src/feature_eng.py`, `src/data_preprocessor.py`, `src/model_builder.py`, `src/model_evaluator.py`, `src/train_pipeline.py`
- A minimal API: `/health`, `/model-info`, `/predict` (rewritten on top of `src/api/`)
- `config/`, `streamlit_app.py`, `Dockerfile`, `trading_bot/` (kept until Stage 4, then removed), `notebooks/`, tests that actually run

### Delete (preserved in `legacy-pre-refactor`)
- `api_layer/` live trading bot (scale bug at `api_layer/live_predictor.py:257`, stale-history corruption, Open-vs-Close mismatch)
- `src/mlops/` A/B, canary, governance model cards, ONNX, supervisor, registry, retraining gates
- `/predict-with-confidence` (fabricated Gaussian noise, `src/api/predictor.py:193`)
- `supervisord.conf`, `start.sh`, `quick-start.sh`, `monitoring/` Grafana provisioning
- Committed junk: `notebooks/catboost_info/`, `api_layer/cache/raw_response_*.json`, `outputs/*.png`

### Checklist
- [x] No `legacy/` folder; the tag is the archive (D3).
- [x] Remove the components; confirm each is still reachable at `legacy-pre-refactor`.
- [x] Rewrite `requirements.txt` from the actual imports of the *kept* code.
- [ ] Track `models/scaler_X.pkl` / `scaler_y.pkl` — **deferred to Stage 3**, which regenerates and commits model + scalers together (owner's Stage 2b instruction).
- [ ] Add `scripts/check_deps.py` and a `Makefile` — **deferred to Stage 5b**; not in the owner's Stage 2b scope.
- [x] Untrack generated artifacts and fix `.gitignore` so tracked/ignored policy is consistent.

### Deliverables
Slim tree; `requirements.txt` that installs; `data/sample/`; this plan updated. (`Makefile`, `scripts/check_deps.py` and `docs/SCOPE.md` were dropped from the Stage 2 scope by the owner's instruction; Stage 5b covers the Makefile and dependency checks.)

### Executed — Stage 2a (`d5b8dcd`, `75c927e`) and 2b (`147d58b`, `5c6a74a`, `66b2353`)
- [x] Reversible +1 relabel for 2023-10-27 → 2025-08-06 in `DataLoader.get_tgju_history`, window/flag in `config/settings.py`, row count logged every run.
- [x] Unit tests: exact rows, flag off, no collisions, row count, boundaries (`tests/test_data_loader_date_shift.py`).
- [x] Verified on the local raw dataset: 503 rows, 0 collisions, 1,424 → 1,424 rows, features 1,424 → 1,394; numbers in `docs/DATA_INTEGRITY.md` → "Stage 2a — Applied fix".
- [x] Deleted `api_layer/`, `src/mlops/`, `src/monitoring/`, `monitoring/`, `supervisord.conf`, `start.sh`, `quick-start.sh`, `main.py`, `setup.py`, `examples/`, stale `outputs/`, `notebooks/catboost_info/`, and the tests for removed modules. 75 paths, all reachable at `legacy-pre-refactor`.
- [x] Minimal API: `/health`, `/model-info`, `/predict` only; starts without MLOps; API key from `API_KEY`/`API_KEY_REQUIRED`.
- [x] Untracked `data/raw`, `data/processed`, `data/mlops_audit.db` (kept on disk); added `data/sample/gold_sample.csv` (200 rows); rebuilt `.gitignore`.
- [x] `requirements.txt` rebuilt from actual imports; TensorFlow/Keras pins kept.
- Deviations from the original Stage 2 text: no `legacy/` folder (D3 uses the tag), no `Makefile`, no `scripts/check_deps.py`, no `docs/SCOPE.md` — the owner's Stage 2b instruction defined the deliverable set and did not include them. Scalers are **not** committed; Stage 3 regenerates model + scalers together (recorded in `docs/STATE.md`).

---

## Stage 3 — Honest modeling and evaluation

**Goal:** find out whether a signal exists, with an evaluation that cannot flatter the model.

### Checklist
- [x] Replace raw-level features with stationary ones. The frozen 23-feature set lives in
  `src/feature_eng.py::add_stationary_features` and is the single source of truth for training
  and serving. The audit's train→test shifts (SMA_7 +13.3σ, Bollinger_Upper +13.6σ, MACD +6.6σ)
  are no longer present as raw levels.
- [x] Implement expanding-window walk-forward validation with five chronological folds, a 30-row
  purge, a 5-row embargo and scalers fit only on each fold's fitting rows.
- [x] Report persistence and ridge baselines on identical folds, alongside the LSTM.
- [x] Report log-return RMSE/MAE, OOS R² vs zero and vs the historical mean, directional
  accuracy with a binomial test **against the up-day base rate**, Diebold–Mariano vs persistence
  with HAC variance and the HLN correction, block-bootstrap CIs, and prediction dispersion.
- [x] Save machine-readable results to `results/` and paste the console output into
  `docs/RESULTS.md`.

### Executed — Stage 3 (`798981a`, `cb75162`, `37585ac`, `8d7715e`, `64c9798`, `5f4abaa`)
- [x] `docs/EVAL_PROTOCOL.md` pre-registered before any model fit; one pre-run hold-out amendment
  (2025-10-01 cutoff, 210 rows) at `cb75162`; no post-run deviations.
- [x] Data variants: V1 raw, V2 corrected (primary), V3 block excluded. V2 re-pairs the global
  series with one complete Yahoo vintage (D23); V3 drops the block and never lets an LSTM
  sequence cross the gap.
- [x] Models: persistence, historical mean, ridge-own, ridge-full, stationary LSTM (5 seeds),
  legacy-spec LSTM (3 seeds, V2 only). Four fixed configurations; no tuning.
- [x] Run: `python -m src.evaluate --variant all --artifact`, 1,259.6 s (21.0 min), 109 LSTM
  fits, inside the 90-minute budget.
- [x] Tests: 35 passed (15 new protocol tests, 6 date-shift tests, 14 pipeline tests).
- [x] Artifact: `models/gold_lstm_stationary_v2.keras` + two scalers + metadata, trained on V2
  pre-hold-out rows, seed 42. Not wired into the API or Streamlit.
- [x] **Verdict: no demonstrated edge.** The stationary LSTM's walk-forward RMSE is 0.018214 vs
  persistence 0.018350 (R² +0.0148, DM p 0.2251, bootstrap CI [−0.0272, +0.0561]); hold-out
  0.026543 vs 0.026545 (R² +0.0001, DM p 0.4984, CI [−0.0577, +0.0630]). Ridge-own beats
  persistence only on the walk-forward; ridge-full is worse in both. The historical mean is the
  only significant walk-forward DM (p 0.0055), but it fails on the hold-out (p 0.2428). V1 vs V2
  and V3 change no conclusion. Full tables in `docs/RESULTS.md`.

### Acceptance criterion (as executed)
```bash
.venv/bin/python -m src.evaluate --variant all --artifact   # exits 0, writes results/ + artifact
PYTHONPATH="$PWD/.venv/lib/python3.12/site-packages:$PWD" \
  .venv/bin/python -m pytest tests/ test_pipeline.py -q   # 35 passed
```

The old `make eval` / `scripts/check_eval.py` acceptance text was a Stage 5b deliverable (Makefile
and scripts); the runnable entry point above is the Stage 3 deliverable. The old file names
(`src/features_stationary.py`, `src/walkforward.py`, `scripts/run_eval.py`, `reports/`) were
superseded by `src/feature_eng.py::add_stationary_features`, `src/eval_data.py`,
`src/eval_metrics.py`, `src/evaluate.py` and `results/`.

### GATE 3
**Owner reviews the results before any narrative is written.** If the edge is still zero, the plan
continues as a negative result — but the owner confirms the framing first. **Stage 3 stops here.**

### GATE 3 decision (2026-11-16) — accepted

The verdict **"no demonstrated edge" is final**. No further model tuning, new features or new
architectures; any extra search after seeing the hold-out would be post-hoc and is out of scope.
The optional same-day global sensitivity stays **unrun**. `trading_bot/` is replaced by the
Stage 4 economic-reality analysis (D26), and Stage 5 is split into 5a serving and 5b
reproducibility/docs. Recorded as D25–D28 in `docs/DECISIONS.md`.

---

## Stage 4 — Economic reality (executed)

**Goal:** quantify what a daily long/flat rule driven by the Stage 3 predictions would have
earned on the hold-out, after costs, against buy-and-hold gold and USD — so the README can
state the economic conclusion with numbers. This is **not** a search for a profitable strategy.

### Executed — Stage 4 (`1e3e634`, `0cc0647`, `9b9caca`, `cf09f8d`, `3b5ac3a`)
- [x] `docs/BACKTEST_PROTOCOL.md` pre-registered and committed (`0cc0647`) before any result:
      hold-out only, seed-42 artifact by inference, S0–S3, four cost scenarios, block bootstrap,
      fixed decision rule.
- [x] `src/backtest_check.py` + `tests/test_backtest_check.py`: 9 tests (cost on each change,
      flat→flat free, no lookahead, S0 compounded product, one-day delay shift).
- [x] `results/backtest.json`, `results/backtest.log`: full strategy × cost table, bootstrap
      CIs, delay sensitivity, gold-in-USD reference, prediction spread.
- [x] `trading_bot/` removed with `git rm`; no kept code imported it; the tag preserves it.
- [x] **Finding: no added value over buy-and-hold.** At 0.75%/side, S2 = +1.13% vs S0 = +56.71%
      (diff −22.45 bp/day, CI [−45.45, −7.89]); S3 = +36.90% vs S0 (diff −7.56 bp/day, CI
      [−23.96, +2.01]). S2 is significantly worse; S3 is not distinguishable from S0 but does
      not beat it. Full tables in `docs/RESULTS.md` §11.
- [x] Prediction spread: seed-42 `std_pred` 0.002482 vs `std_actual` 0.026456 (9.4%), corr
      +0.031; the model is still near-constant. Seed 42 is typical, not stronger than the Stage 3
      5-seed mean.
- [x] One-label validation/hold-out overlap recorded as a deviation (`docs/EVAL_PROTOCOL.md`
      §11 D-1); no retraining, verdict unchanged.

### Acceptance criterion (as executed)
```bash
.venv/bin/python -m src.backtest_check        # exits 0; writes results/backtest.json + log
PYTHONPATH="$PWD/.venv/lib/python3.12/site-packages:$PWD" \
  .venv/bin/python -m pytest tests/ test_pipeline.py -q   # 44 passed
```

The old `make backtest` / `scripts/check_backtest.py` acceptance text belonged to a kept
backtest; the owner replaced that with the economic-reality analysis. The old "If kept"
checklist is satisfied where it applies: hold-out only, costs 0–3% stated, both benchmarks
shown, and the rule is labelled by what it does (a long/flat threshold on the model's
prediction, not "AI").

---

## Stage 5a — Serving

**Goal:** make the stationary model the served model, with no train/serve feature skew.

### Checklist
- [x] Rewire the API to `models/gold_lstm_stationary_v2.keras` + its two scalers; `/model-info`
      reports the 23-feature stationary schema and sequence length 30.
- [x] Rewire Streamlit to the same artifact and the same feature function.
- [x] **One feature function** (`src/feature_eng.py::add_stationary_features`) is used by
      training, evaluation, the API and Streamlit. No second implementation, no raw-level
      fallback.
- [x] The API validates the real `(30, 23)` input and returns a log-return prediction; no
      confidence interval, no fabricated noise.
- [x] Serving tests: the feature function is causal, the API schema matches the artifact
      metadata, and a known input produces the same prediction as the offline path.

### Acceptance criterion (must be runnable)
```bash
make api                                      # starts; /health 200
curl -s localhost:8000/model-info             # 23 features, seq_len 30
streamlit run streamlit_app.py                # starts and predicts
pytest tests/ -q                              # green
```

### Executed — Stage 5a (`1768b2e`, `f587864`, `1bd4a5b`, `f749791`, `e9d65e0`)

Design committed first (`docs/SERVING_DESIGN.md`, `1768b2e`) before any serving code. Then:

1. `src/feature_eng.py` gained `prepare_model_input`, the single raw-row adapter, plus the
   documented constants (`MIN_HISTORY_ROWS = 89`, `MAX_HISTORY_ROWS = 5000`,
   `MAX_ABS_LOG_JUMP = 0.5`) and `InputError` with stable codes.
2. `src/api/` was rewritten: `predictor.py` loads the bundle from the metadata, `security.py`
   compares `API_KEY` with `hmac.compare_digest`, `main.py` exposes three endpoints that take
   raw rows. The old `(30, 15)` contract, `FeatureBuilder`, the rate limiter and every
   price-level metric reference are gone.
3. `streamlit_app.py` was rewritten as four tabs (Findings, Data, Model demo, About) that read
   `results/*.json` and the sample. Every fabricated number in the old UI was removed.
4. New tests: `test_serving_parity.py` (8), `test_api_contract.py` (19),
   `test_streamlit_app.py` (8). Suite: **79 passed** (30 existing `tests/` + 14
   `test_pipeline.py` + 35 new).
5. Footprint measured for the hosting question; recorded in `docs/STATE.md`.

Not changed: `results/`, `models/`, `docs/EVAL_PROTOCOL.md`, `docs/BACKTEST_PROTOCOL.md`,
`Dockerfile`, `README.md`. No retraining.

---

## Stage 5b — Reproducibility, Docker, CI, README (executed)

### Checklist
- [x] `make install`, `make test`, `make check`, `make api`, `make app`, `make docker-build`,
      `make docker-run`, `make evaluate`, `make backtest`, `make fetch-data` exist and are
      documented in the README.
- [x] Minimal GitHub Actions workflow: Python 3.12, pip cache, `requirements-dev.txt`,
      `make check`. No network tests, no training, no data fetch.
- [x] One-command Docker image that actually builds; base image pinned by tag and digest;
      non-root; healthcheck on `/health`; no raw data or legacy artifacts.
- [x] Final `README.md` from scratch: measured numbers only, units in **Rial**, the Stage 3
      negative result, the Stage 4 economic numbers, limitations and lessons learned.
- [x] The old chat artifact and `trading_bot/` instructions are gone (the tag preserves them).
- [x] `LICENSE` (MIT, data excluded), notebooks cleared and moved under `notebooks/exploratory/`,
      the legacy model removed, `.gitignore` updated for opt-in predictions.
- [x] README numbers cannot drift: 58 marked blocks checked against `results/*.json`;
      `docs/README_CLAIMS.md` records every claim with its source.

### Executed — Stage 5b
- `e6f8210` — release plan committed **before** any Stage 5b change.
- `d59dc34` — root `test_pipeline.py` moved to `tests/`; one `pytest` command collects all
  **83** tests (the old 44 = 30 under `tests/` + 14 at the root; plain `pytest` saw only 30).
- `60e9870` — runtime/development dependency split; `tensorflow-cpu` for serving; Python 3.12.
- `1cf8285` — MIT `LICENSE`, predictions ignored, notebooks cleared and moved, legacy model
  removed.
- `361b195` — single-service Dockerfile, digest-pinned, non-root, healthcheck; HF Space port
  config removed; one-service compose kept and documented.
- `eed9ee0` — CI workflow.
- `539f92b` — opt-in `--save-predictions`; scratch smoke run in a temporary directory; note in
  `docs/RESULTS.md` that the headline numbers predate the flag.
- `369f151` — final `README.md`, `docs/README_CLAIMS.md`, `scripts/check_readme_numbers.py`,
  `tests/test_readme_numbers.py`.
- `13ce2c6` — Makefile and `scripts/fetch_data.py`.
- `416eed5` — D31 (GATE 5a accepted) and D32 (Stage 5b mechanics) in `docs/DECISIONS.md`.
- `7fff2dd` — this file: Stage 5b rewritten as an executed log.
- `f996ee8` — README: Docker is primary; the hold-out sentence stops claiming it can rule out
  an effect.
- `746575a` — README Docker section and `make install` / `make check`; the claims rows; the
  `.dockerignore` rule for opt-in predictions.
- `49e117e` — `docs/STATE.md` acceptance outputs, including the Docker build and run evidence.
- `799069d` — the diff figures in `docs/STATE.md` corrected to the measured values.
- `074e5b1` — a note on the absolute paths left in `results/run.log` and `results/backtest.log`.
- `3b476b9` — the diff figures in `docs/STATE.md` synced to the committed tree.

Documentation only after `539f92b`; no code, model or committed result changed.

The image was built and run after the last code commit: 2.99 GB, 4,224.9 s of build time,
`healthy`, and a prediction bit-identical to a local run. That evidence is in
`docs/STATE.md` → "Stage 5b acceptance outputs" §3.

Footprint, Docker evidence, YAML parse and the final acceptance outputs are in
`docs/STATE.md` → "Stage 5b acceptance outputs".

### Acceptance criterion (as executed)
```bash
make check                                      # 83 passed + 58 marked numbers
docker build -t gold-irr-honest-forecasting .   # see STATE for the measured result
python -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml'))"
```

The old `make train` / `make eval` names are superseded by `make evaluate`; the old
`scripts/check_readme_numbers.py` name is kept as written.

---

## Stage map

| Stage | Type | Gate |
|---|---|---|
| 0 | Docs only | none |
| 1 | Read-only investigation | **GATE 1** — fix data or document defect |
| 2 | Deletion / restructuring | none |
| 3 | Modeling + evaluation | **GATE 3** — review before narrative |
| 4 | Economic reality (backtest on saved predictions) | none |
| 5a | Serving (API + Streamlit) | none |
| 5b | Repro + docs | **GATE 5b** — owner reviews the release; no merge by the assistant |
