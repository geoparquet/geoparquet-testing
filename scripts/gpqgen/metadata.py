"""Build GeoParquet 2.0 `geo` metadata dictionaries."""

from __future__ import annotations

import json
from typing import Any

GEOPARQUET_VERSION = "2.0-dev"


def make_geo_metadata(
    primary_column: str = "geometry",
    columns: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """
    Build a GeoParquet `geo` metadata dict.

    Caller supplies the `columns` mapping (column name -> per-column metadata dict
    with keys `encoding`, `geometry_types`, optionally `crs`, `edges`, `bbox`,
    `epoch`, `orientation`).
    """
    if columns is None:
        columns = {
            primary_column: {"encoding": "WKB", "geometry_types": []},
        }
    return {
        "version": GEOPARQUET_VERSION,
        "primary_column": primary_column,
        "columns": columns,
    }


def metadata_bytes(meta: dict[str, Any]) -> bytes:
    """Serialize metadata as deterministic UTF-8 JSON bytes (sorted keys, no whitespace pad)."""
    return json.dumps(meta, sort_keys=True, separators=(",", ":")).encode("utf-8")
