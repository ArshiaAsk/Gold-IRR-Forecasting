# Project State

**Date:** 2026-11-14
**Stage:** 0 complete — documentation baseline. No source code has been changed.
**Branch:** `refactor/honest-portfolio`
**Baseline tag:** `legacy-pre-refactor` → `d1670cc` (annotated)
**Pre-refactor description:** `docs/AUDIT_REPORT.md` (2026-11-13)

---

## Done

- Read `docs/AUDIT_REPORT.md` in full (512 lines). It is the only trustworthy description of the pre-refactor state; the current `README.md` is not.
- Confirmed the working tree had uncommitted changes before starting (`.gitignore` modified, `docs/` untracked) and asked the owner how to proceed. Owner chose: tag `d1670cc` exactly as-is and carry both items into Stage 0.
- Created annotated tag `legacy-pre-refactor` at `d1670cc` and branch `refactor/honest-portfolio`.
- Wrote `docs/PLAN.md` (Stages 1–5, checklist, deliverables, runnable acceptance criteria, two gates).
- Wrote `docs/DECISIONS.md` (D1–D6 accepted, O1–O8 open).
- Wrote this file.
- Committed `docs/AUDIT_REPORT.md` plus the three new docs; committed the `.gitignore` change separately.

## Next

**Stage 1 — data integrity investigation (read-only).** Blocked on nothing except the owner saying go; see `docs/PLAN.md`. GATE 1 is the owner's decision on whether to fix the data.

## Blockers

| ID | Decision | Blocks |
|---|---|---|
| O1 | Rial vs Toman labeling | Stage 3, Stage 5 |
| O2 | Is `geram18` the intended product | Stage 3 |
| O3 | Keep a minimal API at all | Stage 2 |
| O4 | Target role emphasis (ML / MLOps / backend-data) | Stage 5 framing |
| O5 | TGJU data redistribution permission | Stage 5 |
| O6 | Provenance of `signal_history.jsonl` | nothing (credibility only) |
| O7 | Rationale for raw price-level features | Stage 3 narrative |
| O8 | Real deployment target (HF Spaces vs compose) | Stage 5 |

O3 and O4 do not block Stage 1. Stage 1 can start immediately.

---

## Verified environment facts

Everything below was produced by a command in this session. Nothing here is copied from the README.

| Fact | How verified |
|---|---|
| Interpreter is Python 3.12.3 at `.venv/bin/python` | `.venv/bin/python -V` |
| `pytest` is **not installed** in `.venv` | `.venv/bin/python -c "import pytest"` → `ModuleNotFoundError` |
| `yfinance` is **not installed** in `.venv` | `.venv/bin/python -c "import yfinance"` → `ModuleNotFoundError` |
| Raw dataset has **1,424** data rows | `wc -l data/raw/final_gold_dataset.csv` → 1,425 incl. header |
| Processed dataset has **1,394** data rows | `wc -l data/processed/advanced_gold_features.csv` → 1,395 incl. header |
| Repository has **129** commits | `git rev-list --count HEAD` |
| `.env` exists, is untracked, and is ignored at `.gitignore:28` | `git ls-files .env` (empty), `git check-ignore -v .env` |
| `.github/` does not exist (no CI) | `ls -d .github` |
| `Makefile` does not exist | `ls Makefile` |
| `scripts/` does not exist | `ls -d scripts` |
| `docs/` contained only `AUDIT_REPORT.md` before Stage 0 | `ls docs` |
| `docker-compose.yml` defines exactly **one** service, `ml-stack` | `grep -n "^  [a-z]" docker-compose.yml` |
| Model file is tracked; both scalers are **not** | `git ls-files models/` → only `models/gold_lstm_v2.keras`; `models/scaler_X.pkl` and `scaler_y.pkl` exist on disk |
| `logs/test_metrics.json` reports price R² 0.9716991951320707, RMSE 4,840,916.90, MAE 2,883,359.74, MAPE 1.7017, log-return RMSE 0.0275036 — and **no** log-return R² field | `cat logs/test_metrics.json` |
| `trading_bot/outputs/backtest_metrics.json` reports −12.034% return, Sharpe −7.361, max drawdown 15.105%, 30 trades, 40% win rate, benchmark +1,184.94%, period 2021-01-27 → 2025-12-20 (1,384 days) | `cat trading_bot/outputs/backtest_metrics.json` |
| `trading_bot/outputs/portfolio_log.csv` covers 2021-07-19 → 2026-06-11 (1,394 rows) and ends at 859,421,876.91 IRR — i.e. it does **not** match the committed metrics file's period | `head`/`tail`/`wc -l` on the CSV |
| `README.md:600` contains a leftover AI-chat sentence | `sed -n '598,602p' README.md` |
| Undeclared third-party imports exist: `yfinance` (2 files), `curl_cffi` (2), `pytest` (2), `requests` (5, declared only as a commented line) | `grep -rl` per module |
| `python-dotenv` is imported nowhere (0 files) | `grep -rl "import dotenv"` |

## Not verified in this session

Stated plainly so nobody mistakes these for measured facts:

- The weekday distribution (`Mon 243 · Tue 240 · Wed 137 · Thu 90 · Fri 237 · Sat 236 · Sun 241`) is **audit-reported**, not re-derived. Stage 1 reproduces it with `scripts/audit_calendar.py`.
- Model architecture (64→32→16, 33,441 params), the log-return R² of −0.0016, the Diebold–Mariano result and the live-bot scale bug are **audit-reported**. Stage 3 re-derives the first two.
- `python -m unittest test_pipeline` reportedly runs 14 tests successfully (audit §5.6). Not re-run here.
- The backtest has not been re-executed; only the committed JSON was read.

---

## Contradictions found between the audit and the repo

1. **`.agents/` documentation does not exist.** A prior session's memory asserted that `.agents/STATE.md`, `ROADMAP.md`, `CONVENTIONS.md`, `DECISIONS.md`, `LOG.md` and a root `CLAUDE.md` were created at `d1670cc`. They are absent from the working tree and from all git history (`git log --all -- .agents` → empty). The audit was right; the memory was stale and has been corrected.
2. **`docs/` is no longer empty.** The audit describes it as `EMPTY`, which was accurate when written; it now contains `AUDIT_REPORT.md`. This is a timing difference, not an error — but it does mean the audit's tree diagram is already one step behind.
3. **`tests/` contains 6 live test modules, not 8.** The audit counts 8 "test modules"; the directory holds 6 `test_*.py` files plus `conftest.py` and `__init__.py`. The 2 missing modules exist only as bytecode (`test_baselines.cpython-312-pytest-7.4.4.pyc`, `test_no_leakage.cpython-312-pytest-7.4.4.pyc`), which is what the audit meant. Minor wording, no impact.
4. **Committed backtest metrics and the committed portfolio log disagree.** `backtest_metrics.json` says 2021-01-27 → 2025-12-20 / 1,384 days; `portfolio_log.csv` runs 2021-07-19 → 2026-06-11 / 1,394 rows. The audit flags this (§3.3); confirmed here. The log matches the audit's *fresh* run (−14.06%, final 859.4M), so the JSON is the stale artifact.

No contradiction was found in the audit's dependency claims, its `.env` finding, its "no CI" finding, or its README-quote evidence.

---

## How to run (verified commands only)

```bash
# Interpreter used by this project
.venv/bin/python -V                       # Python 3.12.3

# Inspect the frozen pre-refactor state
git show legacy-pre-refactor:README.md
git ls-tree -r --name-only legacy-pre-refactor | head

# Re-derive the row counts
wc -l data/raw/final_gold_dataset.csv data/processed/advanced_gold_features.csv
```

There is **no working test command yet**: `pytest` is not installed in `.venv`, `Makefile` does not exist, and 3 of the 6 test modules fail collection. `make test` is a Stage 2 deliverable, not a current capability. Do not document it as one.
