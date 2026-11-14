# Data Integrity Investigation

**Stage:** 1 · **Date:** 2026-11-14 · **Branch:** `refactor/honest-portfolio` · **HEAD at start:** `d061bd7`
**Scope:** read-only. No source, data or model file was modified. All experiments ran in `/tmp/s1` against copies.
**Source of the "before" state:** `docs/AUDIT_REPORT.md` (2026-11-13, audit of `d1670cc`).

---

## 1. Executive verdict

The weekday distribution the audit reported as implausible **is not a property of the data**. It is a **labelling error in the audit's own table**. The dataset concentrates on **Saturday–Wednesday**, exactly as an Iranian market should. There is no uniform one-day backward shift in the Iranian series.

A *different* defect exists, and it is real: TGJU's own records run **one day early for a contiguous 21-month block, 2023-10-27 → 2025-08-06** (503 rows — 35.3% of the raw dataset, 36.1% of the modelled frame). Inside that block the weekly rest day appears on Thursday instead of Friday, in both the gold and the USD series with identical boundaries. That block is entirely inside the training and validation splits; the test split is clean.

| ID | Hypothesis | Verdict |
|---|---|---|
| **H0** | The audit's weekday table is mislabelled | **VERIFIED** |
| **H1** | The Iranian series is uniformly dated one day early | **REFUTED** |
| **H2** | Jalali→Gregorian conversion is wrong | **REFUTED** |
| **H3** | TGJU date parsing in `data_loader.py` is wrong | **REFUTED** |
| **H4** | The merge/ffill with Yahoo created the weekday pattern | **REFUTED** (the pattern pre-dates the merge). A *separate* merge defect is **VERIFIED** |
| **H5** | Timezone/UTC handling moved dates across midnight | **REFUTED** |
| **H6** | A 21-month sub-period (2023-10-27 → 2025-08-06) is dated one day early | **VERIFIED as an anomaly; INFERRED as a one-day shift** |
| **U1** | Values are Rial, labelled Toman | **VERIFIED** |

The single most important line of code for the calendar question:

```
src/data_loader.py:74    final_df['Date'] = pd.to_datetime(final_df['Date_G']).dt.date
```

The pipeline **never reads the Jalali field and never performs a Jalali conversion**. `Date_G` is TGJU's own Gregorian string. There is no code path in which a conversion bug could exist.

---

## 2. The date path, end to end

### 2.1 Ingestion (historical path, `src/data_loader.py`)

```python
41   url = f"https://api.tgju.org/v1/market/indicator/summary-table-data/{item_slug}"
...
53           session = requests.Session()
54           response = session.get(url, headers=headers, impersonate="chrome110")
...
59                   df = pd.DataFrame(json_data['data'])
...
62                   cols = ['Open', 'Low', 'High', 'Close', 'Change', 'Percent', 'Date_G', 'Date_J']
63                   current_cols = len(df.columns)
64                   if current_cols >= 8:
65                       df.columns = cols + [f'col_{i}' for i in range(8, current_cols)]
...
70                   final_df = df[['Date_G', 'Close']].copy()
71                   final_df['Close'] = final_df['Close'].apply(self.clean_value)
72
73                   # Standardize Date format
74                   final_df['Date'] = pd.to_datetime(final_df['Date_G']).dt.date
```

Notes on this block:

- The response is a JSON **array of 8-element arrays**, not objects. Columns are assigned **positionally**. If TGJU ever reorders the array, `Date_G` and `Close` are silently swapped with no error. I validated the current order (see §3.1) — it is correct.
- `Date_J` (the Jalali string) is **selected away and discarded** at line 70. It never reaches the dataset, the features or the model. This is why H2 and H3 cannot be the cause of any calendar defect.
- `pd.to_datetime` is called **without** `format=`. For strings of the form `2026/02/05` this is unambiguous (the first component is 4 digits and > 12), so pandas parses Y-M-D. I verified this explicitly: parsing with and without an explicit `format='%Y/%m/%d'` returns identical results for all 3,775 records.
- `.dt.date` drops any time component. **There is no time component to drop** — the source field is a date, not a timestamp.

### 2.2 Ingestion (live path, `api_layer/data_fetcher.py`)

The live path does **not** use dates at all. It takes the first row and the first array element:

```python
157             if 'data' in response and len(response['data']) > 0:
158                 latest_row = response['data'][0]  # First row is latest
159                 price_str = latest_row[0] if latest_row else None
```

`latest_row[0]` is the **Open** field of the 8-element row, not `Close`. This is a live-path bug (the bot consumes the session's opening print rather than its close), but it is a *price* bug, not a *date* bug. Out of scope for Stage 1; recorded here so it is not lost. `api_layer/data_fetcher.py` contains no `Date_G`, no `to_datetime`, no timezone call — grep for all three returns nothing.

### 2.3 Global series (Yahoo)

```python
100             gold = yf.Ticker("GC=F")
101             df_gold = gold.history(period="5y")[['Close']].rename(columns={'Close': 'Ounce_USD'}).reset_index()
...
108             df_gold['Date'] = pd.to_datetime(df_gold['Date']).dt.date
109             df_oil['Date'] = pd.to_datetime(df_oil['Date']).dt.date
```

`yf.Ticker.history()` returns a tz-aware index (exchange-local, e.g. `America/New_York`). `pd.to_datetime(...).dt.date` keeps the **local** calendar date — the correct choice for a daily bar. There is no `.tz_convert('UTC')` anywhere in the repo, so no UTC-vs-Tehran crossing can occur. (Verified: `grep -rn "tz_localize\|tz_convert\|Asia/Tehran" src api_layer` → no matches outside `src/mlops/` audit-log timestamps.)

### 2.4 Merge and forward fill

```python
130             main_df = pd.merge(df_gold, df_usd, on='Date', how='outer')     # Iranian series: union of dates
...
146             final_dataset = pd.merge(main_df, df_global, on='Date', how='left')   # global: keep Iranian dates only
...
152         final_dataset['Date'] = pd.to_datetime(final_dataset['Date'])
153         final_dataset.set_index('Date', inplace=True)
154         final_dataset.sort_index(ascending=True, inplace=True)
...
157         final_dataset.ffill(inplace=True)
158         final_dataset.dropna(inplace=True)
```

The date axis of the final dataset is **the union of the two TGJU date sets**. Yahoo contributes no dates: `how='left'` means any Yahoo date absent from TGJU is discarded. Consequences are quantified in §7.

### 2.5 Where the target comes from

```python
69          df['Gold_LogRet'] = np.log(df['Gold_IRR'] / df['Gold_IRR'].shift(1))
...
89          df['Target_Next_LogRet'] = df['Gold_LogRet'].shift(-1)
```

Target = the **next row's** gold return. One step ahead in row space. Discussed in §9.

---

## 3. Raw evidence

### 3.1 The response format and the positional mapping

Command:

```bash
python - <<'EOF'
import json, pandas as pd
d = json.load(open('api_layer/cache/raw_response_20260207_130227.json'))
print(d['url'], d['data']['recordsTotal'], len(d['data']['data']))
print(sorted({len(r) for r in d['data']['data']}))
print(d['data']['data'][0])
EOF
```

Output:

```
https://api.tgju.org/v1/market/indicator/summary-table-data/price_dollar_rl 3775 3775
[8]
['1,609,350', '1,572,300', '1,624,700', '1,622,400', '<span class="high" dir="ltr">53900</span>',
 '<span class="high" dir="ltr">3.44%</span>', '2026/02/05', '1404/11/16']
```

Every row has exactly 8 elements. The last two are a Gregorian date and a Jalali date.

I validated the positional mapping `[Open, Low, High, Close, Change, Percent, Date_G, Date_J]` against the OHLC invariant `Low ≤ min(Open, Close)` and `High ≥ max(Open, Close)`:

```
geram18:          rows=3554  OHLC ordering consistent: 3552/3554
price_dollar_rl:  rows=4002  OHLC ordering consistent: 3994/4002
```

99.8% and 99.8%. A permuted mapping would score near 33%. The mapping is correct; the handful of violations are genuine TGJU data glitches.

The cached file covers **`price_dollar_rl` only** — there is no cached gold response. To get the gold series I re-fetched both slugs from the same endpoint into `/tmp/s1` (network was available):

```bash
python - <<'EOF'
import urllib.request, json
for slug in ["geram18","price_dollar_rl"]:
    url=f"https://api.tgju.org/v1/market/indicator/summary-table-data/{slug}"
    req=urllib.request.Request(url, headers={'User-Agent':'Mozilla/5.0',
        'Referer':f'https://www.tgju.org/profile/{slug}/history','Accept':'application/json'})
    json.dump(json.loads(urllib.request.urlopen(req, timeout=30).read()), open(f"/tmp/s1/{slug}.json","w"))
EOF
```

Result: `geram18` 3,554 rows (2013-07-22 → 2026-11-12), `price_dollar_rl` 4,002 rows (2011-11-26 → 2026-11-12). These live fetches extend past the committed snapshot (2026-06-13), which lets me check the committed CSV against the source rather than against itself.

### 3.2 Twelve raw records spread across history — `geram18`

Format is `Date_G` / `Date_J` exactly as received, then the parsed date and weekday.

```
Date_G=2013/07/22  Date_J=1392/04/31  Close=  1,000,000  -> 2013-07-22 Monday
Date_G=2014/10/20  Date_J=1393/07/28  Close=    960,590  -> 2014-10-20 Monday
Date_G=2016/02/17  Date_J=1394/11/28  Close=  1,001,900  -> 2016-02-17 Wednesday
Date_G=2017/06/19  Date_J=1396/03/29  Close=  1,138,980  -> 2017-06-19 Monday
Date_G=2018/09/10  Date_J=1397/06/19  Close=  3,728,500  -> 2018-09-10 Monday
Date_G=2020/01/13  Date_J=1398/10/23  Close=  4,922,000  -> 2020-01-13 Monday
Date_G=2021/03/03  Date_J=1399/12/13  Close= 10,521,000  -> 2021-03-03 Wednesday
Date_G=2022/04/26  Date_J=1401/02/06  Close= 12,924,000  -> 2022-04-26 Tuesday
Date_G=2023/07/03  Date_J=1402/04/12  Close= 23,846,000  -> 2023-07-03 Monday
Date_G=2024/08/18  Date_J=1403/05/28  Close= 35,560,000  -> 2024-08-18 Sunday
Date_G=2025/10/14  Date_J=1404/07/22  Close=108,433,000  -> 2025-10-14 Tuesday
Date_G=2026/11/12  Date_J=1405/08/21  Close=250,388,000  -> 2026-11-12 Thursday
```

### 3.3 Twelve raw records — `price_dollar_rl`

```
Date_G=2011/11/26  Date_J=1390/09/05  Close=   13,700  -> 2011-11-26 Saturday
Date_G=2013/06/02  Date_J=1392/03/12  Close=   36,478  -> 2013-06-02 Sunday
Date_G=2014/10/18  Date_J=1393/07/26  Close=   32,340  -> 2014-10-18 Saturday
Date_G=2016/03/29  Date_J=1395/01/10  Close=   34,820  -> 2016-03-29 Tuesday
Date_G=2017/10/09  Date_J=1396/07/17  Close=   40,240  -> 2017-10-09 Monday
Date_G=2019/02/12  Date_J=1397/11/23  Close=  119,300  -> 2019-02-12 Tuesday
Date_G=2020/05/27  Date_J=1399/03/07  Close=  175,710  -> 2020-05-27 Wednesday
Date_G=2021/09/08  Date_J=1400/06/17  Close=  278,410  -> 2021-09-08 Wednesday
Date_G=2023/01/05  Date_J=1401/10/15  Close=  394,830  -> 2023-01-05 Thursday
Date_G=2024/05/06  Date_J=1403/02/17  Close=  597,200  -> 2024-05-06 Monday
Date_G=2025/08/23  Date_J=1404/06/01  Close=  941,000  -> 2025-08-23 Saturday
Date_G=2026/11/12  Date_J=1405/08/21  Close=2,669,000  -> 2026-11-12 Thursday
```

**Plausibility.** Every date lands on Saturday–Wednesday except three: `2019-02-12` (Tuesday, fine), `2023-01-05` (Thursday — a real Thursday row, 2.9% of the series), `2025-08-23` (Saturday, a trading day in Iran), and `2026-11-12` (Thursday). No row in either sample falls on a Friday, and the sampled Thursdays are in the low-frequency tail. Nothing here suggests a shift.

Note that `Date_G` and `Date_J` are **mutually consistent** in all twelve rows — e.g. `1404/11/16` is Bahman 16, 1404, which is 2026-02-05. §5 tests this over all 7,556 records.

---

## 4. Weekday histograms, isolated per series

This is the section that settles the question. Each series is counted **on its own date axis, before any merge and before any forward fill**.

```bash
python - <<'EOF'
import pandas as pd, json
WD=['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday']
SW=['Saturday','Sunday','Monday','Tuesday','Wednesday']
m = pd.read_csv('data/raw/final_gold_dataset.csv', index_col='Date', parse_dates=True)
w = m.index.day_name().value_counts().reindex(WD)
print(w.to_string()); print("Sat-Wed share %.1f%%" % (100*w[SW].sum()/w.sum()))
EOF
```

### 4.1 The merged dataset

```
[MERGED final_gold_dataset.csv]  n=1424  Sat-Wed=84.1%
  Mon 241  Tue 243  Wed 240  Thu 137  Fri 90  Sat 237  Sun 236
```

### 4.2 `geram18` alone

```
[geram18, full history 2013-07-22..2026-11-12]  n=3554  Sat-Wed=89.4%
  Mon 637  Tue 631  Wed 646  Thu 274  Fri 101  Sat 631  Sun 634

[geram18, window 2021-06-14..2026-06-13]  n=1417  Sat-Wed=84.3%
  Mon 240  Tue 241  Wed 240  Thu 135  Fri 88  Sat 237  Sun 236
```

### 4.3 `price_dollar_rl` alone

```
[price_dollar_rl, full history 2011-11-26..2026-11-12]  n=4002  Sat-Wed=88.8%
  Mon 713  Tue 709  Wed 723  Thu 341  Fri 108  Sat 705  Sun 703

[price_dollar_rl, window 2021-06-14..2026-06-13]  n=1400  Sat-Wed=85.1%
  Mon 240  Tue 243  Wed 238  Thu 120  Fri 89  Sat 235  Sun 235
```

### 4.4 Yahoo, before the merge

Reconstructed from Yahoo's own timestamps (1,258 daily bars, 2021-11-15 → 2026-11-13):

```
GC=F: rows=1258 2021-11-15..2026-11-13
   Mon 234  Tue 260  Wed 258  Thu 253  Fri 253  Sat 0  Sun 0
```

### 4.5 Conclusion

Both Iranian series show **the same Saturday–Wednesday concentration, before any merge, in the source data itself**. The merged dataset merely inherits it. The merged counts equal the gold counts almost exactly (Sat 237 = 237, Sun 236 = 236) because the date axis is dominated by `geram18`.

**The pattern in the data is the correct Iranian pattern.** Saturday through Wednesday are the working days; Thursday is a partial/carry-over day (137 rows, of which 87 repeat the previous close — 85 of those a carry-over published by TGJU itself, see §8); Friday is the weekly rest day (90 rows, 6.3%).

---

## 5. The audit's table is mislabelled — reproduced exactly

The audit printed `Fri 237 · Sat 236 · Sun 241 · Mon 243 · Tue 240 · Wed 137 · Thu 90`. The multiset `{243, 241, 240, 237, 236, 137, 90}` matches the real counts exactly. Only the **labels** are wrong, and they are wrong by exactly one position.

```bash
python - <<'EOF'
import pandas as pd
c = pd.read_csv('data/raw/final_gold_dataset.csv', index_col='Date',
                parse_dates=True).index.dayofweek.value_counts().sort_index()
print(c.tolist())
print(dict(zip(['Sunday','Monday','Tuesday','Wednesday','Thursday','Friday','Saturday'], c.values)))
EOF
```

```
value_counts by dayofweek 0..6: [241, 243, 240, 137, 90, 237, 236]
with shifted labels : {'Sunday': 241, 'Monday': 243, 'Tuesday': 240, 'Wednesday': 137,
                       'Thursday': 90, 'Friday': 237, 'Saturday': 236}
```

That dictionary, read Friday-first, is `Fri 237, Sat 236, Sun 241, Mon 243, Tue 240, Wed 137, Thu 90` — **character for character the audit's table**.

The mechanism is a classic off-by-one: `Series.dt.dayofweek` is `0=Monday … 6=Sunday`, and the audit paired those integers with a label list starting at `Sunday` instead of `Monday`. Every count was therefore attributed to the weekday before it. `actual Saturday → labelled Friday`, and so on. That single slip produced the entire "one-day backward shift" puzzle.

**H0: VERIFIED. H1: REFUTED.** There is no shift to explain.

---

## 6. Jalali calendar

The pipeline never converts Jalali (§2.1), so no library could be at fault. I checked anyway, because the source carries a Jalali field and a future re-ingest might use it.

I implemented the standard jalaali arithmetic independently (Borkowski/Khayyam algorithm, exact for 1178–1633 Jalali) and converted **every** `Date_J` in both series:

```
geram18:         3554 rows, mismatches = 0
price_dollar_rl: 4002 rows, mismatches = 0
```

Known-date spot checks:

```
1404/01/01 -> 2025-03-21   (Nowruz 1404)          ✓
1403/01/01 -> 2024-03-20   (Nowruz 1403)          ✓
1402/01/01 -> 2023-03-21   (Nowruz 1402)          ✓
1400/01/01 -> 2021-03-21   (Nowruz 1400)          ✓
1403/12/30 -> 2025-03-20   (last day of leap 1403) ✓
is 1403 a leap year in this implementation? True
```

7,556 conversions, zero mismatches, including four Nowruz boundaries and the leap day of 1403. **H2: REFUTED.** TGJU's Jalali↔Gregorian pairing is internally correct; and in any case the pipeline discards the Jalali field.

**H3: REFUTED.** `pd.to_datetime` without `format=` was tested against an explicit `format='%Y/%m/%d'` on all 3,775 cached records: identical output (`identical: True`). The `YYYY/MM/DD` form cannot be read as `DD/MM/YYYY` because the leading component is a four-digit year.

**H5: REFUTED.** There are no timestamps. `Date_G` is a date string; `.dt.date` is a no-op with respect to time; no timezone function is called anywhere in `src/` or `api_layer/`.

---

## 7. A real defect: the 2023-10 → 2025-08 block

While checking H1 I found something the audit missed. The *shape* of the week changes partway through the series.

Rows per weekday, per month, `geram18`:

```
wd       Saturday  Sunday  Monday  Tuesday  Wednesday  Thursday  Friday
2023-09         4       3       4        4          3         3       0
2023-10         4       5       5        4          4         2       1
2023-11         4       4       4        4          5         0       4
2023-12         4       5       4        4          4         0       5
2024-01         4       4       5        5          4         0       4
...
2025-06         2       3       3        1          2         0       2
2025-07         3       3       4        5          5         0       3
2025-08         5       4       4        4          4         2       1
2025-09         4       4       4        5          3         4       0
2025-10         4       4       4        4          5         5       0
```

From **2023-11 through 2025-07 inclusive, Thursday is exactly zero and Friday is 3–5 per month, every single month**. Before and after, Thursday is present and Friday is absent. The same table computed on `price_dollar_rl` shows **identical boundaries** — so this is TGJU's date assignment, not the merge, not the loader.

Exact boundaries, both series:

```
Thursday rows: last before block 2023-10-12, first after block 2025-08-21
Friday   rows: block runs 2023-10-27 .. 2025-08-01
```

### 7.1 Why this is not a market change

Iran's weekly rest day is Friday. A rest day cannot move to Thursday for 21 months and then move back. The dataset's own behaviour confirms the rest day **moved one day earlier** during the block:

| Period | Largest median absolute daily return | Day |
|---|---|---|
| pre-block 2021-06-14..2023-10-12 | 1.36% | **Saturday** |
| block 2023-10-27..2025-08-01 | 1.18% | **Friday** |
| post-block 2025-08-21..2026-06-13 | 1.99% | **Saturday** |

The "first trading day after the weekend" — the day that carries the accumulated weekend move — is Saturday outside the block and **Friday** inside it. That is exactly what a one-day-early label does: it renames real Saturday as Friday.

### 7.2 Alignment against an independent series

Iranian 18k gold is close to `0.75 × global 24k gram price × USD/IRR`, so the *premium return*

```
z_t = log(Gold_IRR_t / Gold_IRR_{t-1}) − log(USD_IRR_t / USD_IRR_{t-1})
```

should track the **same-day** global gold return. Correlation with `GC=F`, by lag (`k=-1` means the Iranian row leads the global row by one day):

```
corr(z_t , GC=F return_{t-k})
  pre-block  (..2023-10-12)              k=-1: +0.128  k=+0: +0.099  k=+1: -0.032   n=311
  BLOCK      (2023-10-27..2025-08-01)    k=-1: +0.231  k=+0: +0.164  k=+1: +0.056   n=318
  post-block (2025-08-21..)              k=-1: -0.100  k=+0: +0.552  k=+1: +0.165   n=154
  whole window                           k=-1: +0.083  k=+0: +0.255  k=+1: +0.057   n=798
```

Post-block is unambiguous: **+0.552 at lag 0 versus −0.100 at lag −1**. The block peaks at lag −1 (+0.231) but only weakly ahead of lag 0 (+0.164). The pre-block is nearly tied.

I also tried a variance-based version of the same test (`sd` of the residual `Gold_LogRet − USD_LogRet − Ounce_LogRet` under each alignment). It is **inconclusive**: the Iranian premium is itself volatile (sd ≈ 1.6–1.8%), larger than the ounce's daily move, so the one-day misalignment is not separable from premium noise.

**Honest verdict on H6:** the *structural* anomaly is **VERIFIED** — Thursday rows vanish and Friday rows appear for 21 months, in both series, with identical boundaries, and the post-weekend return moves from Saturday to Friday. The *mechanism* — that TGJU assigned the preceding calendar day — is **INFERRED**, supported by three independent signals (rest-day position, post-weekend return day, lag-1 alignment peak) but not proven. A plausible competing explanation, which I cannot exclude, is that TGJU changed its publishing schedule rather than its date arithmetic. The distinction matters for the fix: a relabel moves data one day; a schedule change does not.

### 7.3 Where the block sits relative to the splits

Block rows inside each split, measured on the modelled frame (`data/processed/advanced_gold_features.csv`, 1,394 rows, split 976 / 209 / 209):

```
block rows in processed frame: 503 of 1394 (36.1%)
  train: 337   val: 166   test: 0
train 2021-07-19 -> 2024-12-24 | val 2024-12-25 -> 2025-10-01 | test 2025-10-02 -> 2026-06-11
```

The block is **entirely inside train and validation. The test split contains none of it.** So the test-set metrics are not directly contaminated — but 36% of what the model learned from came from a series whose internal date alignment differs from the data it is scored on. A relationship learned in the block cannot transfer to the test period.

(The same 503 rows are 35.3% of the raw merged frame's 1,424 rows; the difference is the 30 rows dropped by the rolling-window warm-up.)

---

## 8. Forward fill

Exact attribution, by comparing each source series' own date set with the merged axis:

```
merged axis rows: 1424
  dates present in geram18 source : 1417  -> gold ffilled on 7 rows
  dates present in usd source     : 1400  -> usd  ffilled on 24 rows
  dates present in Yahoo GC=F     :  836  -> ounce ffilled on 588 rows (41.3%)
  Yahoo dates dropped by how='left': 317
```

So `ffill` is **almost irrelevant for the Iranian series** (7 and 24 rows) and **dominant for the global series** (588 rows, 41.3%).

Per-column duplicate counts in the merged CSV:

```
Gold_IRR   unchanged-vs-prev:  111 ( 7.8%)  longest run: 2
USD_IRR    unchanged-vs-prev:   48 ( 3.4%)  longest run: 2
Ounce_USD  unchanged-vs-prev:  514 (36.1%)  longest run: 4
Oil_USD    unchanged-vs-prev:  515 (36.2%)  longest run: 4
pure duplicate rows (all 4 cols unchanged): 1 (0.1%)
```

**Important distinction:** only **7** of the 111 unchanged gold values were produced by `ffill`. The other **104 are genuine carry-overs in TGJU's own data** — the source published a row with a repeated close:

```
gold unchanged vs prev: 111 rows; ffilled by code: 7; genuine source carry-over: 104
weekday of genuine carry-over: {'Thursday': 85, 'Tuesday': 7, 'Monday': 6, 'Wednesday': 5, 'Sunday': 1}
```

85 of the 104 are Thursdays, out of 137 Thursday rows in the merged frame (87 of those 137 have an unchanged close: 85 genuine carry-overs plus 2 code-filled). TGJU publishes a Thursday row whose close equals the previous close in the large majority of cases — i.e. Thursday is mostly a non-trading day recorded for completeness. Longest ffill run is 2 rows for gold, 4 for the global columns.

The global columns are stale on **every** Saturday and Sunday row:

```
weekday of ounce-ffilled rows: {'Saturday': 237, 'Sunday': 236, 'Monday': 45,
                                'Thursday': 23, 'Wednesday': 23, 'Tuesday': 22, 'Friday': 2}
```

Consequence: **473 of 1,424 rows (33%) have an exactly-zero `Ounce_LogRet` and `Oil_LogRet`**, and every Monday's global "daily" return spans three calendar days. 317 Yahoo observations — 145 Fridays and 117 Thursdays plus 55 others — are dropped entirely by `how='left'`.

**H4: REFUTED** as an explanation of the weekday pattern (the pattern exists in each series before merging). But **VERIFIED** as a separate, real defect: the merged global series is a stale, calendar-misaligned copy of the true daily series on a third of all rows.

---

## 9. Impact analysis: shifting the Iranian series

Ran in `/tmp/s1` against a copy. The Iranian columns (`Gold_IRR`, `USD_IRR`) were shifted by `k ∈ {−1, 0, +1}` rows while the global columns were held fixed, then all features were rebuilt exactly as `src/feature_eng.py` does and the same split was applied (`test = 15%`, ridge `alpha=1.0`).

```bash
python /tmp/s1/impact.py
```

### 9.1 Correlations

| shift | Gold~Ounce | Gold~Oil | Gold~USD | Gold~Ounce lag-1 | Gold~Ounce lead-1 |
|---|---|---|---|---|---|
| **−1** | **−0.049** | −0.040 | 0.572 | +0.016 | +0.165 |
| **0 (current)** | **+0.165** | +0.042 | 0.572 | −0.049 | +0.147 |
| **+1** | +0.147 | +0.064 | 0.572 | +0.165 | +0.053 |

Contemporaneous correlation with the global gold return is **maximal at the current alignment** and collapses to **negative** under the `−1` shift that H1 would have required. `Gold~USD` is invariant (both series shift together) as expected.

On the clean, un-merged axes the same test is sharper (§7.2): `+0.255` at lag 0 versus `+0.083` at lag −1.

### 9.2 Baseline test metrics (target = `Target_Next_LogRet`, 180 test windows, 2025-10-02 → 2026-06-11)

| shift | persistence R² | persistence RMSE | persistence dir. acc | ridge R² | ridge RMSE | ridge dir. acc | n |
|---|---|---|---|---|---|---|---|
| −1 | −0.8018 | 0.035637 | 43.75% | −0.8385 | 0.035997 | 48.56% | 208 |
| **0** | **−0.8046** | **0.035602** | **43.54%** | **−0.8334** | **0.035884** | **48.80%** | **209** |
| +1 | −0.8155 | 0.035608 | 43.27% | −0.8589 | 0.036031 | 48.56% | 208 |

**The picture does not change materially.** Every configuration is deeply negative out-of-sample; persistence and ridge are within 0.03 R² of each other; directional accuracy is below a coin flip for persistence and around 49% for ridge. The shift is not the difference between an edge and no edge. This is consistent with the audit's negative result and with `logs/test_metrics.json` (log-return R² −0.0016 for the LSTM on a differently-defined denominator).

Ridge emitted `LinAlgWarning: ill-conditioned matrix (rcond ≈ 3e-18)` in all three runs, because `SMA_7`, `MACD` and `Bollinger_*` are absolute Rial levels in the tens of millions. That is the O7 defect, confirmed independently; it does not invalidate the comparison, which is like-for-like across shifts.

### 9.3 Lookahead

**Does the current construction leak the future?** No. Every feature at row `t` uses data up to and including `t`; `Target_Next_LogRet = Gold_LogRet.shift(-1)` is the future by design; the scaler is fit on train only (`src/data_preprocessor.py:105-113`); `dropna` happens before the split and is harmless.

**Could a one-day shift have created lookahead?** Not if applied uniformly. A uniform relabel of the whole Iranian series moves every row, feature and target together; it is a change of origin, not a leak. This is why the `−1/+1` results above are clean.

**Where a shift *would* create lookahead** is a *partial* fix — correcting one series and not the other. If `Gold_IRR` were corrected to real day `d` while `USD_IRR` stayed one day early at real `d+1`, then `USD_LogRet` at row `t` would carry information from the same real day as the target, and `Gold~USD` would jump spuriously. **Any fix must be applied to both Iranian series atomically.** This is the main implementation risk, and the reason the recommended fix is expressed at the loader level rather than as a post-hoc column shift.

**Could the block have hidden lookahead?** No, for the same reason: within the block both Iranian series move together. What the block does create is a **regime change in the cross-series relationship** — the global features are effectively one day stale relative to the Iranian series for 503 rows, then correct again. A model can learn a spurious dependence there that does not hold in the test period. That degrades the test score; it does not inflate it.

---

## 10. Unit check

```
Gold_IRR / (0.75 * Ounce_USD/31.1035 * USD_IRR):  median 1.010  IQR 0.994-1.023
first row: Gold_IRR=10,717,000  USD_IRR=240,450  Ounce=1,864.0
```

A ratio of 1.01 across five years, with an interquartile range of ±1.5%, is an exact identity: `Gold_IRR` **is** 0.75 × (ounce price per gram) × USD/IRR. That is the Rial price of one gram of 18-karat gold, with essentially no premium.

Confirmed by the source: `config/settings.py:49  TICKER_GOLD: str = "geram18"` (`گرم ۱۸` = "gram, 18 karat"), `:50  TICKER_USD: str = "price_dollar_rl"` (`_rl` = Rial). The raw response's `Close` for `geram18` on 2026-11-12 is `250,388,000` — 250 million Rial per gram, which at 2,669,000 Rial/USD is ≈ $94/gram ≈ $2,920/oz against a spot of ≈ $4,090. The gap is the 18k/24k ratio (0.75) plus the real premium. The magnitude is unambiguously **Rial**.

The labels are wrong, not the values:

```
src/api/main.py:57          description="Current gold price in Toman",
src/train_pipeline.py:203   self.logger.info(f"  - RMSE: {self.metrics['rmse']:,.2f} Toman")
src/model_evaluator.py:210  textstr = f"RMSE: {metrics['rmse']:,.0f} Toman\n"
README.md:92                **Price Range:** ~10.7M - 11.6M Toman (historical data from 2021-01-27 onwards)
```

`README.md:92` states a range of 10.7M–11.6M "Toman" for a series that actually runs 10.7M–179M **Rial**. Every "Toman" label understates the unit by 10×.

Starting capital: `trading_bot/config/backtest_config.py:12  INITIAL_CAPITAL = 1_000_000_000  # IRR (1 billion Toman)` — 1e9 Rial is $4,159 at the 2021-06-14 rate (240,450 Rial/USD) and $555 at the 2026-06-11 rate (1,801,800 Rial/USD). The audit's "$555" is correct for the end of the sample.

**U1: VERIFIED** — values are Rial; the labels are Toman; the error is 10×.

---

## 11. Verdict table

| Hypothesis | Verdict | Decisive evidence |
|---|---|---|
| H0 — audit table mislabelled | **VERIFIED** | Off-by-one label list reproduces the audit's table exactly (§5) |
| H1 — uniform one-day backward shift | **REFUTED** | Each series independently Sat–Wed ≈ 84–89% (§4); alignment peaks at lag 0 (§7.2, §9.1) |
| H2 — Jalali conversion error | **REFUTED** | 7,556 conversions, 0 mismatches; Nowruz + leap-year checks pass; Jalali field never used by the code (§6) |
| H3 — date parsing error | **REFUTED** | Explicit vs implicit format identical on 3,775 records; Y/M/D unambiguous (§6) |
| H4 — merge/ffill created the pattern | **REFUTED** (pattern pre-exists the merge) / **VERIFIED** (merge creates a *different* defect: 41.3% stale global rows) | §4, §8 |
| H5 — timezone / midnight crossing | **REFUTED** | No timestamps, no tz call in `src/` or `api_layer/` (§2, §6) |
| H6 — 21-month sub-period dated one day early | **VERIFIED** (anomaly) / **INFERRED** (mechanism) | §7 |
| U1 — Rial labelled Toman | **VERIFIED** | Ratio identity 1.010, IQR ±1.5% (§10) |
| Independent spot check of individual dates | **UNKNOWN** | See §12 |

---

## 12. Independent spot check

Network was available, so I fetched `geram18` and `price_dollar_rl` live from TGJU and fetched `GC=F`/`BZ=F` from Yahoo's chart API. Cross-checks:

- `Oil_USD` in the committed CSV matches Yahoo `BZ=F` close **exactly on 835/835 overlapping dates**. The global columns were not corrupted by the merge.
- `Ounce_USD` matches `GC=F` on only **38/835** dates, with a maximum absolute difference of **53.4** on a price of ≈ $4,000 (1.3%). Shift 0 is clearly the best alignment (correlation 0.9999 versus 0.9993 at lag −1), so this is *not* a date shift — most likely a different Yahoo vintage (the CSV was captured in June 2026; my fetch is November 2026). **UNKNOWN** — I did not establish the cause. It is a small error in a feature column and does not affect any date conclusion.
- I did **not** verify individual Iranian prices against a second independent publisher. TGJU is effectively the only machine-readable source for `geram18`, and no substitute was available. The internal checks — Jalali↔Gregorian agreement over 7,556 rows, the OHLC invariant, the gold/USD/ounce identity to 1% — are strong, but they are internal.

**Verdict: no independent external confirmation of individual date values. UNKNOWN.**

---

## 13. Recommended fix

### 13.1 What to fix

**The block, not the calendar.** The uniform-shift fix that H1 implied would *break* correct data (§9.1). The only defensible change is to correct the 2023-10-27 → 2025-08-06 sub-period.

| | |
|---|---|
| **File** | `src/data_loader.py` |
| **Function** | `DataLoader.get_tgju_history(self, item_slug)` (lines 37–91) |
| **Change** | After line 74 (`final_df['Date'] = pd.to_datetime(final_df['Date_G']).dt.date`), apply a documented, data-driven date correction to the rows in the block. Add a new module-level constant and a helper, e.g. `_TGJU_DATE_SHIFT_WINDOWS = [(date(2023,10,27), date(2025,8,6), +1)]` and `_apply_date_shift(df)`, which adds one day to `Date` for rows inside the window. Apply it **before** the gold/USD outer merge at line 130 so both series move together. |
| **Also change** | `api_layer/data_fetcher.py` has no historical path and needs no change — but `latest_row[0]` at line 159 should be `latest_row[3]` (Open → Close). Separate bug, separate commit. |
| **Effort** | ~1 hour to implement and unit-test; ~30 minutes to re-run feature engineering and confirm row counts; **0 minutes to retrain** if the fix is applied before Stage 3 (which retrains anyway). If the fix were applied to the current model, all artifacts would be invalid. |
| **Verification** | After the fix, re-run §7: Thursday count in the block should go from 0 to ~85, Friday from ~86 to ~0; `corr(z_t, GC=F_t)` in the block should rise from +0.164 toward the post-block's +0.55. |

**Before implementing, the block's nature must be settled** (see GATE 1). If TGJU changed its publishing schedule rather than its dates, adding one day to those rows would *introduce* an error. The discriminating test is a second independent source for a handful of dates inside the block — e.g. an archived TGJU page, a Persian financial news archive, or a Wayback snapshot of `tgju.org/profile/geram18/history` from 2024. I did not have one.

### 13.2 What not to do

- Do **not** shift the whole series by −1 or +1. §9.1 shows it destroys the contemporaneous correlation with global gold and does not improve any baseline.
- Do **not** re-date `Gold_IRR` without re-dating `USD_IRR`. A partial fix creates genuine lookahead (§9.3).
- Do **not** "fix" the global columns by switching the merge to `how='outer'`. That would introduce Yahoo dates (including every Friday) that the Iranian series has no observation for, and the ffill would then run in the opposite direction. If the stale-global problem is worth fixing at all, the right fix is to build features on each series' own calendar and align at the feature step — a Stage 3 change, not a Stage 1 one.

### 13.3 Risks

| Risk | Severity | Mitigation |
|---|---|---|
| The block is a publishing-schedule change, not a date shift → the fix introduces a 503-row error | **High** | Resolve at GATE 1 with an external source before coding |
| Fixing gold but not USD → lookahead | **High** | Single helper applied before the merge; assert both series' block boundaries match |
| The block boundary is off by a few days at the edges | Medium | Boundaries are visible in the data (first Friday 2023-10-27, last Friday 2025-08-01); treat edges as ±1 week and document |
| Re-running feature engineering changes every downstream artifact | Medium | Expected and desirable; Stage 3 regenerates them anyway. Do not patch artifacts. |
| `Date` becomes non-monotonic if the shift is applied after the merge | Low | Apply before `set_index`/`sort_index` (line 152–154), then sort |
| Duplicate dates if a shifted row collides with an unshifted one | Low | Assert `df.index.is_unique` after the shift |

---

## 14. Numbers that would change if the fix is applied

**No headline number changes.** The fix corrects the *date labels* of 503 rows; it does not change any price. Consequences:

| Claim | Where | Changes? |
|---|---|---|
| Weekday distribution | audit §2, `docs/PLAN.md:25`, `docs/STATE.md:72` | **Already wrong in the audit** — must be replaced regardless of the fix (§5) |
| 1,424 rows / 1,394 processed rows | `docs/STATE.md:51-52`, `docs/AUDIT_REPORT.md` | **No** — row count is unaffected by re-dating |
| Date range 2021-06-14 → 2026-06-13 | README, audit | **No** — endpoints are outside the block |
| Split sizes 976/209/209, 180 test windows | audit §5 | **No** — same row count, same split points |
| Test metrics (R² 0.9717, RMSE 4.84M, MAPE 1.70%) | `logs/test_metrics.json`, README:145 | **Yes, if retrained.** The test rows are unchanged but the model would be trained on corrected data. The numbers in `logs/` are frozen artifacts and would not be reproducible against a retrained model. |
| Backtest −12.03% / Sharpe −7.36 | `trading_bot/outputs/backtest_metrics.json` | **Yes, if re-run** — the backtest trades on the date axis |
| "Price Range ~10.7M–11.6M Toman" | `README.md:92` | **Yes, on the unit alone** (10× error), independent of the date fix |
| Every "Toman" label | README, `src/api/main.py:57`, `src/train_pipeline.py:203`, `src/model_evaluator.py:210` | **Yes, on the unit alone** |

The date fix and the unit fix are independent. The unit fix changes far more published text.

---

## 15. Contradictions with `docs/AUDIT_REPORT.md`

Per D6, these are escalated rather than silently resolved.

1. **The audit's weekday table is mislabelled.** `docs/AUDIT_REPORT.md` reports `Fri 237 · Sat 236 · Sun 241 · Mon 243 · Tue 240 · Wed 137 · Thu 90` and builds a finding on it. The correct mapping is `Sat 237 · Sun 236 · Mon 241 · Tue 243 · Wed 240 · Thu 137 · Fri 90`. The counts are right; the labels are rotated by one weekday. This is reproduced exactly by an off-by-one label list (§5). **The audit's central data-quality finding is an artefact of its own analysis.** The observation itself — that a Sat–Wed market *would* be consistent with these counts — is correct in spirit; it just does not describe this dataset.
2. **The audit did not detect the 2023-10 → 2025-08 block.** A 35.3% sub-period with a different weekly shape, present in both source series with identical boundaries, is a larger defect than the one the audit reported. It is not mentioned.
3. **The audit's unit finding is confirmed but under-stated.** "Data is Rial, labeled Toman throughout (10× error)" is correct (§10). The additional detail — that the Rial value equals the 18k/ounce/USD identity to 1.0% median, i.e. the *values* are not merely plausible but exactly right — was not established there.
4. **`docs/STATE.md:72`** states the weekday distribution is "audit-reported, not re-derived". It has now been re-derived and is wrong as printed. Corrected in this stage.

No contradiction was found in the audit's account of the loader, the merge, the ffill or the model inputs.

---

## 16. Deviations from `docs/PLAN.md`

`docs/PLAN.md:48` lists `scripts/audit_calendar.py` as a Stage 1 deliverable. The owner's Stage 1 instruction restricted new files to `docs/DATA_INTEGRITY.md` plus updates to `STATE.md` and `DECISIONS.md`, so **no script was committed**. Every figure above was produced by a command run in this session; the commands are inlined in each section and the scratch scripts live in `/tmp/s1` (`analyze.py`, `impact.py`). If a committed, runnable audit script is wanted, it belongs in Stage 2 with the rest of `scripts/`.

The plan's acceptance criterion `grep -c '^|' docs/DATA_INTEGRITY.md ≥ 8` is satisfied (§11, §13.3, §14 alone exceed it).

---

## 17. Reproduction

All commands assume the repo root and `.venv/bin/python` (Python 3.12.3). Nothing writes to the repo.

```bash
# weekday histogram of the merged dataset
.venv/bin/python -c "import pandas as pd; d=pd.read_csv('data/raw/final_gold_dataset.csv',index_col='Date',parse_dates=True); print(d.index.day_name().value_counts())"

# reproduce the audit's mislabelled table
.venv/bin/python -c "import pandas as pd; c=pd.read_csv('data/raw/final_gold_dataset.csv',index_col='Date',parse_dates=True).index.dayofweek.value_counts().sort_index(); print(dict(zip(['Sunday','Monday','Tuesday','Wednesday','Thursday','Friday','Saturday'],c.values)))"

# raw response structure
.venv/bin/python -c "import json; d=json.load(open('api_layer/cache/raw_response_20260207_130227.json')); print(d['url'], len(d['data']['data']), d['data']['data'][0])"

# full analysis (re-fetches both TGJU series and both Yahoo series into /tmp/s1)
python /tmp/s1/analyze.py
python /tmp/s1/impact.py
```

The scratch scripts are not part of the repository and will not survive a reboot; their output is quoted verbatim in this document.
