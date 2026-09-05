# data/orientation/

The GeoParquet spec only allows `orientation: "counterclockwise"` (or omitted). A *violation* of declared orientation lives in `bad_data/`.

| File | Declared | Actual ring winding |
|---|---|---|
| `polygon-ccw.parquet` | counterclockwise | CCW |
| `polygon-cw.parquet`  | (omitted)        | CW  |
| `polygon-with-hole-ccw.parquet` | counterclockwise | CCW exterior, CW hole |
| `multipolygon-ccw.parquet` | counterclockwise | both parts CCW |
| `geometrycollection-polygon-ccw.parquet` | counterclockwise | CCW polygon inside a GeometryCollection |
