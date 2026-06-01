# data/encodings/

GeoParquet 2.0 has a single encoding (`"WKB"`); the variation here is whether the Parquet column uses the native Geometry or native Geography logical type. Only native-geometry (planar `OGC:CRS84`) files are present for now; the native-geography variants are deferred pending tooling that can emit the Parquet native Geography logical type.

| File | Geometry type | Encoding | CRS | Edges |
|---|---|---|---|---|
| `point-native-geometry.parquet` | Point | native-geometry | OGC:CRS84 | planar |
| `linestring-native-geometry.parquet` | LineString | native-geometry | OGC:CRS84 | planar |
| `polygon-native-geometry.parquet` | Polygon | native-geometry | OGC:CRS84 | planar |
| `multipoint-native-geometry.parquet` | MultiPoint | native-geometry | OGC:CRS84 | planar |
| `multilinestring-native-geometry.parquet` | MultiLineString | native-geometry | OGC:CRS84 | planar |
| `multipolygon-native-geometry.parquet` | MultiPolygon | native-geometry | OGC:CRS84 | planar |
