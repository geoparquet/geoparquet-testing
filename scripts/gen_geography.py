"""Generate data/encodings/ native-geography variants with Apache sedonadb.

sedonadb (Apache Sedona) is the only tool in our stack that emits the Parquet
native Geography logical type. It is a heavy pre-release dependency installed in
a SEPARATE environment (see scripts/README.md, "Geography tier"). These files are
committed snapshots; CI does not byte-diff them (pytest validates them instead).

For each data/encodings/<type>-native-geometry.parquet, this reads the geometry
column, converts it to geography (ST_ToGeography -> spherical edges), and writes
<type>-native-geography.parquet carrying:
  * the native Parquet Geography logical type, and
  * our corpus `geo` metadata (the source file's geo with edges flipped to
    "spherical"), injected via DataFusion's `metadata::geo` writer option so it
    survives without a pyarrow round-trip (which would strip the native type).

Pinned tooling for byte-stability: apache-sedona 1.9.0 / sedonadb 0.4.0a128
(bundled datafusion 52.5.0), created_by="geoparquet-testing".
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from gpqgen.metadata import metadata_bytes
from gpqgen.paths import DATA_DIR

ENC_DIR = DATA_DIR / "encodings"
GEOM_KEYS = ["point", "linestring", "polygon", "multipoint", "multilinestring", "multipolygon"]
CREATED_BY = "geoparquet-testing"


def _geography_geo_str(source_geo: dict) -> str:
    """Source geometry file's geo dict with edges flipped to spherical -> sorted-key JSON str."""
    geo = json.loads(json.dumps(source_geo))  # deep copy
    geo["columns"]["geometry"]["edges"] = "spherical"
    return metadata_bytes(geo).decode("utf-8")


def main() -> None:
    try:
        import sedona.db
    except ImportError:
        print(
            "  skip gen_geography: sedonadb not installed "
            "(see scripts/README.md, 'Geography tier')",
            file=sys.stderr,
        )
        return
    import pyarrow.parquet as pq

    sd = sedona.db.connect()
    for gt in GEOM_KEYS:
        src = ENC_DIR / f"{gt}-native-geometry.parquet"
        out = ENC_DIR / f"{gt}-native-geography.parquet"
        source_geo = json.loads(pq.ParquetFile(src).schema_arrow.metadata[b"geo"])
        geo_str = _geography_geo_str(source_geo)
        t = sd.read_parquet(str(src))
        t.to_view("t", overwrite=True)
        df = sd.sql("SELECT col, ST_ToGeography(geometry) AS geometry FROM t")
        df.to_parquet(
            str(out),
            geoparquet_version="none",
            sort_by="geometry",
            compression="snappy",
            options={"created_by": CREATED_BY, "metadata::geo": geo_str},
        )
        print(f"  wrote data/encodings/{out.name}")

    # Realistic native-geography sample (also sedonadb-tooled).
    from gpqgen.paths import SAMPLES_DIR
    from samples import flight_routes

    out = flight_routes.generate(SAMPLES_DIR)
    print(f"  wrote samples/{out.name}")


if __name__ == "__main__":
    main()
