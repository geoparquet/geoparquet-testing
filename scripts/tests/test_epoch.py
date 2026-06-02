"""Conformance: data/epoch/."""

import json

import pyarrow.parquet as pq

from gpqgen.paths import DATA_DIR

EPOCH_DIR = DATA_DIR / "epoch"


def _geo(name: str) -> dict:
    pf = pq.ParquetFile(EPOCH_DIR / name)
    return json.loads(pf.schema_arrow.metadata[b"geo"])


def test_2020_has_epoch_2020():
    geo = _geo("epoch-itrf2014-2020.parquet")
    col = geo["columns"]["geometry"]
    assert col["coordinate_epoch"] == 2020.0
    assert col["crs"]["id"]["code"] == 7843


def test_2024_has_epoch_2024():
    geo = _geo("epoch-itrf2014-2024.parquet")
    col = geo["columns"]["geometry"]
    assert col["coordinate_epoch"] == 2024.0
    assert col["crs"]["id"]["code"] == 7843


def test_coordinates_shifted_between_epochs():
    """Verify the 2024 file's first point is north of the 2020 file's by ~28 cm."""
    import pyarrow as pa
    t_2020 = pq.read_table(EPOCH_DIR / "epoch-itrf2014-2020.parquet")
    t_2024 = pq.read_table(EPOCH_DIR / "epoch-itrf2014-2024.parquet")
    # Decode the first WKB POINT manually: 1 byte endianness + 4 bytes type + 16 bytes XY
    import struct
    def read_xy(b: bytes) -> tuple[float, float]:
        endian = "<" if b[0] == 1 else ">"
        return struct.unpack(f"{endian}dd", b[5:21])
    x20, y20 = read_xy(t_2020.column("geometry")[0].as_py())
    x24, y24 = read_xy(t_2024.column("geometry")[0].as_py())
    # Australian plate moves north ~7cm/yr -> ~28cm over 4 years.
    # 28cm at the equator ≈ 0.0000025 deg latitude. At Sydney (-33.86 lat) similar.
    dy = y24 - y20
    assert 0.0000020 < dy < 0.0000030, f"expected ~28cm northward shift, got dy={dy}"
