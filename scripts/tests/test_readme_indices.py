"""Every generated .parquet must be mentioned by name in its sibling README.md."""

from pathlib import Path

import pytest

from gpqgen.paths import BAD_DATA_DIR, DATA_DIR, SAMPLES_DIR


def _tier_dirs() -> list[Path]:
    dirs = [SAMPLES_DIR, BAD_DATA_DIR]
    dirs.extend(p for p in sorted(DATA_DIR.iterdir()) if p.is_dir())
    return [d for d in dirs if d.exists()]


@pytest.mark.parametrize("tier_dir", _tier_dirs(), ids=lambda p: p.name)
def test_every_parquet_is_in_readme(tier_dir: Path):
    readme = tier_dir / "README.md"
    if not readme.exists():
        pytest.skip(f"{readme} does not exist yet")
    readme_text = readme.read_text()
    for parquet in sorted(tier_dir.glob("*.parquet")):
        assert parquet.name in readme_text, f"{parquet.name} is not mentioned in {readme}"
