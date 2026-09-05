//! The abstract tests of the OGC GeoParquet 2.0 draft (ogc/abstract_tests), one function
//! per conformance class, run on a single file with nothing but the parquet crate.

use std::collections::{BTreeMap, BTreeSet, HashMap};
use std::fs::File;
use std::path::Path;
use std::sync::Arc;

use anyhow::{Context, Result, anyhow};
use arrow::array::{Array, ArrayRef, BinaryArray, BinaryViewArray, LargeBinaryArray};
use parquet::arrow::ProjectionMask;
use parquet::arrow::arrow_reader::ParquetRecordBatchReaderBuilder;
use parquet::basic::{LogicalType, Repetition, Type as PhysicalType};
use parquet::file::metadata::ParquetMetaData;
use parquet::file::reader::{FileReader, SerializedFileReader};
use parquet::schema::types::Type as SchemaType;
use serde::Serialize;
use serde_json::Value;

use crate::crs::{self, Crs};
use crate::spatial;
use crate::wkb;

pub const GEO_METADATA: &str = "/conf/core/geo-metadata";
pub const FILE_METADATA: &str = "/conf/core/file-metadata";
pub const COLUMN_METADATA: &str = "/conf/core/column-metadata";
pub const GEOMETRY_COLUMN_TYPE: &str = "/conf/core/geometry-column-type";
pub const GEOMETRY_COLUMN_NESTING: &str = "/conf/core/geometry-column-nesting";
pub const GEOMETRY_COLUMN_REPETITION: &str = "/conf/core/geometry-column-repetition";
pub const WKB: &str = "/conf/core/wkb";
pub const GEOMETRY_TYPES: &str = "/conf/core/geometry-types";
pub const CRS_PROJJSON: &str = "/conf/core/crs-projjson";
pub const CRS_CONSISTENCY: &str = "/conf/core/crs-consistency";
pub const CRS_DEFAULT: &str = "/conf/core/crs-default";
pub const AXIS_ORDER: &str = "/conf/core/axis-order";
pub const EDGES_VALUE: &str = "/conf/core/edges-value";
pub const EPOCH: &str = "/conf/core/epoch";
pub const ORIENTATION_VALUE: &str = "/conf/core/orientation-value";
pub const ORIENTATION_RINGS: &str = "/conf/core/orientation-rings";
pub const BBOX_ARRAY: &str = "/conf/core/bbox-array";
pub const BBOX_CRS: &str = "/conf/core/bbox-crs";
pub const BBOX_EXTENT: &str = "/conf/core/bbox-extent";
pub const MEDIA_TYPE: &str = "/conf/core/media-type";
pub const COV_KEYS: &str = "/conf/covering/keys";
pub const COV_BBOX_PATHS: &str = "/conf/covering/bbox-paths";
pub const COV_STRUCTURE: &str = "/conf/covering/bbox-column-structure";
pub const COV_TYPE: &str = "/conf/covering/bbox-column-type";
pub const COV_REPETITION: &str = "/conf/covering/bbox-column-repetition";
pub const COV_NESTING: &str = "/conf/covering/bbox-column-nesting";
pub const DIST_STATS: &str = "/conf/distribution/geospatial-statistics";
pub const DIST_SPATIAL_ORDER: &str = "/conf/distribution/spatial-order";

pub const ALL_IDS: [&str; 28] = [
    GEO_METADATA,
    FILE_METADATA,
    COLUMN_METADATA,
    GEOMETRY_COLUMN_TYPE,
    GEOMETRY_COLUMN_NESTING,
    GEOMETRY_COLUMN_REPETITION,
    WKB,
    GEOMETRY_TYPES,
    CRS_PROJJSON,
    CRS_CONSISTENCY,
    CRS_DEFAULT,
    AXIS_ORDER,
    EDGES_VALUE,
    EPOCH,
    ORIENTATION_VALUE,
    ORIENTATION_RINGS,
    BBOX_ARRAY,
    BBOX_CRS,
    BBOX_EXTENT,
    MEDIA_TYPE,
    COV_KEYS,
    COV_BBOX_PATHS,
    COV_STRUCTURE,
    COV_TYPE,
    COV_REPETITION,
    COV_NESTING,
    DIST_STATS,
    DIST_SPATIAL_ORDER,
];
const COVERING_IDS: [&str; 6] = [
    COV_KEYS,
    COV_BBOX_PATHS,
    COV_STRUCTURE,
    COV_TYPE,
    COV_REPETITION,
    COV_NESTING,
];
const EDGES: [&str; 6] = [
    "planar",
    "spherical",
    "vincenty",
    "thomas",
    "andoyer",
    "karney",
];

#[derive(Serialize, Clone, Copy, PartialEq, Eq, Debug)]
#[serde(rename_all = "lowercase")]
pub enum Status {
    Pass,
    Fail,
    Skip,
}

#[derive(Serialize, Debug)]
pub struct Outcome {
    pub id: &'static str,
    pub status: Status,
    pub message: String,
}

impl Outcome {
    pub fn class(&self) -> &str {
        self.id.split('/').nth(2).unwrap_or("")
    }
}

#[derive(Serialize)]
pub struct Report {
    pub file: String,
    pub outcomes: Vec<Outcome>,
}

impl Report {
    pub fn failed(&self, class: &str) -> Vec<&'static str> {
        self.outcomes
            .iter()
            .filter(|o| o.class() == class && o.status == Status::Fail)
            .map(|o| o.id)
            .collect()
    }
    pub fn get(&self, id: &str) -> Option<&Outcome> {
        self.outcomes.iter().find(|o| o.id == id)
    }
}

pub struct Schemas {
    geo: jsonschema::Validator,
    projjson: jsonschema::Validator,
}

impl Schemas {
    pub fn load() -> Result<Schemas> {
        let geo: Value = serde_json::from_str(include_str!("../schemas/geoparquet-2.0.0.json"))?;
        // The PROJJSON schema also describes datums, ellipsoids and operations; a GeoParquet
        // `crs` must be a CRS, so validate against its `crs` definition only.
        let mut projjson: Value =
            serde_json::from_str(include_str!("../schemas/projjson.schema.json"))?;
        projjson["oneOf"] = serde_json::json!([{ "$ref": "#/definitions/crs" }]);
        // schema.json refers to the PROJJSON schema by URL; serve the vendored copy instead of fetching it.
        let registry = jsonschema::Registry::new()
            .add(
                "https://proj.org/schemas/v0.7/projjson.schema.json",
                jsonschema::Resource::from_contents(projjson.clone()),
            )
            .and_then(|b| b.prepare())
            .map_err(|e| anyhow!("schema registry: {e}"))?;
        Ok(Schemas {
            geo: jsonschema::options()
                .with_registry(&registry)
                .build(&geo)
                .map_err(|e| anyhow!("geoparquet schema: {e}"))?,
            projjson: jsonschema::validator_for(&projjson)
                .map_err(|e| anyhow!("projjson schema: {e}"))?,
        })
    }
}

fn schema_errors(v: &jsonschema::Validator, inst: &Value, max: usize) -> Vec<String> {
    v.iter_errors(inst)
        .take(max)
        .map(|e| format!("{} at {}", e, e.instance_path()))
        .collect()
}

/// Accumulates one abstract test's verdict across columns.
struct T {
    id: &'static str,
    fails: Vec<String>,
    notes: Vec<String>,
    applicable: bool,
}

impl T {
    fn new(id: &'static str) -> T {
        T {
            id,
            fails: Vec::new(),
            notes: Vec::new(),
            applicable: false,
        }
    }
    fn ok(&mut self) {
        self.applicable = true;
    }
    fn fail(&mut self, m: impl Into<String>) {
        self.applicable = true;
        self.fails.push(m.into());
    }
    fn note(&mut self, m: impl Into<String>) {
        self.notes.push(m.into());
    }
    fn finish(self) -> Outcome {
        let (status, message) = if !self.fails.is_empty() {
            (Status::Fail, self.fails.join("; "))
        } else if self.applicable {
            (Status::Pass, self.notes.join("; "))
        } else if self.notes.is_empty() {
            (Status::Skip, "not applicable".to_string())
        } else {
            (Status::Skip, self.notes.join("; "))
        };
        Outcome {
            id: self.id,
            status,
            message,
        }
    }
}

fn skip(id: &'static str, m: impl Into<String>) -> Outcome {
    Outcome {
        id,
        status: Status::Skip,
        message: m.into(),
    }
}

fn logical(t: &SchemaType) -> Option<LogicalType> {
    t.get_basic_info().logical_type_ref().cloned()
}

fn is_geo_logical(lt: &Option<LogicalType>) -> bool {
    matches!(
        lt,
        Some(LogicalType::Geometry(_)) | Some(LogicalType::Geography(_))
    )
}

fn parquet_crs(lt: &Option<LogicalType>) -> Option<String> {
    match lt {
        Some(LogicalType::Geometry(g)) => g.crs.clone(),
        Some(LogicalType::Geography(g)) => g.crs.clone(),
        _ => None,
    }
}

fn valid_type_name(s: &str) -> bool {
    let base = s
        .strip_suffix(" ZM")
        .or_else(|| s.strip_suffix(" Z"))
        .or_else(|| s.strip_suffix(" M"))
        .unwrap_or(s);
    wkb::BASE_NAMES.contains(&base)
}

fn bbox_nums(col: &Value) -> Option<Vec<f64>> {
    let a = col.get("bbox")?.as_array()?;
    if ![4, 6, 8].contains(&a.len()) {
        return None;
    }
    a.iter().map(Value::as_f64).collect()
}

fn geographic(col: &Value) -> bool {
    crs::is_geographic(&Crs::from_geo(col), col.get("crs"))
}

/// `covering.bbox` -> the bounding box column it names, or why it cannot be resolved.
fn resolve_bbox_paths(cov: &Value) -> Result<String, String> {
    let bbox = cov.get("bbox").ok_or("covering has no `bbox`")?;
    let obj = bbox.as_object().ok_or("covering.bbox is not an object")?;
    let mut keys: Vec<&str> = obj.keys().map(String::as_str).collect();
    keys.sort_unstable();
    if keys != ["xmax", "xmin", "ymax", "ymin"] {
        return Err(format!(
            "covering.bbox members are {keys:?}, expected exactly xmin, ymin, xmax, ymax"
        ));
    }
    let mut column: Option<&str> = None;
    for (k, v) in obj {
        let arr = v
            .as_array()
            .filter(|a| a.len() == 2 && a.iter().all(Value::is_string))
            .ok_or_else(|| format!("covering.bbox.{k} is not an array of two strings"))?;
        let (first, second) = (arr[0].as_str().unwrap(), arr[1].as_str().unwrap());
        if second != k {
            return Err(format!(
                "covering.bbox.{k} second element is \"{second}\", expected \"{k}\""
            ));
        }
        match column {
            None => column = Some(first),
            Some(c) if c != first => {
                return Err(format!(
                    "covering.bbox paths name different columns (\"{c}\" and \"{first}\")"
                ));
            }
            _ => {}
        }
    }
    Ok(column.unwrap().to_string())
}

#[derive(Default)]
struct Scan {
    rows: usize,
    nulls: usize,
    wkb_errors: Vec<String>,
    types: BTreeSet<String>,
    lonlat_bad: usize,
    outside_bbox: usize,
    rings_checked: usize,
    rings_bad: usize,
    bbox_rep_checked: bool,
    bbox_rep_mismatch: usize,
}

fn binary_at(arr: &ArrayRef, i: usize) -> Result<Option<&[u8]>> {
    if arr.is_null(i) {
        return Ok(None);
    }
    if let Some(a) = arr.as_any().downcast_ref::<BinaryArray>() {
        return Ok(Some(a.value(i)));
    }
    if let Some(a) = arr.as_any().downcast_ref::<LargeBinaryArray>() {
        return Ok(Some(a.value(i)));
    }
    if let Some(a) = arr.as_any().downcast_ref::<BinaryViewArray>() {
        return Ok(Some(a.value(i)));
    }
    Err(anyhow!(
        "column is not a binary array ({:?})",
        arr.data_type()
    ))
}

fn inside_bbox(bb: &[f64], g: &wkb::Geom) -> bool {
    let half = bb.len() / 2;
    let (xmin, ymin, xmax, ymax) = (bb[0], bb[1], bb[half], bb[half + 1]);
    let Some((y0, y1)) = g.range[1] else {
        return true;
    };
    if y0 < ymin || y1 > ymax {
        return false;
    }
    let (x0, x1) = g.range[0].unwrap();
    if xmin <= xmax {
        if x0 < xmin || x1 > xmax {
            return false;
        }
    } else if !g.xy.iter().all(|(x, _)| *x >= xmin || *x <= xmax) {
        return false; // antimeridian: RFC 7946 section 5
    }
    let (z, m) = match bb.len() {
        6 => (Some((bb[2], bb[5])), None),
        8 => (Some((bb[2], bb[6])), Some((bb[3], bb[7]))),
        _ => (None, None),
    };
    for (bounds, range) in [(z, g.range[2]), (m, g.range[3])] {
        if let (Some((lo, hi)), Some((g0, g1))) = (bounds, range)
            && (g0 < lo || g1 > hi)
        {
            return false;
        }
    }
    true
}

fn scan_column(
    path: &Path,
    name: &str,
    bbox_col: Option<&str>,
    declared_bbox: Option<&[f64]>,
    geodesic: bool,
) -> Result<Scan> {
    let builder = ParquetRecordBatchReaderBuilder::try_new(File::open(path)?)?;
    let schema = builder.parquet_schema();
    let root = schema.root_schema().get_fields();
    let mut idx = vec![
        root.iter()
            .position(|f| f.name() == name)
            .ok_or_else(|| anyhow!("no root column {name}"))?,
    ];
    let bbox_col = bbox_col.filter(|b| {
        if let Some(i) = root.iter().position(|f| f.name() == *b) {
            idx.push(i);
            true
        } else {
            false
        }
    });
    let mask = ProjectionMask::roots(schema, idx);
    let reader = builder
        .with_projection(mask)
        .with_batch_size(16 * 1024)
        .build()?;
    let mut sc = Scan::default();
    for batch in reader {
        let batch = batch?;
        let geom = batch
            .column_by_name(name)
            .ok_or_else(|| anyhow!("column {name} missing from batch"))?;
        let bbox_arr = bbox_col.and_then(|b| batch.column_by_name(b));
        for i in 0..batch.num_rows() {
            sc.rows += 1;
            let value = binary_at(geom, i)?;
            if let Some(b) = bbox_arr {
                sc.bbox_rep_checked = true;
                if b.is_null(i) != value.is_none() {
                    sc.bbox_rep_mismatch += 1;
                }
            }
            let Some(bytes) = value else {
                sc.nulls += 1;
                continue;
            };
            let g = match wkb::parse(bytes) {
                Ok(g) => g,
                Err(e) => {
                    if sc.wkb_errors.len() < 5 {
                        sc.wkb_errors.push(format!("row {}: {e}", sc.rows - 1));
                    }
                    continue;
                }
            };
            sc.types.insert(g.type_name());
            if g.xy
                .iter()
                .any(|(x, y)| !(-180.0..=180.0).contains(x) || !(-90.0..=90.0).contains(y))
            {
                sc.lonlat_bad += 1;
            }
            if let Some(bb) = declared_bbox
                && !inside_bbox(bb, &g)
            {
                sc.outside_bbox += 1;
            }
            for rings in &g.polygons {
                for (k, (s, n)) in rings.iter().enumerate() {
                    if *n < 4 {
                        continue;
                    }
                    let pts = &g.xy[*s..*s + *n];
                    let a = wkb::signed_area2(pts);
                    if a == 0.0 {
                        continue;
                    }
                    if geodesic {
                        let (lo, hi) = pts.iter().fold((f64::MAX, f64::MIN), |(lo, hi), p| {
                            (lo.min(p.0), hi.max(p.0))
                        });
                        if hi - lo > 180.0 {
                            continue;
                        }
                    }
                    sc.rings_checked += 1;
                    if (k == 0) != (a > 0.0) {
                        sc.rings_bad += 1;
                    }
                }
            }
        }
    }
    Ok(sc)
}

fn chunk<'a>(
    meta: &'a ParquetMetaData,
    rg: usize,
    name: &str,
) -> Option<&'a parquet::file::metadata::ColumnChunkMetaData> {
    meta.row_groups()[rg]
        .columns()
        .iter()
        .find(|c| c.column_path().parts().first().map(String::as_str) == Some(name))
}

pub fn run(path: &Path, schemas: &Schemas) -> Report {
    let mut out: Vec<Outcome> = Vec::new();
    let file = path.display().to_string();
    let finish = |mut out: Vec<Outcome>, reason: &str| {
        for id in ALL_IDS {
            if !out.iter().any(|o| o.id == id) {
                out.push(skip(id, reason));
            }
        }
        out.sort_by_key(|o| ALL_IDS.iter().position(|i| *i == o.id).unwrap_or(99));
        Report {
            file: file.clone(),
            outcomes: out,
        }
    };

    let reader = match File::open(path)
        .context("open")
        .and_then(|f| SerializedFileReader::new(f).context("parse footer"))
    {
        Ok(r) => r,
        Err(e) => {
            out.push(Outcome {
                id: GEO_METADATA,
                status: Status::Fail,
                message: format!("Parquet footer cannot be read: {e:#}"),
            });
            return finish(out, "file not readable");
        }
    };
    let meta = reader.metadata();
    let mut kv: HashMap<String, String> = HashMap::new();
    if let Some(list) = meta.file_metadata().key_value_metadata() {
        for e in list {
            kv.insert(e.key.clone(), e.value.clone().unwrap_or_default());
        }
    }

    // /conf/core/geo-metadata
    let mut t = T::new(GEO_METADATA);
    let geo = match kv.get("geo") {
        None => {
            t.fail("no `geo` key in FileMetaData.key_value_metadata");
            None
        }
        Some(s) => match serde_json::from_str::<Value>(s) {
            Ok(v @ Value::Object(_)) => {
                let errs = schema_errors(&schemas.geo, &v, 5);
                if errs.is_empty() {
                    t.ok();
                }
                for e in errs {
                    t.fail(format!("JSON Schema: {e}"));
                }
                Some(v)
            }
            Ok(_) => {
                t.fail("`geo` parses as JSON but is not an object");
                None
            }
            Err(e) => {
                t.fail(format!("`geo` does not parse as JSON: {e}"));
                None
            }
        },
    };
    out.push(t.finish());
    let Some(geo) = geo else {
        return finish(out, "no usable geo metadata");
    };

    // /conf/core/file-metadata
    let mut t = T::new(FILE_METADATA);
    match geo.get("version").and_then(Value::as_str) {
        Some("2.0.0") => t.ok(),
        Some(v) => t.fail(format!("version is \"{v}\", expected \"2.0.0\"")),
        None => t.fail("version missing or not a string"),
    }
    let primary = geo
        .get("primary_column")
        .and_then(Value::as_str)
        .unwrap_or("");
    if primary.is_empty() {
        t.fail("primary_column missing or empty");
    }
    let columns: BTreeMap<String, Value> = match geo.get("columns").and_then(Value::as_object) {
        Some(m) if !m.is_empty() => m.iter().map(|(k, v)| (k.clone(), v.clone())).collect(),
        _ => {
            t.fail("columns missing, not an object, or empty");
            BTreeMap::new()
        }
    };
    out.push(t.finish());

    let root: Vec<Arc<SchemaType>> = meta
        .file_metadata()
        .schema_descr()
        .root_schema()
        .get_fields()
        .to_vec();
    let root_by_name: HashMap<&str, &Arc<SchemaType>> =
        root.iter().map(|f| (f.name(), f)).collect();

    // /conf/core/column-metadata
    let mut t = T::new(COLUMN_METADATA);
    t.ok();
    for f in &root {
        if f.is_primitive() && is_geo_logical(&logical(f)) && !columns.contains_key(f.name()) {
            t.fail(format!("root column `{}` has a GEOMETRY/GEOGRAPHY logical type but is not listed in `columns`", f.name()));
        }
    }
    if !primary.is_empty() && !columns.contains_key(primary) {
        t.fail(format!(
            "primary_column `{primary}` is not a member of `columns`"
        ));
    }
    for (name, col) in &columns {
        if !col.is_object() {
            t.fail(format!("columns.{name} is not an object"));
            continue;
        }
        if col.get("encoding").is_none() {
            t.fail(format!("columns.{name} has no `encoding`"));
        }
        if col.get("geometry_types").is_none() {
            t.fail(format!("columns.{name} has no `geometry_types`"));
        }
    }
    out.push(t.finish());
    let columns: BTreeMap<String, Value> =
        columns.into_iter().filter(|(_, c)| c.is_object()).collect();

    // schema-level tests per geometry column
    let mut t_type = T::new(GEOMETRY_COLUMN_TYPE);
    let mut t_nest = T::new(GEOMETRY_COLUMN_NESTING);
    let mut t_rep = T::new(GEOMETRY_COLUMN_REPETITION);
    let mut geom_fields: BTreeMap<&str, &Arc<SchemaType>> = BTreeMap::new();
    for (name, col) in &columns {
        let Some(f) = root_by_name.get(name.as_str()) else {
            t_nest.fail(format!(
                "`{name}`: no schema element with that name at the root of the Parquet schema"
            ));
            continue;
        };
        if f.is_group() {
            t_nest.fail(format!("`{name}` is a group field"));
            continue;
        }
        t_nest.ok();
        geom_fields.insert(name, f);
        t_type.ok();
        if f.get_physical_type() != PhysicalType::BYTE_ARRAY {
            t_type.fail(format!(
                "`{name}`: primitive type is {:?}, expected BYTE_ARRAY",
                f.get_physical_type()
            ));
        }
        let lt = logical(f);
        if !is_geo_logical(&lt) {
            t_type.fail(format!(
                "`{name}`: logical type is {}, expected GEOMETRY or GEOGRAPHY",
                lt.map(|l| format!("{l:?}")).unwrap_or("none".into())
            ));
        }
        match col.get("encoding").and_then(Value::as_str) {
            Some("WKB") | None => {}
            Some(e) => t_type.fail(format!("`{name}`: encoding is \"{e}\", expected \"WKB\"")),
        }
        let bi = f.get_basic_info();
        if !bi.has_repetition() {
            t_rep.fail(format!("`{name}` has no repetition"));
        } else if bi.repetition() == Repetition::REPEATED {
            t_rep.fail(format!("`{name}` is REPEATED"));
        } else {
            t_rep.ok();
        }
    }
    out.push(t_type.finish());
    out.push(t_nest.finish());
    out.push(t_rep.finish());

    // one pass over the data of every geometry column that is a root BYTE_ARRAY
    let mut scans: BTreeMap<&str, Scan> = BTreeMap::new();
    let mut scan_errors: Vec<String> = Vec::new();
    for (name, f) in &geom_fields {
        if f.get_physical_type() != PhysicalType::BYTE_ARRAY {
            continue;
        }
        let col = &columns[*name];
        let bbox = bbox_nums(col);
        let bbox_col = col.get("covering").and_then(|c| resolve_bbox_paths(c).ok());
        let geodesic = col
            .get("edges")
            .and_then(Value::as_str)
            .is_some_and(|e| e != "planar");
        match scan_column(path, name, bbox_col.as_deref(), bbox.as_deref(), geodesic) {
            Ok(sc) => {
                scans.insert(name, sc);
            }
            Err(e) => scan_errors.push(format!("`{name}`: {e:#}")),
        }
    }

    // /conf/core/wkb
    let mut t = T::new(WKB);
    for e in &scan_errors {
        t.fail(format!("cannot read column: {e}"));
    }
    for (name, sc) in &scans {
        t.ok();
        for e in &sc.wkb_errors {
            t.fail(format!("`{name}`: {e}"));
        }
        t.note(format!(
            "`{name}`: {} values decoded, {} null",
            sc.rows - sc.nulls,
            sc.nulls
        ));
    }
    out.push(t.finish());

    // /conf/core/geometry-types
    let mut t = T::new(GEOMETRY_TYPES);
    for (name, col) in &columns {
        let Some(list) = col.get("geometry_types").and_then(Value::as_array) else {
            continue;
        };
        t.ok();
        let mut declared: BTreeSet<String> = BTreeSet::new();
        for v in list {
            match v.as_str() {
                Some(s) if valid_type_name(s) => {
                    if !declared.insert(s.to_string()) {
                        t.fail(format!("`{name}`: geometry_types lists \"{s}\" twice"));
                    }
                }
                Some(s) => t.fail(format!(
                    "`{name}`: \"{s}\" is not a valid geometry type string"
                )),
                None => t.fail(format!("`{name}`: geometry_types contains a non-string")),
            }
        }
        if declared.is_empty() {
            t.note(format!(
                "`{name}`: geometry_types is empty, data not constrained"
            ));
            continue;
        }
        if let Some(sc) = scans.get(name.as_str()) {
            for ty in &sc.types {
                if !declared.contains(ty) {
                    t.fail(format!(
                        "`{name}`: data contains {ty}, which is not in geometry_types {:?}",
                        declared
                    ));
                }
            }
        }
        for rg in 0..meta.num_row_groups() {
            let Some(codes) = chunk(meta, rg, name)
                .and_then(|c| c.geo_statistics())
                .and_then(|s| s.geospatial_types())
            else {
                continue;
            };
            for c in codes {
                match wkb::type_name(*c as u32) {
                    Some(n) if declared.contains(&n) => {}
                    Some(n) => t.fail(format!("`{name}`: row group {rg} statistics list {n} (code {c}), not in geometry_types")),
                    None => t.fail(format!("`{name}`: row group {rg} statistics list unknown code {c}")),
                }
            }
        }
    }
    out.push(t.finish());

    // /conf/core/crs-projjson
    let mut t = T::new(CRS_PROJJSON);
    for (name, col) in &columns {
        match col.get("crs") {
            None | Some(Value::Null) => {}
            Some(v @ Value::Object(_)) => {
                t.ok();
                for e in schema_errors(&schemas.projjson, v, 3) {
                    t.fail(format!("`{name}`: PROJJSON schema: {e}"));
                }
            }
            Some(v) => t.fail(format!(
                "`{name}`: crs is {} , expected a PROJJSON object or null",
                v
            )),
        }
    }
    out.push(t.finish());

    // /conf/core/crs-consistency and /conf/core/crs-default
    let mut t = T::new(CRS_CONSISTENCY);
    let mut td = T::new(CRS_DEFAULT);
    for (name, f) in &geom_fields {
        let col = &columns[*name];
        let lt = logical(f);
        if !is_geo_logical(&lt) {
            continue;
        }
        let a = Crs::from_geo(col);
        let b = Crs::from_parquet(parquet_crs(&lt).as_deref(), &kv);
        match (&a, &b) {
            (Crs::Undefined, Crs::Undefined) => t.ok(),
            (Crs::Authority(..), Crs::Authority(..)) | (Crs::Named(_), Crs::Named(_)) if a == b => {
                t.ok()
            }
            (Crs::Authority(..), Crs::Authority(..))
            | (Crs::Undefined, _)
            | (_, Crs::Undefined) => t.fail(format!(
                "`{name}`: geo crs is {} but Parquet crs is {}",
                a.describe(),
                b.describe()
            )),
            _ => t.note(format!(
                "`{name}`: cannot compare {} with {} without a CRS library",
                a.describe(),
                b.describe()
            )),
        }
        if col.get("crs").is_none() {
            if b == Crs::crs84() {
                td.ok();
            } else {
                td.fail(format!(
                    "`{name}`: no geo crs (default OGC:CRS84) but Parquet crs is {}",
                    b.describe()
                ));
            }
            if let Some(sc) = scans.get(name)
                && sc.lonlat_bad > 0
            {
                td.fail(format!(
                    "`{name}`: {} geometries have coordinates outside [-180,180]x[-90,90]",
                    sc.lonlat_bad
                ));
            }
        }
    }
    out.push(t.finish());
    out.push(td.finish());

    // /conf/core/axis-order (heuristic on geographic CRS)
    let mut t = T::new(AXIS_ORDER);
    for (name, col) in &columns {
        if !geographic(col) {
            t.ok();
            t.note(format!(
                "`{name}`: not a geographic CRS, trivially satisfied"
            ));
            continue;
        }
        if let Some(sc) = scans.get(name.as_str()) {
            t.ok();
            if sc.lonlat_bad > 0 {
                t.fail(format!("`{name}`: {} geometries have first/second coordinates outside longitude/latitude range", sc.lonlat_bad));
            }
        }
    }
    out.push(t.finish());

    // simple member tests
    let mut t = T::new(EDGES_VALUE);
    let mut te = T::new(EPOCH);
    let mut to = T::new(ORIENTATION_VALUE);
    for (name, col) in &columns {
        if let Some(v) = col.get("edges") {
            t.ok();
            if !v.as_str().is_some_and(|s| EDGES.contains(&s)) {
                t.fail(format!("`{name}`: edges is {v}, expected one of {EDGES:?}"));
            }
        }
        if let Some(v) = col.get("epoch") {
            te.ok();
            if !v.is_number() {
                te.fail(format!("`{name}`: epoch is {v}, expected a number"));
            }
        }
        if let Some(v) = col.get("orientation") {
            to.ok();
            if v.as_str() != Some("counterclockwise") {
                to.fail(format!(
                    "`{name}`: orientation is {v}, expected \"counterclockwise\""
                ));
            }
        }
    }
    out.push(t.finish());
    out.push(te.finish());
    out.push(to.finish());

    // /conf/core/orientation-rings
    let mut t = T::new(ORIENTATION_RINGS);
    for (name, col) in &columns {
        if col.get("orientation").is_none() {
            continue;
        }
        let Some(sc) = scans.get(name.as_str()) else {
            t.note(format!("`{name}`: data not readable"));
            continue;
        };
        t.ok();
        if sc.rings_bad > 0 {
            t.fail(format!(
                "`{name}`: {} of {} rings violate counterclockwise exterior / clockwise interior",
                sc.rings_bad, sc.rings_checked
            ));
        } else {
            t.note(format!("`{name}`: {} rings checked", sc.rings_checked));
        }
    }
    out.push(t.finish());

    // /conf/core/bbox-array, bbox-crs, bbox-extent
    let mut ta = T::new(BBOX_ARRAY);
    let mut tc = T::new(BBOX_CRS);
    let mut tx = T::new(BBOX_EXTENT);
    for (name, col) in &columns {
        let Some(b) = col.get("bbox") else { continue };
        ta.ok();
        let Some(arr) = b.as_array() else {
            ta.fail(format!("`{name}`: bbox is not an array"));
            continue;
        };
        if ![4, 6, 8].contains(&arr.len()) {
            ta.fail(format!(
                "`{name}`: bbox has {} elements, expected 4, 6 or 8",
                arr.len()
            ));
            continue;
        }
        let Some(nums) = bbox_nums(col) else {
            ta.fail(format!("`{name}`: bbox contains non-numbers"));
            continue;
        };
        let half = nums.len() / 2;
        let (xmin, ymin, xmax, ymax) = (nums[0], nums[1], nums[half], nums[half + 1]);
        if geographic(col) {
            if ymin > ymax {
                ta.fail(format!("`{name}`: bbox ymin {ymin} > ymax {ymax}"));
            }
            if xmin > xmax {
                ta.note(format!(
                    "`{name}`: bbox crosses the antimeridian (xmin {xmin} > xmax {xmax})"
                ));
            }
            tc.ok();
            if !(-180.0..=180.0).contains(&xmin)
                || !(-180.0..=180.0).contains(&xmax)
                || !(-90.0..=90.0).contains(&ymin)
                || !(-90.0..=90.0).contains(&ymax)
            {
                tc.fail(format!(
                    "`{name}`: bbox {nums:?} is outside longitude/latitude range"
                ));
            }
        } else {
            tc.note(format!(
                "`{name}`: projected or undefined CRS, area of use not checked"
            ));
        }
        if let Some(sc) = scans.get(name.as_str()) {
            tx.ok();
            if sc.outside_bbox > 0 {
                tx.fail(format!(
                    "`{name}`: {} geometries fall outside bbox {nums:?}",
                    sc.outside_bbox
                ));
            }
        }
    }
    out.push(ta.finish());
    out.push(tc.finish());
    out.push(tx.finish());
    out.push(skip(MEDIA_TYPE, "not testable on the file alone"));

    // Bounding Box Covering class
    let covering: Vec<(&String, &Value)> = columns
        .iter()
        .filter(|(_, c)| c.get("covering").is_some())
        .collect();
    if covering.is_empty() {
        for id in COVERING_IDS {
            out.push(skip(id, "no `covering` declared; class not claimed"));
        }
    } else {
        let mut tk = T::new(COV_KEYS);
        let mut tp = T::new(COV_BBOX_PATHS);
        let mut ts = T::new(COV_STRUCTURE);
        let mut tt = T::new(COV_TYPE);
        let mut tr = T::new(COV_REPETITION);
        let mut tn = T::new(COV_NESTING);
        for (name, col) in covering {
            let cov = &col["covering"];
            tk.ok();
            match cov.as_object() {
                None => {
                    tk.fail(format!("`{name}`: covering is not an object"));
                    continue;
                }
                Some(o) => {
                    for k in o.keys().filter(|k| *k != "bbox") {
                        tk.fail(format!("`{name}`: covering has unknown member `{k}`"));
                    }
                    if !o.contains_key("bbox") {
                        tk.fail(format!("`{name}`: covering has no `bbox` member"));
                    }
                }
            }
            tp.ok();
            let bcol = match resolve_bbox_paths(cov) {
                Ok(c) => c,
                Err(e) => {
                    tp.fail(format!("`{name}`: {e}"));
                    continue;
                }
            };
            let Some(bf) = root_by_name.get(bcol.as_str()) else {
                tp.fail(format!("`{name}`: covering names column `{bcol}`, which is not at the root of the Parquet schema"));
                tn.fail(format!("`{name}`: no root column `{bcol}`"));
                continue;
            };
            tn.ok();
            ts.ok();
            if !bf.is_group() {
                ts.fail(format!("`{bcol}` is not a group field"));
                continue;
            }
            let children = bf.get_fields();
            let names: Vec<&str> = children.iter().map(|c| c.name()).collect();
            let expected: &[&str] = match children.len() {
                4 => &["xmin", "ymin", "xmax", "ymax"],
                6 => &["xmin", "ymin", "zmin", "xmax", "ymax", "zmax"],
                n => {
                    ts.fail(format!("`{bcol}` has {n} child fields, expected 4 or 6"));
                    &[]
                }
            };
            if !expected.is_empty() && names != expected {
                ts.fail(format!(
                    "`{bcol}` child fields are {names:?}, expected {expected:?}"
                ));
            }
            tt.ok();
            let mut kinds: BTreeSet<String> = BTreeSet::new();
            for c in children {
                if c.is_group() {
                    tt.fail(format!(
                        "`{bcol}.{}` is a group, expected FLOAT or DOUBLE",
                        c.name()
                    ));
                    continue;
                }
                let pt = c.get_physical_type();
                if pt != PhysicalType::FLOAT && pt != PhysicalType::DOUBLE {
                    tt.fail(format!(
                        "`{bcol}.{}` is {pt:?}, expected FLOAT or DOUBLE",
                        c.name()
                    ));
                }
                kinds.insert(format!("{pt:?}"));
            }
            if kinds.len() > 1 {
                tt.fail(format!("`{bcol}` mixes child types {kinds:?}"));
            }
            tr.ok();
            if let Some(gf) = geom_fields.get(name.as_str()) {
                let (gb, bb) = (gf.get_basic_info(), bf.get_basic_info());
                if gb.has_repetition() && bb.has_repetition() && gb.repetition() != bb.repetition()
                {
                    tr.fail(format!(
                        "`{bcol}` is {:?} but `{name}` is {:?}",
                        bb.repetition(),
                        gb.repetition()
                    ));
                }
            }
            if let Some(sc) = scans.get(name.as_str())
                && sc.bbox_rep_checked
                && sc.bbox_rep_mismatch > 0
            {
                tr.fail(format!(
                    "`{bcol}`: {} rows where the bbox is present xor the geometry is present",
                    sc.bbox_rep_mismatch
                ));
            }
        }
        out.extend([
            tk.finish(),
            tp.finish(),
            ts.finish(),
            tt.finish(),
            tr.finish(),
            tn.finish(),
        ]);
    }

    // Cloud-Optimized Distribution class
    let mut t = T::new(DIST_STATS);
    for (name, f) in &geom_fields {
        if !is_geo_logical(&logical(f)) {
            continue;
        }
        t.ok();
        let missing: Vec<usize> = (0..meta.num_row_groups())
            .filter(|rg| {
                chunk(meta, *rg, name)
                    .and_then(|c| c.geo_statistics())
                    .and_then(|s| s.bounding_box())
                    .is_none()
            })
            .collect();
        if !missing.is_empty() {
            t.fail(format!(
                "`{name}`: no geospatial statistics bbox in row groups {missing:?}"
            ));
        }
    }
    out.push(t.finish());

    let boxes: Option<Vec<[f64; 4]>> = geom_fields.contains_key(primary).then(|| {
        (0..meta.num_row_groups())
            .filter_map(|rg| {
                chunk(meta, rg, primary)
                    .and_then(|c| c.geo_statistics())
                    .and_then(|s| s.bounding_box())
            })
            .map(|b| [b.get_xmin(), b.get_ymin(), b.get_xmax(), b.get_ymax()])
            .collect()
    });
    out.push(match boxes {
        Some(b) if b.len() == meta.num_row_groups() => match spatial::measure(&b) {
            None => skip(DIST_SPATIAL_ORDER, format!("{} row group(s) or degenerate extent: pruning cannot be measured", b.len())),
            Some(m) => {
                let msg = format!(
                    "{} row groups: skip rate {:.3} vs ideal tiling {:.3} (ratio {:.2}, pass at {:.2}); area factor {:.2}",
                    m.row_groups, m.file_skip, m.ideal_skip, m.ratio, spatial::PASS_RATIO, m.area_factor
                );
                Outcome { id: DIST_SPATIAL_ORDER, status: if m.ratio >= spatial::PASS_RATIO { Status::Pass } else { Status::Fail }, message: msg }
            }
        },
        _ => skip(DIST_SPATIAL_ORDER, "primary column lacks geospatial statistics in some row group"),
    });

    finish(out, "not run")
}
