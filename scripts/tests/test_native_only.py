"""Conformance: data/native_only/ — native GEOMETRY columns without `geo` metadata."""

import json
from pathlib import Path

import pyarrow.parquet as pq
import pytest

from gpqgen.paths import BAD_DATA_DIR, DATA_DIR

NATIVE_ONLY_DIR = DATA_DIR / "native_only"
FILES = {
    "native-only-geometry.parquet": ["geometry"],
    "native-only-two-columns.parquet": ["footprint", "centroid"],
}


def _geometry_columns(path: Path) -> list[str]:
    schema = pq.read_metadata(path).schema
    cols = []
    for i in range(len(schema)):
        lt = json.loads(schema.column(i).logical_type.to_json())
        if lt.get("Type") in ("Geometry", "Geography"):
            cols.append(schema.column(i).path)
    return cols


@pytest.mark.parametrize("fname", sorted(FILES))
def test_native_only_has_native_types_and_no_geo(fname: str):
    path = NATIVE_ONLY_DIR / fname
    assert path.exists(), path
    assert b"geo" not in (pq.read_metadata(path).metadata or {})
    assert _geometry_columns(path) == FILES[fname]


def test_missing_geo_metadata_negative_has_no_native_type():
    """The negative must not be readable via the native types, or it is not a defect."""
    path = BAD_DATA_DIR / "missing-geo-metadata.parquet"
    assert b"geo" not in (pq.read_metadata(path).metadata or {})
    assert _geometry_columns(path) == []
