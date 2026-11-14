# Decisions Log

ADR-lite. One entry per decision that changes what gets built. Status values: `accepted`, `proposed`, `open`, `superseded`.

Newest decisions are appended, not reordered. If a decision is reversed, mark it `superseded` and link the replacement — do not delete the history.

---

## D1 — Direction is "B-lite": honest negative result, not a trading product

**Date:** 2026-11-14 · **Status:** accepted

Keep the parts that genuinely work (data loader, feature engineering, training, evaluation, a simple API) and rebuild the evaluation honestly. Quarantine or delete the live bot, the backtest engine, the MLOps theatre and the fabricated confidence interval. Tell the story as a rigorous negative result with lessons learned.

**Context:** the audit found a working pipeline around a model with log-return R² ≈ −0.0016, near-constant predictions, a backtest that does not use the model, and a README that contradicts its own artifacts. Option B (full refactor) was chosen over A (archive as-is), C (pivot to a data product) and D (abandon).

**Consequences:** the portfolio value comes from evaluation discipline, not from the model. Success is measured by whether a senior reviewer can verify every claim in under ten minutes.

---

## D2 — No number enters a document unless it was measured or read

**Date:** 2026-11-14 · **Status:** accepted

Every figure in `README.md`, `docs/*` and any summary must be reproducible by a command in this repo, or read directly from a committed artifact, and the source must be named.

**Context:** the audit's README verification table (32 claims) found the majority contradicted by artifacts — dataset size, date range, architecture, splits, losses, metrics, backtest results, API contract. Several were arithmetically impossible (97/156 stated as 62.5%).

**Consequences:** unverifiable numbers are omitted rather than estimated. Where a figure is quoted from the audit before being re-derived, it is labelled "audit-reported, not re-verified".

---

## D3 — Legacy state is preserved by tag, not by keeping the code in place

**Date:** 2026-11-14 · **Status:** accepted

Annotated tag `legacy-pre-refactor` points at `d1670cc`. All refactor work happens on branch `refactor/honest-portfolio`. Anything deleted in Stage 2 must still be reachable from the tag.

**Context:** the working rule is that nothing is deleted before it is preserved. The repository has 129 commits on a single branch `main` with no tags.

**Consequences:** deletion is reversible by `git checkout legacy-pre-refactor -- <path>`. `main` is not touched by the refactor until the branch is reviewed.

---

## D4 — Stage 0 commits documentation only

**Date:** 2026-11-14 · **Status:** accepted

Stage 0 adds `docs/PLAN.md`, `docs/DECISIONS.md`, `docs/STATE.md` and commits the existing `docs/AUDIT_REPORT.md`. No source, config or data file is modified.

**Consequences:** the first code change happens in Stage 2. Stage 1 is read-only by design.

---

## D5 — `docs/` becomes tracked

**Date:** 2026-11-14 · **Status:** accepted (executed in Stage 0)

`.gitignore` previously contained `docs/*`, which made it impossible to commit the audit or the plan. That rule is removed, and `.venv/` is added so the virtualenv stays untracked.

**Context:** the audit report itself notes `docs/ EMPTY`, which was true only because nothing could be committed there.

**Consequences:** documentation is versioned from now on. `.venv/` was previously untracked only by accident of not being listed.

---

## D6 — The audit is the baseline; contradictions are escalated

**Date:** 2026-11-14 · **Status:** accepted

`docs/AUDIT_REPORT.md` is the reference description of the pre-refactor state. If the code disagrees with it, the disagreement is reported to the owner and recorded here — the audit is not silently "corrected" and the code is not silently trusted.

**Context:** a prior session's memory claimed a `.agents/` documentation set and a root `CLAUDE.md` existed at `d1670cc`. They do not: `.agents/` is absent and `git log --all -- .agents` returns nothing. The audit's statement that they were absent was correct; the memory was wrong and has been corrected.

**Consequences:** every stage report ends with a "contradictions" section, even when it is empty.

---

## D7 — The date axis is not uniformly shifted; the audit's weekday table is wrong

**Date:** 2026-11-14 · **Status:** accepted

The Iranian series is **not** dated one day early. Both TGJU series concentrate on Saturday–Wednesday (84–89%) on their own axes, before any merge. The audit's `Fri 237 · Sat 236 · Sun 241 · Mon 243 · Tue 240 · Wed 137 · Thu 90` is the correct multiset with labels rotated by one weekday; it is reproduced exactly by pairing `dayofweek` (0 = Monday) with a label list starting at `Sunday`.

**Context:** the Stage 0 plan and `docs/STATE.md` treated the weekday distribution as an open, load-bearing anomaly and listed "one-day label shift" as the leading hypothesis. It is neither.

**Consequences:** `docs/DATA_INTEGRITY.md` replaces the audit's weekday finding as the authoritative statement. `docs/AUDIT_REPORT.md` is left unedited (D6) but must not be quoted on this point. No uniform re-dating is permitted — shifting the series by −1 destroys the contemporaneous correlation with global gold (+0.165 → −0.049) and improves no baseline.

---

## D8 — Stage 1 identifies a 21-month sub-period defect but does not fix it

**Date:** 2026-11-14 · **Status:** accepted

A contiguous block, 2023-10-27 → 2025-08-06 (503 rows, 36.1% of the modelled frame, entirely inside train+val), has Thursday rows at exactly zero and Friday rows at 3–5 per month, in both Iranian series with identical boundaries. It is consistent with a one-day-early label but the mechanism is **inferred**, not proven.

**Context:** no independent source for individual dates inside the block was available, and the alternative explanation — a change in TGJU's publishing schedule rather than its date arithmetic — would make a date fix actively harmful.

**Consequences:** the block is documented in `docs/DATA_INTEGRITY.md` §7 and §13 with an explicit risk table. Applying a fix is GATE 1's decision (see below). Until it is answered, Stage 2 does not start and no data file is touched.

---

## D9 — Stage 1 commits documentation only; the audit script is deferred

**Date:** 2026-11-14 · **Status:** accepted

`docs/PLAN.md:48` lists `scripts/audit_calendar.py` as a Stage 1 deliverable. The owner's Stage 1 instruction restricted new files to `docs/DATA_INTEGRITY.md` plus `STATE.md`/`DECISIONS.md`, so no script was committed. All experiments ran in `/tmp/s1`.

**Context:** Stage 1 is read-only by design (D4); a committed script would have been the only executable artifact in a stage whose purpose is evidence, not tooling.

**Consequences:** every figure in `docs/DATA_INTEGRITY.md` was produced by a command run in this session, and the commands are inlined in the document. If a runnable audit script is wanted, it belongs in Stage 2 alongside the rest of `scripts/`.

---

## D10 — Currency stays Rial; every label says IRR

**Date:** 2026-11-14 · **Status:** accepted (was O1)

The series is stored and modelled in Rial. Nothing is converted. Every axis label, metric, README line and API description says **IRR**, never Toman.

**Context:** §10 of `docs/DATA_INTEGRITY.md` verifies the values are Rial (gold/USD/ounce identity holds to a 1.010 median). Every "Toman" label in the current code and README understates the unit by 10×.

**Consequences:** presentation-layer conversion to Toman is rejected — it would create a second unit to reason about for no benefit. The 1B-IRR starting capital is quoted as ≈ $555 at the end-of-sample rate, and the unit is stated next to it. Any remaining "Toman" string is a defect to be fixed in Stage 2.

---

## D11 — `geram18` is the intended product

**Date:** 2026-11-14 · **Status:** accepted (was O2)

The target series is the 18-karat gram price of gold in Rial (`geram18`), with `price_dollar_rl` (USD/IRR) as the second Iranian series. Not a coin (`sekeb`, `emami`), not the ounce.

**Context:** the whole pipeline, the config (`config/settings.py:49`) and the gold/USD/ounce identity all point at `geram18`. A coin series would change both the economics and the narrative.

**Consequences:** the README describes the product as "18k gold, Rial per gram". The 0.75 factor in the ounce identity is explained as the 18k/24k ratio rather than left implicit.

---

## D12 — Keep a minimal API; Streamlit is only the UI

**Date:** 2026-11-14 · **Status:** accepted (was O3)

Keep exactly three endpoints: `/health`, `/model-info`, `/predict`. Streamlit is a presentation layer that calls the same model code, not a parallel serving path.

**Context:** the old repo had an API, a Streamlit app, a live bot and a supervisor all reaching the model by different routes, which is how the live path acquired its own unit and scale bugs.

**Consequences:** the API surface is small enough to test exhaustively. Everything not needed by those three endpoints is out of scope for Stage 2.

---

## D13 — Target role is ML Engineer

**Date:** 2026-11-14 · **Status:** accepted (was O4)

The portfolio is aimed at **ML Engineer** roles. Stage 5 gives depth to honest evaluation, reproducibility and documentation. MLOps stays minimal: a working Docker image and a reproducible run, no registry, no tracking server, no orchestration.

**Context:** the repo's existing MLOps layer never completed a cycle (empty registry, zero audit rows, zero MLflow runs, broken ONNX export). Depth there would advertise something that does not work.

**Consequences:** evaluation discipline is the headline. CI, experiment tracking and deployment automation are explicitly out of scope and are not mentioned as capabilities.

---

## D14 — No raw data in the repo; fetch script plus a small sample

**Date:** 2026-11-14 · **Status:** accepted (was O5)

Do not commit the raw TGJU series. Commit a fetch script and a documented schema, plus a sample of roughly the last 200 rows so the repo runs offline. No full-data redistribution until TGJU permission is confirmed.

**Context:** the source is a single commercial publisher with no stated redistribution licence. The current repo commits 1,424 merged rows and a 3,775-record raw response.

**Consequences:** the committed CSVs are removed in Stage 2. Every result in the README must be reproducible from the fetch script, and the README states plainly that the full data is not redistributed. The 200-row sample is enough to exercise the pipeline, not enough to be a substitute for the source.

---

## D15 — `signal_history.jsonl` was not hand-edited; one record carries a double-scaling bug

**Date:** 2026-11-14 · **Status:** accepted (was O6) · **Verified in Stage 1b**

The author does not recall editing the file. The 442.95 vs 0.0443 mismatch is a **unit-conversion bug in one record**, not an edit.

**Evidence (Stage 1b):** the file has 7 records. Six have `predicted_return_pct / predicted_log_return` exactly 100.0. Only the first (2026-02-08T14:27) has 10,000.0. That value is the float32 result of multiplying the log return by 100 twice: `442.9512939…` versus the recorded `442.9512978` — a relative difference of 8.6e-9, i.e. float32 precision. The same record's own `reasoning` string says "Predicted return 4.43%", computed with a single ×100. The current writer (`api_layer/live_predictor.py:260`) applies ×100 once.

**Consequences:** the record is a genuine artefact of an earlier double-scaling code path, not fabricated data, so the file may be cited — but only with that record excluded or annotated. It is not evidence of a systematic unit bug: 6 of 7 records are correct.

---

## D16 — Raw price-level features are an unexplained defect, documented as a lesson

**Date:** 2026-11-14 · **Status:** accepted (was O7)

The author does not know why `SMA_7`, `MACD` and `Bollinger_*` were passed to the model as absolute Rial levels instead of being normalized. There is no deliberate rationale to reconstruct.

**Context:** this is the single largest modelling defect and the audit's most likely explanation for the train→test distribution shift. Ridge on these features emits `LinAlgWarning: ill-conditioned matrix (rcond ≈ 3e-18)` (reproduced in Stage 1, §9.2).

**Consequences:** Stage 3 normalizes them. "Lessons Learned" states plainly that the choice was a mistake with no justification — the honesty is the point of the piece.

---

## D17 — Deployment target: light Streamlit app plus a simple Docker image

**Date:** 2026-11-14 · **Status:** accepted (was O8)

Ship a light Streamlit app and a single simple Docker image. Primary host is Streamlit Community Cloud.

**Context:** Community Cloud may not be able to reach TGJU. The README's four-service compose stack does not exist; `docker-compose.yml` has one service.

**Consequences:** the hosted app must work from the **bundled sample plus the saved model**, with no network dependency at runtime. The fetch script is for local refresh only. The compose file is reduced to what actually exists.

---

## D18 — G1 resolution step: option (c), two internal sources, one step

**Date:** 2026-11-14 · **Status:** accepted · **Executed in Stage 1b**

Resolve the 2023-10-27 → 2025-08-06 block before choosing between fixing it and documenting it, using two sources that already exist inside the project rather than an external archive:

1. **The Jalali date field** in the raw TGJU response, which `src/data_loader.py:70` discards. Convert with a verified converter and compare against the Gregorian date the code used, inside and outside the block.
2. **Alignment tests** restricted to the block, in a scratch copy: gold↔ounce and USD↔ounce contemporaneous correlation under 0/+1-day relabelling, the `Gold_IRR ≈ 0.75·Ounce/31.1035·USD_IRR` identity under the same shifts inside vs outside the block, and a fixed-holiday price-change check.

**Context:** Stage 1 could only show that the block *looks* like a one-day-early label. The competing explanation — a change in TGJU's publishing schedule rather than its date arithmetic — would make a date fix actively harmful.

**Consequences:** the decision rule was fixed in advance. If the Jalali-derived dates *and* the alignment tests both indicate one day early, fix by using the Jalali-derived dates for the whole series; otherwise document the block as a known limitation and add a sensitivity analysis to Stage 3. Result: see `docs/DATA_INTEGRITY.md` "Stage 1b". The final G1 call is the owner's.

---

## D19 — G1-final: apply the +1 relabel as a reversible loader transform

**Date:** 2026-11-14 · **Status:** accepted · **Executed in Stage 2a**

The 2023-10-27 → 2025-08-06 block is corrected at load time. Rows whose date falls in the window are relabelled **+1 day**, per Iranian series, before the gold/USD merge. The window and an enable flag live in `config/settings.py`; the transform is logged on every run; no raw data file is edited. Setting `DATE_SHIFT_ENABLED = False` restores the raw behaviour exactly.

**Rationale (owner's G1-final call).**

- **The Jalali field cannot witness the defect.** TGJU emits `Date_G` and `Date_J` from a single record, so both are one day early together and the offset stays 0 in all 11,331 records. Its silence is uninformative, not exculpatory — it was never a second witness.
- **The alignment test is the independent evidence.** On an identical row set, the block's same-day correlation with `GC=F` goes **+0.1119 → +0.3803** under +1, matching the clean post-block level **+0.3577**; the same shift destroys the clean period (**+0.3577 → −0.1262**). A transform that restores the block to the clean level and ruins the clean period is measuring alignment and nothing else.
- **The block's Friday rows carry the weekend move** (median |return| 1.179%, zero-change share 0.00). A market closed on Friday cannot produce a Friday row with a return; a one-day-early label can.

**Consequences.**

- The residual risk is unchanged and is recorded: the mechanism is inferred from alignment, not observed at the source (no external archive of an individual date inside the block).
- **Stage 3 evaluates three variants** — raw, corrected, block excluded — as a sensitivity analysis, on identical folds. **The README must report all three**, not just the corrected one.
- The correction is a constant in one function. Reversing it is a config flag, not a data migration.
- Stage 1b's recommendation was (b) document-only. This decision overrides the recommendation, not the evidence; the evidence supports (a) as a defensible engineering call (see "Stage 1b" B3/B5).

---

## D20 — Stage 2b deletion boundary and the one kept-code dependency

**Date:** 2026-11-14 · **Status:** accepted · **Executed in Stage 2b**

Delete the live bot, the MLOps layer, monitoring, supervisor/startup scripts, examples, generated outputs and the tests that exercised them. Keep `trading_bot/` until Stage 4, `streamlit_app.py`, `notebooks/` (without `catboost_info/`) and the minimal API. No `legacy/` folder: the tag is the archive (D3).

**Context:** before each deletion group, kept code was grepped for imports. The only kept module importing deleted code was `streamlit_app.py`, whose `try/except` imported `api_layer.live_predictor` and `api_layer.live_feature_engineering`. Its `load_predictor()` already could not construct `GoldPricePredictor()` (required arguments were never passed), so the two imports were dead weight; they were removed and the guarded import reduced to the kept `src/api/predictor.py`. `src/api/main.py` was the only kept module importing `src.mlops`, and it was rewritten. `src/monitoring/` and `monitoring/` were imported by nothing.

**Consequences:** 75 tracked paths removed, all reachable at `legacy-pre-refactor`. `streamlit_app.py` still has no working local predictor path — that is a Stage 5 concern, not a regression introduced here. Model scalers remain untracked until Stage 3 regenerates them with the model.

---

## D21 — Stage 3 protocol is pre-registered before any model fit

**Date:** 2026-11-14 · **Status:** accepted · **Executed in Stage 3**

`docs/EVAL_PROTOCOL.md` was written and committed (`798981a`) before `results/` existed or any
model was fit. It fixes the task, information timing, the 23-feature set, the three variants,
five expanding folds with purge/embargo, six models, the metrics, the edge rule and the cost
sanity check.

**Pre-run amendment (`cb75162`).** The first draft said "the final 180 rows". A data-shape check
showed those begin 2025-11-05 and would skip October; the hold-out is instead all rows dated
2025-10-01 or later (210 rows), matching the requested "~180 rows, 2025-10 onward". The amendment
was made **before any model fit**. No post-run deviations.

**Consequences:** the edge rule is not renegotiated after seeing results. V1/V3 and the
legacy-spec LSTM are explicitly not eligible for the headline verdict.

---

## D22 — Stationary feature set is frozen; no hyperparameter search

**Date:** 2026-11-14 · **Status:** accepted · **Executed in Stage 3**

The 23 stationary features in `src/feature_eng.py::add_stationary_features` are the single source
of truth for training and serving: gold-return lags 1/2/3/5; USD-return lags 0/1/2/5 (same-day USD
is allowed because the TGJU USD close is available with the gold close); ounce-return lags 1/2/5
(global bars lagged one trading day); oil-return lags 1/5; RSI(14); price-normalised MACD and
signal; Bollinger %B and bandwidth (20); price/SMA−1 (7/20/60); realised volatility (5/20). No raw
price level and no calendar dummy.

One fixed configuration per model family: ridge `alpha=1.0`; LSTM 64→32→16 with dropout 0.3,
Adam 1e-3, batch 16, max 60 epochs, early stopping 10, ReduceLROnPlateau 5/0.5/1e-5. No tuning.
Seeds are repetitions: 5 stationary, 3 legacy. The number of configurations tried is **four**
(ridge-own, ridge-full, stationary LSTM, legacy LSTM), disclosed in `docs/RESULTS.md`.

**Reason:** with ~1,150 pre-hold-out rows and a 210-row hold-out, a hyperparameter search would be
a multiple-testing exercise with little power. Freezing the configuration keeps the edge rule
honest.

---

## D23 — V2 re-pairs the global series with one complete Yahoo vintage

**Date:** 2026-11-14 · **Status:** accepted · **Executed in Stage 3**

The committed CSV stores the Yahoo columns only on the original Iranian dates. V2 needs global
bars on corrected dates absent from the CSV: 110 of the 503 merged block rows, 83 of them
Thursdays. A date-label-only shift would leave the old global pairing and would not correct the
block. All three variants therefore use one complete Yahoo series (`GC=F`, `BZ=F`) for the same
period, merged onto the Iranian dates with the loader's `how='left'` + `ffill` rule; V2 relabels
the Iranian block dates +1 before that merge. The Iranian series is unchanged.

**Verification:** fresh oil matches the CSV exactly on 911/911 overlapping dates; fresh ounce
differs by a median 0.33% in level and 0.018% in log return (corr 0.993), the stale-vintage
effect already noted in `docs/DATA_INTEGRITY.md`.

**Consequence:** V1/V2 differ only in the date correction and the resulting global pairing, not
in the Iranian prices or the global vintage. The V1/V2 differences are tiny; see
`docs/RESULTS.md` §3.

---

## D24 — Stage 3 verdict: no demonstrated edge; artifact not wired in

**Date:** 2026-11-14 · **Status:** accepted · **Executed in Stage 3**

Under the pre-registered rule (`docs/EVAL_PROTOCOL.md` §8), no eligible V2 stationary model
demonstrates edge. The stationary LSTM beats persistence on RMSE in both samples (walk-forward
0.018214 vs 0.018350; hold-out 0.026543 vs 0.026545) but fails the DM significance (p = 0.2251 /
0.4984) and the bootstrap R² CI ([−0.0272, +0.0561] / [−0.0577, +0.0630]). Ridge-own beats
persistence only on the walk-forward; ridge-full is worse in both. The historical-mean drift is
the only model with a significant walk-forward DM (p = 0.0055), but it fails on the hold-out
(p = 0.2428); it is the nominal uptrend, not timing skill.

The primary artifact is `models/gold_lstm_stationary_v2.keras` +
`models/scaler_X_stationary_v2.pkl` + `models/scaler_y_stationary_v2.pkl` + metadata, trained on
V2 pre-hold-out rows (fit 2021-08-28 → 2024-12-31, validation 2025-02-08 → 2025-09-30, seed 42).
It is **not** wired into the API or Streamlit; the existing `models/gold_lstm_v2.keras` remains
for the API.

**Consequence:** Stage 4 is a no-edge / cost-hurdle analysis unless the owner directs otherwise.
The README is not rewritten in Stage 3.

---

## Open decisions

These are the owner's calls. Each names the stage it blocks.

### G1-final — RESOLVED in Stage 2a → **D19 (apply the relabel)** *(was: apply or document?)*

**Resolved 2026-11-14: option (a), applied as a reversible loader transform.** The text below is the state at GATE 1 and is kept for the record; it is superseded by D19.

Stage 1b is complete. The evidence now separates cleanly into two halves:

- **The Jalali field carries no information.** It agrees with the Gregorian field the code already uses in 11,331 of 11,331 records across three datasets and two vintages, inside and outside the block. TGJU derives both from one record, so a conversion bug would show as a non-zero offset and none exists. The Jalali field cannot witness the defect.
- **The alignment tests are decisive.** On an identical set of 235 Iranian returns, matching the ounce one day later raises the block's same-day correlation from **+0.112 to +0.380** (the clean post-block level is +0.358), while doing the same to the post-block data destroys it (**+0.358 → −0.126**). The block's Friday rows carry the weekend move (median |return| 1.179%, zero-change share 0.00) — a move a row dated Friday cannot contain, because the market is closed on Friday.

Because the decision rule required *both* sources to agree, and the first is silent, the rule points at **(b) document only**. Branch (a) as originally worded — "use the Jalali-derived dates" — is not implementable: it is a literal no-op. A fix would have to be the explicit window relabel from §13.1.

Two options:

- **(a) Apply the +1 window relabel** to the 502 raw rows (503 in the merged frame), before the gold/USD merge. Verified in Stage 1b: zero date collisions, no row-count change, no price change. ~1 hour plus a re-run of feature engineering; retraining happens in Stage 3 anyway. **Residual risk: the mechanism is inferred, not observed at the source.**
- **(b) Document it and leave the data alone.** Record it as a known limitation, note it sits entirely in train/val and never in test, and make Stage 3 evaluate with and without the block. Zero risk, but 36% of the training data stays misaligned.

Recommended: **(b)**, because the decision rule requires both sources and one is silent, and because a Stage 3 sensitivity analysis preserves the option at no risk. But the Stage 1b alignment evidence is materially stronger than Stage 1's, and (a) is now a defensible engineering call rather than a guess. The owner decides.

### Resolved in Stage 1b

| Was | Decision | One-line answer |
|---|---|---|
| O1 | **D10** | Keep Rial, label IRR everywhere |
| O2 | **D11** | `geram18` is the intended product |
| O3 | **D12** | Keep `/health`, `/model-info`, `/predict`; Streamlit is only the UI |
| O4 | **D13** | ML Engineer; depth on evaluation, reproducibility, documentation |
| O5 | **D14** | No raw data committed; fetch script + ~200-row sample |
| O6 | **D15** | Not hand-edited; one record has a ×10000 double-scaling bug |
| O7 | **D16** | No rationale; documented as a lesson learned |
| O8 | **D17** | Light Streamlit app + simple Docker image |
