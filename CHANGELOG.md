# Changelog

All notable changes to the geoparquet-testing corpus are recorded here.

## [Unreleased]

### Added
- `data/bbox/`: 6-element (XYZ) and 8-element (XYZM) `bbox` positives, and an antimeridian-crossing `bbox` (`xmin > xmax`, RFC 7946 §5.2) — validators must accept all three.
- `data/orientation/`: positives for a polygon with a (clockwise) hole, a MultiPolygon, and a polygon inside a GeometryCollection, all declaring `counterclockwise`.
- `bad_data/`: `orientation-ccw-declared-hole-ccw`, `orientation-ccw-declared-multipolygon-part-cw` (orientation applies to holes and to every part), `geometry-types-duplicate-entries` (schema `uniqueItems`), `geometry-column-not-in-columns` (a native GEOMETRY column absent from `columns`; new `expected_failure` `geometry_column_undeclared`).
- Self-tests that read the geometry back and check the fixtures really have the property they claim: declared `orientation` matches the actual ring winding (exterior CCW, interior CW, recursing into MultiPolygon and GeometryCollection), every `orientation_mismatch` negative genuinely violates its own declaration, and every declared `bbox` has a spec length and encloses its coordinates (antimeridian-aware). A negative fixture that is accidentally valid is worse than no fixture, because every downstream validator records a pass for a rule it never ran.
- `test_spec_clauses_point_at_a_real_section`: every `spec_clause` in `bad_data/manifest.json` must resolve to a section that exists in the spec.
- `expected_failure` vocabulary: `primary_column_mismatch` (for `primary-column-not-in-columns`, which JSON Schema cannot express and was mislabelled `schema_validation_error`) and `geometry_column_undeclared`.
- Initial three-tier corpus targeting GeoParquet 2.0.0: `data/` (conformance), `samples/` (realistic), `bad_data/` (negative).
- `bad_data/manifest.json` as a machine-readable contract for downstream tools.
- Self-test suite: per-tier invariants, cross-cutting JSON Schema validation (with vendored GeoParquet 2.0.0 + PROJJSON schemas), and README index hygiene.
- GitHub Actions CI: byte-stable regeneration of the deterministic tiers, schema validity, README hygiene, and the 5 MB sample budget.
- `data/encodings/` native-geography variants (6 files, one per geometry type) carrying the Parquet native Geography logical type with spherical edges — generated via Apache sedonadb (the only tool in our stack that emits that logical type).
- `samples/flight-routes-great-circle.parquet` — long-haul origin-destination flight routes as native Geography (great-circle paths via `pyproj.Geod`, spherical edges, OGC:CRS84), generated via Apache sedonadb alongside the encodings geography variants.
- `data/compression/` — six files holding an identical Point table, one per Parquet codec (none, snappy, gzip, brotli, lz4_raw, zstd), exercising reader codec support.
- `samples/buildings-3d.parquet` — 3D building footprints over central Delft from 3DBAG (TU Delft), POLYGON Z lifted to NAP ground elevation, in the EPSG:7415 compound CRS (RD New + NAP height).
- `data/edges/` — four new fixtures for the ellipsoidal-geodesic edge values added in GeoParquet 2.0 (`edges-vincenty`, `edges-thomas`, `edges-andoyer`, `edges-karney`), alongside the existing `planar`/`spherical`.
- `data/geometry_types/` — three fixtures covering `geometry_types` cases not exercised elsewhere: `GeometryCollection`, a mixed `["Polygon", "MultiPolygon"]` column, and an empty `[]` array (types not known).
- `data/bbox/` — a positive file-level `bbox` example (the negative counterpart already lives in `bad_data/bbox-does-not-contain-geometry.parquet`).

### Changed
- Six `spec_clause` links in `bad_data/manifest.json` pointed at sections the spec does not have (`#winding-order` -> `#orientation`, `#version` -> `#version-and-schema` x2, `#wkb-encoding` -> `#encoding` x3). The manifest is the corpus's machine-readable contract, so a link into a non-existent section tells a downstream implementer nothing. Fixtures are byte-identical.
- **Native CRS on the logical type.** GeoParquet 2.0 makes the CRS on the Parquet `GEOMETRY`/`GEOGRAPHY` logical type the source of truth, which MUST NOT disagree with the `geo` metadata CRS. Our pyarrow toolchain can only write the OGC:CRS84 default there, so every file whose CRS is not CRS84 (`data/crs/crs-epsg-3857`, `data/epoch/*`, `data/multi_geometry/two-geom-columns-different-crs`, and samples `us-states`, `australia-gnss-stations*`, `buildings-3d`) is now post-processed with sedonadb (`gen_native_crs.py`, `ST_SetSRID`) to stamp the real native CRS as inline PROJJSON. These join the native-geography files as committed snapshots (CI validates via pytest, does not byte-diff).
- `samples/buildings-3d.parquet` and `samples/bathymetry-contours.parquet` (both written by geopandas as plain `BYTE_ARRAY`) are now promoted to the native Parquet `GEOMETRY` logical type, as GeoParquet 2.0 requires.
- Default corpus compression is now **zstd level 15** (was snappy), matching the GeoParquet `distributing-geoparquet.md` recommendation. All deterministic `data/` and `bad_data/` files were regenerated.
- `samples/bathymetry-contours.parquet` now uses **real** Natural Earth 1:10m bathymetry (depth contours over the Mariana Trench, 0 to -10000 m) instead of synthetic sine-wave lines.
- Geography generation moved from the pre-release `sedonadb 0.4.0a128` nightly to the stable **`sedonadb 0.4.0`** PyPI release (bundled DataFusion 52.5.0 unchanged); the 6 `data/encodings/*-native-geography.parquet` files and `samples/flight-routes-great-circle.parquet` were regenerated. The stable release now requires an explicit zstd level, so generation uses `zstd(15)` (the corpus default).
- Bumped the target from the draft **`2.0-dev`** to the tagged **GeoParquet 2.0.0** schema (from `opengeospatial/geoparquet` `main`): every file's `geo` metadata now declares `version: "2.0.0"`, and the vendored schema was refreshed (`scripts/schemas/geoparquet-2.0.0.schema.json`, replacing `geoparquet-2.0-dev.schema.json`). 2.0.0 folds the geodesic algorithms into the `edges` enum and drops the separate `algorithm` property; the corpus only uses `planar`/`spherical` edges, so all data regenerated byte-clean apart from the version string.

### Deferred
- Two niche CRS-representation variants: `srid:0` (Parquet) + `null` geo `crs` for an unknown CRS (sedonadb refuses to write a null CRS), and full PROJJSON in the geo `crs` + the compact `authority:code` form on the Parquet native metadata (sedonadb only emits inline PROJJSON). The general non-CRS84 native-CRS case is now handled (see Changed).

### Notes
- All CRS metadata uses full PROJJSON; `geo` metadata uses `version: "2.0.0"` and the `epoch` field, matching the official GeoParquet 2.0.0 schema.
