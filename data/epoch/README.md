# data/epoch/

Two files in EPSG:7843 (GDA2020) at the same nominal Sydney location, differing only in `epoch`. The 2024 file's coordinates are propagated forward from the 2020 file using Australian plate velocity (~7 cm/yr north, ~2 cm/yr east) — about 28 cm north over 4 years. Together these demonstrate that epoch is numerically meaningful.

| File | CRS | epoch |
|---|---|---|
| `epoch-itrf2014-2020.parquet` | EPSG:7843 | 2020.0 |
| `epoch-itrf2014-2024.parquet` | EPSG:7843 | 2024.0 |
