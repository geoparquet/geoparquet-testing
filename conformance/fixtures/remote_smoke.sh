#!/usr/bin/env sh
# Public files the checker has been run against. Not part of CI (network). Usage:
#   cd conformance && sh fixtures/remote_smoke.sh [path/to/geoparquet-conf]
set -e
BIN=${1:-./target/release/geoparquet-conf}
# GeoParquet 2.0.0 example: must be Core conformant (exit 0)
$BIN check https://raw.githubusercontent.com/opengeospatial/geoparquet/main/examples/example.parquet --class core
# GeoParquet 1.x files: version, schema version and logical type fail, nothing else (exit 1)
$BIN check https://data.source.coop/cholmes/overture/geoparquet-country-quad-2/AD.parquet || true
$BIN check https://github.com/geoarrow/geoarrow-data/releases/download/v0.2.0/ns-water_water-junc_geo.parquet || true
# Overture Maps (1.1, S3, anonymous): sampled; covering fails on the bbox field order (SI-26)
$BIN check "s3://overturemaps-us-west-2/release/2026-08-19.0/theme=buildings/type=building/" \
  --s3-region us-west-2 --max-files 2 --max-rows 100000 || true
