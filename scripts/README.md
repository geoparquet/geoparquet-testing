# scripts

Generators for the `data/`, `samples/`, and `bad_data/` tiers.

## Setup

Requires [`uv`](https://docs.astral.sh/uv/).

```bash
cd scripts
uv sync --all-extras
```

## Run

```bash
uv run python generate_all.py            # regenerate everything
uv run python gen_encodings.py           # one category
uv run python gen_samples.py --only flight_routes   # one sample
```

The pyarrow generators are deterministic: re-running produces byte-identical output
(CI enforces this). The sedonadb-backed files (`*-native-geography.parquet` and the
non-CRS84 files stamped by `gen_native_crs.py`) are committed snapshots instead — see
below.

## Tests

```bash
uv run pytest tests/ -v
```

## sedonadb tier (native Geography + non-CRS84 native CRS)

Two things in this corpus can only be written by [Apache sedonadb](https://github.com/apache/sedona),
the one tool in our stack that emits the Parquet native Geography logical type and can
write a custom CRS onto the native `GEOMETRY`/`GEOGRAPHY` logical type:

1. **`gen_geography.py`** — the 6 `data/encodings/*-native-geography.parquet` files
   (native Geography logical type, spherical edges) and the
   `samples/flight-routes-great-circle.parquet` sample (long-haul great-circle routes).
2. **`gen_native_crs.py`** — stamps the real native CRS (inline PROJJSON, via
   `ST_SetSRID`) onto the files whose CRS is not OGC:CRS84
   (`data/crs/crs-epsg-3857.parquet`, `data/epoch/*.parquet`,
   `data/multi_geometry/two-geom-columns-different-crs.parquet`, and the samples
   `us-states`, `australia-gnss-stations*`, `buildings-3d`). Our pyarrow toolchain can
   only write the CRS84 default onto the native type, which would conflict with those
   files' `geo` metadata CRS. It also promotes the two geopandas-written samples
   (`buildings-3d`, `bathymetry-contours`) from plain `BYTE_ARRAY` to the native type.

sedonadb is a heavy, generation-only dependency (a ~50 MB wheel needed by nobody else in
the pipeline), so it is **not** part of `scripts/pyproject.toml` / `uv.lock`; install it
into a separate environment. `gen_native_crs.py` reads the base files the pyarrow
generators produce, so run it **after** `generate_all.py`:

```bash
python3 -m venv .venv-geography
.venv-geography/bin/pip install apache-sedona
.venv-geography/bin/pip install "sedonadb==0.4.0"
.venv-geography/bin/pip install pyproj   # for the flight_routes great-circle sample
.venv-geography/bin/python gen_geography.py
.venv-geography/bin/python gen_native_crs.py
```

These files are committed **snapshots**: CI does not byte-diff them (sedonadb isn't
installed in CI); the pytest suite validates them instead. Pinned tooling matters for
byte-stability — apache-sedona 1.9.0 / sedonadb 0.4.0 (bundled datafusion 52.5.0).
The regular repo env (`uv`) can *read* these logical types but cannot *write* them,
so all tests run in the regular env; only generation needs the sedonadb env.

