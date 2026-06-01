"""Run every generator. Each gen_*.py module must expose `main()`."""

from __future__ import annotations

import importlib
import pkgutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def discover_generators() -> list[str]:
    """Return sorted list of gen_*.py module names sitting next to generate_all.py."""
    return sorted(
        name
        for _, name, _ in pkgutil.iter_modules([str(HERE)])
        if name.startswith("gen_")
    )


def main() -> int:
    sys.path.insert(0, str(HERE))
    modules = discover_generators()
    if not modules:
        print("No gen_*.py modules found.", file=sys.stderr)
        return 0
    for name in modules:
        print(f"==> {name}")
        mod = importlib.import_module(name)
        if not hasattr(mod, "main"):
            print(f"  skip: {name} has no main()", file=sys.stderr)
            continue
        mod.main()
    print("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
