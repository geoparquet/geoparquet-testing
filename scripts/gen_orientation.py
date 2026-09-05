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
# CCW exterior ring with a CW interior ring (the spec's required winding for holes)
POLY_WITH_HOLE = "POLYGON ((0 0, 4 0, 4 4, 0 4, 0 0), (1 1, 1 2, 2 2, 2 1, 1 1))"
# Both parts CCW
MULTIPOLY_CCW = "MULTIPOLYGON (((0 0, 1 0, 1 1, 0 1, 0 0)), ((2 2, 3 2, 3 3, 2 3, 2 2)))"
# A polygon nested in a collection is subject to the same rule
COLLECTION_CCW = "GEOMETRYCOLLECTION (POINT (5 5), POLYGON ((0 0, 1 0, 1 1, 0 1, 0 0)))"


def _write(
    fname: str, wkt: str, orientation: str | None, geometry_types: list[str] | None = None
) -> Path:
    table = pa.table({"col": [0], "geometry": ga.as_wkb([wkt])})
    col_meta = {
        "encoding": "WKB",
        "geometry_types": geometry_types or ["Polygon"],
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
    _write("polygon-with-hole-ccw.parquet", POLY_WITH_HOLE, orientation="counterclockwise")
    print("  wrote polygon-with-hole-ccw.parquet")
    _write("multipolygon-ccw.parquet", MULTIPOLY_CCW, orientation="counterclockwise",
           geometry_types=["MultiPolygon"])
    print("  wrote multipolygon-ccw.parquet")
    _write("geometrycollection-polygon-ccw.parquet", COLLECTION_CCW,
           orientation="counterclockwise", geometry_types=["GeometryCollection"])
    print("  wrote geometrycollection-polygon-ccw.parquet")

    (OUT_DIR / "README.md").write_text(
        "# data/orientation/\n\n"
        "The GeoParquet spec only allows `orientation: \"counterclockwise\"` (or omitted). "
        "A *violation* of declared orientation lives in `bad_data/`.\n\n"
        "| File | Declared | Actual ring winding |\n"
        "|---|---|---|\n"
        "| `polygon-ccw.parquet` | counterclockwise | CCW |\n"
        "| `polygon-cw.parquet`  | (omitted)        | CW  |\n"
        "| `polygon-with-hole-ccw.parquet` | counterclockwise | CCW exterior, CW hole |\n"
        "| `multipolygon-ccw.parquet` | counterclockwise | both parts CCW |\n"
        "| `geometrycollection-polygon-ccw.parquet` | counterclockwise | CCW polygon inside a GeometryCollection |\n"
    )


if __name__ == "__main__":
    main()
