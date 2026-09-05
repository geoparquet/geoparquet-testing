"""Follow-up: does a non-finite coordinate in the geo statistics bbox corrupt the
spatial-order verdict? And partial (some-row-group) statistics."""
import struct
from pathlib import Path
import pyarrow as pa
import pyarrow.parquet as pq
import geoarrow.pyarrow as ga
from hlib import geo_meta, HERE
from gpqgen.metadata import metadata_bytes

def point(x, y): return b"\x01" + struct.pack("<I", 1) + struct.pack("<dd", x, y)
INF = float("inf"); NAN = float("nan")
COLP = {"encoding": "WKB", "geometry_types": ["Point"]}


def wkb_arr(vals):
    return ga.wkb().wrap_array(pa.array(vals, pa.binary()))


def write(vals, path, rg=2, col=COLP):
    t = pa.table({"geometry": wkb_arr(vals)})
    meta = dict(t.schema.metadata or {})
    meta[b"geo"] = metadata_bytes(geo_meta(columns={"geometry": col}))
    t = t.replace_schema_metadata(meta)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(t, path, use_dictionary=False, store_schema=True,
                   compression="none", row_group_size=rg, write_statistics=True)
    print("wrote", Path(path).name)


# Badly-ordered scatter (each rg spans full extent) that WITHOUT inf fails spatial-order,
# but WITH one +inf coordinate the metric degenerates. Row groups of 2.
scatter = []
for i in range(16):
    scatter.append(point(0.0, 0.0))
    scatter.append(point(30.0, 30.0))
# inject an inf into the last row group
scatter_inf = scatter[:-1] + [point(INF, 30.0)]
write(scatter_inf, HERE/"stats2_scatter_inf_mask.parquet", rg=2)

# Same but -inf
scatter_ninf = scatter[:-1] + [point(float("-inf"), 30.0)]
write(scatter_ninf, HERE/"stats2_scatter_ninf_mask.parquet", rg=2)

# NaN coordinate in one point (pyarrow stats behavior)
scatter_nan = scatter[:-1] + [point(NAN, 30.0)]
write(scatter_nan, HERE/"stats2_scatter_nan.parquet", rg=2)

# Partial stats: one row group contains an unparseable geometry so pyarrow may omit geo stats
bad = b"\x01" + struct.pack("<I", 3) + struct.pack("<I", 0xFFFFFFFF)  # polygon claiming 4e9 rings
partial = [point(1.0, 1.0), point(2.0, 2.0), bad, point(3.0, 3.0)]
write(partial, HERE/"stats2_partial_stats.parquet", rg=1)

print("done")
