#!/usr/bin/env python3
"""Fetch the TGJU and Yahoo series and write ``data/raw/final_gold_dataset.csv``.

This is the only script that touches the network. It needs the development
dependencies (``yfinance`` and ``curl_cffi``), which serving does not.

Caveats, stated rather than hidden:

* TGJU's endpoint is undocumented and the scraper may break without notice.
* ``data/raw/`` is gitignored; the full series is not redistributed (D14).
* The +1 relabel of 2023-10-27 .. 2025-08-06 is applied by the loader, not by
  this script, so a fresh fetch reproduces the corrected dates.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.data_loader import DataLoader  # noqa: E402


def main() -> int:
    loader = DataLoader()
    frame = loader.fetch_data()
    if frame is None or frame.empty:
        print("Fetch failed: no data returned (see logs/training.log).", file=sys.stderr)
        return 1
    loader.save_raw_data(frame)
    print(
        f"Wrote {len(frame)} rows, {frame.index.min().date()} .. "
        f"{frame.index.max().date()} to data/raw/final_gold_dataset.csv"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
