# scripts

Generators for the `data/`, `samples/`, and `bad_data/` tiers.

## Setup

Requires [`uv`](https://docs.astral.sh/uv/).

```bash
cd scripts
uv sync --all-extras
```

## Run

```bash
uv run python generate_all.py            # regenerate everything
uv run python gen_encodings.py           # one category
uv run python gen_samples.py --only flight_routes   # one sample
```

All generators are deterministic: re-running produces byte-identical output. CI enforces this.

## Tests

```bash
uv run pytest tests/ -v
```
