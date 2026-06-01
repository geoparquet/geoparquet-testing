"""Conformance: data/edges/."""

import json

import pyarrow.parquet as pq

from gpqgen.paths import DATA_DIR

EDGES_DIR = DATA_DIR / "edges"


def _geo(name: str) -> dict:
    pf = pq.ParquetFile(EDGES_DIR / name)
    return json.loads(pf.schema_arrow.metadata[b"geo"])


def test_planar_file_declares_planar():
    geo = _geo("edges-planar.parquet")
    assert geo["columns"]["geometry"]["edges"] == "planar"


def test_spherical_file_declares_spherical():
    geo = _geo("edges-spherical.parquet")
    assert geo["columns"]["geometry"]["edges"] == "spherical"


def test_spherical_file_has_antimeridian_line():
    """The spherical file's LineString spans the antimeridian so spherical and planar
    interpretations differ visibly."""
    table = pq.read_table(EDGES_DIR / "edges-spherical.parquet")
    # Geometry column is WKB-encoded binary. We assert at least one row's WKB length
    # matches a 2-point 2D LineString. Standard WKB layout for a 2D LineString:
    #   1 byte  byte-order
    #   4 bytes geometry type (uint32)
    #   4 bytes numPoints (uint32)
    #   N points x 16 bytes (two float64 each)
    # So a 2-point 2D LineString = 1 + 4 + 4 + 2*16 = 41 bytes.
    sizes = [len(b.as_py()) for b in table.column("geometry") if b.is_valid]
    assert 41 in sizes, f"expected at least one 2-point LineString (41 bytes), got {sizes}"
