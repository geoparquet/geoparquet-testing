"""The fixtures really have the property their metadata claims.

Every other test in this suite reads metadata and checks it against the schema or
against the README index. That leaves the most important question unasked: does
the *geometry* actually do what the file says?

It matters most for `bad_data/`. A negative fixture that is accidentally valid is
worse than no fixture at all — every downstream validator that consumes this
corpus will record a passing test for a rule it never exercised. So the negatives
here are asserted to be genuinely non-conforming, not merely present.

The geometries are read back with shapely rather than geoarrow: the generators
write through geoarrow, so an independent reader is what makes the assertion
evidence rather than a round-trip.
"""

import json

import pyarrow.parquet as pq
import pytest
from shapely import wkb as shapely_wkb

from gpqgen.paths import BAD_DATA_DIR, DATA_DIR

ORIENTATION_DIR = DATA_DIR / "orientation"
BBOX_DIR = DATA_DIR / "bbox"


def _geo(path):
    return json.loads(pq.ParquetFile(path).schema_arrow.metadata[b"geo"])


def _geometries(path, column=None):
    geo = _geo(path)
    column = column or geo["primary_column"]
    table = pq.read_table(path)
    return [shapely_wkb.loads(bytes(v.as_py())) for v in table[column]]


def _ring_is_ccw(ring) -> bool:
    """Shoelace sign of a ring: positive area is counterclockwise.

    Computed here rather than taken from ``shapely.is_ccw`` so the corpus states
    its own definition of the winding it distributes fixtures for.
    """
    coords = list(ring.coords)
    twice_area = sum(x1 * y2 - x2 * y1 for (x1, y1, *_), (x2, y2, *_) in zip(coords, coords[1:]))
    return twice_area > 0


def _ring_windings(geom) -> list[tuple[str, bool]]:
    """Flatten a geometry to [(role, is_ccw)] for every polygon ring in it.

    ``role`` is ``"exterior"`` or ``"interior"``. Recurses through MultiPolygon
    and GeometryCollection, because the spec's rule is about polygon rings
    wherever they appear, not only about top-level Polygons. Non-polygonal parts
    contribute nothing.
    """
    if geom.geom_type == "Polygon":
        return [("exterior", _ring_is_ccw(geom.exterior))] + [
            ("interior", _ring_is_ccw(ring)) for ring in geom.interiors
        ]
    if geom.geom_type in ("MultiPolygon", "GeometryCollection"):
        return [entry for part in geom.geoms for entry in _ring_windings(part)]
    return []


def _conforms_to_counterclockwise(geom) -> bool:
    """The spec rule: exterior rings CCW, interior rings CW."""
    return all(
        is_ccw if role == "exterior" else not is_ccw for role, is_ccw in _ring_windings(geom)
    )


# --- data/orientation/: positives -------------------------------------------


@pytest.mark.parametrize(
    "name",
    sorted(p.name for p in ORIENTATION_DIR.glob("*.parquet")),
)
def test_declared_orientation_matches_the_geometry(name):
    """A file declaring counterclockwise must actually be wound that way.

    Parametrized over the whole directory rather than a fixed list, so a fixture
    added later cannot join the tier without being checked.
    """
    path = ORIENTATION_DIR / name
    declared = _geo(path)["columns"]["geometry"].get("orientation")
    geometries = _geometries(path)
    assert geometries, f"{name} has no geometries to check"

    if declared is None:
        # An omitted orientation asserts nothing about winding (spec: "If no
        # value is set, no assertions are made"), so there is nothing to verify.
        return

    assert declared == "counterclockwise", (
        f"{name} declares orientation={declared!r}; the spec allows only "
        '"counterclockwise" or an omitted value'
    )
    for index, geom in enumerate(geometries):
        rings = _ring_windings(geom)
        assert rings, f"{name} row {index} declares orientation but has no polygon rings"
        assert _conforms_to_counterclockwise(geom), (
            f"{name} row {index} declares counterclockwise but its rings are "
            f"wound {rings} (expected exterior CCW, interior CW)"
        )


def test_orientation_tier_covers_holes_multipolygons_and_collections():
    """The tier is only meaningful if it reaches past a bare single-ring Polygon.

    Guards against the positives silently narrowing back to the trivial case.
    """
    seen = set()
    for path in ORIENTATION_DIR.glob("*.parquet"):
        for geom in _geometries(path):
            if geom.geom_type == "Polygon" and geom.interiors:
                seen.add("polygon-with-hole")
            if geom.geom_type == "MultiPolygon":
                seen.add("multipolygon")
            if geom.geom_type == "GeometryCollection":
                seen.add("geometrycollection")
    assert seen >= {"polygon-with-hole", "multipolygon", "geometrycollection"}, (
        f"orientation tier is missing coverage for {sorted({'polygon-with-hole', 'multipolygon', 'geometrycollection'} - seen)}"
    )


# --- bad_data/: the negatives are genuinely negative -------------------------


def _orientation_negatives() -> list[str]:
    manifest = json.loads((BAD_DATA_DIR / "manifest.json").read_text())
    return sorted(
        name
        for name, entry in manifest.items()
        if entry["expected_failure"] == "orientation_mismatch"
    )


@pytest.mark.parametrize("name", _orientation_negatives())
def test_orientation_negative_really_violates_the_declaration(name):
    """An `orientation_mismatch` fixture must actually mismatch.

    Without this, a fixture whose rings were accidentally wound correctly would
    let every downstream validator record a pass for a rule it never ran.
    """
    path = BAD_DATA_DIR / name
    declared = _geo(path)["columns"]["geometry"].get("orientation")
    assert declared == "counterclockwise", (
        f"{name} is registered as orientation_mismatch but declares "
        f"orientation={declared!r} — there is nothing to mismatch"
    )
    geometries = _geometries(path)
    assert any(not _conforms_to_counterclockwise(geom) for geom in geometries), (
        f"{name} is registered as orientation_mismatch but every ring already "
        "conforms (exterior CCW, interior CW) — the fixture is not negative"
    )


def test_orientation_negatives_cover_holes_and_multipolygon_parts():
    """The rule binds interior rings and every part, not just a lone exterior."""
    violations = set()
    for name in _orientation_negatives():
        for geom in _geometries(BAD_DATA_DIR / name):
            rings = _ring_windings(geom)
            if any(role == "interior" and is_ccw for role, is_ccw in rings):
                violations.add("interior-ring-ccw")
            if geom.geom_type == "MultiPolygon" and not _conforms_to_counterclockwise(geom):
                violations.add("multipolygon-part")
            if geom.geom_type == "Polygon" and not _ring_is_ccw(geom.exterior):
                violations.add("exterior-ring-cw")
    assert violations >= {"interior-ring-ccw", "multipolygon-part", "exterior-ring-cw"}, (
        f"orientation negatives are missing {sorted({'interior-ring-ccw', 'multipolygon-part', 'exterior-ring-cw'} - violations)}"
    )


# --- data/bbox/: the declared extent really bounds the data ------------------


def _coordinates(geom) -> list[tuple]:
    if geom.geom_type == "Point":
        return list(geom.coords)
    if geom.geom_type == "LineString":
        return list(geom.coords)
    if geom.geom_type == "Polygon":
        return list(geom.exterior.coords) + [c for r in geom.interiors for c in r.coords]
    if geom.geom_type in ("MultiPoint", "MultiLineString", "MultiPolygon", "GeometryCollection"):
        return [c for part in geom.geoms for c in _coordinates(part)]
    raise AssertionError(f"unhandled geometry type {geom.geom_type}")


# Position of each dimension within the min-half of a bbox of the given length.
# 4 -> [xmin ymin | xmax ymax], 6 -> [xmin ymin zmin | ...],
# 8 -> [xmin ymin zmin mmin | ...]. The 6-element form is XYZ: the spec states
# that M bounds cannot be given without Z bounds ("producers may produce an XY
# bounding box and omit M bounds"), so a 6-element bbox here is never XYM.
_BBOX_DIMENSION_INDEX = {
    4: {"x": 0, "y": 1},
    6: {"x": 0, "y": 1, "z": 2},
    8: {"x": 0, "y": 1, "z": 2, "m": 3},
}


@pytest.mark.parametrize(
    "name",
    sorted(p.name for p in BBOX_DIR.glob("*.parquet")),
)
def test_declared_bbox_bounds_the_data(name):
    """Every declared bbox has a spec length and really encloses its geometries.

    Longitude is checked with an antimeridian-aware rule: per RFC 7946 section 5
    (which the spec defers to for bbox), an extent that crosses the antimeridian
    is written with ``xmin > xmax`` and the valid range is the union of
    ``[xmin, 180]`` and ``[-180, xmax]``.
    """
    path = BBOX_DIR / name
    column_meta = _geo(path)["columns"]["geometry"]
    bbox = column_meta.get("bbox")
    assert bbox is not None, f"{name} is in data/bbox/ but declares no bbox"
    assert len(bbox) in _BBOX_DIMENSION_INDEX, (
        f"{name} declares a {len(bbox)}-element bbox; the spec defines 4 (XY), 6 (XYZ) and 8 (XYZM)"
    )

    half = len(bbox) // 2
    index = _BBOX_DIMENSION_INDEX[len(bbox)]
    coordinates = [c for geom in _geometries(path) for c in _coordinates(geom)]
    assert coordinates, f"{name} has no coordinates to bound"

    crosses_antimeridian = bbox[index["x"]] > bbox[index["x"] + half]
    for dimension, position in index.items():
        low, high = bbox[position], bbox[position + half]
        values = [c[position] for c in coordinates if len(c) > position]
        if dimension != "x":
            assert low <= high, f"{name}: {dimension}min {low} > {dimension}max {high}"
        if not values:
            continue
        if dimension == "x" and crosses_antimeridian:
            assert all(v >= low or v <= high for v in values), (
                f"{name} declares an antimeridian-crossing extent "
                f"[{low}, {high}] but has longitudes outside "
                f"[{low}, 180] u [-180, {high}]: {sorted(values)}"
            )
        else:
            assert low <= min(values) and max(values) <= high, (
                f"{name}: {dimension} range {min(values)}..{max(values)} is not "
                f"inside declared [{low}, {high}]"
            )


def test_bbox_tier_covers_every_spec_length_and_the_antimeridian():
    """4, 6 and 8 element forms plus the wrapped case are all represented."""
    lengths, wrapped = set(), False
    for path in BBOX_DIR.glob("*.parquet"):
        bbox = _geo(path)["columns"]["geometry"].get("bbox")
        if not bbox:
            continue
        lengths.add(len(bbox))
        if bbox[0] > bbox[len(bbox) // 2]:
            wrapped = True
    assert lengths >= {4, 6, 8}, f"bbox tier is missing lengths {sorted({4, 6, 8} - lengths)}"
    assert wrapped, "bbox tier has no antimeridian-crossing (xmin > xmax) example"
