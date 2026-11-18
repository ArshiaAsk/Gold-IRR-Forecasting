# Stage 6 review — fixes and verification

**Status:** committed before any Stage 6 review fix. **Branch:** `refactor/honest-portfolio`.
**Scope:** the independent review of Stage 6. All five must-fix items and all should-fix items
are in scope except the owner TODOs (license holder, author, contact, citation, TGJU permission).
No new evaluation or backtest run, no retraining, no merge, push or tag. `results/` stays
byte-identical.

| # | Review item | Action | Verification command |
|---|---|---|---|
| 1 | Sample vintage (must-fix 1) | Investigate the committed artifact's training vintage; record the cause in this file; state the sample source, date, rows and hashes in `data/sample/README.md`; add `docs/DATA_MANIFEST.md` (hashes and row counts only); pin the sample SHA-256 in a test; qualify the README "bit-identical" sentence | `sha256sum data/sample/gold_sample.csv`; `python -m pytest tests/test_sample_manifest.py -q`; `git diff --exit-code results/` |
| 2 | Alignment script (must-fix 2) | Commit `scripts/align_gold_ounce.py` with `--data` and `--live`; reproduce the four B2.2 correlations; replace every temporary-directory path reference in the docs | `python scripts/align_gold_ounce.py --live` (network); `grep -rn "tmp/s1\\|tmp/s1b\\|pytest-scratch" docs/ README.md --exclude=REVIEW_FIXES.md` (no output) |
| 3 | Wording (must-fix 4, 5 and should-fix) | Fix "no shorting except S3", "touched once", the Streamlit header, the "87 tests" count, the RESULTS/PLAN status headers, and the sample-README "not enough to evaluate" sentence | `grep -n "no shorting except\|touched once\|scored once\|87 tests\|not.*enough to train or evaluate" README.md docs/RESULTS.md streamlit_app.py data/sample/README.md` (no stale hits); `python scripts/check_readme_numbers.py` |
| 4 | D-1 share | Recompute the share from the artifact's validation predictions; state the denominator for 0.4982% and 0.86%; correct README; append an Errata entry to `docs/EVAL_PROTOCOL.md`; re-check the verdict | `python scripts/d1_share.py`; `grep -n "0.69\|0.4982\|0.86" README.md docs/EVAL_PROTOCOL.md` |
| 5 | Global-grid disclosure | Add `scripts/global_grid_audit.py` (read-only, no model runs); commit `docs/GLOBAL_GRID_AUDIT.md`; add the measured shares to README Limitations and the EVAL_PROTOCOL Errata; state that the effect is unmeasured and the sensitivity run is future work | `python scripts/global_grid_audit.py` (compare with `docs/GLOBAL_GRID_AUDIT.md`) |
| 6 | Pre-registration timing | Add one factual README Limitations sentence with the commit and first-fit timestamps and the reason for the amendment | `grep -n "18:02:01\|18:03:57" README.md`; `git log -1 --format=%cI cb75162`; `head -1 results/run.log` |
| 7 | Cleanup (nice-to-have) | Delete `TradingConfig` and other dead config; the unused pytest fixture; the stale mlflow/onnx/trading_bot ignore rules; the outdated "API/MLOps/training logs" docstring; make `src/utils.py` lazy; grep for removed components | `grep -rn "TradingConfig\|mock_prediction\|mlflow\|onnx\|trading_bot" --include='*.py' --include='*.md' --include='.gitignore' .` (only historical records); `python -m pytest -q` |
| 8 | Verify | Rebuild and run the Docker image; capture `/health`, a sample `/predict` with the CSV headers, and a 401; run `make check`; update `docs/README_CLAIMS.md` and `docs/STATE.md` | `make check`; `docker build -t gold-irr-honest-forecasting .`; `curl` commands in `docs/STATE.md` |

## Sample-vintage investigation

Investigated before changing anything, read-only.

**What the artifact was trained on.** `models/gold_lstm_stationary_v2.metadata.json` records
`git_commit: 8d7715e`, `date_utc: 2026-11-14T14:54:57+00:00`, training window 2021-08-28 →
2024-12-31 and validation window 2025-02-08 → 2025-09-30. `results/run.log` records the same run
starting at `2026-11-14 18:03:57,480` and the inputs: "Raw prices: 1424 rows
2021-06-14..2026-06-13; global series: 1265 rows 2021-06-04..2026-06-12". The two untracked
files are:

| File | Rows | mtime (download) | SHA-256 |
|---|---:|---|---|
| `data/raw/final_gold_dataset.csv` | 1,424 | 2026-06-14 13:34:33 +03:30 | `132992b8…76eb` |
| `data/raw/global_yahoo.csv` | 1,265 | 2026-11-14 18:01:19 +03:30 | `a9cc017a…855e` |

So the artifact saw a June-2026 Iranian snapshot plus a November-2026 Yahoo refresh. The full
manifest is `docs/DATA_MANIFEST.md`.

**Is the sample the tail of the training snapshot?** Two answers, and they differ:

* It is the **exact tail** of `data/raw/final_gold_dataset.csv`: all four columns of the last
  200 rows match (2025-10-14 → 2026-06-13).
* It is **not** the tail of the training frame built from that file plus `global_yahoo.csv`.
  `Gold_IRR`, `USD_IRR` and `Oil_USD` match on all 200 rows; `Ounce_USD` differs on **188 of
  200** rows, maximum absolute difference **35.5 USD**. The sample carries the source file's
  June-2026 ounce vintage; the training frame carries the November-2026 Yahoo vintage.

**The reviewer's three numbers, reproduced.**

| Observation | Sample as shipped | Refreshed global series | Difference |
|---|---:|---:|---:|
| `Ounce_USD` on 2026-06-13 | 4090.300048828125 | 4238.7998046875 | 148.499755859375 |
| Served `log_return` | −0.00045206130016595125 | −0.0004350765375420451 | +1.698476e−05 (3.76%) |
| `ounce_ret_lag1` on 2026-05-17 | 0.0 | −0.026690724101015917 | 0.0266907241 |

The refreshed prediction is reproduced exactly by replacing **only** the sample's `Ounce_USD`
column with the complete global series reindexed onto the sample dates with `ffill`; the oil
column is left as shipped. The 4238.80 value is the 2026-06-12 global bar, forward-filled to
the sample's last row 2026-06-13. The 2026-05-17 shift appears because the source CSV has no
2026-05-15 global bar (the sample's ounce is flat 2026-05-14 → 2026-05-17), while a refreshed
global pull does.

**Cause: a different global vintage (download date), not a TGJU revision and not a date shift.**
The Iranian columns are byte-identical; only the global ounce column differs. The sample was
cut on 2026-11-14 from a raw file downloaded 2026-06-14, whose Yahoo columns were already
merged and forward-filled onto the Iranian grid and therefore lack global bars on non-Iranian
dates (2026-05-15 and 2026-06-12). Stage 3 fetched a fresh global series on 2026-11-14 and
trained against it. The training frame itself is not the reviewer's refreshed frame: its
left-join + `ffill` drops the 2026-06-12 bar (not an Iranian date), so it uses 4114.0 on
2026-06-13, while a date-aligned refresh uses 4238.8. Both are later vintages than the sample.
Cause is determined; nothing here is UNKNOWN.

**Fix.** `data/sample/README.md` states the source, creation date, row range and both hashes,
and says the sample does not match the training vintage. `docs/DATA_MANIFEST.md` is a hash-only
manifest. `tests/test_sample_manifest.py` pins the sample SHA-256 (and the untracked hashes when
present). The README now qualifies the "bit-identical" sentence: it holds for the bundled
sample as shipped, and refreshing the ounce column changes the prediction to −0.0004350765.
The model artifact was **not** regenerated.


## D-1 recomputation

`scripts/d1_share.py` loads the committed seed-42 artifact and scalers, rebuilds the V2
validation sequences and runs one inference pass over the 173 rows. It writes nothing.

| Quantity | Formula | Value |
|---|---|---:|
| zero-prediction approximation (the 0.4982% figure) | `label² / Σy²` | 0.4982% |
| reviewer's "0.86" | `label² / mean(y²)` = `173 · label² / Σy²` | 86.19% |
| exact share of validation loss | `(y − ŷ)² / Σ(y − ŷ)²` | **0.6912%** |

The 0.4982% came from `label² / Σy²` over the 173 validation targets; the 0.86 figure is
`label² / mean(y²)`, which is 173× larger because the mean divides by 173. The reviewer's written
formula `label² / (173 · mean(y²))` is algebraically the first row (0.4982%); the "0.86" is
`label² / mean(y²)` with the 173 dropped, i.e. 0.8619 as a fraction (86.19%), not 0.86% of the
loss. The correct share is the third row, because early stopping minimises
`val_loss = (1/173) Σ(y − ŷ)²` and the label is one of the 173 terms.

The conclusion was re-checked, not assumed: 0.69% is still small, the only channel is epoch
selection, and the hold-out inputs are unchanged (R² +0.000119, DM p = 0.4984, 95% CI
[−0.0577, +0.0630]). This is the seed-42 share; the Stage 3 five-seed fits used the same label,
but their per-seed validation losses were not saved, so their exact shares are not recoverable.

## Global-grid disclosure

`scripts/global_grid_audit.py` rebuilds each variant's price frame with the committed code and
counts, for consecutive rows inside one segment, how often the later row reuses the earlier
Yahoo bar (a forward-filled zero return) and how often the two rows use bars more than one
trading day apart. No model is loaded and nothing is written.

| Variant | comparable | exactly zero (ffill) | span > 1 global day |
|---|---:|---:|---:|
| V1 | 1,363 | 488 (35.80%) | 260 (19.08%) |
| V2 | 1,363 | 491 (36.02%) | 258 (18.93%) |
| V3 | 858 | 309 (36.01%) | 163 (19.00%) |
| sample | 199 | 72 (36.18%) ounce, 73 (36.68%) oil | not measurable (different vintage) |

The effect on the results was **not measured**; no sensitivity run was performed. The README
Limitations bullet and Errata E-2 say so explicitly and make no claim about direction.

## Pre-registration timing

| Event | Timestamp | Source |
|---|---|---|
| Pre-registered protocol | 2026-11-14 17:59:11 +03:30 | `git log -1 --format=%cI 798981a` |
| Hold-out amendment (2025-10-01 cutoff) | 2026-11-14 18:02:01 +03:30 | `git log -1 --format=%cI cb75162` |
| First model fit | 2026-11-14 18:03:57,480 | `head -1 results/run.log` |

The amendment came 1 min 56 s before the first fit. Reason: the first draft said "the final 180
rows"; a data-shape check showed those begin 2025-11-05, which would skip October. The
2025-10-01 cutoff matches the requested period and gives 210 rows.

## Cleanup

* Deleted `TradingConfig` and `config.trading` (zero references), and
  `ModelConfig.get_optimizer_config` (zero references; its assertion in
  `tests/test_pipeline.py` was removed with it).
* Deleted `tests/conftest.py`: it only defined `pytest.mock_prediction`, which no test used.
* `.gitignore`: removed `*.onnx`, `mlruns/`, `mlflow/`, `mlflow.db` and `trading_bot/outputs/`.
  The generic `*.db` / `*.sqlite` rules remain under "Local databases".
* `config/logging.py`: the docstring no longer says "API/MLOps/training logs"; the function is
  used by the API and by the training logger.
* `src/utils.py`: the module-level logger is now a lazy proxy. Importing it no longer opens
  `logs/bot_YYYY-MM-DD.log`; the first log call resolves the same file + console handlers, so
  the CLI entry points behave as before. Verified: `import src.utils` creates no file;
  `logger.info(...)` creates one.
* Grep for removed components (`TradingConfig|config.trading|mock_prediction|mlflow|mlruns|
  onnx|MLOps|trading_bot`) finds **no code hits**. Remaining hits are historical prose:
  `README.md:358` (legacy tag), `docs/STATE.md` (stage logs and the audit inventory),
  `docs/DECISIONS.md` (D3, D26, D31), `docs/RESULTS.md` (the removed bot), and
  `docs/AUDIT_REPORT.md` (the pre-refactor audit).
