"""Generate data/zm/ — XYZ, XYM, XYZM LineStrings."""

from __future__ import annotations

import sys
from pathlib import Path

import geoarrow.pyarrow as ga
import pyarrow as pa

sys.path.insert(0, str(Path(__file__).resolve().parent))

from gen_crs import CRS_OGC_CRS84_AUTH
from gpqgen.metadata import make_geo_metadata
from gpqgen.paths import DATA_DIR, ensure_dir
from gpqgen.write import write_parquet_deterministic

OUT_DIR = DATA_DIR / "zm"


def _write(fname: str, wkts: list[str]) -> Path:
    table = pa.table(
        {
            "col": list(range(len(wkts))),
            "geometry": ga.as_wkb(wkts),
        }
    )
    geo = make_geo_metadata(
        columns={
            "geometry": {
                "encoding": "WKB",
                "geometry_types": ["LineString"],
                "crs": CRS_OGC_CRS84_AUTH,
                "edges": "planar",
            }
        }
    )
    out = OUT_DIR / fname
    write_parquet_deterministic(table, out, geo)
    return out


def main() -> None:
    ensure_dir(OUT_DIR)
    _write("linestring-xyz-native-geometry.parquet", [
        "LINESTRING Z (0 0 100, 1 1 110, 2 2 120)",
        "LINESTRING Z (5 5 50, 6 5 60)",
    ])
    print("  wrote linestring-xyz-native-geometry.parquet")

    _write("linestring-xym-native-geometry.parquet", [
        "LINESTRING M (0 0 0, 1 1 10, 2 2 20)",   # M = elapsed seconds
        "LINESTRING M (5 5 0, 6 5 5)",
    ])
    print("  wrote linestring-xym-native-geometry.parquet")

    _write("linestring-xyzm-native-geometry.parquet", [
        "LINESTRING ZM (0 0 100 0, 1 1 110 10, 2 2 120 20)",
        "LINESTRING ZM (5 5 50 0, 6 5 60 5)",
    ])
    print("  wrote linestring-xyzm-native-geometry.parquet")

    (OUT_DIR / "README.md").write_text(
        "# data/zm/\n\n"
        "LineStrings with Z (elevation), M (measure, e.g., seconds elapsed), and ZM.\n\n"
        "| File | Dimensions |\n"
        "|---|---|\n"
        "| `linestring-xyz-native-geometry.parquet` | XYZ |\n"
        "| `linestring-xym-native-geometry.parquet` | XYM |\n"
        "| `linestring-xyzm-native-geometry.parquet` | XYZM |\n"
    )


if __name__ == "__main__":
    main()
