"""samples/buildings-3d.parquet — 3D building footprints, Delft (NL), from 3DBAG.

Source:    3DBAG (LoD building models for the Netherlands), "pand" footprints.
           https://data.source.coop/cholmes/portolan-nl/tudelft/3dbag/3dbag-pand.parquet
           (mirror of the 3DBAG release by the TU Delft 3D geoinformation group,
           derived from the Dutch BAG building registry). Fetched 2026-06-16.
License:   CC BY 4.0 — © 3DBAG / TU Delft 3D geoinformation; contains BAG data.
           Attribution required: "3DBAG, TU Delft 3D geoinformation group".
Encoding:  WKB (planar edges).
CRS:       EPSG:7415 — "Amersfoort / RD New + NAP height", a 3D **compound CRS**
           (RD New projected horizontal + NAP vertical). Full PROJJSON inline.
Showcases: Polygon **Z** geometry at realistic scale in a compound 3D / projected
           CRS — exercises XYZ coordinates and CompoundCRS PROJJSON. Subset is a
           ~1 km² window over central Delft (~3.9k buildings).

Derived transformation: the upstream "pand" footprints are POLYGON Z with z=0.
Here each footprint's Z is set to its NAP ground-surface height (`b3_h_maaiveld`),
so the buildings sit at their real terrain elevation and the sample carries
meaningful 3D coordinates.

Columns: identificatie (BAG id), bouwjaar (construction year), status, dak_type
(roof type), bouwlagen (storeys), h_maaiveld (ground elevation, m NAP), h_nok
(ridge height, m NAP), volume_lod22 (m³), geometry (WKB Polygon Z).
Rows are sorted by `identificatie` for byte-stable output.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pyarrow as pa

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from gpqgen.metadata import make_geo_metadata
from gpqgen.write import write_parquet_deterministic

SOURCE_URL = (
    "https://data.source.coop/cholmes/portolan-nl/tudelft/3dbag/3dbag-pand.parquet"
)
# ~1 km² window over central Delft, in RD New (EPSG:28992) metres.
BBOX = (84000, 447000, 85000, 448000)
OUT_NAME = "buildings-3d.parquet"


def generate(out_dir: Path) -> Path:
    import duckdb
    import shapely
    from pyproj import CRS

    xmin, ymin, xmax, ymax = BBOX
    con = duckdb.connect()
    con.execute("INSTALL httpfs; LOAD httpfs; INSTALL spatial; LOAD spatial;")
    rows = con.execute(
        f"""
        SELECT identificatie,
               CAST(oorspronkelijkbouwjaar AS INTEGER) AS bouwjaar,
               status,
               b3_dak_type AS dak_type,
               CAST(b3_bouwlagen AS INTEGER) AS bouwlagen,
               b3_h_maaiveld AS h_maaiveld,
               b3_h_nok AS h_nok,
               b3_volume_lod22 AS volume_lod22,
               ST_AsWKB(geom) AS wkb
        FROM read_parquet('{SOURCE_URL}')
        WHERE bbox.xmin >= {xmin} AND bbox.ymin >= {ymin}
          AND bbox.xmax <= {xmax} AND bbox.ymax <= {ymax}
          AND b3_h_maaiveld IS NOT NULL
        ORDER BY identificatie
        """
    ).fetchall()
    ident, bouwjaar, status, dak, lagen, maaiveld, nok, vol, wkb = zip(*rows)

    # Lift each footprint from z=0 to its NAP ground-surface height.
    geometry = []
    for raw, mv in zip(wkb, maaiveld):
        flat = shapely.force_2d(shapely.from_wkb(bytes(raw)))
        lifted = shapely.force_3d(flat, z=float(mv))
        geometry.append(shapely.to_wkb(lifted, output_dimension=3, flavor="iso"))

    table = pa.table(
        {
            "identificatie": pa.array(ident, pa.string()),
            "bouwjaar": pa.array(bouwjaar, pa.int32()),
            "status": pa.array(status, pa.string()),
            "dak_type": pa.array(dak, pa.string()),
            "bouwlagen": pa.array(lagen, pa.int32()),
            "h_maaiveld": pa.array(maaiveld, pa.float64()),
            "h_nok": pa.array(nok, pa.float64()),
            "volume_lod22": pa.array(vol, pa.float64()),
            "geometry": pa.array(geometry, pa.binary()),
        }
    )
    geo = make_geo_metadata(
        columns={
            "geometry": {
                "encoding": "WKB",
                "geometry_types": ["Polygon Z"],
                "crs": CRS.from_epsg(7415).to_json_dict(),
                "edges": "planar",
            }
        }
    )
    out = out_dir / OUT_NAME
    write_parquet_deterministic(table, out, geo)
    return out


if __name__ == "__main__":
    print(generate(Path(__file__).resolve().parents[2] / "samples"))
