"""Non-parquet and malformed-file inputs, and true-duplicate `geo` keys / bad utf8."""
import os
import struct
from pathlib import Path
import pyarrow as pa
import pyarrow.parquet as pq
import geoarrow.pyarrow as ga
from hlib import geo_meta, point, HERE
from gpqgen.metadata import metadata_bytes

PT = point(1.0, 2.0)


def valid_bytes():
    arr = ga.wkb().wrap_array(pa.array([PT], pa.binary()))
    t = pa.table({"geometry": arr})
    meta = dict(t.schema.metadata or {})
    meta[b"geo"] = metadata_bytes(geo_meta(columns={"geometry": {"encoding": "WKB", "geometry_types": []}}))
    t = t.replace_schema_metadata(meta)
    import io
    buf = io.BytesIO()
    pq.write_table(t, buf, compression="none")
    return buf.getvalue()


# empty file
(HERE/"file_empty.parquet").write_bytes(b"")
print("wrote file_empty.parquet")

# 0-byte with different name
(HERE/"file_zero.bin").write_bytes(b"")
print("wrote file_zero.bin")

# a PNG (magic bytes)
png = bytes.fromhex("89504e470d0a1a0a") + b"\x00" * 200
(HERE/"file_png.parquet").write_bytes(png)
print("wrote file_png.parquet")

# random garbage with PAR1 magic at both ends but bogus footer length
gb = b"PAR1" + os.urandom(500) + struct.pack("<I", 0xFFFFFFF0) + b"PAR1"
(HERE/"file_bogus_footerlen.parquet").write_bytes(gb)
print("wrote file_bogus_footerlen.parquet")

# valid parquet truncated in the middle of the footer
vb = valid_bytes()
(HERE/"file_truncated_mid.parquet").write_bytes(vb[:len(vb) - 8])
print(f"wrote file_truncated_mid.parquet (orig {len(vb)} -> {len(vb)-8})")

# valid parquet truncated to just header
(HERE/"file_truncated_head.parquet").write_bytes(vb[:20])
print("wrote file_truncated_head.parquet")

# footer length larger than file
(HERE/"file_footerlen_huge.parquet").write_bytes(b"PAR1" + struct.pack("<I", 0x7FFFFFFF) + b"PAR1")
print("wrote file_footerlen_huge.parquet")

# valid parquet with the `geo` value replaced by invalid UTF-8 bytes
# build with raw geo bytes containing invalid utf-8
arr = ga.wkb().wrap_array(pa.array([PT], pa.binary()))
t = pa.table({"geometry": arr})
meta = dict(t.schema.metadata or {})
meta[b"geo"] = b'{"version":"2.0.0",\xff\xfe"primary_column":"geometry"}'
t = t.replace_schema_metadata(meta)
pq.write_table(t, HERE/"file_geo_bad_utf8.parquet", compression="none")
print("wrote file_geo_bad_utf8.parquet")

# a directory named like a parquet
d = HERE/"file_is_a_directory.parquet"
d.mkdir(exist_ok=True)
print("made directory file_is_a_directory.parquet")

print("done")
