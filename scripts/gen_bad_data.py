"""Generate bad_data/ — files that deliberately violate the GeoParquet spec.

Each violation is one file. The accompanying manifest.json maps filename to
violation description and expected reader failure mode (controlled vocabulary).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Callable, NamedTuple

sys.path.insert(0, str(Path(__file__).resolve().parent))

import geoarrow.pyarrow as ga
import pyarrow as pa

from gpqgen.paths import BAD_DATA_DIR, ensure_dir

# Controlled vocabulary for expected_failure. Documented in bad_data/README.md.
EXPECTED_FAILURES = {
    "wkb_parse_error",
    "schema_validation_error",
    "metadata_missing",
    "metadata_invalid_json",
    "metadata_invalid_utf8",
    "geometry_type_mismatch",
    "crs_mismatch",
    "bbox_mismatch",
    "zm_mismatch",
    "orientation_mismatch",
    "edges_mismatch",
    "epoch_unsupported",
    "version_unknown",
    "version_feature_mismatch",
}


class BadFile(NamedTuple):
    filename: str
    violation: str
    spec_clause: str
    expected_failure: str
    writer: Callable[[Path], None]


# Each writer is added by gen_*_violations() functions in this module.
REGISTRY: list[BadFile] = []


def register(bf: BadFile) -> None:
    if bf.expected_failure not in EXPECTED_FAILURES:
        raise ValueError(f"unknown expected_failure: {bf.expected_failure!r}")
    REGISTRY.append(bf)


def _write_manifest() -> None:
    """Emit bad_data/manifest.json — deterministic key order."""
    entries = {
        bf.filename: {
            "violation": bf.violation,
            "spec_clause": bf.spec_clause,
            "expected_failure": bf.expected_failure,
        }
        for bf in sorted(REGISTRY, key=lambda x: x.filename)
    }
    text = json.dumps(entries, indent=2, sort_keys=True) + "\n"
    (BAD_DATA_DIR / "manifest.json").write_text(text)


def _write_readme() -> None:
    """Emit bad_data/README.md — table of all files + controlled vocabulary."""
    lines = [
        "# bad_data/",
        "",
        "Files that deliberately violate the GeoParquet 2.0 spec. Use these to test that "
        "your reader detects and reports each class of violation. The machine-readable "
        "contract is `manifest.json`.",
        "",
        "## Controlled vocabulary for `expected_failure`",
        "",
    ]
    for ef in sorted(EXPECTED_FAILURES):
        lines.append(f"- `{ef}`")
    lines.extend([
        "",
        "## Files",
        "",
        "| File | Violation | Expected failure |",
        "|---|---|---|",
    ])
    for bf in sorted(REGISTRY, key=lambda x: x.filename):
        lines.append(f"| `{bf.filename}` | {bf.violation} | `{bf.expected_failure}` |")
    (BAD_DATA_DIR / "README.md").write_text("\n".join(lines) + "\n")


def main() -> None:
    ensure_dir(BAD_DATA_DIR)
    # Per-category registration functions are added in Task 3.2.
    register_geometry_type_violations()
    register_crs_violations()
    register_missing_metadata_violations()
    register_wkb_violations()
    register_bbox_violations()
    register_edges_violations()
    register_orientation_violations()
    register_epoch_violations()
    register_zm_violations()
    register_version_violations()
    register_json_validity_violations()

    for bf in REGISTRY:
        bf.writer(BAD_DATA_DIR / bf.filename)
        print(f"  wrote bad_data/{bf.filename}")

    _write_manifest()
    _write_readme()


def register_geometry_type_violations() -> None:
    from gpqgen.metadata import make_geo_metadata
    from gpqgen.write import write_parquet_deterministic
    from bad_helpers import make_simple_point_table

    def writer_mismatch(out: Path) -> None:
        # metadata declares Point, column actually contains LineStrings
        table = pa.table({
            "col": [0, 1],
            "geometry": ga.as_wkb(["LINESTRING (0 0, 1 1)", "LINESTRING (2 2, 3 3)"]),
        })
        meta = make_geo_metadata(columns={"geometry": {
            "encoding": "WKB",
            "geometry_types": ["Point"],
        }})
        write_parquet_deterministic(table, out, meta)

    def writer_missing(out: Path) -> None:
        # declares ["Polygon"], column also contains MultiPolygons
        table = pa.table({
            "col": [0, 1],
            "geometry": ga.as_wkb([
                "POLYGON ((0 0, 1 0, 1 1, 0 0))",
                "MULTIPOLYGON (((2 2, 3 2, 3 3, 2 2)))",
            ]),
        })
        meta = make_geo_metadata(columns={"geometry": {
            "encoding": "WKB",
            "geometry_types": ["Polygon"],
        }})
        write_parquet_deterministic(table, out, meta)

    register(BadFile(
        filename="geometry-types-mismatch-declared-point-actual-linestring.parquet",
        violation="geometry_types declares [\"Point\"] but column contains LineStrings",
        spec_clause="https://github.com/opengeospatial/geoparquet/blob/main/format-specs/geoparquet.md#geometry_types",
        expected_failure="geometry_type_mismatch",
        writer=writer_mismatch,
    ))
    register(BadFile(
        filename="geometry-types-missing-actual-type.parquet",
        violation="geometry_types declares [\"Polygon\"] but column also contains MultiPolygons",
        spec_clause="https://github.com/opengeospatial/geoparquet/blob/main/format-specs/geoparquet.md#geometry_types",
        expected_failure="geometry_type_mismatch",
        writer=writer_missing,
    ))


def register_crs_violations() -> None:
    from gpqgen.metadata import make_geo_metadata
    from gpqgen.write import write_parquet_deterministic
    from bad_helpers import make_simple_point_table

    def writer_mismatch(out: Path) -> None:
        # Schema-level CRS will say one thing; the `geo` metadata says another.
        # (For now we just set the `geo` metadata CRS to EPSG:3857 while encoding
        # plain WKB Point coordinates that are actually CRS84 lon/lat. Implementations
        # comparing schema-level CRS against geo-metadata CRS catch this; readers that
        # only read geo metadata may also catch the units mismatch.)
        table = make_simple_point_table(["POINT (151.0 -33.0)", "POINT (152.0 -34.0)"])
        meta = make_geo_metadata(columns={"geometry": {
            "encoding": "WKB",
            "geometry_types": ["Point"],
            "crs": {"type": "ProjectedCRS", "id": {"authority": "EPSG", "code": 3857}},
        }})
        write_parquet_deterministic(table, out, meta)

    def writer_invalid_projjson(out: Path) -> None:
        table = make_simple_point_table(["POINT (0 0)"])
        meta = make_geo_metadata(columns={"geometry": {
            "encoding": "WKB",
            "geometry_types": ["Point"],
            # Valid JSON, but missing required `type` field — not valid PROJJSON.
            "crs": {"name": "Not a real CRS", "id": {"authority": "XYZ", "code": 999}},
        }})
        write_parquet_deterministic(table, out, meta)

    register(BadFile(
        filename="crs-mismatch-schema-vs-geo-metadata.parquet",
        violation="geo metadata declares EPSG:3857 but coordinates are CRS84 lon/lat",
        spec_clause="https://github.com/opengeospatial/geoparquet/blob/main/format-specs/geoparquet.md#crs",
        expected_failure="crs_mismatch",
        writer=writer_mismatch,
    ))
    register(BadFile(
        filename="crs-invalid-projjson.parquet",
        violation="crs value is JSON but missing required PROJJSON `type` field",
        spec_clause="https://github.com/opengeospatial/geoparquet/blob/main/format-specs/geoparquet.md#crs",
        expected_failure="schema_validation_error",
        writer=writer_invalid_projjson,
    ))


def register_missing_metadata_violations() -> None:
    from gpqgen.metadata import make_geo_metadata, metadata_bytes
    from gpqgen.write import write_parquet_deterministic
    from bad_helpers import (
        make_simple_point_table,
        write_with_metadata_bytes,
        write_without_geo_metadata,
    )
    import json as _json

    def writer_no_geo(out: Path) -> None:
        table = make_simple_point_table(["POINT (0 0)", "POINT (1 1)"])
        write_without_geo_metadata(table, out)

    def writer_missing_version(out: Path) -> None:
        table = make_simple_point_table(["POINT (0 0)"])
        meta = make_geo_metadata()
        meta.pop("version", None)
        write_with_metadata_bytes(table, out, metadata_bytes(meta))

    def writer_missing_primary(out: Path) -> None:
        table = make_simple_point_table(["POINT (0 0)"])
        meta = make_geo_metadata()
        meta.pop("primary_column", None)
        write_with_metadata_bytes(table, out, metadata_bytes(meta))

    def writer_missing_columns(out: Path) -> None:
        table = make_simple_point_table(["POINT (0 0)"])
        meta = make_geo_metadata()
        meta.pop("columns", None)
        write_with_metadata_bytes(table, out, metadata_bytes(meta))

    def writer_primary_not_in_columns(out: Path) -> None:
        table = make_simple_point_table(["POINT (0 0)"])
        meta = make_geo_metadata(primary_column="not_present")
        # restore columns dict but missing the named primary
        meta["columns"] = {"geometry": {"encoding": "WKB", "geometry_types": ["Point"]}}
        write_with_metadata_bytes(table, out, metadata_bytes(meta))

    register(BadFile(
        filename="missing-geo-metadata.parquet",
        violation="no `geo` key in Parquet schema metadata",
        spec_clause="https://github.com/opengeospatial/geoparquet/blob/main/format-specs/geoparquet.md#metadata",
        expected_failure="metadata_missing",
        writer=writer_no_geo,
    ))
    register(BadFile(
        filename="missing-version.parquet",
        violation="`geo` metadata is missing required `version` field",
        spec_clause="https://github.com/opengeospatial/geoparquet/blob/main/format-specs/geoparquet.md#file-metadata",
        expected_failure="schema_validation_error",
        writer=writer_missing_version,
    ))
    register(BadFile(
        filename="missing-primary-column.parquet",
        violation="`geo` metadata is missing required `primary_column`",
        spec_clause="https://github.com/opengeospatial/geoparquet/blob/main/format-specs/geoparquet.md#file-metadata",
        expected_failure="schema_validation_error",
        writer=writer_missing_primary,
    ))
    register(BadFile(
        filename="missing-columns.parquet",
        violation="`geo` metadata is missing required `columns`",
        spec_clause="https://github.com/opengeospatial/geoparquet/blob/main/format-specs/geoparquet.md#file-metadata",
        expected_failure="schema_validation_error",
        writer=writer_missing_columns,
    ))
    register(BadFile(
        filename="primary-column-not-in-columns.parquet",
        violation="`primary_column` value does not appear as a key in `columns`",
        spec_clause="https://github.com/opengeospatial/geoparquet/blob/main/format-specs/geoparquet.md#file-metadata",
        expected_failure="schema_validation_error",
        writer=writer_primary_not_in_columns,
    ))


def register_wkb_violations() -> None:
    from gpqgen.metadata import make_geo_metadata
    from gpqgen.write import write_parquet_deterministic
    from bad_helpers import (
        make_simple_point_table,
        truncate_first_wkb,
        mutate_first_wkb_type_byte,
        prepend_srid_to_first_wkb,
    )

    def writer_truncated(out: Path) -> None:
        table = make_simple_point_table(["POINT (1 2)", "POINT (3 4)"])
        table = truncate_first_wkb(table, drop_bytes=8)
        meta = make_geo_metadata(columns={"geometry": {
            "encoding": "WKB", "geometry_types": ["Point"]}})
        write_parquet_deterministic(table, out, meta)

    def writer_wrong_type_byte(out: Path) -> None:
        # Start with Point (type=1); mutate first row's type code to LineString (type=2)
        table = make_simple_point_table(["POINT (1 2)", "POINT (3 4)"])
        table = mutate_first_wkb_type_byte(table, new_type=2)
        meta = make_geo_metadata(columns={"geometry": {
            "encoding": "WKB", "geometry_types": ["Point"]}})
        write_parquet_deterministic(table, out, meta)

    def writer_with_srid(out: Path) -> None:
        table = make_simple_point_table(["POINT (1 2)", "POINT (3 4)"])
        table = prepend_srid_to_first_wkb(table, srid=4326)
        meta = make_geo_metadata(columns={"geometry": {
            "encoding": "WKB", "geometry_types": ["Point"]}})
        write_parquet_deterministic(table, out, meta)

    register(BadFile(
        filename="wkb-truncated.parquet",
        violation="first row's WKB has 8 bytes chopped from the end",
        spec_clause="https://github.com/opengeospatial/geoparquet/blob/main/format-specs/geoparquet.md#wkb-encoding",
        expected_failure="wkb_parse_error",
        writer=writer_truncated,
    ))
    register(BadFile(
        filename="wkb-wrong-type-byte.parquet",
        violation="first row's WKB header declares LineString but body is a Point",
        spec_clause="https://github.com/opengeospatial/geoparquet/blob/main/format-specs/geoparquet.md#wkb-encoding",
        expected_failure="wkb_parse_error",
        writer=writer_wrong_type_byte,
    ))
    register(BadFile(
        filename="wkb-with-srid-prefix.parquet",
        violation="first row uses EWKB SRID prefix (not allowed in GeoParquet)",
        spec_clause="https://github.com/opengeospatial/geoparquet/blob/main/format-specs/geoparquet.md#wkb-encoding",
        expected_failure="wkb_parse_error",
        writer=writer_with_srid,
    ))


def register_bbox_violations() -> None:
    from gpqgen.metadata import make_geo_metadata
    from gpqgen.write import write_parquet_deterministic
    from bad_helpers import make_simple_point_table

    def writer_bbox_lies(out: Path) -> None:
        # Three Points spanning lon 0..10, lat 0..10; declared bbox is far away.
        table = make_simple_point_table([
            "POINT (0 0)", "POINT (5 5)", "POINT (10 10)",
        ])
        meta = make_geo_metadata(columns={"geometry": {
            "encoding": "WKB",
            "geometry_types": ["Point"],
            "bbox": [100.0, 100.0, 101.0, 101.0],  # wildly wrong
        }})
        write_parquet_deterministic(table, out, meta)

    register(BadFile(
        filename="bbox-does-not-contain-geometry.parquet",
        violation="declared bbox [100,100,101,101] excludes all actual geometries (lon/lat 0-10)",
        spec_clause="https://github.com/opengeospatial/geoparquet/blob/main/format-specs/geoparquet.md#bbox",
        expected_failure="bbox_mismatch",
        writer=writer_bbox_lies,
    ))


def register_edges_violations() -> None:
    from gpqgen.metadata import make_geo_metadata
    from gpqgen.write import write_parquet_deterministic
    import geoarrow.pyarrow as _ga
    import pyarrow as _pa

    def writer_spherical_with_planar_artifact(out: Path) -> None:
        # A LineString that spans from -179 to 179 longitude in a single straight
        # planar segment — interpreted spherically, this would be a near-equatorial
        # great-circle arc, but written as planar coords it implies a line back
        # across most of the globe. Declared `edges: spherical`.
        table = _pa.table({
            "col": [0],
            "geometry": _ga.as_wkb(["LINESTRING (-179 0, 179 0)"]),
        })
        meta = make_geo_metadata(columns={"geometry": {
            "encoding": "WKB",
            "geometry_types": ["LineString"],
            "edges": "spherical",
        }})
        write_parquet_deterministic(table, out, meta)

    register(BadFile(
        filename="edges-spherical-with-planar-antimeridian-line.parquet",
        violation="edges=spherical declared but a planar LineString from -179 to 179 implies "
                  "a line across the long way of the globe",
        spec_clause="https://github.com/opengeospatial/geoparquet/blob/main/format-specs/geoparquet.md#edges",
        expected_failure="edges_mismatch",
        writer=writer_spherical_with_planar_artifact,
    ))


def register_orientation_violations() -> None:
    from gpqgen.metadata import make_geo_metadata
    from gpqgen.write import write_parquet_deterministic
    import geoarrow.pyarrow as _ga
    import pyarrow as _pa

    def writer_declared_ccw_actual_cw(out: Path) -> None:
        # CW exterior ring but metadata says counterclockwise
        table = _pa.table({
            "col": [0],
            "geometry": _ga.as_wkb(["POLYGON ((0 0, 0 1, 1 1, 1 0, 0 0))"]),
        })
        meta = make_geo_metadata(columns={"geometry": {
            "encoding": "WKB",
            "geometry_types": ["Polygon"],
            "orientation": "counterclockwise",
        }})
        write_parquet_deterministic(table, out, meta)

    register(BadFile(
        filename="orientation-ccw-declared-rings-cw.parquet",
        violation="orientation=counterclockwise declared but polygon rings are wound CW",
        spec_clause="https://github.com/opengeospatial/geoparquet/blob/main/format-specs/geoparquet.md#winding-order",
        expected_failure="orientation_mismatch",
        writer=writer_declared_ccw_actual_cw,
    ))


def register_epoch_violations() -> None:
    from gpqgen.metadata import make_geo_metadata
    from gpqgen.write import write_parquet_deterministic
    from bad_helpers import make_simple_point_table

    def writer_epoch_on_unsupported_crs(out: Path) -> None:
        # EPSG:4326 (plain WGS 84) does not support a dynamic coordinate_epoch
        table = make_simple_point_table(["POINT (0 0)"])
        meta = make_geo_metadata(columns={"geometry": {
            "encoding": "WKB",
            "geometry_types": ["Point"],
            "crs": {"type": "GeographicCRS", "id": {"authority": "EPSG", "code": 4326}},
            "coordinate_epoch": 2024.5,
        }})
        write_parquet_deterministic(table, out, meta)

    register(BadFile(
        filename="epoch-on-unsupported-crs.parquet",
        violation="coordinate_epoch set on EPSG:4326 (static datum) which does not support it",
        spec_clause="https://github.com/opengeospatial/geoparquet/blob/main/format-specs/geoparquet.md#coordinate_epoch",
        expected_failure="epoch_unsupported",
        writer=writer_epoch_on_unsupported_crs,
    ))


def register_zm_violations() -> None:
    from gpqgen.metadata import make_geo_metadata
    from gpqgen.write import write_parquet_deterministic
    import geoarrow.pyarrow as _ga
    import pyarrow as _pa

    def writer_declared_xy_actual_xyz(out: Path) -> None:
        # Column actually contains XYZ but metadata claims XY only.
        table = _pa.table({
            "col": [0],
            "geometry": _ga.as_wkb(["POINT Z (1 2 3)"]),
        })
        meta = make_geo_metadata(columns={"geometry": {
            "encoding": "WKB",
            "geometry_types": ["Point"],     # No "Point Z" — declares XY only
        }})
        write_parquet_deterministic(table, out, meta)

    def writer_declared_xyz_actual_xy(out: Path) -> None:
        table = _pa.table({
            "col": [0],
            "geometry": _ga.as_wkb(["POINT (1 2)"]),
        })
        meta = make_geo_metadata(columns={"geometry": {
            "encoding": "WKB",
            "geometry_types": ["Point Z"],   # Declares XYZ
        }})
        write_parquet_deterministic(table, out, meta)

    register(BadFile(
        filename="zm-declared-xy-actual-xyz.parquet",
        violation="geometry_types=[Point] but rows are POINT Z",
        spec_clause="https://github.com/opengeospatial/geoparquet/blob/main/format-specs/geoparquet.md#geometry_types",
        expected_failure="zm_mismatch",
        writer=writer_declared_xy_actual_xyz,
    ))
    register(BadFile(
        filename="zm-declared-xyz-actual-xy.parquet",
        violation="geometry_types=[Point Z] but rows are 2D POINT",
        spec_clause="https://github.com/opengeospatial/geoparquet/blob/main/format-specs/geoparquet.md#geometry_types",
        expected_failure="zm_mismatch",
        writer=writer_declared_xyz_actual_xy,
    ))


def register_version_violations() -> None:
    from gpqgen.metadata import make_geo_metadata
    from gpqgen.write import write_parquet_deterministic
    from bad_helpers import make_simple_point_table

    def writer_unknown_version(out: Path) -> None:
        table = make_simple_point_table(["POINT (0 0)"])
        meta = make_geo_metadata()
        meta["version"] = "99.0.0"
        write_parquet_deterministic(table, out, meta)

    def writer_v1_with_v2_features(out: Path) -> None:
        # Declares version 1.0.0 but uses 2.0-only `coordinate_epoch`.
        table = make_simple_point_table(["POINT (0 0)"])
        meta = make_geo_metadata()
        meta["version"] = "1.0.0"
        meta["columns"] = {"geometry": {
            "encoding": "WKB",
            "geometry_types": ["Point"],
            "coordinate_epoch": 2024.0,
        }}
        write_parquet_deterministic(table, out, meta)

    register(BadFile(
        filename="version-unknown.parquet",
        violation="version=99.0.0 is not a known GeoParquet version",
        spec_clause="https://github.com/opengeospatial/geoparquet/blob/main/format-specs/geoparquet.md#version",
        expected_failure="version_unknown",
        writer=writer_unknown_version,
    ))
    register(BadFile(
        filename="version-1-0-with-2-0-features.parquet",
        violation="version=1.0.0 declared but file uses 2.0-only coordinate_epoch field",
        spec_clause="https://github.com/opengeospatial/geoparquet/blob/main/format-specs/geoparquet.md#version",
        expected_failure="version_feature_mismatch",
        writer=writer_v1_with_v2_features,
    ))


def register_json_validity_violations() -> None:
    from bad_helpers import make_simple_point_table, write_with_metadata_bytes

    def writer_invalid_json(out: Path) -> None:
        table = make_simple_point_table(["POINT (0 0)"])
        # Trailing-comma JSON is invalid per RFC 8259.
        bad = b'{"version": "2.0.0-dev", "primary_column": "geometry", "columns": {"geometry": {"encoding": "WKB",}}}'
        write_with_metadata_bytes(table, out, bad)

    def writer_invalid_utf8(out: Path) -> None:
        table = make_simple_point_table(["POINT (0 0)"])
        # 0xFF is never a valid UTF-8 byte. Wrap inside otherwise-plausible bytes
        # so the file structure is still valid Parquet.
        bad = b'{"version": "2.0.0-dev", "n\xff": "x"}'
        write_with_metadata_bytes(table, out, bad)

    register(BadFile(
        filename="geo-invalid-json.parquet",
        violation="`geo` metadata bytes are not valid JSON (trailing comma)",
        spec_clause="https://github.com/opengeospatial/geoparquet/blob/main/format-specs/geoparquet.md#metadata",
        expected_failure="metadata_invalid_json",
        writer=writer_invalid_json,
    ))
    register(BadFile(
        filename="geo-invalid-utf8.parquet",
        violation="`geo` metadata bytes contain invalid UTF-8 byte (0xFF)",
        spec_clause="https://github.com/opengeospatial/geoparquet/blob/main/format-specs/geoparquet.md#metadata",
        expected_failure="metadata_invalid_utf8",
        writer=writer_invalid_utf8,
    ))


if __name__ == "__main__":
    main()
