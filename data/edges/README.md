# data/edges/

`edges` describes how to interpret the segment between two vertices. GeoParquet 2.0 allows `planar`, `spherical`, and the four ellipsoidal-geodesic formulas `vincenty`, `thomas`, `andoyer`, and `karney` (which use the ellipsoid named by the column `crs`). The default is `planar`.

| File | Edges | Geometry notes |
|---|---|---|
| `edges-planar.parquet` | planar | Two short LineStrings in mid-Pacific |
| `edges-spherical.parquet` | spherical | LineString from (170,10) to (-170,10) — spherically goes the short way across the antimeridian; planarly would span the globe |
| `edges-vincenty.parquet` | vincenty | Transatlantic + transpacific LineStrings; edges follow the `vincenty` ellipsoidal-geodesic formula on the WGS84 ellipsoid |
| `edges-thomas.parquet` | thomas | Transatlantic + transpacific LineStrings; edges follow the `thomas` ellipsoidal-geodesic formula on the WGS84 ellipsoid |
| `edges-andoyer.parquet` | andoyer | Transatlantic + transpacific LineStrings; edges follow the `andoyer` ellipsoidal-geodesic formula on the WGS84 ellipsoid |
| `edges-karney.parquet` | karney | Transatlantic + transpacific LineStrings; edges follow the `karney` ellipsoidal-geodesic formula on the WGS84 ellipsoid |
