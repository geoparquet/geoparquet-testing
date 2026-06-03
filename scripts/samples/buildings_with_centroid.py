"""samples/buildings-with-centroid.parquet — OSM building footprints + centroids.

Source:    OpenStreetMap building footprints via the Overpass API
           (https://overpass-api.de/api/interpreter), a small bbox in central
           Wellington, New Zealand. Fetched 2026-06-02 (frozen snapshot).
License:   ODbL 1.0 — © OpenStreetMap contributors
           (https://www.openstreetmap.org/copyright). Redistribution permitted
           with attribution.
Encoding:  WKB (native geometry, planar edges).
CRS:       OGC:CRS84 (lon/lat, WGS 84) for both geometry columns.
Showcases: TWO native geometry columns in one file:
             - footprint (MultiPolygon, primary_column)
             - centroid  (Point, computed from the footprint)
           geometry_types ["MultiPolygon"] / ["Point"] respectively.

Processing / reproducibility notes:
- Overpass query: [out:json][timeout:60];(way["building"](bbox));out geom;
  over bbox lat -41.2900..-41.2870, lon 174.7740..174.7770 (~300 m square).
- Each closed way becomes a shapely Polygon, wrapped as a single-part
  MultiPolygon; the centroid is computed in CRS84 (planar centroid of lon/lat).
- Capped at the first 300 buildings (sorted by osm_id) to bound size; the bbox
  yields well under that.
- Coordinates are written via shapely WKT at full precision; rows sorted by
  osm_id for byte-stable output within a session.
- LIMITATION: OSM is live data. Re-running the generator re-fetches and may
  differ from this committed snapshot across dates. The committed parquet is a
  frozen snapshot fetched on the date above. Back-to-back runs in one session
  return identical data and are byte-stable.
Columns: osm_id (int64), footprint (WKB MultiPolygon), centroid (WKB Point).
"""

from __future__ import annotations

import sys
from pathlib import Path

import geoarrow.pyarrow as ga
import pyarrow as pa
import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from gpqgen.crs import CRS84
from gpqgen.metadata import make_geo_metadata
from gpqgen.write import write_parquet_deterministic

OVERPASS_URLS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]
# (south, west, north, east) — ~300 m square in central Wellington, NZ.
BBOX = (-41.2900, 174.7740, -41.2870, 174.7770)
MAX_BUILDINGS = 300


def generate(out_dir: Path) -> Path:
    from shapely.geometry import MultiPolygon, Polygon

    s, w, n, e = BBOX
    query = (
        f'[out:json][timeout:60];(way["building"]({s},{w},{n},{e}););out geom;'
    )
    headers = {"User-Agent": "geoparquet-testing-corpus/1.0 (sample generator)"}
    last_err: Exception | None = None
    elements = None
    for url in OVERPASS_URLS:
        for _ in range(3):
            try:
                resp = requests.post(
                    url, data={"data": query}, headers=headers, timeout=120
                )
                resp.raise_for_status()
                elements = resp.json()["elements"]
                break
            except Exception as exc:  # transient 504s / load shedding
                last_err = exc
        if elements is not None:
            break
    if elements is None:
        raise RuntimeError(f"Overpass unreachable: {last_err}")

    rows = []
    for el in elements:
        if el.get("type") != "way":
            continue
        geom = el.get("geometry")
        if not geom or len(geom) < 4:
            continue
        coords = [(pt["lon"], pt["lat"]) for pt in geom]
        if coords[0] != coords[-1]:
            coords.append(coords[0])
        try:
            poly = Polygon(coords)
        except Exception:
            continue
        if not poly.is_valid or poly.is_empty:
            continue
        rows.append((int(el["id"]), MultiPolygon([poly])))

    rows.sort(key=lambda r: r[0])
    rows = rows[:MAX_BUILDINGS]

    osm_ids = [r[0] for r in rows]
    footprints = [r[1].wkt for r in rows]
    centroids = [r[1].centroid.wkt for r in rows]

    table = pa.table(
        {
            "osm_id": pa.array(osm_ids, type=pa.int64()),
            "footprint": ga.as_wkb(footprints),
            "centroid": ga.as_wkb(centroids),
        }
    )
    geo = make_geo_metadata(
        primary_column="footprint",
        columns={
            "footprint": {
                "encoding": "WKB",
                "geometry_types": ["MultiPolygon"],
                "crs": CRS84,
                "edges": "planar",
            },
            "centroid": {
                "encoding": "WKB",
                "geometry_types": ["Point"],
                "crs": CRS84,
                "edges": "planar",
            },
        },
    )
    out = out_dir / "buildings-with-centroid.parquet"
    write_parquet_deterministic(table, out, geo)
    return out


if __name__ == "__main__":
    print(generate(Path(__file__).resolve().parents[2] / "samples"))
