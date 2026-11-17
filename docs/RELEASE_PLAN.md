# Stage 5b — Release Plan

**Status:** committed before any Stage 5b change · **Branch:** `refactor/honest-portfolio`
**Gate:** STOP at GATE 5b. No merge, no push, no release tag.
**Frozen inputs:** `results/`, `models/`, `docs/EVAL_PROTOCOL.md`, `docs/BACKTEST_PROTOCOL.md`.
No retraining, no re-scoring, no new seeds.

This file is the contract for Stage 5b. It is committed first; the work below follows it.

## GATE 5a decisions carried in

| Topic | Decision |
|---|---|
| Primary deliverable | The Docker image. The hosted Streamlit Community Cloud app is best-effort. |
| Runtime TF | Measure `tensorflow-cpu` as the runtime dependency. If it serves and installs plausibly within the official limits, use it. If not, stop and ask the owner. |
| README | English. Title: *Forecasting Iranian Gold (IRR): an end-to-end pipeline and an honest negative result*. |
| Repo name | `gold-irr-honest-forecasting` — used in docs only; nothing is renamed. |
| License | MIT for the code; data explicitly excluded. |
| Merge | Owner merges after review, no squash. |

## Deliverables and acceptance commands

| # | Deliverable | Acceptance command (must exit 0) |
|---|---|---|
| 1 | `tests/test_pipeline.py` moved from the repo root; one command runs the whole suite | `python -m pytest -q` → **79 passed** |
| 2 | `requirements.txt` (runtime) / `requirements-dev.txt` (dev) split; Python 3.12 stated | `python -m pip install -r requirements-dev.txt` in a clean venv |
| 3 | `Makefile` with `install test check evaluate backtest api app docker-build docker-run fetch-data` | `make -n check` and `make check` |
| 4 | Opt-in `--save-predictions` on `src/evaluate.py` | scratch run under `/tmp`; `tests/test_predictions_export.py` |
| 5 | Single-service `Dockerfile` (API + Streamlit, non-root, healthcheck, no raw data) | `docker build -t gold-irr .`; `docker run`; `curl /health`; `POST /predict` |
| 6 | `.github/workflows/ci.yml` on push/PR | YAML parses; every step command run locally in order |
| 7 | `LICENSE` (MIT, data excluded), `.gitignore`, notebooks banner, stale-artifact cleanup | `git ls-files`; grep for secrets/absolute paths |
| 8 | Final `README.md` + `docs/README_CLAIMS.md` + README-numbers test | `python scripts/check_readme_numbers.py`; `make check` |
| 9 | `docs/PLAN.md`, `docs/STATE.md`, `docs/DECISIONS.md` updated with evidence | files read |

## README outline (fixed order)

1. **Title + TL;DR.** The finding first: a complete pipeline (data → stationary features →
   LSTM → API/Streamlit) and a pre-registered evaluation that found **no demonstrated
   predictive edge** for next-day gold returns in Rial; economically, **no added value over
   buy-and-hold**, and nominal gains are mostly rial devaluation. No marketing language.
2. **Headline results.** One small table: walk-forward and hold-out, V2, LSTM vs persistence vs
   historical mean (RMSE, R², DM p, bootstrap CI); the economic table at 0% and 0.75%/side;
   gold in IRR vs USD. Every number is a marked block checked against `results/*.json`.
3. **How to read the results.** Benchmark, walk-forward, hold-out, DM test, bootstrap CI, why
   the historical mean looked significant in walk-forward and not on the hold-out (nominal
   drift), and the break-even cost analysis. Plain language, no formulas beyond one line.
4. **What is in the repo.** Short tree (one line per folder), quickstart (install, test, API,
   app, Docker), API reference (3 endpoints, a real request/response produced by running it,
   min 89 rows, Rial units, the 422 for the block and why, no confidence interval and why).
5. **Data.** TGJU `geram18` in Rial, Yahoo `GC=F`/`BZ=F`; the date-shift defect and the
   reversible relabel with the alignment evidence in one paragraph; the 200-row sample; full
   data not redistributed pending permission; scrapers may break.
6. **Limitations and honesty.** Required: touch count (six passes, three scored, "touched
   once" not literally met, no scored pass re-run); one-label validation/hold-out overlap D-1
   and its direction; ~210 hold-out rows in a trending nominal series (low power); seed-42 is
   the served artifact and 5-seed backtests were not recoverable; EMA warm-up caveat in
   serving; no inflation series (gold in USD is a proxy); the legacy README's fabricated
   numbers are **not** carried over; the legacy tag exists and why.
7. **Lessons learned.** 6–10 bullets, each tied to something that happened here.
8. **License, data terms, citation/contact placeholders** as clearly marked `TODO`.
9. **Length.** Under ~400 lines; no badge wall; no emojis.

## Number-marking convention

Numbers that must not drift are wrapped in HTML comments:

```text
<!-- num:eval_V2.holdout.lstm_stationary.rmse -->0.026543<!-- /num -->
<!-- num:pct:backtest.strategies.C2.S2.total_return -->+1.13%<!-- /num -->
```

* `num:<file>.<dotted.path>` reads `results/<file>.json`.
* Optional transform before the file: `pct` (×100), `pct4` (×100, 4 dp), `bp` (×10 000),
  `int` (exact integer).
* Tolerance is the rounding bound of the printed text (half a unit in the last printed digit).
* A key that does not resolve fails the check. Prose outside marked blocks is covered by
  `docs/README_CLAIMS.md`, not by the automated check.

## Implementation order

1. Commit this plan.
2. Test move + `pytest.ini` coverage + the 44-vs-30 clarification.
3. Dependency split; measure the clean-venv runtime install, import time and peak RSS.
4. Makefile + `scripts/fetch_data.py` + `scripts/check_readme_numbers.py`.
5. `--save-predictions` + scratch smoke run + unit test.
6. Docker build/run evidence; remove the HF Space port config; compose decision.
7. CI workflow; YAML parse; local replay of its commands.
8. Repo hygiene (LICENSE, .gitignore, notebooks, stale artifacts).
9. README + README_CLAIMS + numbers test.
10. Docs (PLAN/STATE/DECISIONS) and final evidence.

## Stop conditions

* `tensorflow-cpu` cannot serve the artifact or install size is implausible → **stop and ask**
  before choosing any fallback.
* The Docker daemon or registry is unreachable → report exactly what failed and what was
  verified instead; never claim a build that did not happen.
* Any number that cannot be traced to `results/*.json`, a command output, or a committed file
  is removed from the README, not softened into vagueness.
