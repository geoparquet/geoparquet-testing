"""samples/flight_routes.py

Source: synthetic / hand-curated long-haul origin-destination airport pairs.
License: CC0 (hand-entered approximate airport coordinates; great-circle paths
         computed with pyproj).
Encoding: native Geography (Parquet native Geography logical type), WKB.
CRS: OGC:CRS84.  Edges: spherical.
Showcases: native Geography logical type at sample scale, great-circle
           interpolation, spherical edges, antimeridian-spanning routes
           (e.g. trans-Pacific), LineString geometries.

Generated via Apache sedonadb (see scripts/README.md "Geography tier"); this
module is invoked by gen_geography.py. Requires pyproj + sedonadb, so the normal
gen_samples.py dispatcher skips it (import fails without those deps).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pyarrow as pa
import pyproj          # module-top import -> dispatcher skips when absent
import sedona.db       # module-top import -> dispatcher skips when absent

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from gpqgen.crs import CRS84
from gpqgen.metadata import GEOPARQUET_VERSION, metadata_bytes

OUT_NAME = "flight-routes-great-circle.parquet"
CREATED_BY = "geoparquet-testing"
NPTS = 48  # intermediate great-circle points per route

# ~20 long-haul OD pairs: (route_id, origin_code, o_lon, o_lat, dest_code, d_lon, d_lat)
# Includes trans-Pacific / antimeridian-spanning and high-latitude polar routes.
ROUTES = [
    (1,  "SFO", -122.375,  37.619, "SYD",  151.177, -33.946),
    (2,  "JFK",  -73.778,  40.641, "HKG",  113.915,  22.309),
    (3,  "LHR",   -0.461,  51.470, "SCL",  -70.786, -33.393),
    (4,  "AKL",  174.785, -37.008, "DOH",   51.608,  25.273),
    (5,  "SFO", -122.375,  37.619, "NRT",  140.386,  35.765),  # trans-Pacific
    (6,  "LAX", -118.408,  33.942, "SIN",  103.994,   1.359),
    (7,  "DXB",   55.364,  25.253, "LAX", -118.408,  33.942),  # near-polar
    (8,  "ORD",  -87.905,  41.978, "DEL",   77.103,  28.556),  # over the pole
    (9,  "CDG",    2.547,  49.010, "GRU",  -46.473, -23.435),
    (10, "EZE",  -58.536, -34.822, "MAD",   -3.567,  40.472),
    (11, "JNB",   28.246, -26.139, "ATL",  -84.428,  33.637),
    (12, "SEA", -122.309,  47.449, "DXB",   55.364,  25.253),  # over the pole
    (13, "YYZ",  -79.631,  43.677, "HKG",  113.915,  22.309),  # over the pole
    (14, "IAH",  -95.341,  29.984, "SYD",  151.177, -33.946),
    (15, "LHR",   -0.461,  51.470, "PER",  115.967, -31.940),
    (16, "DFW",  -97.038,  32.897, "DXB",   55.364,  25.253),
    (17, "HND",  139.781,  35.553, "LHR",   -0.461,  51.470),  # near-polar
    (18, "FRA",    8.570,  50.033, "GRU",  -46.473, -23.435),
    (19, "AKL",  174.785, -37.008, "LAX", -118.408,  33.942),  # antimeridian
    (20, "SIN",  103.994,   1.359, "JFK",  -73.778,  40.641),  # over the pole
]


def _wkt(o_lon: float, o_lat: float, d_lon: float, d_lat: float) -> str:
    """Great-circle LINESTRING from origin to dest with NPTS intermediate points.

    Float coords are fixed to 6 decimals for byte-stable output.
    """
    geod = pyproj.Geod(ellps="WGS84")
    pts = geod.npts(o_lon, o_lat, d_lon, d_lat, NPTS)
    coords = [(o_lon, o_lat)] + pts + [(d_lon, d_lat)]
    body = ", ".join(f"{x:.6f} {y:.6f}" for x, y in coords)
    return f"LINESTRING ({body})"


def generate(out_dir: Path) -> Path:
    route_ids = [r[0] for r in ROUTES]
    origins = [r[1] for r in ROUTES]
    dests = [r[4] for r in ROUTES]
    wkts = [_wkt(r[2], r[3], r[5], r[6]) for r in ROUTES]

    table = pa.table(
        {
            "route_id": pa.array(route_ids, type=pa.int32()),
            "origin": pa.array(origins, type=pa.string()),
            "dest": pa.array(dests, type=pa.string()),
            "wkt": pa.array(wkts, type=pa.string()),
        }
    )

    geo = {
        "version": GEOPARQUET_VERSION,
        "primary_column": "geometry",
        "columns": {
            "geometry": {
                "encoding": "WKB",
                "geometry_types": ["LineString"],
                "crs": CRS84,
                "edges": "spherical",
            }
        },
    }
    geo_str = metadata_bytes(geo).decode("utf-8")

    sd = sedona.db.connect()
    sd.create_data_frame(table).to_view("v", overwrite=True)
    df = sd.sql(
        "SELECT route_id, origin, dest, "
        "ST_ToGeography(ST_SetSRID(ST_GeomFromText(wkt), 4326)) AS geometry FROM v"
    )
    out = out_dir / OUT_NAME
    df.to_parquet(
        str(out),
        geoparquet_version="none",
        sort_by="route_id",
        compression="snappy",
        options={"created_by": CREATED_BY, "metadata::geo": geo_str},
    )
    return out


if __name__ == "__main__":
    print(generate(Path(__file__).resolve().parents[2] / "samples"))
