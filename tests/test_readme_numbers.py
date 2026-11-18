"""The README must not drift from results/*.json.

Every number wrapped in a marked block is re-read from the committed JSON.
See scripts/check_readme_numbers.py for the convention.
"""
from pathlib import Path

from scripts.check_readme_numbers import README, check_readme


def test_readme_marked_numbers_match_results():
    count, failures = check_readme()
    assert count >= 20, f"expected at least 20 marked numbers, found {count}"
    assert not failures, "README numbers drifted:\n" + "\n".join(failures)


def test_readme_exists():
    assert Path(README).is_file()
