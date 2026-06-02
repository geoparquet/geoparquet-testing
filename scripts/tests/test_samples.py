"""Realistic tier: samples/."""

import json
from pathlib import Path

import pyarrow.parquet as pq
import pytest

from gpqgen.paths import SAMPLES_DIR

# Expected sample filenames. Generators below produce these; if a sample is
# skipped (license, missing source), remove its entry here too.
# NOTE: flight-routes-great-circle.parquet is deferred (native-geography logical
# type not yet supported by the toolchain) — see docs/superpowers/plans/2026-06-01-geography-logical-type-deferred.md
# NOTE: nz-building-outlines.parquet is deferred (needs a LINZ Data Service API
# key) — see plan Task 4.2.a and the "Deferred samples" note in samples/README.md.
EXPECTED = [
    "us-states.parquet",
    "airports-global.parquet",
    "australia-gnss-stations.parquet",
    "australia-gnss-stations-2024.parquet",
    "buildings-with-centroid.parquet",
    "gps-trajectory-xyzm.parquet",
    "bathymetry-contours.parquet",
]


@pytest.mark.parametrize("fname", EXPECTED)
def test_sample_exists(fname: str):
    assert (SAMPLES_DIR / fname).exists()


@pytest.mark.parametrize("fname", EXPECTED)
def test_sample_under_size_budget(fname: str):
    p = SAMPLES_DIR / fname
    if not p.exists():
        pytest.skip("file not yet generated")
    assert p.stat().st_size <= 5 * 1024 * 1024, f"{fname} exceeds 5 MB budget"


@pytest.mark.parametrize("fname", EXPECTED)
def test_sample_has_geo_metadata(fname: str):
    p = SAMPLES_DIR / fname
    if not p.exists():
        pytest.skip("file not yet generated")
    pf = pq.ParquetFile(p)
    meta = pf.schema_arrow.metadata or {}
    assert b"geo" in meta
    geo = json.loads(meta[b"geo"])
    assert geo["primary_column"] in geo["columns"]
