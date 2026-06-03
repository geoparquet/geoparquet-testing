# samples/

Realistic-tier files: plausibly-real datasets sized to flex spec features at non-trivial row counts. Each entry below records source, license, and what spec features the file showcases.

Per-file budget: ≤ 5 MB. CI enforces.

| File | Size (KB) | Showcases / source |
|---|---|---|
| `airports-global.parquet` | 48 | _see header of `scripts/samples/airports_global.py`_ |
| `australia-gnss-stations-2024.parquet` | 4 | _see header of `scripts/samples/australia_gnss.py`_ |
| `australia-gnss-stations.parquet` | 4 | _see header of `scripts/samples/australia_gnss.py`_ |
| `bathymetry-contours.parquet` | 17 | _see header of `scripts/samples/bathymetry_contours.py`_ |
| `buildings-with-centroid.parquet` | 21 | _see header of `scripts/samples/buildings_with_centroid.py`_ |
| `gps-trajectory-xyzm.parquet` | 15 | _see header of `scripts/samples/gps_trajectory.py`_ |
| `us-states.parquet` | 343 | _see header of `scripts/samples/us_states.py`_ |

## Deferred samples

Not yet produced (network/license/toolchain gaps):

- `nz-building-outlines.parquet` — LINZ NZ Building Outlines (CC-BY 4.0) requires a LINZ Data Service API key, which is not available in this environment. See plan Task 4.2.a (docs/superpowers/plans/2026-06-01-geoparquet-testing-implementation.md).
- `flight-routes-great-circle.parquet` — native-geography logical type not yet supported by the toolchain — see docs/superpowers/plans/2026-06-01-geography-logical-type-deferred.md.
