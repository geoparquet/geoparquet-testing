# geoparquet-testing

Test corpus for the [GeoParquet](https://github.com/opengeospatial/geoparquet) format, modeled after
[apache/parquet-testing](https://github.com/apache/parquet-testing).

**Targets:** GeoParquet 2.0 (in development).
**Status:** under active construction — file index will be added as generators land.

## Layout

- `data/` — small, systematic conformance files
- `samples/` — realistic datasets that flex spec features at non-trivial size
- `bad_data/` — files that deliberately violate the spec; see `bad_data/manifest.json`
- `scripts/` — generators (run with `uv`)

## Consumption

### As a git submodule

```bash
git submodule add https://github.com/geoparquet/geoparquet-testing tests/data/geoparquet-testing
```

### Pinned to a release

Download a tarball from the [releases page](https://github.com/geoparquet/geoparquet-testing/releases).

## Regenerating files

```bash
cd scripts
uv sync
uv run python generate_all.py
```

## License

Apache 2.0. Realistic samples under `samples/` retain their upstream licenses — see `samples/README.md`.
