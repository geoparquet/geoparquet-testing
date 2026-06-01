"""Deterministic Parquet writes for the test corpus."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

from gpqgen.metadata import metadata_bytes


def write_parquet_deterministic(
    table: pa.Table,
    out_path: Path,
    geo_metadata: dict[str, Any] | bytes | None = None,
    *,
    compression: str = "snappy",
    row_group_size: int = 1024,
) -> None:
    """
    Write `table` to `out_path` with deterministic settings.

    If `geo_metadata` is a dict, it's serialized via `metadata_bytes` (sorted keys,
    no whitespace) and attached as the `geo` key in schema metadata. If it's
    `bytes`, those bytes are used verbatim (used by `bad_data` generators that
    intentionally produce invalid JSON or invalid UTF-8).
    """
    if geo_metadata is not None:
        if isinstance(geo_metadata, dict):
            geo_bytes = metadata_bytes(geo_metadata)
        else:
            geo_bytes = geo_metadata
        new_schema_meta = dict(table.schema.metadata or {})
        new_schema_meta[b"geo"] = geo_bytes
        table = table.replace_schema_metadata(new_schema_meta)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(
        table,
        out_path,
        compression=compression,
        row_group_size=row_group_size,
        # Strip the created-by string for byte-stability across pyarrow versions:
        write_statistics=True,
        use_dictionary=False,
        store_schema=True,
    )
