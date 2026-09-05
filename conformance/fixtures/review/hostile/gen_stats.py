"""Distribution-class attacks needing real geospatial statistics (pyarrow writes them
for GEOMETRY columns). Multi row-group files, inf/nan coords in stats, type mismatches."""
import struct
from pathlib import Path
import pyarrow as pa
import pyarrow.parquet as pq
import geoarrow.pyarrow as ga
from hlib import geo_meta, HERE
from gpqgen.metadata import metadata_bytes

def point(x, y): return b"\x01" + struct.pack("<I", 1) + struct.pack("<dd", x, y)
INF = float("inf")


def wkb_arr(vals):
    return ga.wkb().wrap_array(pa.array(vals, pa.binary()))


def write(vals, geo, path, rg=1):
    t = pa.table({"geometry": wkb_arr(vals)})
    meta = dict(t.schema.metadata or {})
    meta[b"geo"] = metadata_bytes(geo)
    t = t.replace_schema_metadata(meta)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(t, path, use_dictionary=False, store_schema=True,
                   compression="none", row_group_size=rg, write_statistics=True)
    print("wrote", Path(path).name)


COL = {"encoding": "WKB", "geometry_types": []}
COLP = {"encoding": "WKB", "geometry_types": ["Point"]}

# 1. Well spatially-ordered: 16 row groups on a grid, 1 pt each
grid = [point(float(i % 4) * 10, float(i // 4) * 10) for i in range(16)]
write(grid, geo_meta(columns={"geometry": COLP}), HERE/"stats_grid_ordered.parquet", rg=1)

# 2. Badly ordered: 16 row groups, each spanning the whole extent (interleaved)
scatter = []
for i in range(16):
    scatter.append(point(0.0, 0.0))
    scatter.append(point(30.0, 30.0))
write(scatter, geo_meta(columns={"geometry": COLP}), HERE/"stats_scatter.parquet", rg=2)

# 3. One geometry with +inf coordinate -> stats bbox xmax = inf -> spatial::measure NaN?
infpts = [point(float(i), float(i)) for i in range(8)] + [point(INF, INF)]
write(infpts, geo_meta(columns={"geometry": COLP}), HERE/"stats_inf_coord.parquet", rg=1)

# 4. geometry_types declares only Point, but data has a LineString (code 2) -> stats geospatial_types [1,2]
line = b"\x01" + struct.pack("<I", 2) + struct.pack("<I", 2) + struct.pack("<dddd", 0, 0, 1, 1)
mixed = [point(1.0, 2.0), line]
write(mixed, geo_meta(columns={"geometry": ["Point-only-see-below"] and {"encoding": "WKB", "geometry_types": ["Point"]}}),
      HERE/"stats_type_mismatch.parquet", rg=8)

# 5. Declares Point, data is Point, all consistent, many row groups, ordered
write([point(float(i), float(i)) for i in range(64)],
      geo_meta(columns={"geometry": COLP}), HERE/"stats_ok_64.parquet", rg=4)

# 6. Single row group (spatial-order should skip: <2 boxes)
write([point(1.0, 2.0)], geo_meta(columns={"geometry": COLP}),
      HERE/"stats_single_rg.parquet", rg=1024)

# 7. Degenerate extent: all identical points across row groups (w=h=0 -> measure None)
write([point(5.0, 5.0) for _ in range(8)], geo_meta(columns={"geometry": COLP}),
      HERE/"stats_degenerate_extent.parquet", rg=1)

print("done")
