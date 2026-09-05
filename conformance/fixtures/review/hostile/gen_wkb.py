"""Crafted-WKB attacks. Each file has one geometry column with the GEOMETRY logical
type; the geometry bytes are hand-built so we control counts, dimensions, byte order.
"""
import struct
from hlib import (write_wkb_geometry, geo_meta, point, hdr, u32, f64, HERE)

NAN = struct.pack("<d", float("nan"))
INF = struct.pack("<d", float("inf"))
NINF = struct.pack("<d", float("-inf"))

COLS = {"geometry": {"encoding": "WKB", "geometry_types": []}}


def w(name, wkb_list, cols=None, primary="geometry"):
    write_wkb_geometry(HERE / name, wkb_list, geo_meta(columns=cols or COLS, primary=primary))
    print("wrote", name)


# 1. Polygon claiming 0xFFFFFFFF rings -> Vec::with_capacity(4.29e9) of 24-byte elems (~103GB)
w("wkb_poly_rings_ffffffff.parquet",
  [hdr(3) + u32(0xFFFFFFFF)])

# 2. Polygon claiming 100M rings then no data -> with_capacity(2.4GB) then errors reading npts
w("wkb_poly_rings_100m.parquet",
  [hdr(3) + u32(100_000_000)])

# 3. Polygon claiming 500M rings
w("wkb_poly_rings_500m.parquet",
  [hdr(3) + u32(500_000_000)])

# 4. LineString claiming 0xFFFFFFFF points (no pre-alloc expected; should error cleanly)
w("wkb_line_pts_ffffffff.parquet",
  [hdr(2) + u32(0xFFFFFFFF)])

# 5. MultiPolygon claiming 0xFFFFFFFF parts
w("wkb_multipoly_parts_ffffffff.parquet",
  [hdr(6) + u32(0xFFFFFFFF)])

# 6. Polygon: one ring claiming 0xFFFFFFFF points (points not pre-alloc'd)
w("wkb_poly_onering_pts_ffffffff.parquet",
  [hdr(3) + u32(1) + u32(0xFFFFFFFF)])

# 7. GeometryCollection nested exactly 32 deep (should be accepted), innermost a point
def nested_gc(depth):
    if depth == 0:
        return point(1.0, 2.0)
    return hdr(7) + u32(1) + nested_gc(depth - 1)
w("wkb_gc_nested_32.parquet", [nested_gc(32)])

# 8. GeometryCollection nested 33 deep (should be rejected cleanly, not crash)
w("wkb_gc_nested_33.parquet", [nested_gc(33)])

# 9. GeometryCollection nested 200 deep (recursion; ensure no stack overflow before depth check)
w("wkb_gc_nested_200.parquet", [nested_gc(200)])

# 10. GeometryCollection nested 100000 deep -> build iteratively (huge bytes but tests recursion guard early-out)
def nested_gc_iter(depth):
    b = point(1.0, 2.0)
    frame = hdr(7) + u32(1)
    return frame * depth + b
w("wkb_gc_nested_100k.parquet", [nested_gc_iter(100_000)])

# 11. Empty geometries of every type
w("wkb_point_empty.parquet", [hdr(1) + NAN + NAN])                    # POINT EMPTY
w("wkb_line_empty.parquet", [hdr(2) + u32(0)])                       # LINESTRING with 0 pts
w("wkb_poly_zero_rings.parquet", [hdr(3) + u32(0)])                  # POLYGON with 0 rings
w("wkb_multipoint_zero.parquet", [hdr(4) + u32(0)])
w("wkb_multiline_zero.parquet", [hdr(5) + u32(0)])
w("wkb_multipoly_zero.parquet", [hdr(6) + u32(0)])
w("wkb_gc_zero.parquet", [hdr(7) + u32(0)])
# collection of empties
w("wkb_gc_of_empties.parquet",
  [hdr(7) + u32(3) + (hdr(1) + NAN + NAN) + (hdr(2) + u32(0)) + (hdr(3) + u32(0))])

# 12. Rings with 1, 2, 3 points (degenerate)
w("wkb_poly_ring_1pt.parquet", [hdr(3) + u32(1) + u32(1) + f64(0) + f64(0)])
w("wkb_poly_ring_2pt.parquet", [hdr(3) + u32(1) + u32(2) + f64(0)+f64(0)+f64(1)+f64(1)])
w("wkb_poly_ring_3pt.parquet",
  [hdr(3) + u32(1) + u32(3) + f64(0)+f64(0)+f64(1)+f64(0)+f64(0)+f64(1)])

# 13. Inf / NaN coordinates in Z and M only (XY finite)
w("wkb_pointz_inf_z.parquet", [hdr(1001) + f64(1.0)+f64(2.0)+INF])
w("wkb_pointz_nan_z.parquet", [hdr(1001) + f64(1.0)+f64(2.0)+NAN])
w("wkb_pointzm_infnan.parquet", [hdr(3001) + f64(1.0)+f64(2.0)+INF+NAN])
w("wkb_pointm_inf_m.parquet", [hdr(2001) + f64(1.0)+f64(2.0)+INF])
# XY with +/-inf
w("wkb_point_inf_xy.parquet", [hdr(1) + INF + NINF])
# huge coords 1e308 (shoelace overflow)
big = f64(1e308)
w("wkb_poly_huge_coords.parquet",
  [hdr(3) + u32(1) + u32(4) + big+big + f64(-1e308)+big + big+f64(-1e308) + big+big])

# 14. Big-endian outer with little-endian inner (mixed byte order)
be_gc = b"\x00" + struct.pack(">I", 7) + struct.pack(">I", 1) + point(3.0, 4.0, le=True)
w("wkb_mixed_byteorder.parquet", [be_gc])
# fully big-endian point
w("wkb_point_bigendian.parquet", [point(5.0, 6.0, le=False)])

# 15. Inner geometry with different dimension than outer (PointZ inside MultiPoint XY)
mp_mixed = hdr(4) + u32(2) + point(1.0, 2.0) + (hdr(1001) + f64(3.0)+f64(4.0)+f64(5.0))
w("wkb_multipoint_mixed_dim.parquet", [mp_mixed])

# 16. Higher type codes 8-17 (CircularString=8, CompoundCurve=9, CurvePolygon=10,
#     MultiCurve=11, MultiSurface=12, Curve=13, Surface=14, PolyhedralSurface=15, TIN=16, Triangle=17)
for code in range(8, 18):
    w(f"wkb_typecode_{code}.parquet", [hdr(code) + u32(0)])

# 17. EWKB with SRID (0x20000000 flag + srid)
ewkb = b"\x01" + struct.pack("<I", 0x20000001) + struct.pack("<I", 4326) + f64(1.0)+f64(2.0)
w("wkb_ewkb_srid.parquet", [ewkb])

# 18. Value that is 0 bytes long
w("wkb_zero_bytes.parquet", [b""])
# 1-4 bytes
w("wkb_1byte.parquet", [b"\x01"])
w("wkb_4bytes.parquet", [b"\x01\x01\x00\x00"])
# trailing bytes after a valid point
w("wkb_trailing_bytes.parquet", [point(1.0, 2.0) + b"\xde\xad\xbe\xef"])

# 19. Invalid byte-order marker
w("wkb_bad_bom.parquet", [b"\x07" + u32(1) + f64(1)+f64(2)])

# 20. Type code 0 and huge type code
w("wkb_typecode_0.parquet", [hdr(0)])
w("wkb_typecode_huge.parquet", [hdr(999999)])

# 21. null geometry value + valid, and all-null column
w("wkb_with_null.parquet", [point(1.0, 2.0), None])
w("wkb_all_null.parquet", [None, None, None])

print("done")
