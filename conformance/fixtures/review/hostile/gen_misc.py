"""Misc: many real geometry columns (re-scan DoS), undeclared 2nd geo column,
projected-CRS inf (spatial-order NaN with nothing else catching it), duplicate names."""
import struct
from pathlib import Path
import pyarrow as pa
import pyarrow.parquet as pq
import geoarrow.pyarrow as ga
from hlib import geo_meta, HERE
from gpqgen.metadata import metadata_bytes
from gpqgen.crs import EPSG_3857

def point(x, y): return b"\x01" + struct.pack("<I", 1) + struct.pack("<dd", x, y)
INF = float("inf")


def wkb_arr(vals):
    return ga.wkb().wrap_array(pa.array(vals, pa.binary()))


def write(cols_arrays, geo, path, rg=1024):
    t = pa.table(cols_arrays)
    meta = dict(t.schema.metadata or {})
    meta[b"geo"] = metadata_bytes(geo)
    t = t.replace_schema_metadata(meta)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(t, path, use_dictionary=False, store_schema=True,
                   compression="none", row_group_size=rg, write_statistics=True)
    print("wrote", Path(path).name)


# 50 real geometry columns each declared; each triggers a full-file scan
N = 50
arrays = {f"g{i}": wkb_arr([point(float(i), float(i))] * 200) for i in range(N)}
cols = {f"g{i}": {"encoding": "WKB", "geometry_types": ["Point"]} for i in range(N)}
write(arrays, geo_meta(columns=cols, primary="g0"),
      HERE/"misc_50_geo_columns.parquet", rg=50)

# Undeclared second geometry column: two GEOMETRY columns, only one in `columns`
write({"geometry": wkb_arr([point(1.0, 2.0)]),
       "geom2": wkb_arr([point(3.0, 4.0)])},
      geo_meta(columns={"geometry": {"encoding": "WKB", "geometry_types": ["Point"]}}),
      HERE/"misc_undeclared_2nd_geo.parquet")

# Projected CRS (EPSG:3857) with an inf coordinate: lonlat check should NOT fire,
# so does spatial-order still emit NaN pass and nothing else catches inf?
proj_col = {"encoding": "WKB", "geometry_types": ["Point"], "crs": EPSG_3857}
pts = [point(float(i) * 1000, float(i) * 1000) for i in range(8)] + [point(INF, INF)]
write({"geometry": wkb_arr(pts)},
      geo_meta(columns={"geometry": proj_col}),
      HERE/"misc_projected_inf.parquet", rg=1)

print("done")
