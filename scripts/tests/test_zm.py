"""Conformance: data/zm/."""

import json
import struct

import pyarrow.parquet as pq

from gpqgen.paths import DATA_DIR

ZM_DIR = DATA_DIR / "zm"


# WKB type codes per OGC: XYZ adds 1000, XYM adds 2000, XYZM adds 3000.
def _first_wkb_type(path) -> int:
    t = pq.read_table(path)
    b = t.column("geometry")[0].as_py()
    endian = "<" if b[0] == 1 else ">"
    return struct.unpack(f"{endian}I", b[1:5])[0]


def test_xyz_file_has_z_dimension():
    code = _first_wkb_type(ZM_DIR / "linestring-xyz-native-geometry.parquet")
    assert code == 1002, f"expected LineString XYZ (1002), got {code}"


def test_xym_file_has_m_dimension():
    code = _first_wkb_type(ZM_DIR / "linestring-xym-native-geometry.parquet")
    assert code == 2002, f"expected LineString XYM (2002), got {code}"


def test_xyzm_file_has_zm_dimensions():
    code = _first_wkb_type(ZM_DIR / "linestring-xyzm-native-geometry.parquet")
    assert code == 3002, f"expected LineString XYZM (3002), got {code}"


def _declared_geometry_types(path) -> list[str]:
    meta = pq.ParquetFile(path).metadata.metadata
    return json.loads(meta[b"geo"])["columns"]["geometry"]["geometry_types"]


def test_declared_geometry_types_carry_dimension_suffix():
    """Spec: 'a \" Z\" suffix gets added' and the field is 'strictly correct'."""
    expected = {
        "linestring-xyz-native-geometry.parquet": ["LineString Z"],
        "linestring-xym-native-geometry.parquet": ["LineString M"],
        "linestring-xyzm-native-geometry.parquet": ["LineString ZM"],
    }
    for fname, types in expected.items():
        assert _declared_geometry_types(ZM_DIR / fname) == types, fname
