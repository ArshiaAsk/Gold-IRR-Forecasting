#!/usr/bin/env python3
"""
Reproduce the gold-vs-ounce alignment test in docs/DATA_INTEGRITY.md B2.2.

The test fixes the Iranian row set to dates that have a Yahoo ``GC=F`` bar on
both ``d`` and ``d+1``.  The Iranian gold return vector is then identical under
shift 0 and shift +1; only the ounce bar it is matched against changes.  B2.2
reports, for the block and the post-block period:

    block 2023-10-27..2025-08-06  +0.1119 -> +0.3803
    post  2025-08-07..2026-11-12  +0.3577 -> -0.1262

Two modes:

* ``--live`` fetches TGJU ``geram18`` and Yahoo ``GC=F``.  This is the mode that
  reproduces B2.2 exactly; the original scratch script used live data through
  2026-11-12.
* default (offline) reads ``--data`` and ``--global``.  The committed snapshot
  ends 2026-06-13, so it cannot reproduce the post-block period (which ends
  2026-11-12); the block period is still checked.

The script is deliberately not part of CI: it needs either the untracked local
snapshot or network access, and it is a data-quality reproduction, not a test.

Usage:
    python scripts/align_gold_ounce.py --live
    python scripts/align_gold_ounce.py --data data/raw/final_gold_dataset.csv \\
        --global data/raw/global_yahoo.csv
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
DEFAULT_DATA = REPO / "data" / "raw" / "final_gold_dataset.csv"
DEFAULT_GLOBAL = REPO / "data" / "raw" / "global_yahoo.csv"
MANIFEST = REPO / "docs" / "DATA_MANIFEST.md"

PERIODS = [
    ("pre-block", "2022-02-16", "2023-10-26"),
    ("block", "2023-10-27", "2025-08-06"),
    ("post-block", "2025-08-07", "2026-11-12"),
]
EXPECTED = {
    "block": (0.1119, 0.3803),
    "post-block": (0.3577, -0.1262),
}
TGJU_URL = "https://api.tgju.org/v1/market/indicator/summary-table-data/geram18"
YAHOO_URL = "https://query1.finance.yahoo.com/v8/finance/chart/GC=F"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _manifest_hashes() -> dict[str, str]:
    """Read the path -> SHA-256 pairs from docs/DATA_MANIFEST.md."""
    if not MANIFEST.exists():
        return {}
    text = MANIFEST.read_text(encoding="utf-8")
    pairs = {}
    for match in re.finditer(r"`(data/[^`]+)`[^\n]*?`([0-9a-f]{64})`", text):
        pairs[match.group(1)] = match.group(2)
    return pairs


def _check_hash(path: Path, label: str, strict: bool) -> None:
    try:
        key = str(path.relative_to(REPO))
    except ValueError:
        key = str(path)
    expected = _manifest_hashes().get(key, None)
    actual = _sha256(path)
    if expected is None:
        print(f"{label}: SHA-256 {actual} (not listed in docs/DATA_MANIFEST.md)")
        return
    status = "matches" if actual == expected else "DOES NOT MATCH"
    print(f"{label}: SHA-256 {actual} ({status} docs/DATA_MANIFEST.md)")
    if actual != expected and strict:
        raise SystemExit(
            f"{label} does not match docs/DATA_MANIFEST.md; refusing --strict-hash"
        )


def _clean_number(value) -> float:
    text = str(value)
    text = re.sub(r"<[^>]+>", "", text).replace(",", "").replace("%", "").strip()
    return float(text)


def _fetch_tgju_gold() -> pd.Series:
    req = urllib.request.Request(
        TGJU_URL,
        headers={
            "User-Agent": "Mozilla/5.0",
            "Referer": "https://www.tgju.org/profile/geram18/history",
            "Origin": "https://www.tgju.org",
            "Accept": "application/json",
        },
    )
    payload = json.loads(urllib.request.urlopen(req, timeout=30).read())
    rows = payload["data"]
    frame = pd.DataFrame(rows)
    if frame.shape[1] < 8:
        raise SystemExit(f"unexpected TGJU response: {frame.shape[1]} columns")
    frame = frame.iloc[:, :8]
    frame.columns = ["Open", "Low", "High", "Close", "Change", "Percent", "Date_G", "Date_J"]
    out = pd.DataFrame({
        "Date": pd.to_datetime(frame["Date_G"]),
        "Gold_IRR": frame["Close"].map(_clean_number),
    })
    out = out.dropna().sort_values("Date").drop_duplicates("Date", keep="last")
    return out.set_index("Date")["Gold_IRR"]


def _fetch_yahoo_ounce(since: date) -> pd.Series:
    period1 = int(pd.Timestamp(since, tz="UTC").timestamp())
    period2 = int((datetime.now(timezone.utc) + timedelta(days=1)).timestamp())
    url = f"{YAHOO_URL}?period1={period1}&period2={period2}&interval=1d&events=history"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    result = json.loads(urllib.request.urlopen(req, timeout=30).read())["chart"]["result"][0]
    dates = [datetime.fromtimestamp(t, timezone.utc).date() for t in result["timestamp"]]
    closes = result["indicators"]["quote"][0]["close"]
    out = pd.DataFrame({"Date": pd.to_datetime(dates), "Ounce_USD": closes}).dropna()
    out = out.sort_values("Date").drop_duplicates("Date", keep="last")
    return out.set_index("Date")["Ounce_USD"]


def _load_snapshot(data_path: Path, global_path: Path) -> tuple[pd.Series, pd.Series]:
    if not data_path.exists():
        raise SystemExit(
            f"{data_path} is missing. It is the untracked TGJU snapshot (D14).\n"
            "Use --live to fetch TGJU and Yahoo, or point --data at a local copy."
        )
    if not global_path.exists():
        raise SystemExit(
            f"{global_path} is missing. It is the cached Yahoo series (D14).\n"
            "Use --live to fetch TGJU and Yahoo, or point --global at a local copy."
        )
    gold = pd.read_csv(data_path, parse_dates=["Date"]).set_index("Date")["Gold_IRR"]
    ounce = pd.read_csv(global_path, parse_dates=["Date"]).set_index("Date")["Ounce_USD"]
    return gold.sort_index(), ounce.sort_index()


def _candidate_dates(gold: pd.Series, ounce: pd.Series) -> pd.DatetimeIndex:
    """Iranian dates with a Yahoo bar on both d and d+1 (calendar days)."""
    global_dates = set(ounce.index)
    return pd.DatetimeIndex([
        d for d in gold.index
        if d in global_dates and (d + pd.Timedelta(days=1)) in global_dates
    ])


def _correlations(gold: pd.Series, ounce: pd.Series, dates: pd.DatetimeIndex):
    gold_ret = np.log(gold).diff()
    ounce_ret = np.log(ounce).diff()
    rows0, rows1 = [], []
    for d in dates:
        rows0.append((gold_ret.get(d, np.nan), ounce_ret.get(d, np.nan)))
        rows1.append((
            gold_ret.get(d, np.nan),
            np.log(ounce.loc[d + pd.Timedelta(days=1)] / ounce.loc[d]),
        ))
    a0 = pd.DataFrame(rows0, columns=["g", "o"]).dropna()
    a1 = pd.DataFrame(rows1, columns=["g", "o"]).dropna()
    return len(a0), a0["g"].corr(a0["o"]), a1["g"].corr(a1["o"])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA,
                        help="TGJU snapshot CSV (untracked; default data/raw/final_gold_dataset.csv)")
    parser.add_argument("--global", dest="global_path", type=Path, default=DEFAULT_GLOBAL,
                        help="cached Yahoo CSV (untracked; default data/raw/global_yahoo.csv)")
    parser.add_argument("--live", action="store_true",
                        help="fetch TGJU geram18 and Yahoo GC=F (reproduces B2.2 exactly)")
    parser.add_argument("--since", default="2019-01-01",
                        help="Yahoo fetch start date in --live mode (default 2019-01-01)")
    parser.add_argument("--strict-hash", action="store_true",
                        help="exit if a snapshot file does not match docs/DATA_MANIFEST.md")
    args = parser.parse_args()

    if args.live:
        print("Mode: live fetch (TGJU geram18 + Yahoo GC=F)")
        gold = _fetch_tgju_gold()
        ounce = _fetch_yahoo_ounce(date.fromisoformat(args.since))
        source = f"live TGJU through {gold.index[-1].date()}; Yahoo through {ounce.index[-1].date()}"
    else:
        print("Mode: local snapshot")
        gold, ounce = _load_snapshot(args.data, args.global_path)
        _check_hash(args.data, str(args.data), args.strict_hash)
        _check_hash(args.global_path, str(args.global_path), args.strict_hash)
        source = (f"{args.data} through {gold.index[-1].date()}; "
                  f"{args.global_path} through {ounce.index[-1].date()}")

    candidates = _candidate_dates(gold, ounce)
    print(f"Source: {source}")
    print(f"Candidate rows: {len(candidates)} | weekday mix "
          f"{pd.Series(candidates.day_name()).value_counts().to_dict()}")
    print()
    print(f"{'period':<12} {'n':>4} {'shift 0':>9} {'shift +1':>9}  check")

    reproduced = {}
    for name, start, end in PERIODS:
        dates = candidates[(candidates >= start) & (candidates <= end)]
        n, c0, c1 = _correlations(gold, ounce, dates)
        note = ""
        if name in EXPECTED:
            e0, e1 = EXPECTED[name]
            ok = abs(c0 - e0) < 5e-5 and abs(c1 - e1) < 5e-5
            reproduced[name] = ok
            note = "reproduced" if ok else f"expected {e0:+.4f} {e1:+.4f}"
        print(f"{name:<12} {n:>4} {c0:>+9.4f} {c1:>+9.4f}  {note}")

    print()
    if args.live:
        if all(reproduced.values()):
            print("B2.2 reproduced to four decimals.")
            return 0
        print("B2.2 NOT reproduced to four decimals; see the check column.")
        return 1

    if reproduced.get("block"):
        print("Block period reproduced to four decimals from the snapshot.")
    else:
        print("Block period NOT reproduced to four decimals from the snapshot.")
    print("Post-block is not comparable: the snapshot ends "
          f"{gold.index[-1].date()}, B2.2's post-block ends 2026-11-12. "
          "Use --live for the full B2.2 reproduction.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
