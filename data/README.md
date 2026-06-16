# data/

Conformance tier: small, systematic files exercising each spec axis. Each
subdirectory has its own README mapping file → axis exercised → expected reader
behavior.

| Subdirectory | Files | Axis exercised |
|---|---|---|
| [`encodings/`](encodings/) | 12 | Geometry-type × {native-geometry, native-geography} |
| [`crs/`](crs/) | 5 | CRS representation: default (no crs), full PROJJSON by OGC/EPSG id, projected, PROJJSON without id |
| [`edges/`](edges/) | 2 | `edges: "planar"` vs `"spherical"` (antimeridian-crossing line) |
| [`epoch/`](epoch/) | 2 | `epoch` with GDA2020 — visible plate-motion shift |
| [`zm/`](zm/) | 3 | XYZ, XYM, XYZM LineStrings |
| [`multi_geometry/`](multi_geometry/) | 2 | Two geometry columns per row (footprint + centroid) |
| [`orientation/`](orientation/) | 2 | Declared `counterclockwise` + undeclared (CW) |
| [`compression/`](compression/) | 6 | One file per Parquet codec: none, snappy, gzip, brotli, lz4_raw, zstd |

Every file in this tier is:
- generated only with `pyarrow` + `geoarrow-pyarrow` (no geopandas, no shapely),
- 3–10 rows,
- byte-identical across regenerations (enforced by CI).

Exception: the 6 `encodings/*-native-geography.parquet` files are generated with
Apache sedonadb (the only tool that emits the Parquet native Geography logical type)
and committed as snapshots — CI validates them via pytest but does not byte-diff them
(see `scripts/README.md`, "Geography tier").

Exception: the `compression/*.parquet` files cover the Parquet codecs, and some codecs
(notably gzip/zlib) emit platform- and library-build-dependent bytes, so they are not
byte-reproducible across machines. CI does not byte-diff them; pytest asserts each
file's codec instead.
