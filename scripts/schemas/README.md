# scripts/schemas/

Vendored copies of JSON Schemas used by the self-test suite.

| File | Source | Pinned at |
|---|---|---|
| `geoparquet-2.0.0-dev.schema.json` | https://github.com/opengeospatial/geoparquet/blob/main/format-specs/schema.json | 2026-06-02 |
| `projjson-0.7.schema.json` | https://proj.org/schemas/v0.7/projjson.schema.json | 2026-06-02 |

To refresh:

```bash
curl -fsSL https://raw.githubusercontent.com/opengeospatial/geoparquet/main/format-specs/schema.json \
  -o scripts/schemas/geoparquet-2.0.0-dev.schema.json
curl -fsSL https://proj.org/schemas/v0.7/projjson.schema.json \
  -o scripts/schemas/projjson-0.7.schema.json
```

The GeoParquet schema's `crs` property `$ref`s
`https://proj.org/schemas/v0.7/projjson.schema.json`. The vendored
`projjson-0.7.schema.json` has a matching `$id`, so
`tests/test_schema_validation.py` resolves the ref offline via a
`referencing.Registry` (no network needed).

## Notes / known mismatches

`tests/test_schema_validation.py` validates every file's `geo` metadata against
the vendored GeoParquet schema. Current status: **9 pass, 20 xfail**.

- **Auth-code-only CRS (the one real open question — 20 xfailed files).** Most
  of the corpus identifies a CRS by authority code only, e.g.
  `{"type": "GeographicCRS", "id": {"authority": "OGC", "code": "CRS84"}}`. The
  PROJJSON v0.7 schema that the GeoParquet schema `$ref`s requires `name` on
  every CRS object (and `base_crs`/`conversion`/`coordinate_system` on a
  `ProjectedCRS`), so these minimal reference objects fail strict PROJJSON
  validation. This is a genuine spec question — is auth-code-only CRS valid
  PROJJSON? — not a corpus bug. We xfail these files in the test rather than
  rewriting the generators to emit full PROJJSON. Files that pass use either a
  `null` crs or full PROJJSON (`crs-default`, `crs-projjson-full`, the
  `encodings/*` files, `airports-global`).
- **`geometry_types` Z/M/ZM suffixes: OK.** The schema's `items` pattern is
  `^(GeometryCollection|(Multi)?(Point|LineString|Polygon))( Z| M| ZM)?$`, so
  `"LineString ZM"`, `"MultiLineString Z"`, etc. validate fine. The `zm/*`,
  `gps-trajectory-xyzm`, and `bathymetry-contours` files only xfail because of
  their auth-code CRS, not the suffix.
- **Version / epoch: aligned.** The corpus now declares `version: "2.0-dev"`
  (matching the schema `const`) and uses the `epoch` key (matching the schema's
  numeric `epoch` field). The earlier `2.0.0-dev` / `coordinate_epoch`
  mismatches are resolved and no longer cause failures.
- **Encoding:** the schema allows `encoding` `const: "WKB"`; the corpus uses WKB
  exclusively, so there is no encoding mismatch today. If native/GeoArrow
  encodings are added later, this schema would reject them.
