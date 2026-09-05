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


# Section anchors in format-specs/geoparquet.md. Every `spec_clause` must point
# at one of these: a link into a section that does not exist tells a downstream
# implementer nothing, and the manifest is the corpus's machine-readable contract.
# Six entries had rotted to `#winding-order`, `#version` and `#wkb-encoding`
# before this list existed. Update it when the spec gains or renames a section.
SPEC_ANCHORS = frozenset(
    {
        "additional-information",
        "bbox",
        "column-metadata",
        "coordinate-axis-order",
        "crs",
        "crs-parquet-property",
        "edges",
        "encoding",
        "epoch",
        "feature-identifiers",
        "file-extension",
        "file-metadata",
        "geometry-columns",
        "geometry_types",
        "geoparquet-specification",
        "media-type",
        "metadata",
        "nesting",
        "ogccrs84-details",
        "orientation",
        "overview",
        "repetition",
        "version-and-schema",
        "version-compatibility",
    }
)

SPEC_URL = "https://github.com/opengeospatial/geoparquet/blob/main/format-specs/geoparquet.md"


def test_spec_clauses_point_at_a_real_section():
    entries = json.loads(MANIFEST.read_text())
    for fname, entry in entries.items():
        clause = entry["spec_clause"]
        base, _, anchor = clause.partition("#")
        assert base == SPEC_URL, f"{fname}: spec_clause points outside the spec: {clause}"
        assert anchor, f"{fname}: spec_clause has no section anchor: {clause}"
        assert anchor in SPEC_ANCHORS, (
            f"{fname}: spec_clause anchor #{anchor} is not a section of the spec "
            f"(known: {', '.join(sorted(SPEC_ANCHORS))})"
        )
