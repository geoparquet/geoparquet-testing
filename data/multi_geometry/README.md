# data/multi_geometry/

Two geometry columns per row (building `footprint` + its `centroid`). `primary_column` is set to `footprint`. GeoParquet 2.0 allows per-column CRS.

| File | footprint CRS | centroid CRS |
|---|---|---|
| `two-geom-columns-same-crs.parquet` | OGC:CRS84 | OGC:CRS84 |
| `two-geom-columns-different-crs.parquet` | OGC:CRS84 | EPSG:3857 |
