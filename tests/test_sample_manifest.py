"""Pin the bundled sample's SHA-256 and, when present, the untracked data hashes."""
from __future__ import annotations

import hashlib
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SAMPLE = REPO / "data" / "sample" / "gold_sample.csv"
MANIFEST = REPO / "docs" / "DATA_MANIFEST.md"

SAMPLE_SHA256 = "8be4d408dcf62cefb9b84acb1bdf1bc9f825683f6d3eff924c328b46c554fc97"

# Untracked inputs named in docs/DATA_MANIFEST.md. Absent in a clean clone.
UNTRACKED = {
    "data/raw/final_gold_dataset.csv":
        "132992b8c455bcd793829d06fa02fca986fd41bba50c36c41cfb7cc1679176eb",
    "data/raw/global_yahoo.csv":
        "a9cc017ae4e206aa0a50f228fb18bfe56a52bbe922b45023492faad64ae3855e",
    "data/processed/advanced_gold_features.csv":
        "8ef5be530becd16a6a79d9074f10ee437e527f97fc39507b9bb53ccf4868435b",
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def test_sample_hash_is_pinned():
    assert _sha256(SAMPLE) == SAMPLE_SHA256


def test_sample_shape():
    lines = SAMPLE.read_text(encoding="utf-8").splitlines()
    assert lines[0] == "Date,Gold_IRR,USD_IRR,Ounce_USD,Oil_USD"
    assert len(lines) == 201  # header + 200 data rows
    assert lines[1].startswith("2025-10-14,")
    assert lines[-1].startswith("2026-06-13,")


def test_manifest_names_the_pinned_hashes():
    text = MANIFEST.read_text(encoding="utf-8")
    assert SAMPLE_SHA256 in text
    for sha in UNTRACKED.values():
        assert sha in text


def test_untracked_hashes_when_the_files_are_present():
    present = 0
    for relative, expected in sorted(UNTRACKED.items()):
        path = REPO / relative
        if not path.exists():
            continue
        assert _sha256(path) == expected, relative
        present += 1
    if present == 0:
        # A clean clone has none of the untracked inputs; the sample hash above
        # is still pinned and the manifest is still checked.
        return
