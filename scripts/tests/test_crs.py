"""Conformance: data/crs/."""

import json
from pathlib import Path

import pyarrow.parquet as pq
import pytest

from gpqgen.paths import DATA_DIR, SAMPLES_DIR

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


def _all_corpus_parquets() -> list[Path]:
    paths = list(DATA_DIR.rglob("*.parquet")) + list(SAMPLES_DIR.glob("*.parquet"))
    return sorted(paths)


@pytest.mark.parametrize("path", _all_corpus_parquets(), ids=lambda p: p.name)
def test_geo_crs_is_projjson_or_absent(path: Path):
    """Every geo `crs` must be inline PROJJSON (object with `type`) — never a bare
    authority:code string. Codifies the GeoParquet 2.0 rule that the geo metadata
    crs is PROJJSON-or-null only (the authority:code form lives on the Parquet
    native logical type, not here)."""
    meta = pq.ParquetFile(path).schema_arrow.metadata or {}
    if b"geo" not in meta:
        pytest.skip("no geo metadata")
    geo = json.loads(meta[b"geo"])
    for name, col in geo.get("columns", {}).items():
        if "crs" not in col:
            continue
        crs = col["crs"]
        if crs is None:
            continue
        assert isinstance(crs, dict), f"{path.name}:{name} crs must be PROJJSON object or null, got {type(crs).__name__}"
        assert "type" in crs, f"{path.name}:{name} crs must be full PROJJSON (missing `type`)"
