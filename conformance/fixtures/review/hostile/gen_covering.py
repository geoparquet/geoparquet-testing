"""Bounding Box Covering class attacks."""
from pathlib import Path
import pyarrow as pa
import pyarrow.parquet as pq
import geoarrow.pyarrow as ga
from hlib import geo_meta, point, HERE
from gpqgen.metadata import metadata_bytes

PT = point(1.0, 2.0)


def wkb_arr(vals):
    return ga.wkb().wrap_array(pa.array(vals, pa.binary()))


def write(cols_arrays, geo, path):
    t = pa.table(cols_arrays)
    meta = dict(t.schema.metadata or {})
    meta[b"geo"] = metadata_bytes(geo)
    t = t.replace_schema_metadata(meta)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(t, path, use_dictionary=False, store_schema=True, compression="none")
    print("wrote", Path(path).name)


def bbox_struct(xmin=0.0, ymin=0.0, xmax=1.0, ymax=1.0, typ=pa.float64()):
    return pa.StructArray.from_arrays(
        [pa.array([xmin], typ), pa.array([ymin], typ),
         pa.array([xmax], typ), pa.array([ymax], typ)],
        names=["xmin", "ymin", "xmax", "ymax"])


def covering(colref="bbox"):
    return {"bbox": {"xmin": [colref, "xmin"], "ymin": [colref, "ymin"],
                     "xmax": [colref, "xmax"], "ymax": [colref, "ymax"]}}


def geo_with_cov(cov, colname="geometry"):
    return geo_meta(columns={colname: {"encoding": "WKB", "geometry_types": [],
                                       "covering": cov}})


# 1. normal, valid covering
write({"geometry": wkb_arr([PT]), "bbox": bbox_struct()},
      geo_with_cov(covering("bbox")), HERE/"cov_valid.parquet")

# 2. covering points at the geometry column itself (not a struct)
write({"geometry": wkb_arr([PT])},
      geo_with_cov(covering("geometry")), HERE/"cov_points_at_geometry.parquet")

# 3. covering points at a non-struct (int) column
write({"geometry": wkb_arr([PT]), "bbox": pa.array([1], pa.int64())},
      geo_with_cov(covering("bbox")), HERE/"cov_nonstruct.parquet")

# 4. bbox struct with 4 INT32 children
write({"geometry": wkb_arr([PT]),
       "bbox": bbox_struct(0, 0, 1, 1, pa.int32())},
      geo_with_cov(covering("bbox")), HERE/"cov_int32_children.parquet")

# 5. bbox struct nested 3 deep: outer.mid.bbox (covering names top only)
inner = bbox_struct()
mid = pa.StructArray.from_arrays([inner], names=["mid"])
write({"geometry": wkb_arr([PT]), "outer": pa.StructArray.from_arrays([mid], names=["outer_inner"])},
      geo_with_cov(covering("outer")), HERE/"cov_nested3.parquet")

# 6. covering.bbox paths naming different columns for different members
cov = {"bbox": {"xmin": ["A", "xmin"], "ymin": ["B", "ymin"],
                "xmax": ["A", "xmax"], "ymax": ["A", "ymax"]}}
write({"geometry": wkb_arr([PT]), "A": bbox_struct(), "B": bbox_struct()},
      geo_with_cov(cov), HERE/"cov_paths_differ.parquet")

# 7. covering.bbox second element wrong ("xmin" -> ["bbox","xMAX"])
cov = {"bbox": {"xmin": ["bbox", "xMAX"], "ymin": ["bbox", "ymin"],
                "xmax": ["bbox", "xmax"], "ymax": ["bbox", "ymax"]}}
write({"geometry": wkb_arr([PT]), "bbox": bbox_struct()},
      geo_with_cov(cov), HERE/"cov_second_wrong.parquet")

# 8. covering.bbox path with != 2 elements
cov = {"bbox": {"xmin": ["bbox", "xmin", "extra"], "ymin": ["bbox", "ymin"],
                "xmax": ["bbox", "xmax"], "ymax": ["bbox", "ymax"]}}
write({"geometry": wkb_arr([PT]), "bbox": bbox_struct()},
      geo_with_cov(cov), HERE/"cov_path_len3.parquet")

# 9. covering with an extra unknown member
cov = covering("bbox"); cov["extra"] = 1
write({"geometry": wkb_arr([PT]), "bbox": bbox_struct()},
      geo_with_cov(cov), HERE/"cov_extra_member.parquet")

# 10. covering that is not an object
write({"geometry": wkb_arr([PT]), "bbox": bbox_struct()},
      geo_meta(columns={"geometry": {"encoding": "WKB", "geometry_types": [], "covering": [1, 2, 3]}}),
      HERE/"cov_not_object.parquet")

# 11. bbox struct with 6 children but wrong order
b6 = pa.StructArray.from_arrays(
    [pa.array([0.0]) for _ in range(6)],
    names=["xmin", "ymin", "zmin", "xmax", "zmax", "ymax"])  # zmax/ymax swapped
cov = {"bbox": {"xmin": ["bbox", "xmin"], "ymin": ["bbox", "ymin"],
                "xmax": ["bbox", "xmax"], "ymax": ["bbox", "ymax"]}}
write({"geometry": wkb_arr([PT]), "bbox": b6}, geo_with_cov(cov),
      HERE/"cov_6children_wrongorder.parquet")

# 12. covering declared but geometry present-xor-bbox mismatch:
#     geometry null where bbox present
geom = wkb_arr([PT, None])
bb = bbox_struct()
bb2 = pa.StructArray.from_arrays(
    [pa.array([0.0, 0.0]), pa.array([0.0, 0.0]), pa.array([1.0, 1.0]), pa.array([1.0, 1.0])],
    names=["xmin", "ymin", "xmax", "ymax"])
write({"geometry": geom, "bbox": bb2}, geo_with_cov(covering("bbox")),
      HERE/"cov_rep_mismatch.parquet")

print("done")
