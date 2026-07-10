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


def main() -> None:
    ensure_dir(OUT_DIR)
    table = pa.table({"col": list(range(len(WKTS))), "geometry": ga.as_wkb(WKTS)})
    column_meta: dict[str, Any] = {
        "encoding": "WKB",
        "geometry_types": ["Point", "LineString"],
        "crs": CRS84,
        "edges": "planar",
        "bbox": BBOX,
    }
    geo = make_geo_metadata(columns={"geometry": column_meta})
    out = OUT_DIR / "bbox-present.parquet"
    write_parquet_deterministic(table, out, geo)
    print("  wrote data/bbox/bbox-present.parquet")

    (OUT_DIR / "README.md").write_text(
        "# data/bbox/\n\n"
        "Positive example of the optional file-level `bbox` field (the negative case "
        "lives in `bad_data/bbox-does-not-contain-geometry.parquet`).\n\n"
        "| File | `bbox` | Notes |\n"
        "|---|---|---|\n"
        f"| `bbox-present.parquet` | `{BBOX}` | "
        "`[xmin, ymin, xmax, ymax]` correctly bounding the geometries (OGC:CRS84) |\n"
    )


if __name__ == "__main__":
    main()
