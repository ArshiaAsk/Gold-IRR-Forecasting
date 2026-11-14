# Sample data

`gold_sample.csv` is the **last 200 rows** of the merged dataset (2025-10-14 →
2026-06-13), with the same columns as `data/raw/final_gold_dataset.csv`:

| Column | Meaning |
|---|---|
| `Date` | Gregorian date (YYYY-MM-DD) |
| `Gold_IRR` | 18-karat gold, Rial per gram (`geram18`) |
| `USD_IRR` | USD/IRR, Rial (`price_dollar_rl`) |
| `Ounce_USD` | Gold ounce, USD (`GC=F`) |
| `Oil_USD` | Brent crude, USD (`BZ=F`) |

It exists so the repo runs offline. It is **not** enough to train or evaluate the
model, and it does not overlap the 2023-10-27 → 2025-08-06 block that the loader
corrects.

The full series is **not redistributed** (decision D14 / O5): TGJU is a single
commercial publisher with no stated redistribution licence. Redistribution of the
full dataset awaits TGJU's permission. Refresh locally with the fetch path in
`src/data_loader.py`.
