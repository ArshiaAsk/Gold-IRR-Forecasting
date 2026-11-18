# Sample data

`gold_sample.csv` is the **last 200 rows** of `data/raw/final_gold_dataset.csv`
(2025-10-14 → 2026-06-13), with the same columns as that file:

| Column | Meaning |
|---|---|
| `Date` | Gregorian date (YYYY-MM-DD) |
| `Gold_IRR` | 18-karat gold, Rial per gram (`geram18`) |
| `USD_IRR` | USD/IRR, Rial (`price_dollar_rl`) |
| `Ounce_USD` | Gold ounce, USD (`GC=F`) |
| `Oil_USD` | Brent crude, USD (`BZ=F`) |

## Provenance

| Field | Value |
|---|---|
| Source file | `data/raw/final_gold_dataset.csv` (untracked; decision D14) |
| Source rows | 1,424 data rows, 2021-06-14 → 2026-06-13 |
| Source SHA-256 | `132992b8c455bcd793829d06fa02fca986fd41bba50c36c41cfb7cc1679176eb` |
| Sample rows | 200 data rows, 2025-10-14 → 2026-06-13 |
| Sample SHA-256 | `8be4d408dcf62cefb9b84acb1bdf1bc9f825683f6d3eff924c328b46c554fc97` |
| Sample created | 2026-11-14 17:36:11 +03:30 (filesystem mtime) |
| Source file mtime | 2026-06-14 13:34:33 +03:30 (the download date) |

The sample is the exact tail of the source file: all four price columns match the last 200
source rows. It is **not** the tail of the training frame the committed artifact saw. Stage 3
trained on the source file merged with a separately cached Yahoo series
(`data/raw/global_yahoo.csv`, fetched 2026-11-14 18:01:19 +03:30). Against that training
frame, `Gold_IRR`, `USD_IRR` and `Oil_USD` match on all 200 rows, but `Ounce_USD` differs on
188 of 200 rows (maximum absolute difference 35.5 USD): the sample carries the source file's
June-2026 ounce vintage, while the training frame carries the November-2026 Yahoo vintage.
The artifact metadata records the run at `2026-11-14T14:54:57+00:00`, commit `8d7715e`;
`results/run.log` records 1,424 raw rows and a 1,265-row global series. See
`docs/DATA_MANIFEST.md` for the hash-only manifest of the untracked files and
`docs/REVIEW_FIXES.md` for the vintage investigation.

## Use

It exists so the repository runs offline. It is **too short to train on**, and it spans the
hold-out window (2025-10-01 → 2026-06-11), so it **must not be used for tuning** or as an
evaluation sample. It does not overlap the 2023-10-27 → 2025-08-06 block that the loader
corrects.

The full series is **not redistributed** (decision D14 / O5): TGJU is a single
commercial publisher with no stated redistribution licence. Redistribution of the
full dataset awaits TGJU's permission. Refresh locally with the fetch path in
`src/data_loader.py`.
