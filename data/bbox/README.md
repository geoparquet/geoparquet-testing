# data/bbox/

Positive example of the optional file-level `bbox` field (the negative case lives in `bad_data/bbox-does-not-contain-geometry.parquet`).

| File | `bbox` | Notes |
|---|---|---|
| `bbox-present.parquet` | `[-10.0, -5.0, 30.0, 25.0]` | `[xmin, ymin, xmax, ymax]` correctly bounding the geometries (OGC:CRS84) |
| `bbox-xyz-6-element.parquet` | `[0.0, 0.0, 50.0, 6.0, 5.0, 120.0]` | `[xmin, ymin, zmin, xmax, ymax, zmax]` for XYZ LineStrings |
| `bbox-xyzm-8-element.parquet` | `[1.0, 2.0, 3.0, 4.0, 10.0, 20.0, 30.0, 40.0]` | `[xmin, ymin, zmin, mmin, xmax, ymax, zmax, mmax]` for XYZM Points (2.0) |
| `bbox-antimeridian.parquet` | `[170.0, -10.0, -170.0, 10.0]` | `xmin > xmax`: the extent crosses the antimeridian (RFC 7946 section 5.2); geometries lie at longitudes 172..179 and -175 |
