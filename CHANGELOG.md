# Changelog

All notable changes to the geoparquet-testing corpus are recorded here.

## [Unreleased]

### Added
- Initial three-tier corpus targeting GeoParquet 2.0-dev: `data/` (conformance), `samples/` (realistic), `bad_data/` (negative).
- `bad_data/manifest.json` as a machine-readable contract for downstream tools.
- Self-test suite: per-tier invariants, cross-cutting JSON Schema validation (with vendored GeoParquet 2.0-dev + PROJJSON schemas), and README index hygiene.
- GitHub Actions CI: byte-stable regeneration of the deterministic tiers, schema validity, README hygiene, and the 5 MB sample budget.
- `data/encodings/` native-geography variants (6 files, one per geometry type) carrying the Parquet native Geography logical type with spherical edges — generated via Apache sedonadb (the only tool in our stack that emits that logical type).
- `samples/flight-routes-great-circle.parquet` — long-haul origin-destination flight routes as native Geography (great-circle paths via `pyproj.Geod`, spherical edges, OGC:CRS84), generated via Apache sedonadb alongside the encodings geography variants.
- `data/compression/` — six files holding an identical Point table, one per Parquet codec (none, snappy, gzip, brotli, lz4_raw, zstd), exercising reader codec support.
- `samples/buildings-3d.parquet` — 3D building footprints over central Delft from 3DBAG (TU Delft), POLYGON Z lifted to NAP ground elevation, in the EPSG:7415 compound CRS (RD New + NAP height).

### Changed
- Default corpus compression is now **zstd level 15** (was snappy), matching the GeoParquet `distributing-geoparquet.md` recommendation. All deterministic `data/` and `bad_data/` files were regenerated.
- `samples/bathymetry-contours.parquet` now uses **real** Natural Earth 1:10m bathymetry (depth contours over the Mariana Trench, 0 to -10000 m) instead of synthetic sine-wave lines.

### Deferred
- Native-logical-type CRS variants from GeoParquet 2.0 (`srid:0` in the Parquet metadata + `null` geo `crs`; PROJJSON geo `crs` + `authority:code` in the Parquet metadata) — blocked on tooling that can write a custom CRS string into the Parquet native GEOMETRY/GEOGRAPHY logical type.

### Notes
- All CRS metadata uses full PROJJSON; `geo` metadata uses `version: "2.0-dev"` and the `epoch` field, matching the official GeoParquet 2.0-dev schema.
