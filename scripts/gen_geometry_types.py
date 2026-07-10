"""Generate data/geometry_types/ — geometry_types metadata cases.

Covers spec cases for the `geometry_types` field that the other tiers don't:
  * `GeometryCollection` (an accepted type not exercised elsewhere),
  * a mixed column listing multiple types (`["Polygon", "MultiPolygon"]`), which
    the spec explicitly requires over collapsing to just `["MultiPolygon"]`,
  * an empty array `[]`, which explicitly signals "types not known".

All files are native-geometry, OGC:CRS84, planar.
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

OUT_DIR = DATA_DIR / "geometry_types"


def _write(fname: str, wkts: list[str | None], geometry_types: list[str]) -> Path:
    table = pa.table(
        {
            "col": list(range(len(wkts))),
            "geometry": ga.as_wkb(wkts),
        }
    )
    column_meta: dict[str, Any] = {
        "encoding": "WKB",
        "geometry_types": geometry_types,
        "crs": CRS84,
        "edges": "planar",
    }
    geo = make_geo_metadata(columns={"geometry": column_meta})
    out = OUT_DIR / fname
    write_parquet_deterministic(table, out, geo)
    return out


def main() -> None:
    ensure_dir(OUT_DIR)

    _write(
        "geometrycollection.parquet",
        [
            "GEOMETRYCOLLECTION (POINT (30 10), LINESTRING (10 10, 20 20, 10 40))",
            "GEOMETRYCOLLECTION (POLYGON ((0 0, 10 0, 10 10, 0 10, 0 0)))",
            "GEOMETRYCOLLECTION EMPTY",
            None,
        ],
        ["GeometryCollection"],
    )
    print("  wrote data/geometry_types/geometrycollection.parquet")

    # Both Polygon and MultiPolygon present: the spec requires listing both,
    # not collapsing to ["MultiPolygon"].
    _write(
        "polygon-and-multipolygon.parquet",
        [
            "POLYGON ((30 10, 40 40, 20 40, 10 20, 30 10))",
            "MULTIPOLYGON (((30 20, 45 40, 10 40, 30 20)), ((15 5, 40 10, 10 20, 5 10, 15 5)))",
        ],
        ["Polygon", "MultiPolygon"],
    )
    print("  wrote data/geometry_types/polygon-and-multipolygon.parquet")

    # Empty array: geometry types are explicitly "not known" even though concrete
    # geometries are present.
    _write(
        "types-unknown-empty.parquet",
        [
            "POINT (30 10)",
            "LINESTRING (10 10, 20 20)",
            "POLYGON ((0 0, 10 0, 10 10, 0 10, 0 0))",
        ],
        [],
    )
    print("  wrote data/geometry_types/types-unknown-empty.parquet")

    (OUT_DIR / "README.md").write_text(
        "# data/geometry_types/\n\n"
        "Cases for the `geometry_types` column-metadata field. All files are native "
        "Geometry, OGC:CRS84, planar edges.\n\n"
        "| File | `geometry_types` | Notes |\n"
        "|---|---|---|\n"
        "| `geometrycollection.parquet` | `[\"GeometryCollection\"]` | "
        "GeometryCollection geometries (plus one EMPTY and one NULL) |\n"
        "| `polygon-and-multipolygon.parquet` | `[\"Polygon\", \"MultiPolygon\"]` | "
        "Mixed column — the spec requires listing both, not collapsing to `[\"MultiPolygon\"]` |\n"
        "| `types-unknown-empty.parquet` | `[]` | "
        "Empty array explicitly signals the geometry types are not known |\n"
    )


if __name__ == "__main__":
    main()
