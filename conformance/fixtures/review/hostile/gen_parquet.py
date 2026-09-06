"""Parquet-structure and metadata attacks."""
import json
import struct
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import geoarrow.pyarrow as ga

from hlib import (write_wkb_geometry, write_plain_binary, geo_meta, point,
                  simple_columns, HERE)
from gpqgen.metadata import metadata_bytes

PT = point(1.0, 2.0)
PT2 = point(3.0, 4.0)
COLS = {"geometry": {"encoding": "WKB", "geometry_types": []}}


def attach_geo(table, geo):
    meta = dict(table.schema.metadata or {})
    meta[b"geo"] = geo if isinstance(geo, bytes) else metadata_bytes(geo)
    return table.replace_schema_metadata(meta)


def wkb_arr(vals):
    return ga.wkb().wrap_array(pa.array(vals, pa.binary()))


def write(table, path, **kw):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(table, path, use_dictionary=False, store_schema=True,
                   write_statistics=True, compression="none", **kw)
    print("wrote", Path(path).name)


# 1. zero rows
t = pa.table({"geometry": wkb_arr([])})
write(attach_geo(t, geo_meta(columns=COLS)), HERE/"pq_zero_rows.parquet")

# 2. all-null geometry column (typed)
t = pa.table({"geometry": wkb_arr([None, None])})
write(attach_geo(t, geo_meta(columns=COLS)), HERE/"pq_all_null.parquet")

# 3. REPEATED geometry column: list<binary> with geo logical type on the item
inner = ga.wkb().wrap_array(pa.array([PT, PT2], pa.binary()))
listarr = pa.ListArray.from_arrays(pa.array([0, 2], pa.int32()), inner)
t = pa.table({"geometry": listarr})
write(attach_geo(t, geo_meta(columns=COLS)), HERE/"pq_repeated_list.parquet")

# 4. geometry nested in a struct that shares the name with a root column
structarr = pa.StructArray.from_arrays([wkb_arr([PT])], names=["geometry"])
t = pa.table({"geometry": structarr})
write(attach_geo(t, geo_meta(columns=COLS)), HERE/"pq_nested_struct.parquet")

# 5. column names: dot, spaces, unicode, empty
for nm, fn in [("a.b", "pq_name_dot"), ("has spaces", "pq_name_spaces"),
               ("𝔤𝔢𝔬", "pq_name_unicode"), ("", "pq_name_empty")]:
    cols = {nm: {"encoding": "WKB", "geometry_types": []}}
    t = pa.table({nm: wkb_arr([PT])})
    write(attach_geo(t, geo_meta(columns=cols, primary=nm)), HERE/f"{fn}.parquet")

# 6. dictionary-encoded binary geometry column
t = pa.table({"geometry": wkb_arr([PT, PT, PT2])})
Path(HERE/"pq_dict_encoded.parquet")
pq.write_table(attach_geo(t, geo_meta(columns=COLS)), HERE/"pq_dict_encoded.parquet",
               use_dictionary=True, store_schema=True, compression="none")
print("wrote pq_dict_encoded.parquet")

# 7. large_binary geometry
la = pa.array([PT, PT2], pa.large_binary())
t = pa.table({"geometry": ga.wkb().wrap_array(la) if False else la})
# geoarrow may not wrap large_binary; write plain large_binary + geo metadata
write(attach_geo(pa.table({"geometry": la}), geo_meta(columns=COLS)),
      HERE/"pq_large_binary.parquet")

# 8. 200 row groups of 1 row
t = pa.table({"geometry": wkb_arr([PT]*200)})
write(attach_geo(t, geo_meta(columns=COLS)), HERE/"pq_200_rowgroups.parquet",
      row_group_size=1)

# 9. duplicate `geo` keys in key_value_metadata (two entries with key "geo")
# pyarrow dedups dict metadata, so build via low-level: write normal then patch is hard.
# Instead attach both "geo" and confirm behavior with a second differing key via list.
# Use the schema metadata twice is impossible in a dict; emulate with thrift not available.
# Skip true-duplicate; do a `geo` plus `GEO` (case) plus other keys.
t = pa.table({"geometry": wkb_arr([PT])})
meta = {b"geo": metadata_bytes(geo_meta(columns=COLS)),
        b"GEO": b"{}", b"other": b"x"}
write(t.replace_schema_metadata(meta), HERE/"pq_extra_keys.parquet")

# 10. 50 MB geo value (valid JSON but enormous 'columns' padding string)
big = geo_meta(columns=COLS)
big["_pad"] = "A" * (50 * 1024 * 1024)
write(attach_geo(pa.table({"geometry": wkb_arr([PT])}), big),
      HERE/"pq_geo_50mb.parquet")

# 11. deeply nested JSON in geo (arrays 2000 deep) -> raw bytes
depth = 2000
nested = "[" * depth + "]" * depth
raw = '{"version":"2.0.0","primary_column":"geometry","columns":{"geometry":{"encoding":"WKB","geometry_types":[],"x":' + nested + '}}}'
write(attach_geo(pa.table({"geometry": wkb_arr([PT])}), raw.encode()),
      HERE/"pq_geo_deep_json.parquet")

# 12. columns with 1000 entries most nonexistent
manycols = {"geometry": {"encoding": "WKB", "geometry_types": []}}
for i in range(1000):
    manycols[f"ghost{i}"] = {"encoding": "WKB", "geometry_types": ["Point"]}
write(attach_geo(pa.table({"geometry": wkb_arr([PT])}), geo_meta(columns=manycols)),
      HERE/"pq_1000_ghost_columns.parquet")

# 13. primary_column pointing to an int64 column that IS listed in columns
t = pa.table({"n": pa.array([1, 2], pa.int64())})
cols = {"n": {"encoding": "WKB", "geometry_types": []}}
write(attach_geo(t, geo_meta(columns=cols, primary="n")), HERE/"pq_primary_int64.parquet")

# 14. geometry_types with 10000 entries
cols = {"geometry": {"encoding": "WKB", "geometry_types": ["Point"] * 10000}}
write(attach_geo(pa.table({"geometry": wkb_arr([PT])}), geo_meta(columns=cols)),
      HERE/"pq_geomtypes_10000.parquet")

# 15. bbox variants (5, 7 elements; strings; huge -> Infinity via raw json)
for tag, arr in [("5elem", "[0,0,0,0,0]"), ("7elem", "[0,0,0,0,0,0,0]"),
                 ("strings", '["a","b","c","d"]'),
                 ("huge", "[1e400,1e400,-1e400,-1e400]"),
                 ("nan_like", "[1e400,0,0,1e400]")]:
    raw = ('{"version":"2.0.0","primary_column":"geometry","columns":{"geometry":'
           '{"encoding":"WKB","geometry_types":[],"bbox":' + arr + '}}}')
    write(attach_geo(pa.table({"geometry": wkb_arr([PT])}), raw.encode()),
          HERE/f"pq_bbox_{tag}.parquet")

# 16. crs as string / array / huge object
for tag, crs in [("string", '"EPSG:4326"'), ("array", "[1,2,3]"),
                 ("huge", '{"' + "k"*10 + '":"' + "v"*100000 + '"}')]:
    raw = ('{"version":"2.0.0","primary_column":"geometry","columns":{"geometry":'
           '{"encoding":"WKB","geometry_types":[],"crs":' + crs + '}}}')
    write(attach_geo(pa.table({"geometry": wkb_arr([PT])}), raw.encode()),
          HERE/f"pq_crs_{tag}.parquet")

print("done")
