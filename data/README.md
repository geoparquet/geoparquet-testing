# data/

Conformance tier: small, systematic files exercising each spec axis. Each
subdirectory has its own README mapping file → axis exercised → expected reader
behavior.

| Subdirectory | Files | Axis exercised |
|---|---|---|
| [`encodings/`](encodings/) | 6 | Geometry-type (native-geometry; native-geography deferred) |
| [`crs/`](crs/) | 5 | CRS representation: default, OGC/EPSG auth codes, full PROJJSON |
| [`edges/`](edges/) | 2 | `edges: "planar"` vs `"spherical"` (antimeridian-crossing line) |
| [`epoch/`](epoch/) | 2 | `epoch` with GDA2020 — visible plate-motion shift |
| [`zm/`](zm/) | 3 | XYZ, XYM, XYZM LineStrings |
| [`multi_geometry/`](multi_geometry/) | 2 | Two geometry columns per row (footprint + centroid) |
| [`orientation/`](orientation/) | 2 | Declared `counterclockwise` + undeclared (CW) |

Every file in this tier is:
- generated only with `pyarrow` + `geoarrow-pyarrow` (no geopandas, no shapely),
- 3–10 rows,
- byte-identical across regenerations (enforced by CI).
