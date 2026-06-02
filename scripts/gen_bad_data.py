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


# Placeholder registrations — implementations in Task 3.2.
def register_geometry_type_violations() -> None: ...
def register_crs_violations() -> None: ...
def register_missing_metadata_violations() -> None: ...
def register_wkb_violations() -> None: ...
def register_bbox_violations() -> None: ...
def register_edges_violations() -> None: ...
def register_orientation_violations() -> None: ...
def register_epoch_violations() -> None: ...
def register_zm_violations() -> None: ...
def register_version_violations() -> None: ...
def register_json_validity_violations() -> None: ...


if __name__ == "__main__":
    main()
