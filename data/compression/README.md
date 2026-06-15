# data/compression/

Six files holding an identical native-geometry Point table, each written with a different Parquet compression codec. A conformant reader must open all of them. The corpus default codec is zstd (level 15); these files exercise the others.

| File | Parquet codec |
|---|---|
| `compression-none.parquet` | UNCOMPRESSED |
| `compression-snappy.parquet` | SNAPPY |
| `compression-gzip.parquet` | GZIP |
| `compression-brotli.parquet` | BROTLI |
| `compression-lz4-raw.parquet` | LZ4 |
| `compression-zstd.parquet` | ZSTD |

Note: `compression-lz4-raw.parquet` uses the Parquet-conformant LZ4_RAW codec (pyarrow reports it as `LZ4`). Compression level is not stored in the file.
