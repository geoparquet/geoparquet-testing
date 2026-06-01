"""Generate data/crs/ — 5 files exercising CRS representation variants."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import geoarrow.pyarrow as ga
import pyarrow as pa

sys.path.insert(0, str(Path(__file__).resolve().parent))

from gen_encodings import CRS_OGC_CRS84
from gpqgen.metadata import make_geo_metadata
from gpqgen.paths import DATA_DIR, ensure_dir
from gpqgen.write import write_parquet_deterministic

OUT_DIR = DATA_DIR / "crs"

# Compact auth-code-only CRS dicts. The spec allows minimal `{type, id}` PROJJSON.
CRS_OGC_CRS84_AUTH = {
    "type": "GeographicCRS",
    "id": {"authority": "OGC", "code": "CRS84"},
}

CRS_EPSG_4326_AUTH = {
    "type": "GeographicCRS",
    "id": {"authority": "EPSG", "code": 4326},
}

CRS_EPSG_3857_AUTH = {
    "type": "ProjectedCRS",
    "id": {"authority": "EPSG", "code": 3857},
}

# Full inline PROJJSON for EPSG:4326 WITHOUT an `id` field — forces readers to
# build the CRS from the body rather than dereferencing the authority code.
CRS_PROJJSON_FULL_NO_ID = {
    "$schema": "https://proj.org/schemas/v0.5/projjson.schema.json",
    "type": "GeographicCRS",
    "name": "WGS 84",
    "datum": {
        "type": "GeodeticReferenceFrame",
        "name": "World Geodetic System 1984",
        "ellipsoid": {
            "name": "WGS 84",
            "semi_major_axis": 6378137,
            "inverse_flattening": 298.257223563,
        },
    },
    "coordinate_system": {
        "subtype": "ellipsoidal",
        "axis": [
            {"name": "Geodetic latitude",  "abbreviation": "Lat", "direction": "north", "unit": "degree"},
            {"name": "Geodetic longitude", "abbreviation": "Lon", "direction": "east", "unit": "degree"},
        ],
    },
}


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
All files are native-geometry Point columns.

| File | CRS representation |
|---|---|
| `crs-default.parquet` | **No `crs` field** — readers must default to OGC:CRS84 |
| `crs-ogc-crs84.parquet` | Auth-code-only PROJJSON: `{type, id: {authority: OGC, code: CRS84}}` |
| `crs-epsg-4326.parquet` | Auth-code-only PROJJSON: `{type, id: {authority: EPSG, code: 4326}}` (lat,lon order — distinct from CRS84) |
| `crs-epsg-3857.parquet` | Auth-code-only PROJJSON for projected CRS: `{type: ProjectedCRS, id: {authority: EPSG, code: 3857}}` |
| `crs-projjson-full.parquet` | Full inline PROJJSON for WGS 84, WITHOUT `id` field |
"""
    (OUT_DIR / "README.md").write_text(text)


def main() -> None:
    ensure_dir(OUT_DIR)
    print(f"  wrote {_write('crs-default.parquet', None).name}")
    print(f"  wrote {_write('crs-ogc-crs84.parquet', CRS_OGC_CRS84_AUTH).name}")
    print(f"  wrote {_write('crs-epsg-4326.parquet', CRS_EPSG_4326_AUTH).name}")
    print(f"  wrote {_write('crs-epsg-3857.parquet', CRS_EPSG_3857_AUTH).name}")
    print(f"  wrote {_write('crs-projjson-full.parquet', CRS_PROJJSON_FULL_NO_ID).name}")
    _write_readme()


if __name__ == "__main__":
    main()
