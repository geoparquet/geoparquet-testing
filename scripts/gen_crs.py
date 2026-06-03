"""Generate data/crs/ — 5 files exercising CRS representation variants.

All `crs` values are full PROJJSON v0.7 objects (generated once via pyproj and
hard-coded in gpqgen.crs), so every file validates against the GeoParquet schema.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import geoarrow.pyarrow as ga
import pyarrow as pa

sys.path.insert(0, str(Path(__file__).resolve().parent))

from gpqgen.crs import CRS84, EPSG_3857, EPSG_4326, WGS84_NO_ID
from gpqgen.metadata import make_geo_metadata
from gpqgen.paths import DATA_DIR, ensure_dir
from gpqgen.write import write_parquet_deterministic

OUT_DIR = DATA_DIR / "crs"


def _write(fname: str, crs: dict[str, Any] | None) -> Path:
    table = pa.table(
        {
            "col": [0, 1, 2],
            "geometry": ga.as_wkb(["POINT (1 2)", "POINT (3 4)", None]),
        }
    )
    col_meta: dict[str, Any] = {
        "encoding": "WKB",
        "geometry_types": ["Point"],
        "edges": "planar",
    }
    if crs is not None:
        col_meta["crs"] = crs
    geo = make_geo_metadata(columns={"geometry": col_meta})
    out = OUT_DIR / fname
    write_parquet_deterministic(table, out, geo)
    return out


def _write_readme() -> None:
    text = """# data/crs/

Five files exercising how a CRS can be expressed in GeoParquet 2.0 metadata.
All files are native-geometry Point columns. Every `crs` value is full PROJJSON
v0.7 (with `name` and all required fields), so all files validate against the
GeoParquet schema.

| File | CRS representation |
|---|---|
| `crs-default.parquet` | **No `crs` field** — readers default to OGC:CRS84 |
| `crs-ogc-crs84.parquet` | Full PROJJSON for OGC:CRS84 (with `id` = OGC:CRS84) |
| `crs-epsg-4326.parquet` | Full PROJJSON for EPSG:4326 (lat,lon order; `id` = EPSG:4326) |
| `crs-epsg-3857.parquet` | Full PROJJSON for projected EPSG:3857 Web Mercator (`id` = EPSG:3857) |
| `crs-projjson-full.parquet` | Full inline PROJJSON for WGS 84, WITHOUT `id` field |
"""
    (OUT_DIR / "README.md").write_text(text)


def main() -> None:
    ensure_dir(OUT_DIR)
    print(f"  wrote {_write('crs-default.parquet', None).name}")
    print(f"  wrote {_write('crs-ogc-crs84.parquet', CRS84).name}")
    print(f"  wrote {_write('crs-epsg-4326.parquet', EPSG_4326).name}")
    print(f"  wrote {_write('crs-epsg-3857.parquet', EPSG_3857).name}")
    print(f"  wrote {_write('crs-projjson-full.parquet', WGS84_NO_ID).name}")
    _write_readme()


if __name__ == "__main__":
    main()
