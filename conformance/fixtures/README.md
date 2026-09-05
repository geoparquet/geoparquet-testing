# Fixtures: the checker's regression suite

Four generated sets of GeoParquet files, each written by a Python script with pyarrow and
geoarrow-pyarrow (plus the corpus generators' `gpqgen` helpers), and one manifest of the verdict
the checker must give for each file.

| Set | Script(s) | What it covers |
| --- | --- | --- |
| `author` | `make_fixtures.py` | 6/8-element and antimeridian `bbox`, the Bounding Box Covering class (positives and every negative), the Parquet `crs` forms (`EPSG:3857`, inline PROJJSON, `srid:0`, `projjson:<key>`), cases surfaced by the reviews (WKB member type/dimension, ring-count bomb, deep collection, ellipsoid `crs`, unjustified antimeridian bbox, missing `encoding`, phantom column, one-dimensional extent). |
| `spec` | `review/spec/make_fixtures.py` | One file per place where a reviewer suspected the code deviated from the abstract-test text: ideal tiling, CRS by name, URN crs, `encoding` types, nesting, degenerate extents, bbox forms. |
| `hostile` | `review/hostile/gen_*.py` (shared `hlib.py`) | 126 attacks: WKB counts of 2^32-1, nesting to 100 000, empty geometries of every type, ±inf/NaN, big-endian, EWKB, unknown type codes, zero rows, all-null, REPEATED, nested, dictionary/large/view binary, 200 row groups, 50 MB `geo`, 2000-deep JSON, 1000 phantom columns, garbage `crs` parameters, covering variants, non-Parquet bytes with a `.parquet` name. |
| `code` | `review/code/make.py` | Allocation bombs, dictionary-hinted geometry, `large_binary`, nested dimension mismatch, shoelace precision at 1e7 offsets. |

`expected.json` maps each generated file to the abstract tests that must fail for it (and, by
omission, the ones that must not). It was produced with `verify --update` after the verdicts were
reviewed by hand in the hardening round; treat a diff in it as a behaviour change to be justified.

```
cd scripts && uv run python ../conformance/fixtures/generate.py      # writes fixtures/out/<set>/
cd ../conformance && cargo run --release -- verify fixtures/out       # compares with expected.json
cargo run --release -- verify fixtures/out --update                   # after reviewing a change
```

The other layers of the suite: `cargo test` (WKB decoder and spatial metric unit tests), `corpus ..`
(this repository's `data/` must pass and `bad_data/` must fail the mapped test), and the remote
smoke list in `remote_smoke.sh` (public files on S3/HTTPS; needs the network, not run in CI).
