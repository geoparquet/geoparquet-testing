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


def _geometry_logical_type(path: Path) -> str:
    pf = pq.ParquetFile(path)
    gi = pf.schema_arrow.names.index("geometry")
    return pf.schema.column(gi).logical_type.to_json()


@pytest.mark.parametrize("gt", GEOMETRY_TYPES)
@pytest.mark.parametrize("enc", ["native-geometry", "native-geography"])
def test_encoding_file_exists(gt: str, enc: str):
    assert (ENCODINGS_DIR / f"{gt}-{enc}.parquet").exists()


@pytest.mark.parametrize("gt", GEOMETRY_TYPES)
@pytest.mark.parametrize("enc", ["native-geometry", "native-geography"])
def test_encoding_file_has_geo_metadata(gt: str, enc: str):
    pf = pq.ParquetFile(ENCODINGS_DIR / f"{gt}-{enc}.parquet")
    meta = pf.schema_arrow.metadata or {}
    assert b"geo" in meta
    geo = json.loads(meta[b"geo"])
    assert geo["primary_column"] == "geometry"
    assert geo["columns"]["geometry"]["encoding"] == "WKB"


@pytest.mark.parametrize("gt", GEOMETRY_TYPES)
def test_geography_has_spherical_edges(gt: str):
    pf = pq.ParquetFile(ENCODINGS_DIR / f"{gt}-native-geography.parquet")
    geo = json.loads(pf.schema_arrow.metadata[b"geo"])
    assert geo["columns"]["geometry"]["edges"] == "spherical"


@pytest.mark.parametrize("gt", GEOMETRY_TYPES)
def test_geometry_files_have_geometry_logical_type(gt: str):
    path = ENCODINGS_DIR / f"{gt}-native-geometry.parquet"
    assert _geometry_logical_type(path) == '{"Type": "Geometry"}'


@pytest.mark.parametrize("gt", GEOMETRY_TYPES)
def test_geography_files_have_native_geography_logical_type(gt: str):
    path = ENCODINGS_DIR / f"{gt}-native-geography.parquet"
    assert _geometry_logical_type(path) == '{"Type": "Geography"}'
