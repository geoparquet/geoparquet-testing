"""Canonical paths in the geoparquet-testing repo."""

from pathlib import Path

# scripts/gpqgen/paths.py -> scripts/ -> repo root
REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_ROOT / "data"
SAMPLES_DIR = REPO_ROOT / "samples"
BAD_DATA_DIR = REPO_ROOT / "bad_data"


def ensure_dir(path: Path) -> Path:
    """Create `path` (and parents) if missing; return it."""
    path.mkdir(parents=True, exist_ok=True)
    return path
