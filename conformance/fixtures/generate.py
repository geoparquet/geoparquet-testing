"""Generate every fixture set into conformance/fixtures/out/<set>/.

Run from the repository's scripts/ directory so the uv environment (pyarrow, geoarrow-pyarrow)
and the gpqgen helpers are available:

    cd scripts && uv run python ../conformance/fixtures/generate.py

Then, from conformance/:  cargo run --release -- verify fixtures/out
"""
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SETS = {
    "author": [HERE / "make_fixtures.py"],
    "spec": [HERE / "review/spec/make_fixtures.py"],
    "hostile": sorted((HERE / "review/hostile").glob("gen_*.py")),
    "code": [HERE / "review/code/make.py"],
}

total = 0
for name, scripts in SETS.items():
    out = HERE / "out" / name
    out.mkdir(parents=True, exist_ok=True)
    for script in scripts:
        subprocess.run([sys.executable, str(script)], cwd=script.parent, check=True, stdout=subprocess.DEVNULL)
    n = len(list(out.glob("*.parquet")))
    total += n
    print(f"{name}: {n} files")
print(f"{total} fixtures under {HERE / 'out'}")
