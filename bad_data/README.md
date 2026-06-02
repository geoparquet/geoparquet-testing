# bad_data/

Files that deliberately violate the GeoParquet 2.0 spec. Use these to test that your reader detects and reports each class of violation. The machine-readable contract is `manifest.json`.

## Controlled vocabulary for `expected_failure`

- `bbox_mismatch`
- `crs_mismatch`
- `edges_mismatch`
- `epoch_unsupported`
- `geometry_type_mismatch`
- `metadata_invalid_json`
- `metadata_invalid_utf8`
- `metadata_missing`
- `orientation_mismatch`
- `schema_validation_error`
- `version_feature_mismatch`
- `version_unknown`
- `wkb_parse_error`
- `zm_mismatch`

## Files

| File | Violation | Expected failure |
|---|---|---|
| `bbox-does-not-contain-geometry.parquet` | declared bbox [100,100,101,101] excludes all actual geometries (lon/lat 0-10) | `bbox_mismatch` |
| `crs-invalid-projjson.parquet` | crs value is JSON but missing required PROJJSON `type` field | `schema_validation_error` |
| `crs-mismatch-schema-vs-geo-metadata.parquet` | geo metadata declares EPSG:3857 but coordinates are CRS84 lon/lat | `crs_mismatch` |
| `edges-spherical-with-planar-antimeridian-line.parquet` | edges=spherical declared but a planar LineString from -179 to 179 implies a line across the long way of the globe | `edges_mismatch` |
| `epoch-on-unsupported-crs.parquet` | epoch set on EPSG:4326 (static datum) which does not support it | `epoch_unsupported` |
| `geo-invalid-json.parquet` | `geo` metadata bytes are not valid JSON (trailing comma) | `metadata_invalid_json` |
| `geo-invalid-utf8.parquet` | `geo` metadata bytes contain invalid UTF-8 byte (0xFF) | `metadata_invalid_utf8` |
| `geometry-types-mismatch-declared-point-actual-linestring.parquet` | geometry_types declares ["Point"] but column contains LineStrings | `geometry_type_mismatch` |
| `geometry-types-missing-actual-type.parquet` | geometry_types declares ["Polygon"] but column also contains MultiPolygons | `geometry_type_mismatch` |
| `missing-columns.parquet` | `geo` metadata is missing required `columns` | `schema_validation_error` |
| `missing-geo-metadata.parquet` | no `geo` key in Parquet schema metadata | `metadata_missing` |
| `missing-primary-column.parquet` | `geo` metadata is missing required `primary_column` | `schema_validation_error` |
| `missing-version.parquet` | `geo` metadata is missing required `version` field | `schema_validation_error` |
| `orientation-ccw-declared-rings-cw.parquet` | orientation=counterclockwise declared but polygon rings are wound CW | `orientation_mismatch` |
| `primary-column-not-in-columns.parquet` | `primary_column` value does not appear as a key in `columns` | `schema_validation_error` |
| `version-1-0-with-2-0-features.parquet` | version=1.0.0 declared but file uses 2.0-only epoch field | `version_feature_mismatch` |
| `version-unknown.parquet` | version=99.0.0 is not a known GeoParquet version | `version_unknown` |
| `wkb-truncated.parquet` | first row's WKB has 8 bytes chopped from the end | `wkb_parse_error` |
| `wkb-with-srid-prefix.parquet` | first row uses EWKB SRID prefix (not allowed in GeoParquet) | `wkb_parse_error` |
| `wkb-wrong-type-byte.parquet` | first row's WKB header declares LineString but body is a Point | `wkb_parse_error` |
| `zm-declared-xy-actual-xyz.parquet` | geometry_types=[Point] but rows are POINT Z | `zm_mismatch` |
| `zm-declared-xyz-actual-xy.parquet` | geometry_types=[Point Z] but rows are 2D POINT | `zm_mismatch` |
