"""Generate data/edges/ — planar vs spherical."""

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

OUT_DIR = DATA_DIR / "edges"


def _write(fname: str, wkts: list[str], edges: str) -> Path:
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
                "edges": edges,
            }
        }
    )
    out = OUT_DIR / fname
    write_parquet_deterministic(table, out, geo)
    return out


def main() -> None:
    ensure_dir(OUT_DIR)
    # Planar: a short line in mid-Pacific
    _write("edges-planar.parquet", [
        "LINESTRING (10 10, 20 20)",
        "LINESTRING (30 30, 40 40)",
    ], edges="planar")
    print("  wrote data/edges/edges-planar.parquet")
    # Spherical: a line from (170, 10) to (-170, 10) — spherically the short way
    # across the antimeridian (~20° of arc), planarly a long line back across the globe.
    _write("edges-spherical.parquet", [
        "LINESTRING (170 10, -170 10)",
        "LINESTRING (-30 -60, 30 60)",  # great-circle-ish equator-crossing
    ], edges="spherical")
    print("  wrote data/edges/edges-spherical.parquet")

    (OUT_DIR / "README.md").write_text(
        "# data/edges/\n\n"
        "| File | Edges | Geometry notes |\n"
        "|---|---|---|\n"
        "| `edges-planar.parquet` | planar | Two short LineStrings in mid-Pacific |\n"
        "| `edges-spherical.parquet` | spherical | LineString from (170,10) to (-170,10) — "
        "spherically goes the short way across the antimeridian; planarly would span the globe |\n"
    )


if __name__ == "__main__":
    main()
