"""samples/bathymetry-contours.parquet — synthetic offshore depth contours.

Source:    SYNTHETIC. Deterministic parametric contour lines; not real soundings.
License:   CC0 / public domain (machine-generated).
Encoding:  WKB (native geometry, planar edges).
CRS:       OGC:CRS84 (lon/lat, WGS 84).
Showcases: XYZ MultiLineString geometry where Z carries depth (negative metres
           below sea level). ~50 rows, one constant-depth contour per row.
           geometry_types = ["MultiLineString Z"].

Contours span a small offshore box east of Sydney (lon 151.3-152.0,
lat -34.0 to -33.5). Each contour is a deterministic wavy line whose vertical
amplitude scales with depth, so deeper contours wander more. Float formatting
is fixed-width so output is byte-stable.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import geoarrow.pyarrow as ga
import pyarrow as pa

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from gpqgen.crs import CRS84
from gpqgen.metadata import make_geo_metadata
from gpqgen.write import write_parquet_deterministic

N_CONTOURS = 50
N_VERTICES = 24            # vertices per contour line
LON_MIN, LON_MAX = 151.3, 152.0
LAT_BASE = -33.5           # northern edge; contours drift south with depth


def _contour_wkt(index: int, depth: int) -> str:
    # Deeper (more negative) contours sit further south and wave more.
    lat_center = LAT_BASE - 0.5 * (index / max(N_CONTOURS - 1, 1))
    amp = 0.01 + 0.0008 * index
    pts = []
    for j in range(N_VERTICES):
        frac = j / (N_VERTICES - 1)
        lon = LON_MIN + (LON_MAX - LON_MIN) * frac
        lat = lat_center + amp * math.sin(frac * math.pi * 3 + index * 0.3)
        pts.append(f"{lon:.6f} {lat:.6f} {float(depth):.2f}")
    return "MULTILINESTRING Z ((" + ", ".join(pts) + "))"


def generate(out_dir: Path) -> Path:
    depths = [-10 * (i + 1) for i in range(N_CONTOURS)]  # -10, -20, ... -500
    wkts = [_contour_wkt(i, d) for i, d in enumerate(depths)]
    table = pa.table(
        {
            "depth_m": pa.array(depths, type=pa.int64()),
            "geometry": ga.as_wkb(wkts),
        }
    )
    geo = make_geo_metadata(
        columns={
            "geometry": {
                "encoding": "WKB",
                "geometry_types": ["MultiLineString Z"],
                "crs": CRS84,
                "edges": "planar",
            }
        }
    )
    out = out_dir / "bathymetry-contours.parquet"
    write_parquet_deterministic(table, out, geo)
    return out
