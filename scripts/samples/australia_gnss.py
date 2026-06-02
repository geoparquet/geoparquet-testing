"""samples/australia-gnss-stations.parquet (+ -2024.parquet) — GDA2020 GNSS sites.

Source:    SYNTHETIC / hand-curated. ~30 approximate coordinates hand-entered to
           sit near real Australian cities and GNSS sites. These are NOT taken
           from any licensed dataset; they are rounded, plausible placeholders.
License:   CC0 / public domain (hand-entered approximate coordinates).
Encoding:  WKB (native geometry, planar edges).
CRS:       EPSG:7843 (GDA2020), a dynamic datum.
Showcases: epoch + dynamic datum + plate-motion propagation +
           paired files. Two files are produced:
             - australia-gnss-stations.parquet       epoch 2020.0
             - australia-gnss-stations-2024.parquet  epoch 2024.0
           The 2024 positions are the 2020 positions shifted by the Australian
           plate velocity (~7 cm/yr north, ~2 cm/yr east) over 4 years, using
           the constants in gen_epoch.py. Same 30 rows / row order in both
           files; only coordinates and the epoch differ.

`generate()` writes BOTH files and returns the path of the 2020 file (the
dispatcher prints one name; the README globs both).
"""

from __future__ import annotations

import sys
from pathlib import Path

import geoarrow.pyarrow as ga
import pyarrow as pa

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from gen_epoch import CRS_GDA2020, DLAT_PER_YEAR, DLON_PER_YEAR
from gpqgen.metadata import make_geo_metadata
from gpqgen.write import write_parquet_deterministic

YEARS = 4.0  # 2020.0 -> 2024.0

# (station_code, name, lon, lat) at epoch 2020.0. Hand-entered approximate
# coordinates near real Australian cities/sites. Row order is fixed here.
STATIONS = [
    ("SYDN", "Sydney", 151.20930, -33.86880),
    ("MELB", "Melbourne", 144.96320, -37.81360),
    ("PERT", "Perth", 115.85730, -31.95350),
    ("DARW", "Darwin", 130.84560, -12.46340),
    ("BRIS", "Brisbane", 153.02510, -27.46980),
    ("ADEL", "Adelaide", 138.60070, -34.92850),
    ("HOBT", "Hobart", 147.32720, -42.88210),
    ("CANB", "Canberra", 149.13000, -35.28090),
    ("ALIC", "Alice Springs", 133.88070, -23.69800),
    ("CARN", "Cairns", 145.77810, -16.92030),
    ("NEWC", "Newcastle", 151.78170, -32.92670),
    ("WOLL", "Wollongong", 150.89310, -34.42780),
    ("GCST", "Gold Coast", 153.40000, -28.01670),
    ("TOWN", "Townsville", 146.81690, -19.25900),
    ("GEEL", "Geelong", 144.36170, -38.14990),
    ("BALL", "Ballarat", 143.85030, -37.56220),
    ("BEND", "Bendigo", 144.27940, -36.75700),
    ("LAUN", "Launceston", 147.13970, -41.42910),
    ("ALBY", "Albany", 117.88370, -35.02690),
    ("BROO", "Broome", 122.23740, -17.95540),
    ("KALG", "Kalgoorlie", 121.46550, -30.74900),
    ("MTIS", "Mount Isa", 139.49270, -20.72560),
    ("ROCK", "Rockhampton", 150.50690, -23.37810),
    ("TOOW", "Toowoomba", 151.95070, -27.56020),
    ("BUND", "Bundaberg", 152.34890, -24.86610),
    ("DUBB", "Dubbo", 148.60140, -32.24340),
    ("WAGA", "Wagga Wagga", 147.36980, -35.10820),
    ("PTAU", "Port Augusta", 137.76330, -32.49270),
    ("MILD", "Mildura", 142.13680, -34.20630),
    ("KARR", "Karratha", 116.84720, -20.73640),
]


def _write(fname: str, epoch: float, dlat: float, dlon: float, out_dir: Path) -> Path:
    codes = [s[0] for s in STATIONS]
    names = [s[1] for s in STATIONS]
    wkts = [f"POINT ({s[2] + dlon:.8f} {s[3] + dlat:.8f})" for s in STATIONS]
    table = pa.table(
        {
            "station_code": pa.array(codes, type=pa.string()),
            "name": pa.array(names, type=pa.string()),
            "geometry": ga.as_wkb(wkts),
        }
    )
    geo = make_geo_metadata(
        columns={
            "geometry": {
                "encoding": "WKB",
                "geometry_types": ["Point"],
                "crs": CRS_GDA2020,
                "edges": "planar",
                "epoch": epoch,
            }
        }
    )
    out = out_dir / fname
    write_parquet_deterministic(table, out, geo)
    return out


def generate(out_dir: Path) -> Path:
    out_2020 = _write(
        "australia-gnss-stations.parquet", 2020.0, 0.0, 0.0, out_dir
    )
    _write(
        "australia-gnss-stations-2024.parquet",
        2024.0,
        DLAT_PER_YEAR * YEARS,
        DLON_PER_YEAR * YEARS,
        out_dir,
    )
    return out_2020
