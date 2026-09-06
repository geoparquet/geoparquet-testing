"""Adversarial fixtures for the conformance checker (not part of the corpus; written to
fixtures/out/author/, git-ignored). Run everything with: cd scripts && uv run python ../conformance/fixtures/generate.py"""
import json, sys
from pathlib import Path
import geoarrow.pyarrow as ga
import pyarrow as pa
import pyarrow.parquet as pq
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from gpqgen.crs import CRS84
from gpqgen.metadata import make_geo_metadata
from gpqgen.write import write_parquet_deterministic

OUT = Path(__file__).resolve().parent / "out" / "author"
OUT.mkdir(parents=True, exist_ok=True)
EPSG3857 = {"$schema": "https://proj.org/schemas/v0.7/projjson.schema.json", "type": "ProjectedCRS", "name": "WGS 84 / Pseudo-Mercator",
  "base_crs": {"type": "GeographicCRS", "name": "WGS 84", "datum_ensemble": {"name": "World Geodetic System 1984 ensemble", "members": [{"name": "World Geodetic System 1984 (Transit)"}, {"name": "World Geodetic System 1984 (G2296)"}], "ellipsoid": {"name": "WGS 84", "semi_major_axis": 6378137, "inverse_flattening": 298.257223563}, "accuracy": "2.0", "id": {"authority": "EPSG", "code": 6326}},
    "coordinate_system": {"subtype": "ellipsoidal", "axis": [{"name": "Geodetic latitude", "abbreviation": "Lat", "direction": "north", "unit": "degree"}, {"name": "Geodetic longitude", "abbreviation": "Lon", "direction": "east", "unit": "degree"}]}, "id": {"authority": "EPSG", "code": 4326}},
  "conversion": {"name": "Popular Visualisation Pseudo-Mercator", "method": {"name": "Popular Visualisation Pseudo Mercator", "id": {"authority": "EPSG", "code": 1024}},
    "parameters": [{"name": "Latitude of natural origin", "value": 0, "unit": "degree", "id": {"authority": "EPSG", "code": 8801}}, {"name": "Longitude of natural origin", "value": 0, "unit": "degree", "id": {"authority": "EPSG", "code": 8802}}, {"name": "False easting", "value": 0, "unit": "metre", "id": {"authority": "EPSG", "code": 8806}}, {"name": "False northing", "value": 0, "unit": "metre", "id": {"authority": "EPSG", "code": 8807}}]},
  "coordinate_system": {"subtype": "Cartesian", "axis": [{"name": "Easting", "abbreviation": "X", "direction": "east", "unit": "metre"}, {"name": "Northing", "abbreviation": "Y", "direction": "north", "unit": "metre"}]},
  "id": {"authority": "EPSG", "code": 3857}}

def col(**kw):
    c = {"encoding": "WKB", "geometry_types": ["Point"], "crs": CRS84}
    c.update(kw); return c

def write(name, table, columns, primary="geometry", extra_kv=None):
    geo = make_geo_metadata(primary_column=primary, columns=columns)
    if extra_kv:
        meta = dict(table.schema.metadata or {}); meta.update({k.encode(): v.encode() for k, v in extra_kv.items()})
        table = table.replace_schema_metadata(meta)
    write_parquet_deterministic(table, OUT / f"{name}.parquet", geo)
    print(f"wrote {name}: {pq.ParquetFile(OUT / f'{name}.parquet').schema}".replace("\n", " | ")[:300])

pts = ["POINT (1 1)", "POINT (2 2)", "POINT (3 3)"]
geom = ga.as_wkb(pts)

# --- bbox negatives the corpus lacks ---
write("bbox6_z_outside", pa.table({"geometry": ga.as_wkb(["LINESTRING Z (0 0 100, 1 1 500)"])}),
      {"geometry": col(geometry_types=["LineString Z"], bbox=[0.0, 0.0, 50.0, 1.0, 1.0, 120.0])})
write("bbox_antimeridian_point_outside", pa.table({"geometry": ga.as_wkb(["POINT (175 0)", "POINT (-175 5)", "POINT (0 0)"])}),
      {"geometry": col(bbox=[170.0, -10.0, -170.0, 10.0])})
write("bbox8_m_outside", pa.table({"geometry": ga.as_wkb(["POINT ZM (1 2 3 99)"])}),
      {"geometry": col(geometry_types=["Point ZM"], bbox=[1.0, 2.0, 3.0, 4.0, 10.0, 20.0, 30.0, 40.0])})

# --- covering: bbox struct column ---
def bbox_struct(xs, types=("double",)*4, names=("xmin", "ymin", "xmax", "ymax"), nulls=None):
    arrays = [pa.array([None if (nulls and nulls[i]) else float(v[j]) for i, v in enumerate(xs)], type=getattr(pa, t)()) if False else None for j, t in enumerate(types)]
    fields = []; cols = []
    for j, (t, n) in enumerate(zip(types, names)):
        typ = pa.float64() if t == "double" else pa.float32()
        cols.append(pa.array([float(v[j]) for v in xs], type=typ)); fields.append(pa.field(n, typ))
    arr = pa.StructArray.from_arrays(cols, fields=fields, mask=pa.array(nulls, pa.bool_()) if nulls else None)
    return arr

boxes = [(1, 1, 1, 1), (2, 2, 2, 2), (3, 3, 3, 3)]
COV = {"bbox": {"xmin": ["bbox", "xmin"], "ymin": ["bbox", "ymin"], "xmax": ["bbox", "xmax"], "ymax": ["bbox", "ymax"]}}
write("cov_ok", pa.table({"geometry": geom, "bbox": bbox_struct(boxes)}), {"geometry": col(covering=COV)})
write("cov_wrong_order", pa.table({"geometry": geom, "bbox": bbox_struct(boxes, names=("xmin", "xmax", "ymin", "ymax"))}),
      {"geometry": col(covering={"bbox": {"xmin": ["bbox", "xmin"], "ymin": ["bbox", "ymin"], "xmax": ["bbox", "xmax"], "ymax": ["bbox", "ymax"]}})})
write("cov_mixed_types", pa.table({"geometry": geom, "bbox": bbox_struct(boxes, types=("double", "float", "double", "double"))}), {"geometry": col(covering=COV)})
write("cov_second_element_wrong", pa.table({"geometry": geom, "bbox": bbox_struct(boxes)}),
      {"geometry": col(covering={"bbox": {"xmin": ["bbox", "x_min"], "ymin": ["bbox", "ymin"], "xmax": ["bbox", "xmax"], "ymax": ["bbox", "ymax"]}})})
write("cov_two_columns", pa.table({"geometry": geom, "bbox": bbox_struct(boxes), "other": bbox_struct(boxes)}),
      {"geometry": col(covering={"bbox": {"xmin": ["bbox", "xmin"], "ymin": ["other", "ymin"], "xmax": ["bbox", "xmax"], "ymax": ["bbox", "ymax"]}})})
write("cov_unknown_key", pa.table({"geometry": geom, "bbox": bbox_struct(boxes)}), {"geometry": col(covering={**COV, "hilbert": ["h"]})})
write("cov_missing_column", pa.table({"geometry": geom}), {"geometry": col(covering=COV)})
write("cov_nested", pa.table({"geometry": geom, "wrap": pa.StructArray.from_arrays([bbox_struct(boxes)], names=["bbox"])}), {"geometry": col(covering=COV)})
write("cov_undeclared_bbox_column", pa.table({"geometry": geom, "bbox": bbox_struct(boxes)}), {"geometry": col()})
# nullness mismatch: geometry null in row 1, bbox present everywhere
geom_null = ga.as_wkb(pa.array([pts[0], None, pts[2]]))
write("cov_nullness_mismatch", pa.table({"geometry": geom_null, "bbox": bbox_struct(boxes)}), {"geometry": col(covering=COV)})
write("cov_nullness_ok", pa.table({"geometry": geom_null, "bbox": bbox_struct(boxes, nulls=[False, True, False])}), {"geometry": col(covering=COV)})

# --- CRS forms on the Parquet logical type ---
def with_crs(crs):
    return ga.with_crs(geom, crs)
write("crs_parquet_authority_ok", pa.table({"geometry": with_crs("EPSG:3857")}), {"geometry": col(crs=EPSG3857)})
write("crs_parquet_authority_mismatch", pa.table({"geometry": with_crs("EPSG:4326")}), {"geometry": col(crs=EPSG3857)})
write("crs_parquet_projjson_inline_ok", pa.table({"geometry": with_crs(EPSG3857)}), {"geometry": col(crs=EPSG3857)})
write("crs_srid0_null_ok", pa.table({"geometry": with_crs("srid:0")}), {"geometry": col(crs=None)})
write("crs_srid0_but_geo_crs84", pa.table({"geometry": with_crs("srid:0")}), {"geometry": col()})
write("crs_projjson_key_ok", pa.table({"geometry": with_crs("projjson:my_crs")}), {"geometry": col(crs=EPSG3857)}, extra_kv={"my_crs": json.dumps(EPSG3857)})
write("crs_geo_epsg4326_parquet_crs84", pa.table({"geometry": with_crs("OGC:CRS84")}), {"geometry": col(crs={**CRS84, "id": {"authority": "EPSG", "code": 4326}})})
# geometry_types uniqueness and stats: declared empty list with mixed data must pass
write("types_empty_mixed", pa.table({"geometry": ga.as_wkb(["POINT (1 1)", "LINESTRING (0 0, 1 1)"])}), {"geometry": col(geometry_types=[])})

# --- cases surfaced by the review round (spec, hostile and code reviewers) ---
import struct

def wkb_le(type_code, body):
    return b"\x01" + struct.pack("<I", type_code) + body

def wkb_point(x, y, z=None):
    if z is None:
        return wkb_le(1, struct.pack("<dd", x, y))
    return wkb_le(1001, struct.pack("<ddd", x, y, z))

def raw_geometry(values):
    return ga.wkb().wrap_array(pa.array(values, pa.binary()))

# MultiPolygon whose member is a Point: byte-legal, grammar-illegal -> wkb FAIL
write("wkb_multipolygon_with_point", pa.table({"geometry": raw_geometry([wkb_le(6, struct.pack("<I", 1) + wkb_point(0, 0))])}),
      {"geometry": col(geometry_types=["MultiPolygon"])})
# MultiPoint XY containing a Point Z -> wkb FAIL (member dimension differs)
write("wkb_multipoint_with_point_z", pa.table({"geometry": raw_geometry([wkb_le(4, struct.pack("<I", 1) + wkb_point(0, 0, 1))])}),
      {"geometry": col(geometry_types=["MultiPoint"])})
# Polygon header claiming 4 billion rings -> wkb FAIL, no allocation
write("wkb_ring_count_bomb", pa.table({"geometry": raw_geometry([wkb_le(3, struct.pack("<I", 0xFFFFFFFF))])}),
      {"geometry": col(geometry_types=["Polygon"])})
# 40-deep GeometryCollection is legal WKB -> pass
deep = wkb_point(1, 1)
for _ in range(40):
    deep = wkb_le(7, struct.pack("<I", 1) + deep)
write("wkb_deep_collection_ok", pa.table({"geometry": raw_geometry([deep])}), {"geometry": col(geometry_types=["GeometryCollection"])})
# crs that is valid PROJJSON but an ellipsoid, not a CRS -> geo-metadata passes, crs-projjson fails
write("crs_geo_ellipsoid", pa.table({"geometry": geom}),
      {"geometry": col(crs={"type": "Ellipsoid", "name": "WGS 84", "semi_major_axis": 6378137, "inverse_flattening": 298.257223563})})
# antimeridian bbox declared but all data east of 170 -> bbox-array FAIL, bbox-extent pass
write("bbox_antimeridian_unjustified", pa.table({"geometry": ga.as_wkb(["POINT (172 0)", "POINT (179 5)"])}),
      {"geometry": col(bbox=[170.0, -10.0, -170.0, 10.0])})
# geo crs absent, Parquet crs an inline PROJJSON without id -> crs-default inconclusive (note), not FAIL
crs84_noid = {k: v for k, v in CRS84.items() if k != "id"}
write("crs_default_parquet_projjson_noid", pa.table({"geometry": with_crs(crs84_noid)}), {"geometry": {"encoding": "WKB", "geometry_types": ["Point"]}})
# encoding missing / not a string -> geometry-column-type FAIL (step 4), besides the schema failure
write("encoding_missing", pa.table({"geometry": geom}), {"geometry": {"geometry_types": ["Point"], "crs": CRS84}})
write("encoding_number", pa.table({"geometry": geom}), {"geometry": {"encoding": 1, "geometry_types": ["Point"], "crs": CRS84}})
# columns lists a name that exists nowhere in the schema -> no nesting failure (spec does not require it)
write("phantom_column", pa.table({"geometry": geom}), {"geometry": col(), "ghost": col()})
# points on one meridian sorted by latitude, 4 row groups of 2 rows: one-dimensional extent, still ordered
meridian = ga.as_wkb([f"POINT (10 {lat})" for lat in range(8)])
geo = make_geo_metadata(columns={"geometry": col()})
write_parquet_deterministic(pa.table({"geometry": meridian}), OUT / "order_degenerate_x.parquet", geo, row_group_size=2)
print("wrote order_degenerate_x")
