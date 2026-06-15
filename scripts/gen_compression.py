"""Generate data/compression/ — one file per Parquet compression codec.

Every file holds the SAME trivial native-geometry Point table; only the Parquet
compression codec differs. This exercises that a GeoParquet reader can open files
regardless of which Parquet-supported codec was used. The corpus default is
zstd-15 (see gpqgen.write); these files make the other codecs explicit.

Compression LEVEL is never recorded in the Parquet file, so the conformance test
asserts only the codec. Note `lz4_raw` (the Parquet-conformant LZ4 variant) is
reported by pyarrow as the codec string "LZ4".
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import geoarrow.pyarrow as ga
import pyarrow as pa

sys.path.insert(0, str(Path(__file__).resolve().parent))

from gpqgen.crs import CRS84
from gpqgen.metadata import make_geo_metadata
from gpqgen.paths import DATA_DIR, ensure_dir
from gpqgen.write import write_parquet_deterministic

OUT_DIR = DATA_DIR / "compression"

# (filename codec label, pyarrow compression arg, displayed codec)
CODECS: list[tuple[str, str, str]] = [
    ("none", "none", "UNCOMPRESSED"),
    ("snappy", "snappy", "SNAPPY"),
    ("gzip", "gzip", "GZIP"),
    ("brotli", "brotli", "BROTLI"),
    ("lz4-raw", "lz4_raw", "LZ4"),
    ("zstd", "zstd", "ZSTD"),
]


def _table() -> pa.Table:
    return pa.table(
        {
            "col": [0, 1, 2],
            "geometry": ga.as_wkb(["POINT (1 2)", "POINT (3 4)", None]),
        }
    )


def _write(label: str, compression: str) -> Path:
    column_meta: dict[str, Any] = {
        "encoding": "WKB",
        "geometry_types": ["Point"],
        "crs": CRS84,
        "edges": "planar",
    }
    geo = make_geo_metadata(columns={"geometry": column_meta})
    out = OUT_DIR / f"compression-{label}.parquet"
    write_parquet_deterministic(table=_table(), out_path=out, geo_metadata=geo, compression=compression)
    return out


def _write_readme() -> None:
    lines = [
        "# data/compression/",
        "",
        "Six files holding an identical native-geometry Point table, each written with a "
        "different Parquet compression codec. A conformant reader must open all of them. "
        "The corpus default codec is zstd (level 15); these files exercise the others.",
        "",
        "| File | Parquet codec |",
        "|---|---|",
    ]
    for label, _compression, displayed in CODECS:
        lines.append(f"| `compression-{label}.parquet` | {displayed} |")
    lines.append("")
    lines.append(
        "Note: `compression-lz4-raw.parquet` uses the Parquet-conformant LZ4_RAW codec "
        "(pyarrow reports it as `LZ4`). Compression level is not stored in the file."
    )
    (OUT_DIR / "README.md").write_text("\n".join(lines) + "\n")


def main() -> None:
    ensure_dir(OUT_DIR)
    for label, compression, _displayed in CODECS:
        out = _write(label, compression)
        print(f"  wrote {out.relative_to(OUT_DIR.parent.parent)}")
    _write_readme()


if __name__ == "__main__":
    main()
