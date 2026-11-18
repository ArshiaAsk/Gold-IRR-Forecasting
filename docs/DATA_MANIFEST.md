# Data manifest (hash-only)

The training inputs are **not redistributed** (decision D14). This file records what the
committed artifact was trained on without reproducing any data value: file name, row count,
column names, date range, size, SHA-256 and filesystem mtime. The mtime is metadata, not part
of the hash.

Hashes were read on 2026-11-18 from the local checkout. A clone without the untracked files
cannot reproduce them; that is expected.

## Stage 3 inputs (used by the committed artifact)

| File | Rows | Columns | Date range | Bytes | SHA-256 | mtime |
|---|---:|---|---|---:|---|---|
| `data/raw/final_gold_dataset.csv` | 1,424 | `Date, Gold_IRR, USD_IRR, Ounce_USD, Oil_USD` | 2021-06-14 → 2026-06-13 | 91,592 | `132992b8c455bcd793829d06fa02fca986fd41bba50c36c41cfb7cc1679176eb` | 2026-06-14 13:34:33 +03:30 |
| `data/raw/global_yahoo.csv` | 1,265 | `Date, Ounce_USD, Oil_USD` | 2021-06-04 → 2026-06-12 | 55,742 | `a9cc017ae4e206aa0a50f228fb18bfe56a52bbe922b45023492faad64ae3855e` | 2026-11-14 18:01:19 +03:30 |

`results/run.log` records the same shapes: raw prices 1,424 rows (2021-06-14 → 2026-06-13) and
global series 1,265 rows (2021-06-04 → 2026-06-12). The artifact metadata records commit
`8d7715e` and `date_utc` `2026-11-14T14:54:57+00:00`.

## Legacy processed file (not used by the committed artifact)

| File | Rows | Columns | Date range | Bytes | SHA-256 | mtime |
|---|---:|---|---|---:|---|---|
| `data/processed/advanced_gold_features.csv` | 1,394 | 30 legacy feature columns | 2021-07-19 → 2026-06-11 | 723,753 | `8ef5be530becd16a6a79d9074f10ee437e527f97fc39507b9bb53ccf4868435b` | 2026-06-15 12:32:04 +03:30 |

This is the old raw-level feature frame (`src/train_pipeline.py`). Stage 3 does not read it.

## Bundled sample (tracked)

| File | Rows | Columns | Date range | Bytes | SHA-256 |
|---|---:|---|---|---:|---|
| `data/sample/gold_sample.csv` | 200 | `Date, Gold_IRR, USD_IRR, Ounce_USD, Oil_USD` | 2025-10-14 → 2026-06-13 | 13,107 | `8be4d408dcf62cefb9b84acb1bdf1bc9f825683f6d3eff924c328b46c554fc97` |

The sample is the exact tail of `data/raw/final_gold_dataset.csv`. It is not the tail of the
training frame: `Ounce_USD` differs on 188 of 200 rows because the sample carries the June-2026
source vintage and the training frame carries the November-2026 Yahoo vintage. See
`data/sample/README.md` and `docs/REVIEW_FIXES.md`.

## Verify

```bash
sha256sum data/raw/final_gold_dataset.csv data/raw/global_yahoo.csv \
  data/processed/advanced_gold_features.csv data/sample/gold_sample.csv
wc -l data/raw/final_gold_dataset.csv data/raw/global_yahoo.csv \
  data/processed/advanced_gold_features.csv data/sample/gold_sample.csv
python -m pytest tests/test_sample_manifest.py -q
```

The test pins the sample SHA-256 unconditionally. It checks the untracked-file hashes only when
those files are present, so a clean clone still passes.
