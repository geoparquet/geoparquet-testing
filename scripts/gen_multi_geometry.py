"""Generate data/multi_geometry/ — two geometry columns per row."""

from __future__ import annotations

import sys
from pathlib import Path

import geoarrow.pyarrow as ga
import pyarrow as pa

sys.path.insert(0, str(Path(__file__).resolve().parent))

from gen_crs import CRS_EPSG_3857_AUTH, CRS_OGC_CRS84_AUTH
from gpqgen.metadata import make_geo_metadata
from gpqgen.paths import DATA_DIR, ensure_dir
from gpqgen.write import write_parquet_deterministic

OUT_DIR = DATA_DIR / "multi_geometry"

FOOTPRINTS_CRS84 = [
    "MULTIPOLYGON (((0 0, 1 0, 1 1, 0 1, 0 0)))",
    "MULTIPOLYGON (((2 2, 3 2, 3 3, 2 3, 2 2)))",
    "MULTIPOLYGON (((4 4, 5 4, 5 5, 4 5, 4 4)))",
]
CENTROIDS_CRS84 = [
    "POINT (0.5 0.5)",
    "POINT (2.5 2.5)",
    "POINT (4.5 4.5)",
]

# Same centroids reprojected to EPSG:3857 (Web Mercator). At low latitudes, lon * 111319.49 ≈ x.
# Computed once and hard-coded for byte stability — no pyproj dependency.
CENTROIDS_3857 = [
    "POINT (55659.745 55672.518)",     # (0.5, 0.5) -> Mercator
    "POINT (278298.726 278445.451)",   # (2.5, 2.5)
    "POINT (500957.708 501429.493)",   # (4.5, 4.5)
]


def _write(fname: str, centroids: list[str], centroid_crs: dict) -> Path:
    table = pa.table(
        {
            "building_id": [1, 2, 3],
            "footprint": ga.as_wkb(FOOTPRINTS_CRS84),
            "centroid": ga.as_wkb(centroids),
        }
    )
    geo = make_geo_metadata(
        primary_column="footprint",
        columns={
            "footprint": {
                "encoding": "WKB",
                "geometry_types": ["MultiPolygon"],
                "crs": CRS_OGC_CRS84_AUTH,
                "edges": "planar",
            },
            "centroid": {
                "encoding": "WKB",
                "geometry_types": ["Point"],
                "crs": centroid_crs,
                "edges": "planar",
            },
        },
    )
    out = OUT_DIR / fname
    write_parquet_deterministic(table, out, geo)
    return out


def main() -> None:
    ensure_dir(OUT_DIR)
    _write("two-geom-columns-same-crs.parquet", CENTROIDS_CRS84, CRS_OGC_CRS84_AUTH)
    print("  wrote two-geom-columns-same-crs.parquet")
    _write("two-geom-columns-different-crs.parquet", CENTROIDS_3857, CRS_EPSG_3857_AUTH)
    print("  wrote two-geom-columns-different-crs.parquet")

    (OUT_DIR / "README.md").write_text(
        "# data/multi_geometry/\n\n"
        "Two geometry columns per row (building `footprint` + its `centroid`). "
        "`primary_column` is set to `footprint`. GeoParquet 2.0 allows per-column CRS.\n\n"
        "| File | footprint CRS | centroid CRS |\n"
        "|---|---|---|\n"
        "| `two-geom-columns-same-crs.parquet` | OGC:CRS84 | OGC:CRS84 |\n"
        "| `two-geom-columns-different-crs.parquet` | OGC:CRS84 | EPSG:3857 |\n"
    )


if __name__ == "__main__":
    main()
