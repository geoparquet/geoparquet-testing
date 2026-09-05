"""Generate data/bbox/ — a positive example carrying a file-level `bbox`.

The corpus otherwise only exercises `bbox` negatively (see
`bad_data/bbox-does-not-contain-geometry.parquet`). This tier provides the
positive counterpart: a valid `bbox` that correctly bounds the geometries.

Native Geometry, OGC:CRS84, planar. bbox is [xmin, ymin, xmax, ymax] per
RFC 7946 section 5.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import geoarrow.pyarrow as ga
import pyarrow as pa

sys.path.insert(0, str(Path(__file__).resolve().parent))

from gpqgen.crs import CRS84
from gpqgen.metadata import make_geo_metadata
from gpqgen.paths import DATA_DIR, ensure_dir
from gpqgen.write import write_parquet_deterministic

OUT_DIR = DATA_DIR / "bbox"

# Geometries whose combined extent is exactly [-10, -5, 30, 25].
WKTS = [
    "POINT (-10 -5)",              # south-west corner
    "POINT (30 25)",              # north-east corner
    "LINESTRING (0 0, 15 10, 5 20)",  # interior
]
BBOX = [-10.0, -5.0, 30.0, 25.0]


# XYZ LineStrings: 6-element bbox [xmin, ymin, zmin, xmax, ymax, zmax]
WKTS_XYZ = ["LINESTRING Z (0 0 100, 1 1 110, 2 2 120)", "LINESTRING Z (5 5 50, 6 5 60)"]
BBOX_XYZ = [0.0, 0.0, 50.0, 6.0, 5.0, 120.0]
# XYZM Points: 8-element bbox [xmin, ymin, zmin, mmin, xmax, ymax, zmax, mmax]
WKTS_XYZM = ["POINT ZM (1 2 3 4)", "POINT ZM (10 20 30 40)"]
BBOX_XYZM = [1.0, 2.0, 3.0, 4.0, 10.0, 20.0, 30.0, 40.0]
# Points on both sides of the antimeridian: xmin > xmax per RFC 7946 section 5.2
WKTS_ANTIMERIDIAN = ["POINT (175 0)", "POINT (-175 5)", "LINESTRING (172 -3, 179 4)"]
BBOX_ANTIMERIDIAN = [170.0, -10.0, -170.0, 10.0]


def _write(fname: str, wkts: list[str], geometry_types: list[str], bbox: list[float]) -> None:
    table = pa.table({"col": list(range(len(wkts))), "geometry": ga.as_wkb(wkts)})
    column_meta: dict[str, Any] = {
        "encoding": "WKB",
        "geometry_types": geometry_types,
        "crs": CRS84,
        "edges": "planar",
        "bbox": bbox,
    }
    geo = make_geo_metadata(columns={"geometry": column_meta})
    write_parquet_deterministic(table, OUT_DIR / fname, geo)
    print(f"  wrote data/bbox/{fname}")


def main() -> None:
    ensure_dir(OUT_DIR)
    _write("bbox-present.parquet", WKTS, ["Point", "LineString"], BBOX)
    _write("bbox-xyz-6-element.parquet", WKTS_XYZ, ["LineString Z"], BBOX_XYZ)
    _write("bbox-xyzm-8-element.parquet", WKTS_XYZM, ["Point ZM"], BBOX_XYZM)
    _write("bbox-antimeridian.parquet", WKTS_ANTIMERIDIAN, ["Point", "LineString"], BBOX_ANTIMERIDIAN)

    (OUT_DIR / "README.md").write_text(
        "# data/bbox/\n\n"
        "Positive example of the optional file-level `bbox` field (the negative case "
        "lives in `bad_data/bbox-does-not-contain-geometry.parquet`).\n\n"
        "| File | `bbox` | Notes |\n"
        "|---|---|---|\n"
        f"| `bbox-present.parquet` | `{BBOX}` | "
        "`[xmin, ymin, xmax, ymax]` correctly bounding the geometries (OGC:CRS84) |\n"
        f"| `bbox-xyz-6-element.parquet` | `{BBOX_XYZ}` | "
        "`[xmin, ymin, zmin, xmax, ymax, zmax]` for XYZ LineStrings |\n"
        f"| `bbox-xyzm-8-element.parquet` | `{BBOX_XYZM}` | "
        "`[xmin, ymin, zmin, mmin, xmax, ymax, zmax, mmax]` for XYZM Points (2.0) |\n"
        f"| `bbox-antimeridian.parquet` | `{BBOX_ANTIMERIDIAN}` | "
        "`xmin > xmax`: the extent crosses the antimeridian (RFC 7946 section 5.2); "
        "geometries lie at longitudes 172..179 and -175 |\n"
    )


if __name__ == "__main__":
    main()
