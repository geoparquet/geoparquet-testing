"""Adversarial fixtures for the spec review of the Rust GeoParquet 2.0 conformance prototype.

Writes .parquet files into conformance/fixtures/out/spec/. Each fixture targets one
abstract test where the code's verdict is suspected to differ from the OGC text.
"""
import json
import struct
import sys
from pathlib import Path

import geoarrow.pyarrow as ga
import pyarrow as pa
import pyarrow.parquet as pq

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[3] / "scripts"))
from gpqgen.crs import CRS84, EPSG_3857  # noqa: E402
from gpqgen.metadata import make_geo_metadata  # noqa: E402
from gpqgen.write import write_parquet_deterministic  # noqa: E402

OUT = HERE.parents[1] / "out" / "spec"
OUT.mkdir(parents=True, exist_ok=True)


def col(**kw):
    c = {"encoding": "WKB", "geometry_types": ["Point"], "crs": CRS84}
    c.update(kw)
    for k in [k for k, v in kw.items() if v is ...]:
        c.pop(k)
    return c


def write(name, table, columns, primary="geometry", extra_kv=None, row_group_size=1024):
    geo = make_geo_metadata(primary_column=primary, columns=columns)
    if extra_kv:
        meta = dict(table.schema.metadata or {})
        meta.update({k.encode(): v.encode() for k, v in extra_kv.items()})
        table = table.replace_schema_metadata(meta)
    write_parquet_deterministic(table, OUT / f"{name}.parquet", geo, row_group_size=row_group_size)
    print(f"wrote {name}")


def wkb_point(x, y):
    return b"\x01" + struct.pack("<I", 1) + struct.pack("<dd", x, y)


pts = ["POINT (1 1)", "POINT (2 2)", "POINT (3 3)"]
geom = ga.as_wkb(pts)


def with_crs(crs):
    return ga.with_crs(geom, crs)


# ---------------------------------------------------------------------------
# 1. WKB robustness: a Polygon whose ring count is 0xFFFFFFFF (then truncated).
#    Expected: /conf/core/wkb FAIL. Suspected: Vec::with_capacity(4G) aborts the process.
huge = b"\x01" + struct.pack("<I", 3) + struct.pack("<I", 0xFFFFFFFF) + struct.pack("<I", 4)
write("wkb_huge_nrings",
      pa.table({"geometry": pa.array([huge, wkb_point(1, 1)], type=pa.binary())}),
      {"geometry": col(geometry_types=[])})

# 1b. MultiPolygon whose single member is a Point: not decodable as WKB MultiPolygon.
#     Expected: /conf/core/wkb FAIL. Suspected: passes (type = MultiPolygon).
mp_bad = b"\x01" + struct.pack("<I", 6) + struct.pack("<I", 1) + wkb_point(1, 1)
write("wkb_multipolygon_with_point",
      pa.table({"geometry": pa.array([mp_bad], type=pa.binary())}),
      {"geometry": col(geometry_types=["MultiPolygon"])})

# ---------------------------------------------------------------------------
# 2. crs-default: geo `crs` absent, Parquet crs = inline PROJJSON of CRS84 without `id`
#    (also: with `ids` instead of `id`). Expected: PASS (same CRS) or "cannot compare".
#    Suspected: /conf/core/crs-default FAIL.
noid = {k: v for k, v in CRS84.items() if k != "id"}
write("crs_default_parquet_projjson_noid",
      pa.table({"geometry": with_crs(json.dumps(noid))}), {"geometry": col(crs=...)})
ids = dict(noid)
ids["ids"] = [{"authority": "OGC", "code": "CRS84"}]
write("crs_default_parquet_projjson_ids",
      pa.table({"geometry": with_crs(json.dumps(ids))}), {"geometry": col(crs=...)})
# 2b. URN form for the Parquet crs (not one of the Parquet-sanctioned forms, but the same CRS).
write("crs_default_parquet_urn",
      pa.table({"geometry": with_crs("urn:ogc:def:crs:OGC:1.3:CRS84")}), {"geometry": col(crs=...)})
# 2c. geo crs null but Parquet crs unset (text: FAIL, not both undefined) - verification only
write("crs_null_parquet_unset", pa.table({"geometry": geom}), {"geometry": col(crs=None)})

# ---------------------------------------------------------------------------
# 3. geo-metadata: geo crs is a valid PROJJSON *ellipsoid* object. It validates against the
#    full PROJJSON schema referenced by schema.json, so step 3 of geo-metadata must PASS.
#    Suspected: /conf/core/geo-metadata FAIL (code validates against definitions/crs only).
ellipsoid = {"type": "Ellipsoid", "name": "WGS 84", "semi_major_axis": 6378137,
             "inverse_flattening": 298.257223563}
write("crs_geo_ellipsoid", pa.table({"geometry": geom}), {"geometry": col(crs=ellipsoid)})

# ---------------------------------------------------------------------------
# 4. geometry-column-type step 4: `encoding` absent / not a string.
#    Expected: /conf/core/geometry-column-type FAIL. Suspected: PASS.
write("encoding_missing", pa.table({"geometry": geom}), {"geometry": col(encoding=...)})
write("encoding_number", pa.table({"geometry": geom}), {"geometry": col(encoding=1)})

# ---------------------------------------------------------------------------
# 5. `columns` member naming a column that does not exist. The Standard explicitly does not
#    require existence (clause 6 NOTE). Suspected: /conf/core/geometry-column-nesting FAIL.
write("phantom_column", pa.table({"geometry": geom}),
      {"geometry": col(), "ghost": {"encoding": "WKB", "geometry_types": []}})

# ---------------------------------------------------------------------------
# 6. covering.bbox names a column that does not exist anywhere.
#    Expected: bbox-paths FAIL. Suspected: bbox-column-nesting also FAIL.
COV = {"bbox": {"xmin": ["bbox", "xmin"], "ymin": ["bbox", "ymin"],
                "xmax": ["bbox", "xmax"], "ymax": ["bbox", "ymax"]}}
write("cov_missing_column", pa.table({"geometry": geom}), {"geometry": col(covering=COV)})


def bbox_struct(xs, names=("xmin", "ymin", "xmax", "ymax"), nulls=None, nullable=True):
    fields, cols = [], []
    for j, n in enumerate(names):
        cols.append(pa.array([float(v[j]) for v in xs], type=pa.float64()))
        fields.append(pa.field(n, pa.float64()))
    return pa.StructArray.from_arrays(cols, fields=fields,
                                      mask=pa.array(nulls, pa.bool_()) if nulls else None)


boxes = [(1, 1, 1, 1), (2, 2, 2, 2), (3, 3, 3, 3)]
# 6b. covering ok (control)
write("cov_ok", pa.table({"geometry": geom, "bbox": bbox_struct(boxes)}), {"geometry": col(covering=COV)})

# ---------------------------------------------------------------------------
# 7. axis-order: explicit CRS84 PROJJSON (lon-lat axis order) with a longitude of 200.
#    Step 1 restricts the test to lat-lon ordered CRS; for CRS84 the NOTE says trivially satisfied.
#    Suspected: /conf/core/axis-order FAIL (heuristic applied to every geographic CRS).
write("axis_crs84_explicit_lon200",
      pa.table({"geometry": ga.as_wkb(["POINT (200 10)"])}), {"geometry": col()})

# ---------------------------------------------------------------------------
# 8. bbox-extent verification: 6-element bbox excluding z; empty geometries inside bbox.
write("bbox6_z_outside", pa.table({"geometry": ga.as_wkb(["LINESTRING Z (0 0 100, 1 1 500)"])}),
      {"geometry": col(geometry_types=["LineString Z"], bbox=[0.0, 0.0, 50.0, 1.0, 1.0, 120.0])})
nan = float("nan")
mp_empty_member = b"\x01" + struct.pack("<I", 4) + struct.pack("<I", 2) + wkb_point(nan, nan) + wkb_point(0.5, 0.5)
write("bbox_empty_geoms",
      pa.table({"geometry": pa.array([wkb_point(nan, nan), mp_empty_member,
                                      b"\x01" + struct.pack("<I", 7) + struct.pack("<I", 0), wkb_point(0.2, 0.2)], type=pa.binary())}),
      {"geometry": col(geometry_types=["Point", "MultiPoint", "GeometryCollection"], bbox=[0.0, 0.0, 1.0, 1.0])})
# 8b. projected CRS with xmin > xmax: the text has no rule (bbox-array step 2 is geographic only)
write("bbox_projected_xmin_gt_xmax",
      pa.table({"geometry": ga.with_crs(ga.as_wkb(["POINT (2000 5)", "POINT (-2000 5)"]), "EPSG:3857")}),
      {"geometry": col(crs=EPSG_3857, bbox=[1000.0, 0.0, -1000.0, 10.0])})

# ---------------------------------------------------------------------------
# 9. spatial-order metric. Multi-row-group files.
def strips(n, per=100):
    wkts = []
    for i in range(n):
        for j in range(per):
            wkts.append(f"POINT ({i + j / per:.4f} {(j % 10) / 10:.4f})")
    return wkts


for n in (2, 3, 5, 10):
    write(f"order_{n}_strips_perfect", pa.table({"geometry": ga.as_wkb(strips(n))}),
          {"geometry": col()}, row_group_size=100)

# all x identical, rows sorted by y: extent degenerate in x, perfectly ordered in y
wk = [f"POINT (0 {i / 100:.4f})" for i in range(400)]
write("order_degenerate_x", pa.table({"geometry": ga.as_wkb(wk)}), {"geometry": col()}, row_group_size=100)
# every row group spans the whole extent (random order)
wk = []
for g in range(4):
    for j in range(100):
        wk.append(f"POINT ({(j * 37) % 100 / 10:.2f} {(j * 53) % 100 / 10:.2f})")
write("order_random_4", pa.table({"geometry": ga.as_wkb(wk)}), {"geometry": col()}, row_group_size=100)
# single row group
write("order_single_rg", pa.table({"geometry": geom}), {"geometry": col()})
# every row group is a single identical point (all boxes identical and zero area)
write("order_all_same_point", pa.table({"geometry": ga.as_wkb(["POINT (1 1)"] * 400)}), {"geometry": col()}, row_group_size=100)

# ---------------------------------------------------------------------------
# 10. WKB nested deeper than 32 (valid WKB; code rejects at depth > 32)
def gc(inner):
    return b"\x01" + struct.pack("<I", 7) + struct.pack("<I", 1) + inner


deep = wkb_point(1, 1)
for _ in range(34):
    deep = gc(deep)
write("wkb_deep_nesting", pa.table({"geometry": pa.array([deep], type=pa.binary())}),
      {"geometry": col(geometry_types=["GeometryCollection"])})

print("done")

# ---------------------------------------------------------------------------
# 11. bbox-array step 2: xmin > xmax declared but the data does not cross the antimeridian
#     (all longitudes in [172, 179]). Text: "when xmin > xmax, [verify] that the declared extent
#     crosses the antimeridian". Suspected: PASS (code only notes).
write("bbox_antimeridian_unjustified",
      pa.table({"geometry": ga.as_wkb(["POINT (172 0)", "POINT (179 5)"])}),
      {"geometry": col(bbox=[170.0, -10.0, -170.0, 10.0])})

# 12. crs-consistency Named-vs-Named heuristic: two PROJJSON objects without `id`, same `name`,
#     different definitions (geographic vs projected). Suspected: PASS by name equality.
geo_side = {k: v for k, v in CRS84.items() if k != "id"}
parquet_side = {k: v for k, v in EPSG_3857.items() if k != "id"}
parquet_side["name"] = geo_side["name"]
write("crs_named_same_name_different_crs",
      pa.table({"geometry": with_crs(json.dumps(parquet_side))}), {"geometry": col(crs=geo_side)})

# 13. geometry_types non-empty, data OK, but a GeometryCollection Z member: top-level dim only
write("gc_z_top_level", pa.table({"geometry": ga.as_wkb(["GEOMETRYCOLLECTION Z (POINT Z (1 1 1))"])}),
      {"geometry": col(geometry_types=["GeometryCollection Z"])})
print("done2")
