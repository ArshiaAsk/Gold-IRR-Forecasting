# Stage 6 review — fixes and verification

**Status:** committed before any Stage 6 review fix. **Branch:** `refactor/honest-portfolio`.
**Scope:** the independent review of Stage 6. All five must-fix items and all should-fix items
are in scope except the owner TODOs (license holder, author, contact, citation, TGJU permission).
No new evaluation or backtest run, no retraining, no merge, push or tag. `results/` stays
byte-identical.

| # | Review item | Action | Verification command |
|---|---|---|---|
| 1 | Sample vintage (must-fix 1) | Investigate the committed artifact's training vintage; record the cause in this file; state the sample source, date, rows and hashes in `data/sample/README.md`; add `docs/DATA_MANIFEST.md` (hashes and row counts only); pin the sample SHA-256 in a test; qualify the README "bit-identical" sentence | `sha256sum data/sample/gold_sample.csv`; `python -m pytest tests/test_sample_manifest.py -q`; `git diff --exit-code results/` |
| 2 | Alignment script (must-fix 2) | Commit `scripts/align_gold_ounce.py` with `--data` and `--live`; reproduce the four B2.2 correlations; replace every `/tmp` reference in the docs | `python scripts/align_gold_ounce.py --live` (network); `grep -rn "/tmp" docs/ README.md` (no output) |
| 3 | Wording (must-fix 4, 5 and should-fix) | Fix "no shorting except S3", "touched once", the Streamlit header, the "87 tests" count, the RESULTS/PLAN status headers, and the sample-README "not enough to evaluate" sentence | `grep -n "no shorting except\|touched once\|scored once\|87 tests\|not.*enough to train or evaluate" README.md docs/RESULTS.md streamlit_app.py data/sample/README.md` (no stale hits); `python scripts/check_readme_numbers.py` |
| 4 | D-1 share | Recompute the share from the artifact's validation predictions; state the denominator for 0.4982% and 0.86%; correct README; append an Errata entry to `docs/EVAL_PROTOCOL.md`; re-check the verdict | `python -m pytest tests/test_d1_share.py -q`; `grep -n "0.69\|0.4982\|0.86" README.md docs/EVAL_PROTOCOL.md` |
| 5 | Global-grid disclosure | Add `scripts/global_grid_audit.py` (read-only, no model runs); commit `docs/GLOBAL_GRID_AUDIT.md`; add the measured shares to README Limitations and the EVAL_PROTOCOL Errata; state that the effect is unmeasured and the sensitivity run is future work | `python scripts/global_grid_audit.py --check docs/GLOBAL_GRID_AUDIT.md` |
| 6 | Pre-registration timing | Add one factual README Limitations sentence with the commit and first-fit timestamps and the reason for the amendment | `grep -n "18:02:01\|18:03:57" README.md`; `git log -1 --format=%cI cb75162`; `head -1 results/run.log` |
| 7 | Cleanup (nice-to-have) | Delete `TradingConfig` and other dead config; the unused pytest fixture; the stale mlflow/onnx/trading_bot ignore rules; the outdated "API/MLOps/training logs" docstring; make `src/utils.py` lazy; grep for removed components | `grep -rn "TradingConfig\|mock_prediction\|mlflow\|onnx\|trading_bot" --include='*.py' --include='*.md' --include='.gitignore' .` (only historical records); `python -m pytest -q` |
| 8 | Verify | Rebuild and run the Docker image; capture `/health`, a sample `/predict` with the CSV headers, and a 401; run `make check`; update `docs/README_CLAIMS.md` and `docs/STATE.md` | `make check`; `docker build -t gold-irr-honest-forecasting .`; `curl` commands in `docs/STATE.md` |

## Sample-vintage investigation

Filled in by the sample-vintage commit (item 1). Until then this section is a placeholder, not
a finding.
