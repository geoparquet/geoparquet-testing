# bad_data/

Files that deliberately violate the GeoParquet 2.0 spec. Use these to test that your reader detects and reports each class of violation. The machine-readable contract is `manifest.json`.

## Controlled vocabulary for `expected_failure`

- `bbox_mismatch`
- `crs_mismatch`
- `edges_mismatch`
- `epoch_unsupported`
- `geometry_type_mismatch`
- `metadata_invalid_json`
- `metadata_invalid_utf8`
- `metadata_missing`
- `orientation_mismatch`
- `schema_validation_error`
- `version_feature_mismatch`
- `version_unknown`
- `wkb_parse_error`
- `zm_mismatch`

## Files

| File | Violation | Expected failure |
|---|---|---|
