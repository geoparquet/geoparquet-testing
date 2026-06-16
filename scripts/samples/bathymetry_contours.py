"""samples/bathymetry-contours.parquet — real ocean depth contours (Natural Earth).

Source:    Natural Earth 1:10m physical "Bathymetry" (ne_10m_bathymetry_all).
           https://www.naturalearthdata.com/downloads/10m-physical-vectors/
           CDN: https://naciscdn.org/naturalearth/10m/physical/ne_10m_bathymetry_all.zip
           Fetched 2026-06-16.
License:   Public domain (Natural Earth — no permission needed, no attribution required).
Encoding:  WKB (planar edges).
CRS:       OGC:CRS84 (lon/lat, WGS 84).
Showcases: XYZ MultiLineString geometry where Z carries depth (negative metres below
           sea level). Subset is a window over the Mariana Trench / Philippine Sea
           (lon 140-150, lat 5-22) — real generalized seafloor contours spanning the
           full Natural Earth depth range, 0 down to -10000 m. geometry_types =
           ["MultiLineString Z"].

Natural Earth ships bathymetry as polygon depth bands (one shapefile per depth, 0
to 10000 m). Each band's polygon boundaries become a contour MultiLineString, with
every vertex's Z set to that band's depth (negative metres). The contour *lines* are
clipped to the region window (clipping the lines, not the polygons, avoids drawing a
rectangular frame along the bbox edges). One row per source feature; depth carried
both as the `depth_m` attribute and in the geometry Z.

Columns: depth_m (int, metres below sea level, negative), featurecla, scalerank,
geometry (WKB MultiLineString Z). Rows sorted by (depth_m, geometry) for byte-stable
output.
"""

from __future__ import annotations

import io
import re
import sys
import tempfile
import zipfile
from pathlib import Path

import pyarrow as pa

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from gpqgen.crs import CRS84
from gpqgen.metadata import make_geo_metadata
from gpqgen.write import write_parquet_deterministic

ZIP_URL = "https://naciscdn.org/naturalearth/10m/physical/ne_10m_bathymetry_all.zip"
# Window over the Mariana Trench / Philippine Sea, in lon/lat (WGS 84).
BBOX = (140.0, 5.0, 150.0, 22.0)
OUT_NAME = "bathymetry-contours.parquet"


def generate(out_dir: Path) -> Path:
    import geopandas as gpd
    import requests
    import shapely
    from shapely.geometry import MultiLineString, box

    resp = requests.get(ZIP_URL, timeout=120)
    resp.raise_for_status()
    region = box(*BBOX)

    def to_multilinestring(geom):
        """Collect all line components of geom into a MultiLineString (or None)."""
        if geom is None or geom.is_empty:
            return None
        if geom.geom_type == "LineString":
            return MultiLineString([geom])
        if geom.geom_type == "MultiLineString":
            return geom
        # GeometryCollection (e.g. a tangent point alongside lines): keep the lines.
        parts = [g for g in getattr(geom, "geoms", []) if g.geom_type == "LineString"]
        return MultiLineString(parts) if parts else None

    depth_m, featurecla, scalerank, geometry = [], [], [], []
    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        shp_names = sorted(n for n in zf.namelist() if n.endswith(".shp"))
        with tempfile.TemporaryDirectory() as tmp:
            zf.extractall(tmp)
            for shp in shp_names:
                depth = int(re.search(r"_(\d+)\.shp$", shp).group(1))
                gdf = gpd.read_file(Path(tmp) / Path(shp).name)
                gdf = gdf[gdf.intersects(region)].copy()
                if gdf.empty:
                    continue
                # Lines first, THEN clip the lines — clipping polygons would add a
                # rectangular frame along the bbox; clipping lines just trims them.
                gdf["geometry"] = gdf.geometry.boundary
                gdf = gpd.clip(gdf, region)
                for _, row in gdf.iterrows():
                    mls = to_multilinestring(row.geometry)
                    if mls is None:
                        continue
                    lifted = shapely.force_3d(mls, z=-float(depth))
                    depth_m.append(-depth)
                    featurecla.append(row.get("featurecla"))
                    scalerank.append(int(row["scalerank"]) if row.get("scalerank") is not None else None)
                    geometry.append(shapely.to_wkb(lifted, output_dimension=3, flavor="iso"))

    # Stable order independent of file/clip iteration order.
    order = sorted(range(len(geometry)), key=lambda i: (depth_m[i], geometry[i]))
    table = pa.table(
        {
            "depth_m": pa.array([depth_m[i] for i in order], pa.int64()),
            "featurecla": pa.array([featurecla[i] for i in order], pa.string()),
            "scalerank": pa.array([scalerank[i] for i in order], pa.int32()),
            "geometry": pa.array([geometry[i] for i in order], pa.binary()),
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
    out = out_dir / OUT_NAME
    write_parquet_deterministic(table, out, geo)
    return out


if __name__ == "__main__":
    print(generate(Path(__file__).resolve().parents[2] / "samples"))
