"""Tests for gpqgen helpers."""

import json

from gpqgen.metadata import GEOPARQUET_VERSION, make_geo_metadata, metadata_bytes


def test_make_geo_metadata_defaults():
    meta = make_geo_metadata()
    assert meta["version"] == GEOPARQUET_VERSION
    assert meta["primary_column"] == "geometry"
    assert "geometry" in meta["columns"]
    assert meta["columns"]["geometry"]["encoding"] == "WKB"


def test_metadata_bytes_is_deterministic():
    meta = {
        "version": "2.0.0-dev",
        "primary_column": "geometry",
        "columns": {"geometry": {"encoding": "WKB", "geometry_types": ["Point"]}},
    }
    a = metadata_bytes(meta)
    b = metadata_bytes(meta)
    assert a == b
    # sorted keys -> 'columns' comes before 'primary_column'
    parsed = json.loads(a)
    assert list(parsed.keys()) == sorted(parsed.keys())
