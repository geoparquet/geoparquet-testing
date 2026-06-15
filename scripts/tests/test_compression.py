"""Conformance: data/compression/."""

from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from gpqgen.paths import DATA_DIR
from gpqgen.write import write_parquet_deterministic

COMPRESSION_DIR = DATA_DIR / "compression"

# filename label -> expected codec string as pyarrow reports it
EXPECTED_CODECS = {
    "none": "UNCOMPRESSED",
    "snappy": "SNAPPY",
    "gzip": "GZIP",
    "brotli": "BROTLI",
    "lz4-raw": "LZ4",
    "zstd": "ZSTD",
}


def _codec(path: Path) -> str:
    return pq.ParquetFile(path).metadata.row_group(0).column(0).compression


@pytest.mark.parametrize("label", EXPECTED_CODECS)
def test_compression_file_exists(label: str):
    assert (COMPRESSION_DIR / f"compression-{label}.parquet").exists()


@pytest.mark.parametrize(("label", "expected"), EXPECTED_CODECS.items())
def test_compression_codec(label: str, expected: str):
    path = COMPRESSION_DIR / f"compression-{label}.parquet"
    assert _codec(path) == expected


def test_default_writer_uses_zstd(tmp_path: Path):
    """The corpus default codec is zstd — guards against regressing the default."""
    out = tmp_path / "default.parquet"
    write_parquet_deterministic(table=pa.table({"col": [0, 1, 2]}), out_path=out)
    assert _codec(out) == "ZSTD"
