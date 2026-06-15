"""Helpers for producing intentionally-broken Parquet files.

These functions wrap the pattern: write a valid Parquet file, then mutate either
its schema metadata or its byte content to inject a specific violation.
"""

from __future__ import annotations

import json
import struct
from pathlib import Path
from typing import Any

import geoarrow.pyarrow as ga
import pyarrow as pa
import pyarrow.parquet as pq


def write_with_metadata_bytes(
    table: pa.Table,
    out_path: Path,
    geo_bytes: bytes,
) -> None:
    """Write `table` with a literal `geo` metadata bytes value (may be invalid JSON/UTF-8)."""
    new_meta = dict(table.schema.metadata or {})
    new_meta[b"geo"] = geo_bytes
    table = table.replace_schema_metadata(new_meta)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(table, out_path, compression="zstd", compression_level=15, row_group_size=1024)


def write_without_geo_metadata(table: pa.Table, out_path: Path) -> None:
    """Write `table` with NO `geo` metadata key at all."""
    new_meta = dict(table.schema.metadata or {})
    new_meta.pop(b"geo", None)
    table = table.replace_schema_metadata(new_meta)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(table, out_path, compression="zstd", compression_level=15, row_group_size=1024)


def truncate_first_wkb(table: pa.Table, drop_bytes: int = 8) -> pa.Table:
    """Return a new table whose first geometry row's WKB has `drop_bytes` chopped off the end."""
    col = table.column("geometry")
    py = col.to_pylist()
    if py[0] is not None:
        py[0] = py[0][:-drop_bytes]
    return table.set_column(
        table.column_names.index("geometry"),
        "geometry",
        pa.array(py, type=pa.binary()),
    )


def mutate_first_wkb_type_byte(table: pa.Table, new_type: int) -> pa.Table:
    """Rewrite the WKB type code (bytes 1-4) of the first row to `new_type`."""
    col = table.column("geometry")
    py = col.to_pylist()
    if py[0] is not None:
        b = bytearray(py[0])
        endian = "<" if b[0] == 1 else ">"
        struct.pack_into(f"{endian}I", b, 1, new_type)
        py[0] = bytes(b)
    return table.set_column(
        table.column_names.index("geometry"),
        "geometry",
        pa.array(py, type=pa.binary()),
    )


def prepend_srid_to_first_wkb(table: pa.Table, srid: int = 4326) -> pa.Table:
    """
    Convert the first row's WKB into EWKB by setting the SRID flag on the type code
    and prepending the SRID as a 4-byte int. EWKB is NOT permitted by GeoParquet.
    """
    col = table.column("geometry")
    py = col.to_pylist()
    if py[0] is not None:
        b = bytearray(py[0])
        endian = "<" if b[0] == 1 else ">"
        # OR the SRID flag (0x20000000) into the existing type code.
        original_type = struct.unpack(f"{endian}I", bytes(b[1:5]))[0]
        struct.pack_into(f"{endian}I", b, 1, original_type | 0x20000000)
        srid_bytes = struct.pack(f"{endian}I", srid)
        py[0] = bytes(b[:5]) + srid_bytes + bytes(b[5:])
    return table.set_column(
        table.column_names.index("geometry"),
        "geometry",
        pa.array(py, type=pa.binary()),
    )


def make_simple_point_table(wkts: list[str | None]) -> pa.Table:
    """A trivial table with one int column and a WKB-encoded geometry column."""
    return pa.table({"col": list(range(len(wkts))), "geometry": ga.as_wkb(wkts)})
