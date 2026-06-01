"""Generate data/encodings/ — 6 files = 6 geometry types, native-geometry encoding.

Each file holds 3-5 rows: one or more concrete geometries, one EMPTY, one NULL.
Native-geometry uses OGC:CRS84 planar.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import geoarrow.pyarrow as ga
import pyarrow as pa

# Make sibling package importable when running as a script
sys.path.insert(0, str(Path(__file__).resolve().parent))

from gpqgen.metadata import make_geo_metadata
from gpqgen.paths import DATA_DIR, ensure_dir
from gpqgen.write import write_parquet_deterministic

OUT_DIR = DATA_DIR / "encodings"

# CRS84 represented as an OGC auth code dict. Spec-compliant for GeoParquet 2.0.
CRS_OGC_CRS84: dict[str, Any] = {
    "$schema": "https://proj.org/schemas/v0.5/projjson.schema.json",
    "type": "GeographicCRS",
    "name": "WGS 84 (CRS84)",
    "datum_ensemble": {
        "name": "World Geodetic System 1984 ensemble",
        "members": [
            {"name": "World Geodetic System 1984 (Transit)"},
            {"name": "World Geodetic System 1984 (G730)"},
            {"name": "World Geodetic System 1984 (G873)"},
            {"name": "World Geodetic System 1984 (G1150)"},
            {"name": "World Geodetic System 1984 (G1674)"},
            {"name": "World Geodetic System 1984 (G1762)"},
            {"name": "World Geodetic System 1984 (G2139)"},
        ],
        "ellipsoid": {
            "name": "WGS 84",
            "semi_major_axis": 6378137,
            "inverse_flattening": 298.257223563,
        },
        "accuracy": "2.0",
        "id": {"authority": "EPSG", "code": 6326},
    },
    "coordinate_system": {
        "subtype": "ellipsoidal",
        "axis": [
            {"name": "Geodetic longitude", "abbreviation": "Lon", "direction": "east", "unit": "degree"},
            {"name": "Geodetic latitude",  "abbreviation": "Lat", "direction": "north", "unit": "degree"},
        ],
    },
    "scope": "Horizontal component of 3D system.",
    "area": "World.",
    "bbox": {"south_latitude": -90, "west_longitude": -180, "north_latitude": 90, "east_longitude": 180},
    "id": {"authority": "OGC", "code": "CRS84"},
}


# Geometry-type -> list of WKT strings (last entry is None, second-last is EMPTY).
SAMPLES: dict[str, list[str | None]] = {
    "point": [
        "POINT (30 10)",
        "POINT (40 40)",
        "POINT EMPTY",
        None,
    ],
    "linestring": [
        "LINESTRING (30 10, 10 30, 40 40)",
        "LINESTRING EMPTY",
        None,
    ],
    "polygon": [
        "POLYGON ((30 10, 40 40, 20 40, 10 20, 30 10))",
        "POLYGON ((35 10, 45 45, 15 40, 10 20, 35 10), (20 30, 35 35, 30 20, 20 30))",
        "POLYGON EMPTY",
        None,
    ],
    "multipoint": [
        "MULTIPOINT ((30 10))",
        "MULTIPOINT ((10 40), (40 30), (20 20), (30 10))",
        "MULTIPOINT EMPTY",
        None,
    ],
    "multilinestring": [
        "MULTILINESTRING ((30 10, 10 30, 40 40))",
        "MULTILINESTRING ((10 10, 20 20, 10 40), (40 40, 30 30, 40 20, 30 10))",
        "MULTILINESTRING EMPTY",
        None,
    ],
    "multipolygon": [
        "MULTIPOLYGON (((30 10, 40 40, 20 40, 10 20, 30 10)))",
        "MULTIPOLYGON (((30 20, 45 40, 10 40, 30 20)), ((15 5, 40 10, 10 20, 5 10, 15 5)))",
        "MULTIPOLYGON EMPTY",
        None,
    ],
}

# Display-cased geometry types for `geometry_types` metadata.
GEOMETRY_TYPE_CASE = {
    "point": "Point",
    "linestring": "LineString",
    "polygon": "Polygon",
    "multipoint": "MultiPoint",
    "multilinestring": "MultiLineString",
    "multipolygon": "MultiPolygon",
}


def _write_one(geom_key: str, encoding: str) -> Path:
    """Write one encoding-tier file. encoding ∈ {'native-geometry', 'native-geography'}."""
    wkt_list = SAMPLES[geom_key]
    table = pa.table(
        {
            "col": list(range(len(wkt_list))),
            "geometry": ga.as_wkb(wkt_list),
        }
    )
    column_meta: dict[str, Any] = {
        "encoding": "WKB",
        "geometry_types": [GEOMETRY_TYPE_CASE[geom_key]],
        "crs": CRS_OGC_CRS84,
    }
    # Currently unused (deferred): native-geography variants are not generated yet.
    if encoding == "native-geography":
        column_meta["edges"] = "spherical"
    else:
        column_meta["edges"] = "planar"

    geo_meta = make_geo_metadata(columns={"geometry": column_meta})
    out_path = OUT_DIR / f"{geom_key}-{encoding}.parquet"
    write_parquet_deterministic(table, out_path, geo_meta)
    return out_path


def _write_readme() -> None:
    lines = [
        "# data/encodings/",
        "",
        "GeoParquet 2.0 has a single encoding (`\"WKB\"`); the variation here is whether the "
        "Parquet column uses the native Geometry or native Geography logical type. "
        "Only native-geometry (planar `OGC:CRS84`) files are present for now; the "
        "native-geography variants are deferred pending tooling that can emit the Parquet "
        "native Geography logical type.",
        "",
        "| File | Geometry type | Encoding | CRS | Edges |",
        "|---|---|---|---|---|",
    ]
    for geom_key, cased in GEOMETRY_TYPE_CASE.items():
        for encoding in ("native-geometry",):
            edges = "spherical" if encoding == "native-geography" else "planar"
            lines.append(f"| `{geom_key}-{encoding}.parquet` | {cased} | {encoding} | OGC:CRS84 | {edges} |")
    (OUT_DIR / "README.md").write_text("\n".join(lines) + "\n")


def main() -> None:
    ensure_dir(OUT_DIR)
    for geom_key in SAMPLES:
        for encoding in ("native-geometry",):
            out = _write_one(geom_key, encoding)
            print(f"  wrote {out.relative_to(OUT_DIR.parent.parent)}")
    _write_readme()


if __name__ == "__main__":
    main()
