"""Deterministic Parquet writes for the test corpus."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

from gpqgen.metadata import metadata_bytes


DEFAULT_ZSTD_LEVEL = 15


def write_parquet_deterministic(
    table: pa.Table,
    out_path: Path,
    geo_metadata: dict[str, Any] | bytes | None = None,
    *,
    compression: str = "zstd",
    compression_level: int | None = None,
    row_group_size: int = 1024,
) -> None:
    """
    Write `table` to `out_path` with deterministic settings.

    The corpus default is zstd at level 15 (matching the GeoParquet
    distributing-geoparquet.md recommendation). Pass a different `compression`
    (e.g. "snappy", "gzip", "brotli", "lz4_raw", "none") to exercise other codecs;
    `compression_level` is forwarded only for codecs that support it.

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

    # Default zstd to level 15; passing a level to a level-less codec would raise.
    if compression == "zstd" and compression_level is None:
        compression_level = DEFAULT_ZSTD_LEVEL

    extra: dict[str, Any] = {}
    if compression_level is not None:
        extra["compression_level"] = compression_level

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
        **extra,
    )
