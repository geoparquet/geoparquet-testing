# Changelog

All notable changes to the geoparquet-testing corpus are recorded here.

## [Unreleased]

### Added
- Initial three-tier corpus targeting GeoParquet 2.0-dev: `data/` (conformance), `samples/` (realistic), `bad_data/` (negative).
- `bad_data/manifest.json` as a machine-readable contract for downstream tools.
- Self-test suite: per-tier invariants, cross-cutting JSON Schema validation (with vendored GeoParquet 2.0-dev + PROJJSON schemas), and README index hygiene.
- GitHub Actions CI: byte-stable regeneration of the deterministic tiers, schema validity, README hygiene, and the 5 MB sample budget.
- `data/encodings/` native-geography variants (6 files, one per geometry type) carrying the Parquet native Geography logical type with spherical edges — generated via Apache sedonadb (the only tool in our stack that emits that logical type).

### Deferred
- `flight-routes` native-geography sample — pending toolchain integration for the Parquet native Geography logical type at sample scale.
- `samples/nz-building-outlines` — requires a LINZ Data Service API key.

### Notes
- All CRS metadata uses full PROJJSON; `geo` metadata uses `version: "2.0-dev"` and the `epoch` field, matching the official GeoParquet 2.0-dev schema.
