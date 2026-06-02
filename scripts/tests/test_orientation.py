"""Conformance: data/orientation/."""

import json

import pyarrow.parquet as pq

from gpqgen.paths import DATA_DIR

OR_DIR = DATA_DIR / "orientation"


def _geo(name: str) -> dict:
    pf = pq.ParquetFile(OR_DIR / name)
    return json.loads(pf.schema_arrow.metadata[b"geo"])


def test_ccw_file_declares_counterclockwise():
    geo = _geo("polygon-ccw.parquet")
    assert geo["columns"]["geometry"]["orientation"] == "counterclockwise"


def test_cw_file_omits_orientation():
    geo = _geo("polygon-cw.parquet")
    assert "orientation" not in geo["columns"]["geometry"], (
        "polygon-cw.parquet should not declare orientation — its rings are CW (the "
        "default is undefined per spec, and a CW-declaring `orientation` value does "
        "not exist; the spec only allows omitted or `counterclockwise`)"
    )
