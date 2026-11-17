#!/usr/bin/env python3
"""Verify the numbers marked in README.md against ``results/*.json``.

Convention (documented in docs/RELEASE_PLAN.md):

    <!-- num:eval_V2.holdout.lstm_stationary.rmse -->0.026543<!-- /num -->
    <!-- num:pct@backtest.strategies.C2.S2.total_return -->+1.13%<!-- /num -->

* ``<file>.<dotted.path>`` reads ``results/<file>.json``.
* Optional transform before ``@``: ``raw`` (default), ``pct``, ``pct4``, ``bp``,
  ``int``.
* The printed text may carry ``%``, ``+`` and thousands separators; the
  comparison tolerance is half a unit in the last printed digit.

A marked block that does not resolve, does not parse, or disagrees with the
JSON fails the check. Run with no arguments; exits 1 on any failure.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
RESULTS_DIR = ROOT / "results"

BLOCK_RE = re.compile(
    r"<!--\s*num:([A-Za-z0-9_.@-]+)\s*-->\s*([^<]*?)\s*<!--\s*/num\s*-->"
)

TRANSFORMS = {
    "raw": (1.0, 0),
    "pct": (100.0, 2),
    "pct4": (100.0, 4),
    "bp": (10000.0, 2),
    "int": (1.0, 0),
}

MIN_BLOCKS = 20


class CheckError(Exception):
    """A marked block cannot be verified."""


def _lookup(key: str) -> Tuple[float, str, int]:
    """Return (expected value, transform, default decimals) for a marked key."""
    transform = "raw"
    spec = key
    if "@" in spec:
        transform, spec = spec.split("@", 1)
    if transform not in TRANSFORMS:
        raise CheckError(f"unknown transform {transform!r}")
    factor, decimals = TRANSFORMS[transform]

    if "." not in spec:
        raise CheckError("key must be <file>.<dotted.path>")
    file_stem, path = spec.split(".", 1)
    path_file = RESULTS_DIR / f"{file_stem}.json"
    if not path_file.exists():
        raise CheckError(f"results file not found: {path_file.relative_to(ROOT)}")
    with open(path_file, "r", encoding="utf-8") as f:
        node: Any = json.load(f)
    for part in path.split("."):
        if isinstance(node, list):
            node = node[int(part)]
        elif isinstance(node, dict):
            if part not in node:
                raise CheckError(f"path not found in {path_file.name}: {path}")
            node = node[part]
        else:
            raise CheckError(f"cannot descend into {type(node).__name__} at {part!r}")
    if isinstance(node, bool) or not isinstance(node, (int, float)):
        raise CheckError(f"value at {path} is not numeric: {node!r}")
    return float(node) * factor, transform, decimals


def _parse_display(text: str, transform: str) -> Tuple[float, int]:
    cleaned = text.strip().replace(",", "").replace("%", "").replace("+", "")
    cleaned = cleaned.replace("\u2212", "-")  # unicode minus
    try:
        value = float(cleaned)
    except ValueError as exc:
        raise CheckError(f"cannot parse displayed value {text!r}") from exc
    if transform == "int":
        if value != int(value):
            raise CheckError(f"int block displays a non-integer: {text!r}")
        return value, 0
    if "." in cleaned:
        decimals = len(cleaned.split(".")[1])
    else:
        decimals = 0
    return value, decimals


def check_readme(readme: Path = README) -> Tuple[int, List[str]]:
    """Return (number of blocks checked, list of failure messages)."""
    if not readme.exists():
        return 0, [f"{readme.name} does not exist"]
    text = readme.read_text(encoding="utf-8")
    matches = list(BLOCK_RE.finditer(text))
    failures: List[str] = []
    seen: Dict[str, str] = {}
    for match in matches:
        key, display = match.group(1), match.group(2)
        try:
            expected, transform, _ = _lookup(key)
            got, decimals = _parse_display(display, transform)
            tolerance = 0.5 * (10 ** -decimals) + 1e-12
            if abs(got - expected) > tolerance:
                failures.append(
                    f"{key}: README shows {display!r} ({got:g}), results say "
                    f"{expected:g} (diff {abs(got - expected):.3g}, tol {tolerance:g})"
                )
            seen[key] = display
        except CheckError as exc:
            failures.append(f"{key}: {exc}")
    if len(matches) < MIN_BLOCKS:
        failures.append(
            f"only {len(matches)} marked blocks found; expected at least {MIN_BLOCKS}"
        )
    return len(matches), failures


def main() -> int:
    count, failures = check_readme()
    if failures:
        print(f"README number check FAILED ({len(failures)} problem(s)):")
        for line in failures:
            print(f"  - {line}")
        return 1
    print(f"README number check passed: {count} marked numbers match results/*.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
