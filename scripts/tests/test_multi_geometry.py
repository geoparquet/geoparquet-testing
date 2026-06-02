"""Conformance: data/multi_geometry/."""

import json

import pyarrow.parquet as pq

from gpqgen.paths import DATA_DIR

MG_DIR = DATA_DIR / "multi_geometry"


def _geo(name: str) -> dict:
    pf = pq.ParquetFile(MG_DIR / name)
    return json.loads(pf.schema_arrow.metadata[b"geo"])


def test_same_crs_file_has_two_geom_columns():
    geo = _geo("two-geom-columns-same-crs.parquet")
    assert set(geo["columns"].keys()) == {"footprint", "centroid"}
    assert geo["primary_column"] == "footprint"


def test_same_crs_file_both_columns_have_crs84():
    geo = _geo("two-geom-columns-same-crs.parquet")
    for name in ("footprint", "centroid"):
        crs = geo["columns"][name]["crs"]
        assert crs["id"]["authority"] == "OGC"


def test_different_crs_file_columns_have_different_crs():
    geo = _geo("two-geom-columns-different-crs.parquet")
    assert geo["columns"]["footprint"]["crs"]["id"]["authority"] == "OGC"
    assert geo["columns"]["centroid"]["crs"]["id"]["authority"] == "EPSG"
    assert int(geo["columns"]["centroid"]["crs"]["id"]["code"]) == 3857
