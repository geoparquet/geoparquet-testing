"""For every .parquet under data/ and samples/, validate the `geo` metadata
against the GeoParquet 2.0-dev JSON Schema (with the PROJJSON crs $ref resolved
from a vendored local copy).

All `crs` values in the corpus are full PROJJSON v0.7 objects (with `name` and
all required fields), generated once via pyproj and hard-coded in gpqgen.crs, so
every file validates cleanly.
"""

import json
from pathlib import Path

import pyarrow.parquet as pq
import pytest
from jsonschema import Draft7Validator
from referencing import Registry, Resource

from gpqgen.paths import DATA_DIR, SAMPLES_DIR

SCHEMA_DIR = Path(__file__).resolve().parent.parent / "schemas"
GEO_SCHEMA_PATH = SCHEMA_DIR / "geoparquet-2.0.0-dev.schema.json"
PROJJSON_SCHEMA_PATH = SCHEMA_DIR / "projjson-0.7.schema.json"


def _registry() -> Registry:
    projjson = json.loads(PROJJSON_SCHEMA_PATH.read_text())
    # The geoparquet schema $refs the projjson schema by its canonical URI.
    # Register the vendored copy under that exact URI so resolution is offline.
    proj_uri = projjson.get("$id") or "https://proj.org/schemas/v0.7/projjson.schema.json"
    return Registry().with_resource(proj_uri, Resource.from_contents(projjson))


def _validator() -> Draft7Validator:
    schema = json.loads(GEO_SCHEMA_PATH.read_text())
    return Draft7Validator(schema, registry=_registry())


def _all_valid_parquets() -> list[Path]:
    paths = list(DATA_DIR.rglob("*.parquet")) + list(SAMPLES_DIR.glob("*.parquet"))
    return sorted(paths)


@pytest.mark.parametrize(
    "path",
    _all_valid_parquets(),
    ids=lambda p: str(p.relative_to(p.parents[1])),
)
def test_geo_metadata_valid_against_schema(path: Path):
    pf = pq.ParquetFile(path)
    meta = pf.schema_arrow.metadata or {}
    assert b"geo" in meta, f"{path} has no geo metadata"
    geo = json.loads(meta[b"geo"])

    errors = sorted(_validator().iter_errors(geo), key=lambda e: list(e.path))
    assert not errors, f"{path}: {[e.message for e in errors]}"
