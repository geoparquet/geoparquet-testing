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
