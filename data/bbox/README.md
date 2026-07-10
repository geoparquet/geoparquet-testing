# data/bbox/

Positive example of the optional file-level `bbox` field (the negative case lives in `bad_data/bbox-does-not-contain-geometry.parquet`).

| File | `bbox` | Notes |
|---|---|---|
| `bbox-present.parquet` | `[-10.0, -5.0, 30.0, 25.0]` | `[xmin, ymin, xmax, ymax]` correctly bounding the geometries (OGC:CRS84) |
