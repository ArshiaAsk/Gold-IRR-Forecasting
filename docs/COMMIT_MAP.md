# Commit map after the author-email rewrite

On 2026-11-19 the commits in `origin/main..main` (84 commits) were rewritten to replace a
private author/committer email address with the GitHub noreply identity. Only the identity
changed: every commit keeps its tree, author date, committer date, subject and parents, and
the `--no-ff` merge of `refactor/honest-portfolio` is preserved. `origin/main` (`d1670cc`)
and everything reachable from it were not rewritten.

This table maps each pre-rewrite 7-character abbreviation to its post-rewrite abbreviation.
No email addresses appear in this file. Use it to resolve a hash quoted in the pre-registered
protocol bodies (`docs/EVAL_PROTOCOL.md`, `docs/BACKTEST_PROTOCOL.md`), which keep their
original hashes by design.

| Old | New | Author date | Subject |
|---|---|---|---|
| `5ecb6e0` | `dab1936` | 2026-11-18 | Merge branch 'refactor/honest-portfolio' |
| `b5819a0` | `81be0bc` | 2026-11-18 | docs: add author, contact, citation and data terms |
| `802132e` | `926e7da` | 2026-11-18 | build(docker): actually exclude nested __pycache__ from the image |
| `31fb085` | `9c04c20` | 2026-11-18 | docs(results): drop the 'touched once' hold-out claim from validation |
| `02f051f` | `3160581` | 2026-11-18 | fix(evaluate): stop repeating the retracted hold-out 'touched once' claim |
| `a270209` | `aaef67a` | 2026-11-18 | docs: fix the 173x wording in the D-1 explanation |
| `6e984f5` | `6e27d0b` | 2026-11-18 | docs(review): record the alignment-script output |
| `bc92c17` | `f3cc19b` | 2026-11-18 | docs(state): record the Stage 6 review verification and claim sources |
| `d4d9353` | `ef63f1e` | 2026-11-18 | chore: remove dead config, the unused fixture and stale ignore rules |
| `52b3da0` | `892fc3c` | 2026-11-18 | docs(protocol): append the global-grid disclosure to the Errata |
| `fd67d67` | `094b0e3` | 2026-11-18 | docs(data): measure the global forward-fill grid and the pre-registration timing |
| `d9fcd81` | `9b3cd46` | 2026-11-18 | docs(protocol): append the D-1 correction to an Errata section |
| `a3c3d53` | `2678b44` | 2026-11-18 | fix(docs): recompute the D-1 validation share as 0.69% of the loss |
| `85f27e9` | `648c4db` | 2026-11-18 | docs: fix the no-shorting, touch-count, test-count and status wording |
| `bdc6fc5` | `d920850` | 2026-11-18 | feat(scripts): reproduce the gold-ounce alignment test and remove scratch paths |
| `838dd14` | `dd4b088` | 2026-11-18 | fix(data): document the sample vintage and pin its SHA-256 |
| `5c2208e` | `82cd476` | 2026-11-18 | docs(review): map the Stage 6 review fixes and record the no-new-runs rule |
| `4d53735` | `e666a16` | 2026-11-18 | docs(state): record the Stage 6 verification block |
| `5bc9516` | `ee9a11c` | 2026-11-18 | docs(readme): record the Stage 6 Docker rebuild measurement |
| `383000d` | `4bcc421` | 2026-11-18 | chore(results): redact absolute paths from the committed run logs |
| `833fe0d` | `fb3eecd` | 2026-11-18 | docs: remove managed-deployment references |
| `5917b80` | `166867a` | 2026-11-18 | docs(decisions): record GATE 5b acceptance and the Docker-only decision |
| `d293c75` | `f429b7f` | 2026-11-18 | docs(readme): add a runnable sample prediction and exact field names |
| `15f4cda` | `6227f58` | 2026-11-18 | fix(api): accept the sample CSV header verbatim |
| `2423b80` | `e46e20a` | 2026-11-18 | docs: add the Stage 6 release-fix plan |
| `32560a0` | `8ae3633` | 2026-11-17 | docs(state): final sync of the diff figures |
| `cd08985` | `93eb840` | 2026-11-17 | docs(plan): name the last two documentation commits |
| `3b476b9` | `7431d75` | 2026-11-17 | docs(state): sync the diff figures with the committed tree |
| `074e5b1` | `3822ef8` | 2026-11-17 | docs(state): note the absolute paths left in the committed run logs |
| `77745d8` | `528f4de` | 2026-11-17 | docs(plan): add the release commits to the executed list |
| `799069d` | `29133b4` | 2026-11-17 | docs(state): use the measured diff figures |
| `49e117e` | `62608ce` | 2026-11-17 | docs(state): record the Stage 5b acceptance outputs |
| `746575a` | `0130a5e` | 2026-11-17 | docs: document the built image with its measured size and build time |
| `f996ee8` | `20ee917` | 2026-11-17 | docs(readme): state that Docker is primary and stop overclaiming the hold-out |
| `7fff2dd` | `ecb89c7` | 2026-11-17 | docs(plan): mark Stages 0-5b complete and GATE 5b pending review |
| `416eed5` | `9b93902` | 2026-11-17 | docs: record the GATE 5a decisions and the Stage 5b release mechanics |
| `9aab948` | `5fd0ee1` | 2026-11-17 | build: tolerate interrupted downloads when installing the docker runtime |
| `13ce2c6` | `879d87e` | 2026-11-17 | build: add make targets for install, test, evaluate, serving, docker and data fetch |
| `369f151` | `31a057f` | 2026-11-17 | docs: rewrite the readme from measured results and check its numbers against the json |
| `539f92b` | `6aa03f3` | 2026-11-17 | feat(eval): add an opt-in per-row prediction export and note that headlines predate it |
| `eed9ee0` | `77a4b6f` | 2026-11-17 | ci: run the suite and the readme number check on push and pull requests |
| `361b195` | `131e4f3` | 2026-11-17 | build: pin python 3.12, run as non-root and drop the Hugging Face Space port |
| `1cf8285` | `067e1f5` | 2026-11-17 | chore: add the MIT license, ignore predictions, clear notebooks and drop the legacy model |
| `60e9870` | `10cb5f5` | 2026-11-17 | build: split runtime and development requirements, use tensorflow-cpu for serving |
| `d59dc34` | `9d3515b` | 2026-11-17 | test: move the root pipeline tests under tests/ so one pytest command runs everything |
| `e6f8210` | `45afcae` | 2026-11-17 | docs: commit the stage 5b release plan before any changes |
| `afc1b24` | `a3000ad` | 2026-11-17 | docs: state both length checks in the serving design |
| `72fb667` | `81dbd4a` | 2026-11-17 | docs: record gate 4 decisions and stage 5a acceptance |
| `e9d65e0` | `e16fc67` | 2026-11-17 | test(serving): parity, causality, validation, auth, output and streamlit smoke |
| `f749791` | `60b0e71` | 2026-11-17 | feat(ui): four-tab streamlit app over the committed results and artifact |
| `1bd4a5b` | `9156234` | 2026-11-17 | feat(api): serve the stationary seed-42 artifact from raw rows |
| `f587864` | `0074e45` | 2026-11-17 | feat(serving): one raw-row adapter for the shared feature function |
| `1768b2e` | `92cf95d` | 2026-11-17 | docs: pre-register the stage 5a serving design |
| `379eede` | `812df2b` | 2026-11-16 | docs: state that the stage 3 hold-out promise was not literally met |
| `ef56cef` | `068bba6` | 2026-11-16 | docs: record gate 3 decisions, stage 4 status and the 5a/5b split |
| `3ba3a20` | `3455b12` | 2026-11-16 | docs: add the economic reality section (stage 4) |
| `3b5ac3a` | `31ae157` | 2026-11-16 | feat(backtest): commit stage 4 results and run log |
| `bd17759` | `765a25e` | 2026-11-16 | chore: remove trading_bot (preserved in legacy-pre-refactor) |
| `cf09f8d` | `35a9769` | 2026-11-16 | docs: record the stage 4 backtest run and touch count |
| `9b9caca` | `783ab26` | 2026-11-16 | feat(backtest): stage 4 long/flat economic check with pre-registered accounting |
| `0cc0647` | `228b904` | 2026-11-16 | docs: pre-register the stage 4 economic-reality backtest |
| `1e3e634` | `5a8ce1c` | 2026-11-16 | docs: record the one-label validation/hold-out overlap found in the stage 4 audit |
| `0370453` | `ab7d594` | 2026-11-14 | docs: note the optional same-day sensitivity and the single-variant command |
| `f2c5eb3` | `2edfba0` | 2026-11-14 | docs: add full V1 and V3 per-model result tables |
| `e74d719` | `5f1887e` | 2026-11-14 | fix(eval): attach the run log in main() so imports cannot truncate it |
| `e08469f` | `3599dc2` | 2026-11-14 | docs: record the stage 3 deviation status in the protocol |
| `2838827` | `982857b` | 2026-11-14 | docs: stage 3 results, decisions, plan and state (GATE 3) |
| `5f4abaa` | `e59858c` | 2026-11-14 | chore(eval): track the stage 3 run log |
| `64c9798` | `41a450c` | 2026-11-14 | feat(eval): commit stage 3 results and primary V2 artifact with scalers |
| `8d7715e` | `479a9ab` | 2026-11-14 | test(eval): protocol invariants (causality, target, scaler, folds, variants) |
| `37585ac` | `fe932e9` | 2026-11-14 | feat(eval): stationary features, metrics, variants, folds and entry point |
| `cb75162` | `74d9369` | 2026-11-14 | docs: correct pre-registered hold-out to the 2025-10-01 cutoff (before any model fit) |
| `798981a` | `bda5992` | 2026-11-14 | docs: pre-register stage 3 evaluation protocol before any model run |
| `2332efc` | `17181e7` | 2026-11-14 | docs: explain 503 vs 502 relabelled rows (merge-union, not boundary) |
| `830ed93` | `4f2ce44` | 2026-11-14 | docs: stage 2a/2b plan, state, decisions and acceptance outputs |
| `66b2353` | `0a35d06` | 2026-11-14 | chore: untrack generated data, add a 200-row sample and fix dependencies |
| `5c6a74a` | `e5751a6` | 2026-11-14 | feat(api): minimal three-endpoint service without MLOps wiring |
| `147d58b` | `a0f8cfd` | 2026-11-14 | chore: remove live bot, MLOps layer, monitoring and supervisor stack |
| `75c927e` | `0fb6f2c` | 2026-11-14 | docs: record G1-final decision (D19) and the applied-fix verification |
| `d5b8dcd` | `659b257` | 2026-11-14 | feat(data): reversible +1 day relabel for the 2023-10-27..2025-08-06 block |
| `6edf09f` | `4647f72` | 2026-11-14 | docs: stage 1b g1 resolution — jalali field and alignment tests (read-only) |
| `14dec06` | `145dc7d` | 2026-11-14 | docs: stage 1 data integrity investigation (read-only) |
| `d061bd7` | `ec6bc78` | 2026-11-14 | docs: add stage 0 plan, decisions and state |
| `61d130a` | `e0035cb` | 2026-11-14 | chore: track docs/ and ignore .venv/ |
