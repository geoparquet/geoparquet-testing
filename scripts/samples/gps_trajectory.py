"""samples/gps-trajectory-xyzm.parquet — synthetic Sydney-area GPS walk.

Source:    SYNTHETIC. A deterministic parametric path; not a real GPS trace.
License:   CC0 / public domain (machine-generated).
Encoding:  WKB (native geometry, planar edges).
CRS:       OGC:CRS84 (lon/lat, WGS 84).
Showcases: XYZM coordinates in a single LineString — Z carries elevation in
           metres, M carries elapsed time in seconds. One row, ~500 vertices.
           geometry_types = ["LineString ZM"]. WKB type code 3002.

The path is a gentle deterministic meander near Sydney CBD (lon 151.2093,
lat -33.8688). Float formatting is fixed-width so output is byte-stable.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import geoarrow.pyarrow as ga
import pyarrow as pa

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from gen_crs import CRS_OGC_CRS84_AUTH
from gpqgen.metadata import make_geo_metadata
from gpqgen.write import write_parquet_deterministic

N_VERTICES = 500
START_LON = 151.2093
START_LAT = -33.8688


def _wkt() -> str:
    pts = []
    for i in range(N_VERTICES):
        lon = START_LON + 0.0002 * i * math.cos(i / 20.0)
        lat = START_LAT + 0.0002 * i * math.sin(i / 30.0)
        z = 20.0 + 5.0 * math.sin(i / 15.0)   # elevation, metres
        m = i * 2.0                            # elapsed seconds (2 s / vertex)
        pts.append(f"{lon:.6f} {lat:.6f} {z:.2f} {m:.1f}")
    return "LINESTRING ZM (" + ", ".join(pts) + ")"


def generate(out_dir: Path) -> Path:
    table = pa.table(
        {
            "track_id": pa.array([1], type=pa.int64()),
            "geometry": ga.as_wkb([_wkt()]),
        }
    )
    geo = make_geo_metadata(
        columns={
            "geometry": {
                "encoding": "WKB",
                "geometry_types": ["LineString ZM"],
                "crs": CRS_OGC_CRS84_AUTH,
                "edges": "planar",
            }
        }
    )
    out = out_dir / "gps-trajectory-xyzm.parquet"
    write_parquet_deterministic(table, out, geo)
    return out
