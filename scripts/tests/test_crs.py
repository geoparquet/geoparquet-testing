"""Conformance: data/crs/."""

import json
from pathlib import Path

import pyarrow.parquet as pq
import pytest

from gpqgen.paths import DATA_DIR

CRS_DIR = DATA_DIR / "crs"

EXPECTED_FILES = [
    "crs-default.parquet",
    "crs-ogc-crs84.parquet",
    "crs-epsg-4326.parquet",
    "crs-epsg-3857.parquet",
    "crs-projjson-full.parquet",
]


@pytest.mark.parametrize("fname", EXPECTED_FILES)
def test_crs_file_exists(fname: str):
    assert (CRS_DIR / fname).exists()


def _geo(fname: str) -> dict:
    pf = pq.ParquetFile(CRS_DIR / fname)
    return json.loads(pf.schema_arrow.metadata[b"geo"])


def test_default_has_no_crs_field():
    geo = _geo("crs-default.parquet")
    assert "crs" not in geo["columns"]["geometry"], (
        "crs-default.parquet must OMIT the crs field — readers default to OGC:CRS84"
    )


def test_ogc_crs84_uses_ogc_authority():
    geo = _geo("crs-ogc-crs84.parquet")
    crs = geo["columns"]["geometry"]["crs"]
    assert crs["id"]["authority"] == "OGC"
    assert str(crs["id"]["code"]) == "CRS84"


def test_epsg_4326_uses_epsg_authority():
    geo = _geo("crs-epsg-4326.parquet")
    crs = geo["columns"]["geometry"]["crs"]
    assert crs["id"]["authority"] == "EPSG"
    assert int(crs["id"]["code"]) == 4326


def test_epsg_3857_uses_epsg_projected():
    geo = _geo("crs-epsg-3857.parquet")
    crs = geo["columns"]["geometry"]["crs"]
    assert crs["id"]["authority"] == "EPSG"
    assert int(crs["id"]["code"]) == 3857
    assert crs["type"] == "ProjectedCRS"


def test_projjson_full_has_no_id():
    geo = _geo("crs-projjson-full.parquet")
    crs = geo["columns"]["geometry"]["crs"]
    assert "id" not in crs, "projjson-full must NOT include an `id` field — full inline PROJJSON only"
    assert "type" in crs
