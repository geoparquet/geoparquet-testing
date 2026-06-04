"""Dispatcher for samples/ realistic-tier generators.

Usage:
  uv run python gen_samples.py                    # all samples
  uv run python gen_samples.py --only flight_routes
"""

from __future__ import annotations

import argparse
import importlib
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from gpqgen.paths import SAMPLES_DIR, ensure_dir

# Sample module name -> human-readable label for README.
SAMPLES = [
    "us_states",
    "airports_global",
    "australia_gnss",
    "buildings_with_centroid",
    "gps_trajectory",
    "bathymetry_contours",
]

# Output parquet filename -> producing module under scripts/samples/.
FILE_TO_MODULE = {
    "gps-trajectory-xyzm.parquet": "gps_trajectory",
    "bathymetry-contours.parquet": "bathymetry_contours",
    "australia-gnss-stations.parquet": "australia_gnss",
    "australia-gnss-stations-2024.parquet": "australia_gnss",
    "airports-global.parquet": "airports_global",
    "us-states.parquet": "us_states",
    "buildings-with-centroid.parquet": "buildings_with_centroid",
    "flight-routes-great-circle.parquet": "flight_routes",
}

# Samples not yet produced, with the reason. Documented in samples/README.md by
# _write_readme() so the note survives README regeneration.
DEFERRED_SAMPLES = [
    (
        "nz-building-outlines.parquet",
        "LINZ NZ Building Outlines (CC-BY 4.0) requires a LINZ Data Service API "
        "key, which is not available in this environment. See plan Task 4.2.a "
        "(docs/superpowers/plans/2026-06-01-geoparquet-testing-implementation.md).",
    ),
]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", default=None, help="Generate only the named sample.")
    args = parser.parse_args()

    ensure_dir(SAMPLES_DIR)
    targets = SAMPLES if args.only is None else [args.only]
    for name in targets:
        if name not in SAMPLES:
            print(f"unknown sample: {name}", file=sys.stderr)
            return 2
        try:
            mod = importlib.import_module(f"samples.{name}")
        except ImportError as e:
            print(f"  skip samples.{name}: import failed ({e})")
            continue
        if not hasattr(mod, "generate"):
            print(f"  skip samples.{name}: no generate(out_dir) function")
            continue
        out = mod.generate(SAMPLES_DIR)
        print(f"  wrote samples/{out.name}")

    # Re-write samples/README.md indexing whatever exists on disk now.
    _write_readme()
    return 0


def _write_readme() -> None:
    paths = sorted(SAMPLES_DIR.glob("*.parquet"))
    lines = [
        "# samples/",
        "",
        "Realistic-tier files: plausibly-real datasets sized to flex spec features at "
        "non-trivial row counts. Each entry below records source, license, and what "
        "spec features the file showcases.",
        "",
        "Per-file budget: ≤ 5 MB. CI enforces.",
        "",
        "| File | Size (KB) | Showcases / source |",
        "|---|---|---|",
    ]
    for p in paths:
        size_kb = p.stat().st_size // 1024
        module = FILE_TO_MODULE.get(p.name, p.stem.replace('-', '_'))
        lines.append(f"| `{p.name}` | {size_kb} | _see header of `scripts/samples/{module}.py`_ |")
    if DEFERRED_SAMPLES:
        lines += [
            "",
            "## Deferred samples",
            "",
            "Not yet produced (network/license/toolchain gaps):",
            "",
        ]
        for name, reason in DEFERRED_SAMPLES:
            lines.append(f"- `{name}` — {reason}")
    (SAMPLES_DIR / "README.md").write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    raise SystemExit(main())
