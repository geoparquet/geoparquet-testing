"""Generate data/native_only/ — native Parquet geometry without GeoParquet `geo` metadata.

Parquet files whose geometry columns use the native GEOMETRY/GEOGRAPHY logical types but carry
no `geo` key are what DuckDB, Apache Iceberg and the data platforms write. GeoParquet 2.0
readers read them (opengeospatial/geoparquet#308), taking the CRS from the logical type, so they
are positives, not violations. The negative case, a WKB column that nothing identifies as
geometry, is bad_data/missing-geo-metadata.parquet.
"""

from __future__ import annotations

import sys
from pathlib import Path

import geoarrow.pyarrow as ga
import pyarrow as pa

sys.path.insert(0, str(Path(__file__).resolve().parent))

from gpqgen.paths import DATA_DIR, ensure_dir
from gpqgen.write import write_parquet_deterministic

OUT_DIR = DATA_DIR / "native_only"


def main() -> None:
    ensure_dir(OUT_DIR)
    # one native GEOMETRY column, CRS omitted on the logical type (= OGC:CRS84)
    table = pa.table(
        {
            "id": [1, 2, 3],
            "geometry": ga.as_wkb(["POINT (1 1)", "LINESTRING (0 0, 1 1)", "POLYGON ((0 0, 1 0, 1 1, 0 0))"]),
        }
    )
    write_parquet_deterministic(table.replace_schema_metadata(None), OUT_DIR / "native-only-geometry.parquet")
    # two native GEOMETRY columns: with no `primary_column`, readers take the first
    table = pa.table(
        {
            "id": [1, 2],
            "footprint": ga.as_wkb(["POLYGON ((0 0, 2 0, 2 2, 0 0))", "POLYGON ((5 5, 6 5, 6 6, 5 5))"]),
            "centroid": ga.as_wkb(["POINT (1.33 0.67)", "POINT (5.67 5.33)"]),
        }
    )
    write_parquet_deterministic(table.replace_schema_metadata(None), OUT_DIR / "native-only-two-columns.parquet")

    (OUT_DIR / "README.md").write_text(
        "# data/native_only/\n\n"
        "Parquet files whose geometry columns use the native Parquet `GEOMETRY` logical type but carry\n"
        "**no** GeoParquet `geo` metadata, as written by DuckDB, Apache Iceberg and the data platforms.\n"
        "GeoParquet 2.0 readers read them, taking the CRS from the logical type\n"
        "([opengeospatial/geoparquet#308](https://github.com/opengeospatial/geoparquet/issues/308)).\n"
        "They are positives: a reader must open them and find the geometry columns. The negative case,\n"
        "a WKB column that nothing identifies as geometry, is `bad_data/missing-geo-metadata.parquet`.\n\n"
        "| File | Contents | Expected reader behavior |\n"
        "|---|---|---|\n"
        "| `native-only-geometry.parquet` | one native `GEOMETRY` column (Point, LineString, Polygon), "
        "no `crs` on the logical type | geometry column `geometry`, CRS OGC:CRS84 |\n"
        "| `native-only-two-columns.parquet` | two native `GEOMETRY` columns, `footprint` and `centroid` | "
        "both are geometry columns; `footprint` (the first) is the primary |\n"
    )
    print(f"wrote {OUT_DIR}")


if __name__ == "__main__":
    main()
