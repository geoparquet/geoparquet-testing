"""Shared helpers for the hostile GeoParquet test generators.

Writes files into conformance/fixtures/out/hostile/. Provides a raw-WKB writer
that wraps arbitrary bytes in the geoarrow.wkb extension type so pyarrow emits
the GEOMETRY logical type, plus a plain-binary writer (no logical type).
"""
from __future__ import annotations

import struct
import sys
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import geoarrow.pyarrow as ga

SRC = Path(__file__).resolve().parent
HERE = SRC.parents[1] / "out" / "hostile"  # output directory (the generators write HERE / name)
HERE.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(SRC.parents[3] / "scripts"))  # the corpus generators' package, gpqgen

from gpqgen.metadata import make_geo_metadata, metadata_bytes  # noqa: E402


def geo_meta(columns=None, primary="geometry", version="2.0.0", extra=None):
    m = make_geo_metadata(primary_column=primary, columns=columns)
    m["version"] = version
    if extra:
        m.update(extra)
    return m


def write_wkb_geometry(path, wkb_list, geo_dict, colname="geometry",
                       compression="none", row_group_size=1024):
    """Write a table with a single geometry column carrying the GEOMETRY logical
    type (via geoarrow.wkb extension) and `geo` metadata. wkb_list: list[bytes|None]."""
    arr = ga.wkb().wrap_array(pa.array(wkb_list, pa.binary()))
    table = pa.table({colname: arr})
    meta = dict(table.schema.metadata or {})
    meta[b"geo"] = geo_dict if isinstance(geo_dict, bytes) else metadata_bytes(geo_dict)
    table = table.replace_schema_metadata(meta)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(table, path, compression=compression,
                   row_group_size=row_group_size, use_dictionary=False,
                   store_schema=True, write_statistics=True)


def write_plain_binary(path, wkb_list, geo_dict, colname="geometry",
                       compression="none", row_group_size=1024):
    """Write geometry as plain pa.binary() (NO logical type)."""
    table = pa.table({colname: pa.array(wkb_list, pa.binary())})
    meta = dict(table.schema.metadata or {})
    meta[b"geo"] = geo_dict if isinstance(geo_dict, bytes) else metadata_bytes(geo_dict)
    table = table.replace_schema_metadata(meta)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(table, path, compression=compression,
                   row_group_size=row_group_size, use_dictionary=False,
                   store_schema=True, write_statistics=True)


# ---- WKB byte construction (little-endian by default) ----
def point(x, y, le=True):
    bo = b"\x01" if le else b"\x00"
    end = "<" if le else ">"
    return bo + struct.pack(f"{end}I", 1) + struct.pack(f"{end}dd", x, y)


def hdr(code, le=True):
    bo = b"\x01" if le else b"\x00"
    end = "<" if le else ">"
    return bo + struct.pack(f"{end}I", code)


def u32(n, le=True):
    return struct.pack(("<" if le else ">") + "I", n)


def f64(x, le=True):
    return struct.pack(("<" if le else ">") + "d", x)


def simple_columns(colname="geometry", **extra):
    col = {"encoding": "WKB", "geometry_types": []}
    col.update(extra)
    return {colname: col}
