"""Fixtures from the Rust code review: allocation bombs, dictionary hints, shoelace precision.
Writes into conformance/fixtures/out/code/."""
import json, struct
from pathlib import Path
import pyarrow as pa, pyarrow.parquet as pq
OUT = Path(__file__).resolve().parents[2] / "out" / "code"
OUT.mkdir(parents=True, exist_ok=True)
def geo(cols, primary="geometry"):
    return json.dumps({"version": "2.0.0", "primary_column": primary,
                       "columns": {c: {"encoding": "WKB", "geometry_types": []} for c in cols}})
def write(name, table, cols, primary="geometry"):
    meta = dict(table.schema.metadata or {}); meta[b"geo"] = geo(cols, primary).encode()
    pq.write_table(table.replace_schema_metadata(meta), OUT / f"{name}.parquet", compression="none")
    print("wrote", name)
point = struct.pack("<BIdd", 1, 1, 1.0, 2.0)
# polygon header claiming 0xFFFFFFFF rings, then nothing
poly_huge_rings = struct.pack("<BII", 1, 3, 0xFFFFFFFF)
poly_4g_rings = struct.pack("<BII", 1, 3, 0x10000000)
line_huge_pts = struct.pack("<BII", 1, 2, 0xFFFFFFFF)
# multipolygon with 1000 polygons each claiming 0x0FFFFFFF rings -> 1000 x 4 GiB with_capacity
mp = struct.pack("<BII", 1, 6, 1000) + b"".join(struct.pack("<BII", 1, 3, 0x0FFFFFFF) for _ in range(1000))
write("wkb_huge_nrings", pa.table({"geometry": pa.array([point, poly_huge_rings], pa.binary())}), ["geometry"])
write("wkb_4g_nrings", pa.table({"geometry": pa.array([point, poly_4g_rings], pa.binary())}), ["geometry"])
write("wkb_huge_npts", pa.table({"geometry": pa.array([point, line_huge_pts], pa.binary())}), ["geometry"])
write("wkb_multipolygon_4g_each", pa.table({"geometry": pa.array([point, mp], pa.binary())}), ["geometry"])
# dictionary-typed second geometry column (ARROW:schema says dictionary<int32, binary>)
d = pa.array([point, point, None], pa.binary()).dictionary_encode()
write("dict_geometry", pa.table({"geometry": pa.array([point, point, point], pa.binary()), "geometry2": d}), ["geometry", "geometry2"])
# large_binary geometry
write("large_binary_geometry", pa.table({"geometry": pa.array([point, None], pa.large_binary())}), ["geometry"])
# nested dimension mismatch: MultiPoint XY containing a Point Z
mpz = struct.pack("<BII", 1, 4, 1) + struct.pack("<BIddd", 1, 1001, 1.0, 2.0, 3.0)
write("wkb_nested_dim_mismatch", pa.table({"geometry": pa.array([mpz], pa.binary())}), ["geometry"])
# polygon with huge projected coordinates and a tiny ring (shoelace precision)
def ring(pts): return struct.pack("<I", len(pts)) + b"".join(struct.pack("<dd", *p) for p in pts)
big = 1.0e7
sq = [(big, big), (big+1e-6, big), (big+1e-6, big+1e-6), (big, big+1e-6), (big, big)]  # CCW, area 1e-12
poly = struct.pack("<BII", 1, 3, 1) + ring(sq)
t = pa.table({"geometry": pa.array([poly], pa.binary())})
meta = {b"geo": json.dumps({"version": "2.0.0", "primary_column": "geometry", "columns": {"geometry": {"encoding": "WKB", "geometry_types": ["Polygon"], "orientation": "counterclockwise", "crs": None}}}).encode()}
pq.write_table(t.replace_schema_metadata(meta), OUT / "shoelace_precision.parquet", compression="none"); print("wrote shoelace_precision")
