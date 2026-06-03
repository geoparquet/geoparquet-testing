# Changelog

All notable changes to the geoparquet-testing corpus are recorded here.

## [Unreleased]

### Added
- Initial three-tier corpus targeting GeoParquet 2.0-dev: `data/` (conformance), `samples/` (realistic), `bad_data/` (negative).
- `bad_data/manifest.json` as a machine-readable contract for downstream tools.
- Self-test suite: per-tier invariants, cross-cutting JSON Schema validation (with vendored GeoParquet 2.0-dev + PROJJSON schemas), and README index hygiene.
- GitHub Actions CI: byte-stable regeneration of the deterministic tiers, schema validity, README hygiene, and the 5 MB sample budget.

### Deferred
- Native-geography logical-type files (encodings geography variants, `flight-routes` sample) — pending toolchain support for the Parquet native Geography logical type.
- `samples/nz-building-outlines` — requires a LINZ Data Service API key.

### Notes
- All CRS metadata uses full PROJJSON; `geo` metadata uses `version: "2.0-dev"` and the `epoch` field, matching the official GeoParquet 2.0-dev schema.
