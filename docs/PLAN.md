# Refactor Plan — Honest Portfolio Piece (B-lite)

**Status:** Stage 0 complete · **Branch:** `refactor/honest-portfolio` · **Baseline tag:** `legacy-pre-refactor` (→ `d1670cc`)
**Source of truth for the "before" state:** `docs/AUDIT_REPORT.md` (2026-11-13, read-only audit of `d1670cc`)

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

---

## Stage 2 — Scope reduction

**Goal:** cut the repo down to what actually works, and make a fresh clone able to run.

### Keep
- `src/data_loader.py`, `src/feature_eng.py`, `src/data_preprocessor.py`, `src/model_builder.py`, `src/model_evaluator.py`, `src/train_pipeline.py`
- A minimal API: `/health`, `/model-info`, `/predict` (rewritten on top of `src/api/`)
- `config/`, tests that actually run

### Quarantine or delete (preserved in `legacy-pre-refactor`)
- `api_layer/` live trading bot (scale bug at `api_layer/live_predictor.py:257`, stale-history corruption, Open-vs-Close mismatch)
- `trading_bot/` backtest engine (does not use the model: `USE_REAL_PREDICTIONS=False`)
- `src/mlops/` A/B, canary, governance model cards, ONNX, supervisor, registry, retraining gates
- `/predict-with-confidence` (fabricated Gaussian noise, `src/api/predictor.py:193`)
- `streamlit_app.py`, `supervisord.conf`, `monitoring/` Grafana provisioning
- Committed junk: `notebooks/catboost_info/`, `api_layer/cache/raw_response_*.json`, `outputs/*.png`, `models/gold_lstm_v2.keras` if retraining supersedes it

### Checklist
- [ ] Decide quarantine folder (`legacy/`) vs deletion, per component; record the rationale in `docs/DECISIONS.md`.
- [ ] Remove the components; confirm each is still reachable at `legacy-pre-refactor`.
- [ ] Rewrite `requirements.txt` from the actual imports of the *kept* code. Verified missing today: `yfinance`, `curl_cffi`, `pytest`, `requests` (present only as a commented line), `python-dotenv` (imported nowhere).
- [ ] Track `models/scaler_X.pkl` and `models/scaler_y.pkl` (currently on disk, untracked, and `.gitignore` has `*.pkl`) — or make training deterministically reproduce them and say which.
- [ ] Add `scripts/check_deps.py`: every third-party import in non-`legacy/` code is declared in `requirements.txt`.
- [ ] Add a `Makefile` with `train`, `test`, `api`, `eval` targets.
- [ ] Untrack generated artifacts and fix `.gitignore` so tracked/ignored policy is consistent.

### Deliverables
Slim tree; `requirements.txt` that installs; `Makefile`; `scripts/check_deps.py`; `docs/SCOPE.md` listing what was kept, moved, deleted and why.

### Acceptance criterion (must be runnable)
```bash
python scripts/check_deps.py                                  # exits 0
git ls-files | grep -E 'catboost_info|raw_response_' ; test $? -eq 1   # no matches
git ls-files models/ | grep -c 'scaler'                       # 2
git cat-file -e legacy-pre-refactor:api_layer/live_predictor.py && echo preserved
make test                                                     # exits 0
```

---

## Stage 3 — Honest modeling and evaluation

**Goal:** find out whether a signal exists, with an evaluation that cannot flatter the model.

### Checklist
- [ ] Replace raw-level features (`SMA_7`, `MACD`, `Bollinger_*` are price levels, 10M–200M Rial) with stationary ones: returns, price-normalized indicators, realized volatility. The audit measured train→test shifts of SMA_7 +13.3σ, Bollinger_Upper +13.6σ, MACD +6.6σ.
- [ ] Implement walk-forward validation with a fixed, declared fold scheme (no shuffling, no leakage).
- [ ] Always report, side by side: **persistence** and **ridge** baselines, on the identical folds.
- [ ] Report log-return R² (not price-level R²), RMSE, MAE, directional accuracy **with a binomial test**, and **Diebold–Mariano** vs persistence.
- [ ] Report prediction dispersion (std, min, max) to expose near-constant output — the audit measured pred std 0.00057 vs actual 0.0275.
- [ ] Save machine-readable results to `reports/` and paste the console output into `docs/RESULTS.md`.

### Deliverables
`src/features_stationary.py` (or equivalent), `src/walkforward.py`, `scripts/run_eval.py`, `reports/eval_walkforward.json`, `docs/RESULTS.md`.

### Acceptance criterion (must be runnable)
```bash
make eval                     # exits 0
python scripts/check_eval.py  # exits 0: report has persistence + ridge + lstm rows,
                              # every row has dm_pvalue_vs_persistence and dir_acc_n,
                              # and no metric is reported at price level without the label "persistence baseline"
```

### GATE 3
**Owner reviews the results before any narrative is written.** If the edge is still zero, the plan continues as a negative result — but the owner confirms the framing first.

---

## Stage 4 — Honest backtest or replacement

**Goal:** either a defensible out-of-sample backtest, or a documented explanation of why no edge exists.

### If kept
- [ ] Out-of-sample only — trades start no earlier than the first walk-forward test date.
- [ ] Round-trip costs 1.5–3%, stated explicitly in the report (audit: current model is 0.7%/side with no spread).
- [ ] Benchmarks: buy-and-hold gold **and** buy-and-hold USD, always displayed next to the strategy.
- [ ] The strategy is labelled by what it actually trades on. If it is a momentum rule, it says "momentum", not "AI".

### If replaced
- [ ] `docs/NO_EDGE.md`: the evidence for why no edge exists, the cost hurdle required to overcome it, and what would have to be true for a signal to be plausible.

### Acceptance criterion (must be runnable)
```bash
make backtest                 # exits 0 (if kept)
python scripts/check_backtest.py
# asserts: start_date >= first OOS date; round_trip_cost between 0.015 and 0.03;
#          both benchmark keys present; no in-sample date range
```

---

## Stage 5 — Reproducibility and documentation

### Checklist
- [ ] `make train`, `make test`, `make api` work from a clean clone.
- [ ] Test suite green, including the 3 modules that fail collection today (`test_data_fetcher.py`, `test_live_predictor.py`, `test_live_signal_generator.py` — missing `yfinance` / import path).
- [ ] Minimal GitHub Actions workflow: install, lint, test.
- [ ] One-command Docker that actually builds (audit: current build did not finish in ~12 min; base image unpinned).
- [ ] Final `README.md`: measured numbers only, units in **Rial**, a "Findings / Negative Result" section and a "Lessons Learned" section.
- [ ] Delete the chat artifact at the current `README.md:600`.

### Deliverables
`Makefile`, `.github/workflows/ci.yml`, working `Dockerfile` + `docker-compose.yml`, final `README.md`, `docs/LESSONS.md`.

### Acceptance criterion (must be runnable)
```bash
make test && make train && make eval           # exits 0
docker build -t gold-portfolio .               # exits 0
python scripts/check_readme_numbers.py         # every number in README traces to a file in reports/
```

---

## Stage map

| Stage | Type | Gate |
|---|---|---|
| 0 | Docs only | none |
| 1 | Read-only investigation | **GATE 1** — fix data or document defect |
| 2 | Deletion / restructuring | none |
| 3 | Modeling + evaluation | **GATE 3** — review before narrative |
| 4 | Backtest or no-edge analysis | none |
| 5 | Repro + docs | none |
