"""samples/airports-global.parquet — large airports worldwide (OurAirports).

Source:    OurAirports `airports.csv`
           https://davidmegginson.github.io/ourairports-data/airports.csv
           Fetched 2026-06-02.
License:   Public domain (OurAirports data is dedicated to the public domain;
           https://ourairports.com/data/ — "You may use any of this data however
           you wish."). No attribution required.
Encoding:  WKB (native geometry, planar edges).
CRS:       default — the `crs` field is OMITTED, so readers default to OGC:CRS84
           (lon/lat, WGS 84).
Showcases: Point geometry with a default (omitted) CRS. Filtered to
           type == "large_airport" (~1,200 rows). geometry_types = ["Point"].

Columns: ident (str), name (str), iso_country (str), geometry (WKB Point).
Rows are sorted by `ident` for byte-stable output.
"""

from __future__ import annotations

import io
import sys
from pathlib import Path

import geoarrow.pyarrow as ga
import pyarrow as pa
import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from gpqgen.metadata import make_geo_metadata
from gpqgen.write import write_parquet_deterministic

CSV_URL = "https://davidmegginson.github.io/ourairports-data/airports.csv"


def generate(out_dir: Path) -> Path:
    import pandas as pd

    resp = requests.get(CSV_URL, timeout=60)
    resp.raise_for_status()
    df = pd.read_csv(io.StringIO(resp.text))

    df = df[df["type"] == "large_airport"].copy()
    df = df.sort_values("ident").reset_index(drop=True)

    idents = df["ident"].fillna("").astype(str).tolist()
    names = df["name"].fillna("").astype(str).tolist()
    countries = df["iso_country"].fillna("").astype(str).tolist()
    wkts = [
        f"POINT ({lon:.6f} {lat:.6f})"
        for lon, lat in zip(df["longitude_deg"], df["latitude_deg"])
    ]

    table = pa.table(
        {
            "ident": pa.array(idents, type=pa.string()),
            "name": pa.array(names, type=pa.string()),
            "iso_country": pa.array(countries, type=pa.string()),
            "geometry": ga.as_wkb(wkts),
        }
    )
    geo = make_geo_metadata(
        columns={
            "geometry": {
                "encoding": "WKB",
                "geometry_types": ["Point"],
                "edges": "planar",
            }
        }
    )
    out = out_dir / "airports-global.parquet"
    write_parquet_deterministic(table, out, geo)
    return out


if __name__ == "__main__":
    print(generate(Path(__file__).resolve().parents[2] / "samples"))
