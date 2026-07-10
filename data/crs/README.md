# data/crs/

Five files exercising how a CRS can be expressed in GeoParquet 2.0 metadata.
All files are native-geometry Point columns. Every `crs` value is full PROJJSON
v0.7 (with `name` and all required fields), so all files validate against the
GeoParquet schema.

| File | CRS representation |
|---|---|
| `crs-default.parquet` | **No `crs` field** — readers default to OGC:CRS84 |
| `crs-ogc-crs84.parquet` | Full PROJJSON for OGC:CRS84 (with `id` = OGC:CRS84) |
| `crs-epsg-4326.parquet` | Full PROJJSON for EPSG:4326 (lat,lon order; `id` = EPSG:4326) |
| `crs-epsg-3857.parquet` | Full PROJJSON for projected EPSG:3857 Web Mercator (`id` = EPSG:3857) |
| `crs-projjson-full.parquet` | Full inline PROJJSON for WGS 84, WITHOUT `id` field |

In GeoParquet 2.0 the geo-metadata `crs` field is always full inline PROJJSON (or
`null`), and the CRS also travels on the Parquet native GEOMETRY/GEOGRAPHY logical
type, where it is the source of truth. For the non-CRS84 file here
(`crs-epsg-3857.parquet`) that native CRS is stamped by sedonadb as inline PROJJSON
(`gen_native_crs.py`), because our pyarrow toolchain can only write the CRS84
default onto the native type. The CRS84/EPSG:4326 files need no such stamp: an
empty native CRS already means OGC:CRS84, and the spec treats EPSG:4326 as
equivalent.

Two niche representation variants from the Parquet `crs`-property split are still
**deferred**: `srid:0` (Parquet) + `null` (geo) for an unknown CRS (sedonadb
refuses to write a null CRS), and PROJJSON (geo) + the compact `authority:code`
(Parquet) native form (sedonadb only emits inline PROJJSON). See
`scripts/README.md`.
