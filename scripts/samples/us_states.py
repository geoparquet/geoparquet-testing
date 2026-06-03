"""samples/us-states.parquet — US states & provinces (Natural Earth 10m).

Source:    Natural Earth `ne_10m_admin_1_states_provinces`, GitHub mirror
           https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_10m_admin_1_states_provinces.geojson
           Fetched 2026-06-02.
License:   Public domain (Natural Earth — "no permission is needed to use Natural
           Earth. Crediting the authors is unnecessary."). No attribution required.
Encoding:  WKB (native geometry, planar edges).
CRS:       EPSG:5070 (NAD83 / Conus Albers — Albers Equal Area Conic, metres),
           reprojected from the source EPSG:4326.
Showcases: MultiPolygon geometry in a projected (planar) CRS with an authority
           code. ~51 rows (50 states + DC), filtered iso_a2 == "US".
           geometry_types = ["MultiPolygon"] (Polygon sources cast to
           MultiPolygon so the column is homogeneous).

Processing notes (for byte-stability and the 5 MB budget):
- Filtered to iso_a2 == "US".
- Reprojected to EPSG:5070.
- Simplified with a 200 m tolerance (gdf.simplify(200), in the projected CRS) to
  fit comfortably under the 5 MB budget while staying recognizable.
- Coordinates snapped with shapely set_precision(1.0) (1 m grid) so the WKB is
  byte-stable across runs despite floating-point reprojection.
- Rows sorted by state name; column order pinned.
Kept columns: name, postal, iso_3166_2, geometry.
"""

from __future__ import annotations

import sys
from pathlib import Path

import geoarrow.pyarrow as ga
import pyarrow as pa
import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from gpqgen.crs import EPSG_5070
from gpqgen.metadata import make_geo_metadata
from gpqgen.write import write_parquet_deterministic

URL = (
    "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/"
    "master/geojson/ne_10m_admin_1_states_provinces.geojson"
)

SIMPLIFY_TOLERANCE_M = 200.0
PRECISION_GRID_M = 1.0


def generate(out_dir: Path) -> Path:
    import tempfile

    import geopandas as gpd
    import shapely
    from shapely.geometry import MultiPolygon

    # fiona/geopandas' urllib lacks certifi roots; fetch via requests then read.
    resp = requests.get(URL, timeout=120)
    resp.raise_for_status()
    with tempfile.NamedTemporaryFile(suffix=".geojson", delete=False) as fh:
        fh.write(resp.content)
        tmp_path = fh.name

    gdf = gpd.read_file(tmp_path)
    Path(tmp_path).unlink(missing_ok=True)

    # Filter to US states.
    if (gdf["iso_a2"] == "US").any():
        gdf = gdf[gdf["iso_a2"] == "US"].copy()
    elif "adm0_a3" in gdf.columns and (gdf["adm0_a3"] == "USA").any():
        gdf = gdf[gdf["adm0_a3"] == "USA"].copy()
    else:
        gdf = gdf[gdf["admin"] == "United States of America"].copy()

    gdf = gdf.to_crs(epsg=5070)
    gdf["geometry"] = gdf.simplify(SIMPLIFY_TOLERANCE_M)
    # Snap to a 1 m grid for byte-stability across runs.
    gdf["geometry"] = shapely.set_precision(
        gdf.geometry.values, PRECISION_GRID_M
    )

    # Homogenize to MultiPolygon.
    def to_multi(geom):
        if geom.geom_type == "Polygon":
            return MultiPolygon([geom])
        return geom

    gdf["geometry"] = gdf.geometry.apply(to_multi)

    gdf = gdf.sort_values("name").reset_index(drop=True)

    names = gdf["name"].fillna("").astype(str).tolist()
    postal = gdf["postal"].fillna("").astype(str).tolist()
    iso = gdf["iso_3166_2"].fillna("").astype(str).tolist()
    wkts = gdf.geometry.to_wkt().tolist()

    table = pa.table(
        {
            "name": pa.array(names, type=pa.string()),
            "postal": pa.array(postal, type=pa.string()),
            "iso_3166_2": pa.array(iso, type=pa.string()),
            "geometry": ga.as_wkb(wkts),
        }
    )
    geo = make_geo_metadata(
        columns={
            "geometry": {
                "encoding": "WKB",
                "geometry_types": ["MultiPolygon"],
                "crs": EPSG_5070,
                "edges": "planar",
            }
        }
    )
    out = out_dir / "us-states.parquet"
    write_parquet_deterministic(table, out, geo)
    return out


if __name__ == "__main__":
    print(generate(Path(__file__).resolve().parents[2] / "samples"))
