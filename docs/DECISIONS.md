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

## Open decisions

These are the owner's calls. Each names the stage it blocks.

### O1 — Rial or Toman labeling *(blocks Stage 3 and Stage 5)*

The series is Rial: `TICKER_GOLD="geram18"`, values 10.5M–206.1M (audit-reported). Every "Toman" label in the current README and code is off by 10×, and the 1B IRR starting capital is ≈ $555.

Options: (a) keep Rial everywhere and say so; (b) convert to Toman (÷10) at the presentation layer only; (c) convert in the data layer. Affects every number in the final README.

### O2 — Is the gram-18 series the intended product? *(blocks Stage 3)*

`geram18` is the 18-karat gram price — not a coin (`sekeb`, `emami`) and not the ounce. If the intent was a coin or an investment product, the series and the entire narrative change.

### O3 — Keep a minimal API at all? *(blocks Stage 2)*

The plan assumes yes: `/health`, `/model-info`, `/predict` only. The alternative is to drop serving entirely and present the work as a research notebook plus report. Keeping it demonstrates backend skills; dropping it removes a surface that can only ever serve a model with no edge.

### O4 — Target role emphasis *(blocks Stage 5 framing)*

Which story is the README optimised for: **ML engineer** (modeling + evaluation rigor), **MLOps / platform** (reproducibility, CI, Docker, serving), or **backend / data** (pipeline, API, data quality)? Owner to fill in. This decides which sections get depth and which get a paragraph.

### O5 — Data licensing and redistribution *(blocks Stage 5)*

Do you have permission to redistribute TGJU-sourced data in a public repo? If not, the committed CSVs must be replaced by a fetch script plus a documented schema, and the README must say the data is not redistributed.

### O6 — Provenance of `api_layer/cache/signal_history.jsonl` *(blocks nothing; affects credibility)*

One record claims `predicted_return_pct` 442.95 while its own `predicted_log_return` is 0.0443 — inconsistent by 100×. Was the file hand-edited? If so, it should not be cited as evidence anywhere, even as a "real log line".

### O7 — Why were raw price-level features used? *(blocks Stage 3 narrative only)*

`SMA_7`, `MACD` and `Bollinger_*` were fed to the model as absolute Rial levels rather than normalized. This is the single largest modeling defect and the audit's most likely explanation for the 13σ train→test shift. If there was a deliberate reason, it belongs in "Lessons Learned"; if not, say so plainly — that honesty is the point of the piece.

### O8 — Real deployment target *(blocks Stage 5)*

The `Dockerfile` targets Hugging Face Spaces (Streamlit on 7860); the README documents a four-service compose stack that does not exist (`docker-compose.yml` has one service, `ml-stack`). Which one is the actual target for the "one-command Docker" deliverable?
