# data/native_only/

Parquet files whose geometry columns use the native Parquet `GEOMETRY` logical type but carry
**no** GeoParquet `geo` metadata, as written by DuckDB, Apache Iceberg and the data platforms.
GeoParquet 2.0 readers read them, taking the CRS from the logical type
([opengeospatial/geoparquet#308](https://github.com/opengeospatial/geoparquet/issues/308)).
They are positives: a reader must open them and find the geometry columns. The negative case,
a WKB column that nothing identifies as geometry, is `bad_data/missing-geo-metadata.parquet`.

| File | Contents | Expected reader behavior |
|---|---|---|
| `native-only-geometry.parquet` | one native `GEOMETRY` column (Point, LineString, Polygon), no `crs` on the logical type | geometry column `geometry`, CRS OGC:CRS84 |
| `native-only-two-columns.parquet` | two native `GEOMETRY` columns, `footprint` and `centroid` | both are geometry columns; `footprint` (the first) is the primary |
