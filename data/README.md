# data/

Conformance tier: small, systematic files exercising each spec axis. Each
subdirectory has its own README mapping file → axis exercised → expected reader
behavior.

| Subdirectory | Files | Axis exercised |
|---|---|---|
| [`encodings/`](encodings/) | 12 | Geometry-type × {native-geometry, native-geography} |
| [`crs/`](crs/) | 5 | CRS representation: default (no crs), full PROJJSON by OGC/EPSG id, projected, PROJJSON without id |
| [`edges/`](edges/) | 6 | `planar`, `spherical`, and the four ellipsoidal-geodesic values (`vincenty`, `thomas`, `andoyer`, `karney`) |
| [`epoch/`](epoch/) | 2 | `epoch` with GDA2020 — visible plate-motion shift |
| [`geometry_types/`](geometry_types/) | 3 | `GeometryCollection`, mixed `["Polygon","MultiPolygon"]`, empty `[]` (unknown) |
| [`zm/`](zm/) | 3 | XYZ, XYM, XYZM LineStrings |
| [`bbox/`](bbox/) | 1 | Positive file-level `bbox` (negative case lives in `bad_data/`) |
| [`multi_geometry/`](multi_geometry/) | 2 | Two geometry columns per row (footprint + centroid) |
| [`orientation/`](orientation/) | 2 | Declared `counterclockwise` + undeclared (CW) |
| [`compression/`](compression/) | 6 | One file per Parquet codec: none, snappy, gzip, brotli, lz4_raw, zstd |

Most files in this tier are generated only with `pyarrow` + `geoarrow-pyarrow`
(no geopandas, no shapely), hold 3–10 rows, and are byte-identical across
regenerations (enforced by CI). Three sets of files are committed **snapshots**
instead — CI validates them via pytest but does not byte-diff them:

- The 6 `encodings/*-native-geography.parquet` files, generated with Apache
  sedonadb (the only tool that emits the Parquet native Geography logical type).
  See `scripts/README.md`, "Geography tier".
- The files whose real CRS is not OGC:CRS84 (`crs/crs-epsg-3857.parquet`,
  `epoch/*.parquet`, `multi_geometry/two-geom-columns-different-crs.parquet`).
  GeoParquet 2.0 makes the CRS on the native logical type the source of truth, and
  our pyarrow toolchain can only write the CRS84 default there, so these are
  post-processed with sedonadb (`ST_SetSRID`) to stamp the real native CRS. See
  `gen_native_crs.py`.
- The `compression/*.parquet` files: some codecs (notably gzip/zlib) emit
  platform- and library-build-dependent bytes, so they are not byte-reproducible
  across machines. pytest asserts each file's codec instead.
