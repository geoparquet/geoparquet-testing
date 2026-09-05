# geoparquet-conf (experiment)

A GeoParquet 2.0 conformance checker in Rust that runs the abstract tests of the OGC draft
(`ogc/abstract_tests/` in opengeospatial/geoparquet#304) on a single file, using only the Apache
Arrow Rust `parquet` crate. No DuckDB, no GDAL, no PROJ. Written in one session to assess Chris
Holmes's suggestion of "a clean test suite ... don't pull in duckdb". **Prototype, not a product.**

## What it does

```
geoparquet-conf check file.parquet [--json] [--class core|covering|distribution]
geoparquet-conf check s3://bucket/prefix/ --max-files 5 --max-rows 100000 --s3-region us-west-2
geoparquet-conf check https://host/path/file.parquet     # also gs://, az://, a local directory
geoparquet-conf corpus ..          # from conformance/: data/ must pass, bad_data/ must fail the mapped test
```

Remote objects are read with range requests through the `object_store` crate (anonymous when no
credentials are in the environment; `--opt key=value` passes any object_store option). The footer
comes down in one request; the scan fetches whole column chunks, merged per row group and split into
16 MB parts fetched concurrently. `--max-rows N` reads only the first row groups that hold N rows and
marks the data tests as sampled, which is how a 700 MB Overture file is checked in a few seconds.
Exit codes: 0 conformant, 1 a test failed, 2 the tool could not run (unreadable path, bad URL).

Every abstract test of the three conformance classes is implemented and reports pass / fail / skip
with a message naming the column and the offending value:

| Class | Tests | Notes |
| --- | --- | --- |
| Core | 20 | `media-type` always skipped (not testable on a file). |
| Bounding Box Covering | 6 | Skipped as "not claimed" when no column declares `covering`. |
| Cloud-Optimized Distribution | 2 | `spatial-order` uses the pruning metric with gpio's parameters (geoparquet-io #774: 20 windows of 10 % side, seed 42, pass at 0.70 of the ideal tiling's skip rate, verdict withheld below five row groups) and also prints the area factor Σ row-group bbox area / extent. The window sequence differs from gpio's, so near-threshold verdicts can differ. |

Design: one pass over the data per geometry column (arrow record batches, WKB decoded by a
150-line ISO WKB reader that rejects EWKB), everything else from the footer. Schema validation
uses the vendored GeoParquet 2.0.0 `schema.json` and the PROJJSON 0.7 schema (registered under its
URL, so the tool works offline; validated against the PROJJSON `crs` definition only, because the
full PROJJSON schema also accepts datums and ellipsoids). CRS equality is by authority:code after
normalising EPSG:4326 / OGC:CRS84; a PROJJSON without an `id` is reported as "cannot compare
without a CRS library" rather than passed or failed.

## Results (2026-09-05)

this corpus at `main` 6f7ede1 (48 valid + 26 defective files), whole run 0.03 s (0.7 s before the PROJJSON schema was vendored, all of it a network fetch):

* data/: 48 of 48 pass Core; all 48 carry geospatial statistics; spatial order not measurable
  (single row group).
* bad_data/: 24 of 24 files with an OGC requirement are failed by the mapped test; the remaining
  two (`edges_mismatch`, `epoch_unsupported`) have no OGC requirement, as expected.

33 adversarial fixtures of the author's (`fixtures/make_fixtures.py`: 6/8-element and antimeridian bbox
violations, 11 covering positives/negatives incl. nullness mismatch and nested column, 7 Parquet
`crs` forms: `EPSG:3857`, inline PROJJSON, `srid:0`, `projjson:<key>`, mismatches): all behave as
intended.

Multi-row-group files (DuckDB, `GEOPARQUET_VERSION 'V2'`), full Core + Distribution run, Docker on an
M-series laptop:

| File | Rows | Row groups | Wall time | spatial-order (ours) | gpio `check spatial` (main) |
| --- | --- | --- | --- | --- | --- |
| points, random order | 1 000 000 | 10 | 0.41 s | FAIL ratio 0.00 | poor |
| points, Hilbert | 1 000 000 | 10 | 0.22 s | PASS ratio 0.93 | ordered |
| 20 clusters, Hilbert | 500 000 | 10 | 0.16 s | PASS ratio 1.00 | ordered |
| squares, DuckDB ST_Hilbert on polygons | 200 000 | 4 | 0.17 s | ratio 0.67, verdict withheld (< 5 row groups) | poor |
| same squares after `gpio sort hilbert` | 200 000 | 4 | 0.17 s | ratio 0.93, verdict withheld (< 5 row groups) | ordered |

The two tools agree on every file. The wall time includes decoding every WKB value; gpio's full
`check spec` on the same files takes several seconds because of the DuckDB start-up and sampling.

Remote files, from a laptop (about 5 MB/s to S3):

| Target | Rows read | Bytes / requests | Wall time | Result |
| --- | --- | --- | --- | --- |
| opengeospatial/geoparquet `examples/example.parquet` (GitHub raw) | all | 0.03 MB / 1 | 0.26 s | Core conformant |
| Overture 2026-08-19.0 buildings part-00000 (5.0 M rows, S3) | first 100 000 | 21 MB / 2 | 6 s | 1.1 file: version and logical type fail as expected; Covering: `bbox` fields in the wrong order (see below) |
| Overture buildings partition (512 objects), `--max-files 2` | 100 000 each | 2 x 21 MB | 12 s | same, per file |
| Overture 2026-08-19.0 divisions/division_area part-00000 (721 MB, 138 481 polygons, S3), whole file | all | 804 MB / 341 | 240 s | every WKB polygon decoded; same verdicts |
| source.coop / geoarrow-data 1.0 files (HTTPS) | all | 1 to 8 MB / 1 | 1 to 4 s | 1.0 files fail version and logical type as expected |

## Hardening round (2026-09-06)

Three independent reviews (spec-conformance, hostile input, Rust code/perf) and 150+ crafted files.
No crash, hang or memory blow-up was found; the verdict and text problems they found are fixed here:
bounded WKB allocations and count checks, Multi* member type and dimension checks, NaN only allowed
for empty points, shoelace computed relative to the first vertex, the ideal tiling with exactly n
tiles, non-finite statistics rejected, one-dimensional extents measured, wrapping row-group boxes
split, strict `<authority>:<code>` parsing and PROJJSON `ids`, CRS comparison never by name, inconclusive
CRS comparisons reported as notes instead of failures, `geo-metadata` validated against the published
schema (and `crs-projjson` against the PROJJSON `crs` definition), the antimeridian form of `bbox`
required to be justified by the data, a missing `columns` member no longer failing nesting, a missing
bounding-box column failing only `bbox-paths`, `encoding` missing or non-string failing
`geometry-column-type`, dictionary-hinted binary columns read as WKB, unread columns reported on every
data test, tool errors distinguished from conformance failures (exit 2), `--class` validated. Unit
tests cover the decoder and the metric (`cargo test`).

## Test suite

Four layers, all but the last in CI (`.github/workflows/conformance.yml`):

1. `cargo test`: unit tests of the WKB decoder and the spatial-order metric.
2. `geoparquet-conf corpus ..`: this repository's `data/` must pass Core and `bad_data/` must fail
   the test mapped from its `expected_failure`.
3. `geoparquet-conf verify fixtures/out`: 192 generated fixtures in four sets (the author's, and
   the spec, hostile and code reviewers') against `fixtures/expected.json`, the manifest of which
   tests must fail for each file. See [`fixtures/README.md`](fixtures/README.md).
4. `fixtures/remote_smoke.sh`: the public files on S3 and HTTPS listed above (needs the network).

## Findings for the spec and the corpus

0. **Every Overture Maps file orders its bbox struct `xmin, xmax, ymin, ymax`.** GeoParquet 1.1 and
   PR #302 both say the fields "MUST be ordered in this same way" (`xmin, ymin, xmax, ymax`), so the
   largest producer fails `/conf/covering/bbox-column-structure`, and no validator had ever checked the
   order. Readers use field names; the order requirement carries no information and should probably
   go from #302.
1. `bad_data/crs-invalid-projjson.parquet` (a `crs` without `type`) passes the PROJJSON JSON Schema:
   the schema's top-level `oneOf` also accepts ellipsoids, datums and operations, and `{id, name}` is
   a valid ellipsoid. The OGC test `/conf/core/crs-projjson` should say "PROJJSON **CRS** object"
   (the schema's `definitions/crs`), and so should `geoparquet.md`. Done here.
2. `bad_data/epoch-on-unsupported-crs.parquet` carries a stub `crs` (`{"type": "GeographicCRS",
   "id": ...}`) that is not valid PROJJSON (no name, datum or coordinate system). The fixture wants to
   test only the epoch; it should carry a full PROJJSON. gpio does not notice because its
   `crs_valid` check only looks at `type`.
3. pyarrow 25 writes an unset Parquet `crs` when asked for `EPSG:4326` or `OGC:CRS84`; fine for
   the spec (both mean OGC:CRS84) but a test suite must treat "unset" and those two as equal.
4. `schema.json` reaches the PROJJSON schema through a remote `$ref`; validators must vendor it or
   they need the network at validation time.
5. DuckDB `ORDER BY ST_Hilbert(...)` on polygons produced a file whose first row group spans the
   whole extent (rows 0-51 200 came from everywhere); `gpio sort hilbert` sorts the same data
   correctly. Worth a look by whoever owns the DuckDB spatial example in the guide.

## What a real implementation would still need

* Semantic CRS comparison (PROJJSON without `id`, `srid:<n>` with a registry): needs PROJ or a
  registry table; the prototype reports "cannot compare" instead. This is the one place where
  "pure Rust" costs something real.
* GeoArrow-encoded geometry columns are not read (GeoParquet 2.0 Core requires WKB, so the
  abstract tests do not need them either).
* A report format agreed with OGC CITE, packaging (cargo install, static binaries, a Python wheel
  via maturin if wanted), and one arrow pass for files with several geometry columns (today each
  geometry column is scanned separately).
* More unit tests; the fixture sets and their manifest are the regression suite today.

## Building

`cargo build --release` (the toolchain is pinned to 1.98.0 by `rust-toolchain.toml`; CI uses the same version), or with Docker:

```
docker run --rm -v "$PWD":/work -w /work rust:1-slim-bookworm cargo build --release
```

Dependencies: parquet 59.3, arrow-array, object_store (aws, gcp, azure, http), tokio, jsonschema
(no network features), serde_json, clap, anyhow. MSRV 1.88.
