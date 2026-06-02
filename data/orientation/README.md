# data/orientation/

The GeoParquet spec only allows `orientation: "counterclockwise"` (or omitted). A *violation* of declared orientation lives in `bad_data/`.

| File | Declared | Actual ring winding |
|---|---|---|
| `polygon-ccw.parquet` | counterclockwise | CCW |
| `polygon-cw.parquet`  | (omitted)        | CW  |
