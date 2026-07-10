"""Generate data/edges/ — planar vs spherical."""

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
                "crs": CRS84,
                "edges": edges,
            }
        }
    )
    out = OUT_DIR / fname
    write_parquet_deterministic(table, out, geo)
    return out


# The four ellipsoidal-geodesic edge interpretations added in GeoParquet 2.0.
# Each follows a path along the ellipsoid specified by the `crs` (WGS84 here);
# they differ only in the distance/geodesic formula used, so they share geometry.
# A transatlantic line (New York -> Paris) makes the geodesic vs planar path
# distinction meaningful.
GEODESIC_EDGES = ["vincenty", "thomas", "andoyer", "karney"]
GEODESIC_LINES = [
    "LINESTRING (-73.78 40.64, 2.55 49.01)",   # JFK -> Paris CDG, great-circle arcs north
    "LINESTRING (151.18 -33.95, -118.41 33.94)",  # Sydney -> Los Angeles, crosses the antimeridian
]


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
    # The four ellipsoidal-geodesic interpretations (new in GeoParquet 2.0).
    for edges in GEODESIC_EDGES:
        _write(f"edges-{edges}.parquet", GEODESIC_LINES, edges=edges)
        print(f"  wrote data/edges/edges-{edges}.parquet")

    rows = [
        ("edges-planar.parquet", "planar", "Two short LineStrings in mid-Pacific"),
        ("edges-spherical.parquet", "spherical",
         "LineString from (170,10) to (-170,10) — spherically goes the short way across the "
         "antimeridian; planarly would span the globe"),
    ]
    for edges in GEODESIC_EDGES:
        rows.append((
            f"edges-{edges}.parquet", edges,
            f"Transatlantic + transpacific LineStrings; edges follow the `{edges}` "
            "ellipsoidal-geodesic formula on the WGS84 ellipsoid",
        ))
    lines = [
        "# data/edges/",
        "",
        "`edges` describes how to interpret the segment between two vertices. GeoParquet 2.0 "
        "allows `planar`, `spherical`, and the four ellipsoidal-geodesic formulas "
        "`vincenty`, `thomas`, `andoyer`, and `karney` (which use the ellipsoid named by the "
        "column `crs`). The default is `planar`.",
        "",
        "| File | Edges | Geometry notes |",
        "|---|---|---|",
    ]
    lines += [f"| `{f}` | {e} | {n} |" for f, e, n in rows]
    (OUT_DIR / "README.md").write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
