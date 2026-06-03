"""Generate data/orientation/ — declared CCW vs undeclared (rings happen to be CW)."""

from __future__ import annotations

import sys
from pathlib import Path

import geoarrow.pyarrow as ga
import pyarrow as pa

sys.path.insert(0, str(Path(__file__).resolve().parent))

from gpqgen.crs import CRS84
from gpqgen.metadata import make_geo_metadata
from gpqgen.paths import DATA_DIR, ensure_dir
from gpqgen.write import write_parquet_deterministic

OUT_DIR = DATA_DIR / "orientation"

# CCW exterior ring: (0,0) -> (1,0) -> (1,1) -> (0,1) -> (0,0)
POLY_CCW = "POLYGON ((0 0, 1 0, 1 1, 0 1, 0 0))"
# CW exterior ring: (0,0) -> (0,1) -> (1,1) -> (1,0) -> (0,0)
POLY_CW = "POLYGON ((0 0, 0 1, 1 1, 1 0, 0 0))"


def _write(fname: str, wkt: str, orientation: str | None) -> Path:
    table = pa.table({"col": [0], "geometry": ga.as_wkb([wkt])})
    col_meta = {
        "encoding": "WKB",
        "geometry_types": ["Polygon"],
        "crs": CRS84,
        "edges": "planar",
    }
    if orientation is not None:
        col_meta["orientation"] = orientation
    geo = make_geo_metadata(columns={"geometry": col_meta})
    out = OUT_DIR / fname
    write_parquet_deterministic(table, out, geo)
    return out


def main() -> None:
    ensure_dir(OUT_DIR)
    _write("polygon-ccw.parquet", POLY_CCW, orientation="counterclockwise")
    print("  wrote polygon-ccw.parquet")
    _write("polygon-cw.parquet", POLY_CW, orientation=None)
    print("  wrote polygon-cw.parquet")

    (OUT_DIR / "README.md").write_text(
        "# data/orientation/\n\n"
        "The GeoParquet spec only allows `orientation: \"counterclockwise\"` (or omitted). "
        "A *violation* of declared orientation lives in `bad_data/`.\n\n"
        "| File | Declared | Actual ring winding |\n"
        "|---|---|---|\n"
        "| `polygon-ccw.parquet` | counterclockwise | CCW |\n"
        "| `polygon-cw.parquet`  | (omitted)        | CW  |\n"
    )


if __name__ == "__main__":
    main()
