"""Generate data/epoch/ — same CRS (GDA2020, EPSG:7843), two epochs."""

from __future__ import annotations

import sys
from pathlib import Path

import geoarrow.pyarrow as ga
import pyarrow as pa

sys.path.insert(0, str(Path(__file__).resolve().parent))

from gpqgen.metadata import make_geo_metadata
from gpqgen.paths import DATA_DIR, ensure_dir
from gpqgen.write import write_parquet_deterministic

OUT_DIR = DATA_DIR / "epoch"

CRS_GDA2020 = {
    "type": "GeographicCRS",
    "id": {"authority": "EPSG", "code": 7843},
}

# Sydney CBD as of epoch 2020.0
SYDNEY_2020_LON = 151.2093
SYDNEY_2020_LAT = -33.8688

# Australian plate velocity at this location is ~7 cm/yr north, ~2 cm/yr east.
# Over 4 years (2020.0 -> 2024.0): ~28 cm north, ~8 cm east.
# Convert to degrees (1 deg latitude ≈ 111_320 m everywhere; 1 deg longitude
# at this latitude ≈ 111_320 * cos(33.87°) ≈ 92_500 m).
DLAT_PER_YEAR = 0.07 / 111_320          # ~6.3e-7 deg/yr
DLON_PER_YEAR = 0.02 / 92_500           # ~2.2e-7 deg/yr
YEARS = 4.0
SYDNEY_2024_LAT = SYDNEY_2020_LAT + DLAT_PER_YEAR * YEARS
SYDNEY_2024_LON = SYDNEY_2020_LON + DLON_PER_YEAR * YEARS


def _write(fname: str, lon: float, lat: float, epoch: float) -> Path:
    table = pa.table(
        {
            "station": ["SYD1", "SYD2", "SYD3"],
            "geometry": ga.as_wkb([
                f"POINT ({lon} {lat})",
                f"POINT ({lon + 0.01} {lat + 0.01})",
                f"POINT ({lon - 0.01} {lat - 0.01})",
            ]),
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
    out = OUT_DIR / fname
    write_parquet_deterministic(table, out, geo)
    return out


def main() -> None:
    ensure_dir(OUT_DIR)
    _write("epoch-itrf2014-2020.parquet", SYDNEY_2020_LON, SYDNEY_2020_LAT, 2020.0)
    print("  wrote data/epoch/epoch-itrf2014-2020.parquet")
    _write("epoch-itrf2014-2024.parquet", SYDNEY_2024_LON, SYDNEY_2024_LAT, 2024.0)
    print("  wrote data/epoch/epoch-itrf2014-2024.parquet")

    (OUT_DIR / "README.md").write_text(
        "# data/epoch/\n\n"
        "Two files in EPSG:7843 (GDA2020) at the same nominal Sydney location, "
        "differing only in `epoch`. The 2024 file's coordinates are "
        "propagated forward from the 2020 file using Australian plate velocity "
        "(~7 cm/yr north, ~2 cm/yr east) — about 28 cm north over 4 years. "
        "Together these demonstrate that epoch is numerically meaningful.\n\n"
        "| File | CRS | epoch |\n"
        "|---|---|---|\n"
        "| `epoch-itrf2014-2020.parquet` | EPSG:7843 | 2020.0 |\n"
        "| `epoch-itrf2014-2024.parquet` | EPSG:7843 | 2024.0 |\n"
    )


if __name__ == "__main__":
    main()
