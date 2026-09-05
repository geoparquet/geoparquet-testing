"""A valid GeoParquet 2.0 file to confirm the tool's happy path."""
from hlib import write_wkb_geometry, geo_meta, point, simple_columns, HERE

wkb = [point(10.0, 20.0), point(30.0, 40.0), point(-5.0, -8.0)]
cols = simple_columns(geometry={"encoding": "WKB",
                                "geometry_types": ["Point"],
                                "bbox": [-5.0, -8.0, 30.0, 40.0]})
write_wkb_geometry(HERE / "baseline.parquet", wkb, geo_meta(columns=cols))
print("wrote baseline.parquet")
