"""Unit tests for the reversible TGJU block date correction (decision D19).

The correction relabels rows dated 2023-10-27 .. 2025-08-06 by +1 day. These
tests use synthetic frames only, so they run without network access or raw data.
"""
from datetime import date

import pandas as pd
import pytest

from config.settings import config
from src.data_loader import apply_block_date_shift

WINDOW_START = date(2023, 10, 27)
WINDOW_END = date(2025, 8, 6)


def _frame(dates):
    """Build a frame shaped like the loader's output (Date is datetime.date)."""
    return pd.DataFrame(
        {
            'Date': pd.to_datetime(pd.Series(dates)).dt.date,
            'Gold_IRR': [float(i) for i in range(len(dates))],
        }
    )


def _shift(dates, enabled=True):
    out, n = apply_block_date_shift(
        _frame(dates), WINDOW_START, WINDOW_END, days=1, enabled=enabled
    )
    return list(out['Date']), n, out


def test_config_defaults_are_the_verified_window():
    assert config.data.DATE_SHIFT_ENABLED is True
    assert config.data.DATE_SHIFT_WINDOW_START == WINDOW_START
    assert config.data.DATE_SHIFT_WINDOW_END == WINDOW_END
    assert config.data.DATE_SHIFT_DAYS == 1


def test_relabels_exactly_the_rows_inside_the_window():
    dates = [
        date(2023, 10, 20),  # before
        date(2023, 10, 27),  # first day of window
        date(2024, 6, 3),    # inside
        date(2025, 8, 6),    # last day of window
        date(2025, 8, 10),   # after (2025-08-07 is absent from the source)
    ]
    out_dates, n, out = _shift(dates)

    assert n == 3
    assert out_dates == [
        date(2023, 10, 20),
        date(2023, 10, 28),
        date(2024, 6, 4),
        date(2025, 8, 7),
        date(2025, 8, 10),
    ]
    # Prices must not move.
    assert list(out['Gold_IRR']) == [0.0, 1.0, 2.0, 3.0, 4.0]


def test_flag_off_leaves_the_frame_unchanged():
    dates = [date(2023, 10, 26), date(2024, 1, 1), date(2025, 8, 6)]
    original = _frame(dates)
    out, n = apply_block_date_shift(
        original, WINDOW_START, WINDOW_END, days=1, enabled=False
    )

    assert n == 0
    assert out is original  # returned untouched, not a copy
    assert list(out['Date']) == dates


def test_row_count_is_unchanged_and_dates_stay_unique():
    # A realistic contiguous run that ends on the window's last day. The real
    # source has no row dated 2025-08-07, which is why the shift is collision-free.
    dates = list(pd.date_range('2023-10-20', '2025-08-06').date) + [
        date(2025, 8, 10),
        date(2025, 8, 11),
    ]
    out_dates, n, out = _shift(dates)

    assert n == sum(1 for d in dates if WINDOW_START <= d <= WINDOW_END)
    assert len(out) == len(dates)
    assert len(set(out_dates)) == len(out_dates)
    assert out['Date'].is_unique


def test_first_and_last_rows_and_the_days_around_them():
    # Day before the window: untouched.
    before, n_before, _ = _shift([date(2023, 10, 26)])
    assert before == [date(2023, 10, 26)] and n_before == 0

    # First day of the window: moved exactly one day.
    first, n_first, _ = _shift([date(2023, 10, 27)])
    assert first == [date(2023, 10, 28)] and n_first == 1

    # Last day of the window: moved exactly one day.
    last, n_last, _ = _shift([date(2025, 8, 6)])
    assert last == [date(2025, 8, 7)] and n_last == 1

    # Day after the window: untouched (tested alone to avoid a synthetic collision).
    after, n_after, _ = _shift([date(2025, 8, 7)])
    assert after == [date(2025, 8, 7)] and n_after == 0


def test_collision_is_refused_instead_of_silently_duplicating():
    # 2025-08-07 does not exist in the real source; if it ever appears, the
    # shift must fail loudly rather than corrupt the merge.
    dates = [date(2025, 8, 6), date(2025, 8, 7)]
    with pytest.raises(ValueError, match="duplicate"):
        _shift(dates)
