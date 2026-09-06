"""Attacks on crs.rs: garbage crs parameters on the native GEOMETRY/GEOGRAPHY
logical type, and geo-vs-parquet crs mismatches. Also GEOGRAPHY + edges planar."""
from pathlib import Path
import pyarrow as pa
import pyarrow.parquet as pq
import geoarrow.pyarrow as ga
from hlib import geo_meta, point, HERE
from gpqgen.metadata import metadata_bytes

PT = point(1.0, 2.0)


def write_native(path, crs=None, edge=None, geo_col=None, geo_extra=None,
                 file_kv=None):
    t = ga.wkb()
    if crs is not None:
        t = t.with_crs(crs)
    if edge is not None:
        t = t.with_edge_type(edge)
    arr = t.wrap_array(pa.array([PT], pa.binary()))
    table = pa.table({"geometry": arr})
    col = geo_col if geo_col is not None else {"encoding": "WKB", "geometry_types": []}
    geo = geo_meta(columns={"geometry": col})
    if geo_extra:
        geo.update(geo_extra)
    meta = dict(table.schema.metadata or {})
    meta[b"geo"] = metadata_bytes(geo)
    if file_kv:
        for k, v in file_kv.items():
            meta[k.encode()] = v.encode()
    table = table.replace_schema_metadata(meta)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(table, path, use_dictionary=False, store_schema=True,
                   compression="none")
    print("wrote", Path(path).name)


# Garbage Parquet crs strings, with geo crs absent (default CRS84)
for tag, crs in [("epsg_empty", "EPSG:"), ("colon", ":"), ("srid_empty", "srid:"),
                 ("srid0", "srid:0"), ("projjson_missing", "projjson:missing"),
                 ("brace_notjson", "{not json"),
                 ("big100k", "X" * 100000)]:
    try:
        write_native(HERE/f"crs_garbage_{tag}.parquet", crs=crs)
    except Exception as e:
        print(f"SKIP crs_garbage_{tag}: {e!r}")

# srid:0 (undefined) with geo crs null (undefined) -> should be consistent
write_native(HERE/"crs_srid0_geonull.parquet", crs="srid:0",
             geo_col={"encoding": "WKB", "geometry_types": [], "crs": None})

# projjson:key that exists in file kv but is not valid json
write_native(HERE/"crs_projjson_badkey.parquet", crs="projjson:mykey",
             file_kv={"mykey": "{ this is not json"})

# projjson:key that exists and is valid PROJJSON
import json
from gpqgen.crs import EPSG_3857
write_native(HERE/"crs_projjson_goodkey.parquet", crs="projjson:mykey",
             file_kv={"mykey": json.dumps(EPSG_3857)})

# GEOGRAPHY logical type (spherical edges) but geo edges = "planar" (inconsistent)
write_native(HERE/"crs_geography_edges_planar.parquet", edge="spherical",
             geo_col={"encoding": "WKB", "geometry_types": [], "edges": "planar"})

# GEOGRAPHY logical type with geo edges = spherical (consistent)
write_native(HERE/"crs_geography_edges_spherical.parquet", edge="spherical",
             geo_col={"encoding": "WKB", "geometry_types": [], "edges": "spherical"})

# Parquet crs = EPSG:4326 but geo crs = a projected CRS (mismatch)
write_native(HERE/"crs_mismatch_authority.parquet", crs="EPSG:4326",
             geo_col={"encoding": "WKB", "geometry_types": [], "crs": EPSG_3857})

print("done")
