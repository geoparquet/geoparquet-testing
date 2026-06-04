# scripts/schemas/

Vendored copies of JSON Schemas used by the self-test suite.

| File | Source | Pinned at |
|---|---|---|
| `geoparquet-2.0-dev.schema.json` | https://github.com/opengeospatial/geoparquet/blob/main/format-specs/schema.json | 2026-06-02 |
| `projjson-0.7.schema.json` | https://proj.org/schemas/v0.7/projjson.schema.json | 2026-06-02 |

To refresh:

```bash
curl -fsSL https://raw.githubusercontent.com/opengeospatial/geoparquet/main/format-specs/schema.json \
  -o scripts/schemas/geoparquet-2.0-dev.schema.json
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
the vendored GeoParquet schema. Current status: **all files pass**.

- **CRS is full PROJJSON.** Every file's `crs` is a full PROJJSON v0.7 object
  (with `name` and, for projected CRSs, `base_crs`/`conversion`/
  `coordinate_system`), generated once via pyproj and hard-coded in
  `gpqgen/crs.py`. Earlier the corpus used auth-code-only reference objects such
  as `{"type": "GeographicCRS", "id": {"authority": "OGC", "code": "CRS84"}}`,
  which fail strict PROJJSON validation because the v0.7 schema requires `name`
  on every CRS object. Those files were temporarily xfailed; they now emit full
  PROJJSON and pass. Files with a `null`/absent crs (`crs-default`) also pass.
- **`geometry_types` Z/M/ZM suffixes: OK.** The schema's `items` pattern is
  `^(GeometryCollection|(Multi)?(Point|LineString|Polygon))( Z| M| ZM)?$`, so
  `"LineString ZM"`, `"MultiLineString Z"`, etc. validate fine.
- **Version / epoch: aligned.** The corpus now declares `version: "2.0-dev"`
  (matching the schema `const`) and uses the `epoch` key (matching the schema's
  numeric `epoch` field). The earlier `2.0.0-dev` / `coordinate_epoch`
  mismatches are resolved and no longer cause failures.
- **Encoding:** the schema allows `encoding` `const: "WKB"`; the corpus uses WKB
  exclusively, so there is no encoding mismatch today. If native/GeoArrow
  encodings are added later, this schema would reject them.
