# Stage 6 — release fixes

**Status:** committed before any Stage 6 change. **Branch:** `refactor/honest-portfolio`.
**Scope:** small release fixes only. No retraining, no changes to committed numeric results,
no merge, no push, no tag.

1. **API field names.** `POST /predict` accepts the sample CSV header verbatim (`Date`,
   `Gold_IRR`, `USD_IRR`, `Ounce_USD`, `Oil_USD`). `date` remains an alias. A request that
   supplies both `date` and `Date` with different values is rejected with 422. Tests prove
   the sample-header path, the old lowercase path and the conflict rule.
2. **README.** A runnable "predict from the sample" example, executed against a live server
   and pasted with its real output; the exact accepted field names in the API section;
   `make check` re-run; `docs/README_CLAIMS.md` updated for every touched claim.
3. **Logs.** The absolute paths in `results/run.log` and `results/backtest.log` are replaced
   by `<REPO>` and nothing else. Proof: masked diff, unchanged line counts, and a digit-only
   checksum equal on both sides. Recorded in `docs/DECISIONS.md` as a narrow exception to
   "do not touch `results/`".
4. **Hosted-app cleanup.** No reference to a hosted app, Hugging Face or port 7860 remains in
   tracked files. Docker is the only deployment deliverable (D33).
5. **Docker.** Rebuild only because files copied into the image changed. Run the image and
   show `/health`, a `/predict` built from the raw sample rows with the CSV's original column
   names, and a 401 for a wrong key. Report build time and size.
6. **State.** A final verification block in `docs/STATE.md`: `make check` output, test count,
   clean `git status`, the branch log, and the owner's remaining TODOs.

**Acceptance:** the full suite passes, `make check` passes, `git status` is clean, and the
only change under `results/` is the path redaction.
