# Project State

**Date:** 2026-11-14
**Stage:** 1b complete — G1 resolution step. Read-only; no source, data or model file changed. **At GATE 1-final.**
**Branch:** `refactor/honest-portfolio`
**Baseline tag:** `legacy-pre-refactor` → `d1670cc` (annotated)
**Pre-refactor description:** `docs/AUDIT_REPORT.md` (2026-11-13)
**Stage 1 report:** `docs/DATA_INTEGRITY.md` (this is the authoritative data-quality document; "Stage 1b" is its last section)

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

## Next

**GATE 1-final — the owner decides between (a) applying the +1 window relabel and (b) documenting the block only.** No Stage 2 work starts until this is answered. Recommendation on the table: **(b)**, with a Stage 3 sensitivity analysis (train and evaluate with and without the 503 block rows). See `docs/DECISIONS.md` → G1-final and `docs/DATA_INTEGRITY.md` → "Stage 1b".

## Blockers

| ID | Decision | Blocks |
|---|---|---|
| **G1-final** | **Apply the +1 relabel, or document only** | **Stage 2 onward** |

O1–O8 are resolved (D10–D17). O3 and O4 do not block Stage 2.

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
| `signal_history.jsonl`: 7 records, **6 at ratio 100.0**, 1 at **10,000.0** | `api_layer/cache/signal_history.jsonl`; see D15 |

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
3. **`tests/` contains 6 live test modules, not 8.** The audit counts 8 "test modules"; the directory holds 6 `test_*.py` files plus `conftest.py` and `__init__.py`. The 2 missing modules exist only as bytecode, which is what the audit meant. Minor wording, no impact.
4. **Committed backtest metrics and the committed portfolio log disagree.** `backtest_metrics.json` says 2021-01-27 → 2025-12-20 / 1,384 days; `portfolio_log.csv` runs 2021-07-19 → 2026-06-11 / 1,394 rows. Confirmed here. The log matches the audit's *fresh* run (−14.06%, final 859.4M), so the JSON is the stale artifact.
5. **The audit's weekday table is mislabelled.** It prints `Fri 237 · Sat 236 · Sun 241 · Mon 243 · Tue 240 · Wed 137 · Thu 90`. The real mapping is `Sat 237 · Sun 236 · Mon 241 · Tue 243 · Wed 240 · Thu 137 · Fri 90` — the same counts, rotated by one weekday. Reproduced exactly by an off-by-one label list. The audit's central data-quality finding was an artefact of its own analysis. See `docs/DATA_INTEGRITY.md` §5.
6. **The audit missed the 2023-10 → 2025-08 block** — a 36% sub-period with a different weekly shape, present identically in both source series. See `docs/DATA_INTEGRITY.md` §7.
7. **Stage 1 overstated the Jalali field's evidential value.** §6 correctly used `Date_J → Date_G` agreement to refute a conversion bug, but the agreement also means the field cannot detect a date that is wrong in both columns. Stage 1b extends the check to 11,331 records and concludes the field is not an independent witness. Nothing in §6 is wrong; the implication that it could confirm the block is.
8. **Stage 1's block-alignment test was weaker than it looked.** §7.2 reported the block peaking at lag −1 (+0.231) only slightly ahead of lag 0 (+0.164). That test let the matched row set change between shifts. Stage 1b holds the row set fixed and gets +0.112 → +0.380, with the post-block going +0.358 → −0.126. The Stage 1b result supersedes §7.2 as the alignment evidence; §7.2 is left as written.

No contradiction was found in the audit's dependency claims, its `.env` finding, its "no CI" finding, its account of the loader/merge/ffill, or its README-quote evidence.

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

# Re-derive the weekday table (the audit's version is mislabelled)
.venv/bin/python -c "import pandas as pd; d=pd.read_csv('data/raw/final_gold_dataset.csv',index_col='Date',parse_dates=True); print(d.index.day_name().value_counts())"
```

There is **no working test command yet**: `pytest` is not installed in `.venv`, `Makefile` does not exist, and 3 of the 6 test modules fail collection. `make test` is a Stage 2 deliverable, not a current capability. Do not document it as one.
