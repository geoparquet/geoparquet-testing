# scripts/schemas/

Vendored copies of JSON Schemas used by the self-test suite.

| File | Source | Pinned at |
|---|---|---|
| `geoparquet-2.0.0-dev.schema.json` | https://github.com/opengeospatial/geoparquet/blob/main/format-specs/schema.json | 2026-06-02 |

To refresh:

```bash
curl -fsSL https://raw.githubusercontent.com/opengeospatial/geoparquet/main/format-specs/schema.json \
  -o scripts/schemas/geoparquet-2.0.0-dev.schema.json
```

## Notes / known mismatches (read before Task 5.2)

The vendored schema is the in-development GeoParquet 2.0 schema, but it does **not**
match our corpus verbatim:

- **Version string:** the schema requires `version` `const: "2.0-dev"`, while every file
  in our corpus declares `version: "2.0.0-dev"`. As written, all 29 files fail validation
  on the version field alone. Task 5.2 must account for this (e.g. relax/patch the
  `version` constraint when validating, or treat the version field specially). Do NOT
  change the generators to emit `"2.0-dev"` solely to satisfy this schema without a
  deliberate decision.
- **Remote `$ref` for CRS:** the column `crs` property references
  `https://proj.org/schemas/v0.7/projjson.schema.json`. A plain `Draft7Validator` raises
  an *unresolvable reference* error (not a validation error) when a `crs` is present.
  Task 5.2 must supply a resolver/registry for the PROJJSON schema or stub the `crs`
  subschema.
- **Encoding:** the schema only allows `encoding` `const: "WKB"`. Our corpus uses WKB
  exclusively (despite filenames like `point-native-geometry.parquet`), so there is no
  encoding-enum mismatch today. If native/GeoArrow encodings are added later, this schema
  would reject them.
- **Coordinate epoch:** the schema's field is named `epoch` (number); our 4 files that
  carry an epoch use the key `coordinate_epoch`. The column subschema has no
  `additionalProperties: false`, so `coordinate_epoch` is accepted as an unknown extra key
  rather than rejected — but it is also not validated against the `epoch` constraint.
