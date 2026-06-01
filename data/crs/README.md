# data/crs/

Five files exercising how a CRS can be expressed in GeoParquet 2.0 metadata.
All files are native-geometry Point columns.

| File | CRS representation |
|---|---|
| `crs-default.parquet` | **No `crs` field** — readers must default to OGC:CRS84 |
| `crs-ogc-crs84.parquet` | Auth-code-only PROJJSON: `{type, id: {authority: OGC, code: CRS84}}` |
| `crs-epsg-4326.parquet` | Auth-code-only PROJJSON: `{type, id: {authority: EPSG, code: 4326}}` (lat,lon order — distinct from CRS84) |
| `crs-epsg-3857.parquet` | Auth-code-only PROJJSON for projected CRS: `{type: ProjectedCRS, id: {authority: EPSG, code: 3857}}` |
| `crs-projjson-full.parquet` | Full inline PROJJSON for WGS 84, WITHOUT `id` field |
