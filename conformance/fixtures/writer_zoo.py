"""Writer zoo: write one small dataset as GeoParquet with every writer available, then run the
checker on the results (out/zoo/). Not part of CI: needs the ogr2ogr CLI (GDAL >= 3.11), and the
Python packages duckdb, sedonadb, geopandas, shapely, geoarrow-pyarrow, pyarrow, e.g.

    uv run --with duckdb --with sedonadb --with geopandas --with geoarrow-pyarrow python writer_zoo.py
    cargo run --release -- check fixtures/out/zoo/ --max-files 20
"""
import json, random, subprocess, sys
from pathlib import Path
import pyarrow as pa, pyarrow.parquet as pq
import shapely
from shapely.geometry import Point, Polygon, mapping

OUT = Path(__file__).parent / "out" / "zoo"; OUT.mkdir(parents=True, exist_ok=True)
random.seed(7)
feats = []
for i in range(200):
    feats.append((i, "point", Point(-9 + 12 * random.random(), 36 + 7 * random.random())))
for i in range(50):
    x, y = -9 + 12 * random.random(), 36 + 7 * random.random()
    feats.append((200 + i, "square", Polygon([(x, y), (x + 0.1, y), (x + 0.1, y + 0.1), (x, y + 0.1), (x, y)])))  # CCW
gj = {"type": "FeatureCollection", "features": [{"type": "Feature", "properties": {"id": i, "kind": k}, "geometry": mapping(g)} for i, k, g in feats]}
src = OUT / "source.geojson"; src.write_text(json.dumps(gj))
wkb = [shapely.to_wkb(g) for _, _, g in feats]
ids = [i for i, _, _ in feats]
results = {}

def done(name, ok=True, note=""):
    results[name] = (ok, note); print(f"{'wrote' if ok else 'FAILED'} {name} {note}")

# 1. DuckDB spatial, GeoParquet V2, CRS84 and EPSG:3857
try:
    import duckdb
    con = duckdb.connect(); con.execute("INSTALL spatial; LOAD spatial;")
    con.execute(f"CREATE TABLE t AS SELECT id, kind, geom AS geometry FROM ST_Read('{src}')")
    con.execute(f"COPY t TO '{OUT}/duckdb_crs84.parquet' (FORMAT PARQUET, GEOPARQUET_VERSION 'V2')"); done("duckdb_crs84")
    con.execute(f"COPY (SELECT id, kind, ST_Transform(geometry, 'EPSG:4326', 'EPSG:3857', always_xy := true) AS geometry FROM t) TO '{OUT}/duckdb_3857.parquet' (FORMAT PARQUET, GEOPARQUET_VERSION 'V2')"); done("duckdb_3857", note="(does DuckDB record the CRS?)")
except Exception as e: done("duckdb", False, str(e)[:200])

# 2. GDAL 3.12 ogr2ogr: native geo types, with and without GeoParquet metadata
for name, lco, extra in [
    ("gdal_geotypes_crs84", ["USE_PARQUET_GEO_TYPES=YES", "WRITE_COVERING_BBOX=YES"], []),
    ("gdal_geotypes_only_crs84", ["USE_PARQUET_GEO_TYPES=ONLY"], []),
    ("gdal_geotypes_3857", ["USE_PARQUET_GEO_TYPES=YES"], ["-t_srs", "EPSG:3857"]),
    ("gdal_legacy_crs84", ["USE_PARQUET_GEO_TYPES=NO", "WRITE_COVERING_BBOX=YES"], []),
]:
    cmd = ["ogr2ogr", "-f", "Parquet", str(OUT / f"{name}.parquet"), str(src), *extra] + sum([["-lco", o] for o in lco], [])
    r = subprocess.run(cmd, capture_output=True, text=True)
    done(name, r.returncode == 0, (r.stderr.strip()[:200] if r.returncode else ""))

# 3. SedonaDB 0.4: GeoParquet 2.0 (input: the pyarrow native-type file written below, so run after it)
def sedona_writers():
    import sedonadb
    sd = sedonadb.connect()
    sd.read_parquet(str(OUT / "pyarrow_native_no_geo.parquet")).to_view("src", overwrite=True)
    df = sd.sql("SELECT id, ST_SetSRID(geometry, 4326) AS geometry FROM src")
    df.to_parquet(str(OUT / "sedonadb_crs84.parquet"), geoparquet_version="2.0"); done("sedonadb_crs84")
    df3 = sd.sql("SELECT id, ST_Transform(ST_SetSRID(geometry, 4326), 'EPSG:3857') AS geometry FROM src")
    df3.to_parquet(str(OUT / "sedonadb_3857.parquet"), geoparquet_version="2.0"); done("sedonadb_3857")
    df.to_parquet(str(OUT / "sedonadb_v11_crs84.parquet"), geoparquet_version="1.1"); done("sedonadb_v11_crs84")

# 4. GeoPandas 1.1.4: newest schema it knows is 1.1.0
try:
    import geopandas as gpd
    gdf = gpd.read_file(src)
    gdf.to_parquet(OUT / "geopandas_v11_crs84.parquet", schema_version="1.1.0", write_covering_bbox=True); done("geopandas_v11_crs84")
    try:
        gdf.to_parquet(OUT / "geopandas_v20_crs84.parquet", schema_version="2.0.0"); done("geopandas_v20_crs84")
    except Exception as e: done("geopandas_v20_crs84", False, str(e)[:160])
except Exception as e: done("geopandas", False, str(e)[:200])

# 5. geoarrow-pyarrow: write_geoparquet_table (native types via extension arrays)
try:
    import geoarrow.pyarrow as ga
    from geoarrow.pyarrow.io import write_geoparquet_table
    table = pa.table({"id": ids, "geometry": ga.as_wkb(wkb)})
    write_geoparquet_table(table, OUT / "geoarrow_crs84.parquet", write_bbox=True, write_geometry_types=True); done("geoarrow_crs84")
except Exception as e: done("geoarrow", False, str(e)[:200])

# 6. pyarrow alone: native GEOMETRY logical type, no `geo` metadata at all (what a non-geo writer produces)
try:
    import geoarrow.pyarrow as ga
    pq.write_table(pa.table({"id": ids, "geometry": ga.as_wkb(wkb)}), OUT / "pyarrow_native_no_geo.parquet"); done("pyarrow_native_no_geo")
except Exception as e: done("pyarrow", False, str(e)[:200])

try:
    sedona_writers()
except Exception as e: done("sedonadb", False, str(e)[:300])

print("\n== parquet-level view ==")
for f in sorted(OUT.glob("*.parquet")):
    try:
        pf = pq.ParquetFile(f); md = pf.metadata.metadata or {}
        geo = json.loads(md[b"geo"]) if b"geo" in md else None
        gtype = next((str(pf.schema.column(i).logical_type) for i in range(pf.schema.column(0).path and len(pf.schema) or 0) if pf.schema.column(i).name == "geometry"), "?")
        ver = geo.get("version") if geo else "no geo"
        crs = geo["columns"]["geometry"].get("crs", "absent") if geo else "-"
        crs_s = ("PROJJSON " + str(crs.get("id"))) if isinstance(crs, dict) else str(crs)
        print(f"{f.name:34s} geo={ver:10s} logical={gtype[:60]:60s} geo.crs={crs_s}")
    except Exception as e:
        print(f"{f.name:34s} unreadable: {str(e)[:120]}")
