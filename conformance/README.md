# geoparquet-conf (experiment)

A GeoParquet 2.0 conformance checker in Rust that runs the abstract tests of the OGC draft
(`ogc/abstract_tests/` in opengeospatial/geoparquet#304) on a single file, using only the Apache
Arrow Rust `parquet` crate. No DuckDB, no GDAL, no PROJ. Written in one session to assess Chris
Holmes's suggestion of "a clean test suite ... don't pull in duckdb". **Prototype, not a product.**

## What it does

```
geoparquet-conf check file.parquet [--json] [--class core|covering|distribution]
geoparquet-conf corpus ..          # from conformance/: data/ must pass, bad_data/ must fail the mapped test
```

Every abstract test of the three conformance classes is implemented and reports pass / fail / skip
with a message naming the column and the offending value:

| Class | Tests | Notes |
| --- | --- | --- |
| Core | 20 | `media-type` always skipped (not testable on a file). |
| Bounding Box Covering | 6 | Skipped as "not claimed" when no column declares `covering`. |
| Cloud-Optimized Distribution | 2 | `spatial-order` uses the pruning metric with fixed parameters (20 windows of 10 % side, seed, pass at 0.70 of the ideal tiling's skip rate) and also prints the area factor Σ row-group bbox area / extent. |

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

22 extra adversarial fixtures (`fixtures/make_fixtures.py`, run from `scripts/` with `uv run python ../conformance/fixtures/make_fixtures.py`: 6/8-element and antimeridian bbox
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
| squares, DuckDB ST_Hilbert on polygons | 200 000 | 4 | 0.17 s | FAIL ratio 0.67 | poor |
| same squares after `gpio sort hilbert` | 200 000 | 4 | 0.17 s | PASS ratio 0.93 | ordered |

The two tools agree on every file. The wall time includes decoding every WKB value; gpio's full
`check spec` on the same files takes several seconds because of the DuckDB start-up and sampling.

## Findings for the spec and the corpus

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
* Partitioned datasets, remote files (object_store crate would make this straightforward), a
  machine-readable report format agreed with OGC CITE, and packaging (cargo install, static
  binaries, a Python wheel via maturin if wanted).
* Tests of its own beyond the corpus and the fixture script.

## Building

`cargo build --release` with a Rust 1.98 toolchain, or with Docker:

```
docker run --rm -v "$PWD":/work -w /work rust:1-slim-bookworm cargo build --release
```

Dependencies: parquet 59.3 (arrow feature + codecs), arrow, jsonschema, serde_json, clap, anyhow.
