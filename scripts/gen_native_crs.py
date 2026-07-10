"""Stamp a native Parquet CRS onto the non-OGC:CRS84 files, using Apache sedonadb.

GeoParquet 2.0 makes the CRS on the Parquet `GEOMETRY`/`GEOGRAPHY` logical type
the source of truth, and it MUST NOT describe a different CRS than the GeoParquet
`geo` metadata `crs`. Our pyarrow/geoarrow toolchain cannot write a custom CRS
onto that native logical type (it always emits an empty `crs`, i.e. the OGC:CRS84
default), so files whose real CRS is *not* CRS84 would otherwise carry a native
CRS (CRS84) that conflicts with their `geo` metadata.

sedonadb is the one tool in our stack that writes a real native CRS: `ST_SetSRID`
puts inline PROJJSON on the logical type. This module post-processes the affected
committed files — reading each, wrapping the relevant geometry column(s) in
`ST_SetSRID(col, <code>)`, and rewriting with the original `geo` metadata bytes
preserved (so `geometry_types`, `edges`, `epoch`, our inline-PROJJSON `crs`, etc.
are untouched). The native CRS sedonadb emits and our `geo` `crs` both describe
the same authority code, so the two agree as the spec requires.

This is a heavy, generation-only dependency installed in a SEPARATE environment
(see scripts/README.md, "Geography tier"). Like the native-geography files, the
outputs are committed snapshots that CI does not byte-diff (pytest validates
them). It also upgrades the two geopandas-written samples (`buildings-3d`,
`bathymetry-contours`) from plain BYTE_ARRAY to the native logical type.

Run AFTER the pyarrow generators (which produce the CRS84-default base files that
this overwrites): see scripts/README.md.
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from gpqgen.paths import DATA_DIR, SAMPLES_DIR
from gpqgen.write import DEFAULT_ZSTD_LEVEL

CREATED_BY = "geoparquet-testing"

# path (relative to repo root's data/ or samples/) -> {geometry column: EPSG code}.
# The code is the authority code of the column's `geo` metadata CRS. CRS84/EPSG:4326
# columns are left untouched (their empty native CRS already means OGC:CRS84);
# code 4326 is used only to promote the two plain-BYTE_ARRAY samples to the native
# logical type (sedonadb writes an empty native CRS for 4326, i.e. the CRS84 default).
DATA_TARGETS: dict[str, dict[str, int]] = {
    "crs/crs-epsg-3857.parquet": {"geometry": 3857},
    "epoch/epoch-itrf2014-2020.parquet": {"geometry": 7843},
    "epoch/epoch-itrf2014-2024.parquet": {"geometry": 7843},
    "multi_geometry/two-geom-columns-different-crs.parquet": {"centroid": 3857},
}
SAMPLE_TARGETS: dict[str, dict[str, int]] = {
    "us-states.parquet": {"geometry": 5070},
    "australia-gnss-stations.parquet": {"geometry": 7843},
    "australia-gnss-stations-2024.parquet": {"geometry": 7843},
    "buildings-3d.parquet": {"geometry": 7415},      # compound RD New + NAP; also promotes to native
    "bathymetry-contours.parquet": {"geometry": 4326},  # CRS84: promote plain BYTE_ARRAY to native
}


def _stamp(sd, path: Path, codes: dict[str, int]) -> None:
    import pyarrow.parquet as pq

    pf = pq.ParquetFile(path)
    geo_bytes = (pf.schema_arrow.metadata or {})[b"geo"].decode("utf-8")
    names = pf.schema_arrow.names

    select = ", ".join(
        f"ST_SetSRID({n}, {codes[n]}) AS {n}" if n in codes else n for n in names
    )
    sd.read_parquet(str(path)).to_view("src", overwrite=True)
    df = sd.sql(f"SELECT {select} FROM src")

    tmp = Path(tempfile.mkstemp(suffix=".parquet", dir=str(path.parent))[1])
    df.to_parquet(
        str(tmp),
        geoparquet_version="none",
        compression=f"zstd({DEFAULT_ZSTD_LEVEL})",
        options={"created_by": CREATED_BY, "metadata::geo": geo_bytes},
    )
    os.replace(tmp, path)


def main() -> None:
    try:
        import sedona.db
    except ImportError:
        print(
            "  skip gen_native_crs: sedonadb not installed "
            "(see scripts/README.md, 'Geography tier')",
            file=sys.stderr,
        )
        return

    sd = sedona.db.connect()
    for rel, codes in DATA_TARGETS.items():
        _stamp(sd, DATA_DIR / rel, codes)
        print(f"  stamped data/{rel}")
    for rel, codes in SAMPLE_TARGETS.items():
        _stamp(sd, SAMPLES_DIR / rel, codes)
        print(f"  stamped samples/{rel}")


if __name__ == "__main__":
    main()
