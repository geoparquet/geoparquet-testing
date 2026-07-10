# data/geometry_types/

Cases for the `geometry_types` column-metadata field. All files are native Geometry, OGC:CRS84, planar edges.

| File | `geometry_types` | Notes |
|---|---|---|
| `geometrycollection.parquet` | `["GeometryCollection"]` | GeometryCollection geometries (plus one EMPTY and one NULL) |
| `polygon-and-multipolygon.parquet` | `["Polygon", "MultiPolygon"]` | Mixed column — the spec requires listing both, not collapsing to `["MultiPolygon"]` |
| `types-unknown-empty.parquet` | `[]` | Empty array explicitly signals the geometry types are not known |
