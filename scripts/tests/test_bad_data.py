"""Negative tier: bad_data/."""

import json
from pathlib import Path

import pyarrow.parquet as pq
import pytest

from gpqgen.paths import BAD_DATA_DIR

MANIFEST = BAD_DATA_DIR / "manifest.json"


def test_manifest_exists():
    assert MANIFEST.exists()


def test_manifest_entries_have_required_keys():
    entries = json.loads(MANIFEST.read_text())
    for fname, entry in entries.items():
        assert set(entry.keys()) >= {"violation", "spec_clause", "expected_failure"}
        assert (BAD_DATA_DIR / fname).exists(), f"manifest lists {fname} but file is missing"


def test_no_orphan_bad_files():
    """Every .parquet in bad_data/ is listed in the manifest."""
    entries = json.loads(MANIFEST.read_text())
    for p in BAD_DATA_DIR.glob("*.parquet"):
        assert p.name in entries, f"{p.name} present but not in manifest.json"


def test_all_files_open():
    """Bad files must still be valid Parquet at the container level — the violation
    is in geometry/metadata semantics, not Parquet structure."""
    entries = json.loads(MANIFEST.read_text())
    for fname in entries:
        # `metadata_invalid_utf8` and similar may still open as Parquet — the
        # violation is in the geo key, not the file structure.
        pq.ParquetFile(BAD_DATA_DIR / fname)
