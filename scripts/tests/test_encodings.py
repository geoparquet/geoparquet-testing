"""Conformance: data/encodings/."""

import json
from pathlib import Path

import pyarrow.parquet as pq
import pytest

from gpqgen.paths import DATA_DIR

ENCODINGS_DIR = DATA_DIR / "encodings"

GEOMETRY_TYPES = [
    "point",
    "linestring",
    "polygon",
    "multipoint",
    "multilinestring",
    "multipolygon",
]


@pytest.mark.parametrize("gt", GEOMETRY_TYPES)
@pytest.mark.parametrize("enc", ["native-geometry"])
def test_encoding_file_exists(gt: str, enc: str):
    assert (ENCODINGS_DIR / f"{gt}-{enc}.parquet").exists()


@pytest.mark.parametrize("gt", GEOMETRY_TYPES)
@pytest.mark.parametrize("enc", ["native-geometry"])
def test_encoding_file_has_geo_metadata(gt: str, enc: str):
    pf = pq.ParquetFile(ENCODINGS_DIR / f"{gt}-{enc}.parquet")
    meta = pf.schema_arrow.metadata or {}
    assert b"geo" in meta
    geo = json.loads(meta[b"geo"])
    assert geo["primary_column"] == "geometry"
    assert geo["columns"]["geometry"]["encoding"] == "WKB"
