//! The two places a GeoParquet 2.0 file states its CRS, reduced to something comparable
//! without a CRS library: an authority:code pair, "undefined", or "cannot tell".

use serde_json::Value;
use std::collections::HashMap;

#[derive(Debug, Clone, PartialEq)]
pub enum Crs {
    Undefined,
    Authority(String, String),
    /// PROJJSON without an identifier: describes a CRS, but equality needs a CRS library.
    Named(String),
    Unparsed(String),
}

impl Crs {
    pub fn crs84() -> Crs {
        Crs::Authority("OGC".into(), "CRS84".into())
    }

    /// EPSG:4326 and OGC:CRS84 are the same CRS for GeoParquet (longitude first).
    pub fn authority(a: &str, c: &str) -> Crs {
        let a = a.trim().to_ascii_uppercase();
        let c = c.trim().to_string();
        if (a == "EPSG" && c == "4326") || (a == "OGC" && c.eq_ignore_ascii_case("CRS84")) {
            return Crs::crs84();
        }
        Crs::Authority(a, c)
    }

    fn from_id(id: &Value) -> Option<Crs> {
        let auth = id.get("authority")?.as_str()?;
        let code = match id.get("code")? {
            Value::Number(n) => n.to_string(),
            Value::String(s) => s.clone(),
            _ => return None,
        };
        if auth.is_empty() || code.is_empty() {
            return None;
        }
        Some(Crs::authority(auth, &code))
    }

    pub fn from_projjson(v: &Value) -> Crs {
        if let Some(c) = v.get("id").and_then(Crs::from_id) {
            return c;
        }
        if let Some(c) = v
            .get("ids")
            .and_then(Value::as_array)
            .and_then(|a| a.first())
            .and_then(Crs::from_id)
        {
            return c;
        }
        Crs::Named(format!(
            "{} \"{}\"",
            v.get("type").and_then(Value::as_str).unwrap_or("PROJJSON"),
            v.get("name").and_then(Value::as_str).unwrap_or("unnamed")
        ))
    }

    /// GeoParquet column metadata `crs`: absent = OGC:CRS84, null = undefined, object = PROJJSON.
    pub fn from_geo(col: &Value) -> Crs {
        match col.get("crs") {
            None => Crs::crs84(),
            Some(Value::Null) => Crs::Undefined,
            Some(v @ Value::Object(_)) => Crs::from_projjson(v),
            Some(v) => Crs::Unparsed(v.to_string()),
        }
    }

    /// Parquet logical-type `crs` parameter (Parquet Geospatial.md, "crs customization").
    pub fn from_parquet(param: Option<&str>, file_kv: &HashMap<String, String>) -> Crs {
        let Some(p) = param.map(str::trim).filter(|p| !p.is_empty()) else {
            return Crs::crs84();
        };
        if p.starts_with('{') {
            return match serde_json::from_str::<Value>(p) {
                Ok(v) => Crs::from_projjson(&v),
                Err(e) => Crs::Unparsed(format!("inline PROJJSON does not parse: {e}")),
            };
        }
        if let Some(rest) = p.strip_prefix("srid:") {
            return if rest == "0" {
                Crs::Undefined
            } else {
                Crs::Unparsed(format!("srid:{rest} (no authority; not resolvable)"))
            };
        }
        if let Some(key) = p.strip_prefix("projjson:") {
            return match file_kv.get(key) {
                Some(s) => match serde_json::from_str::<Value>(s) {
                    Ok(v) => Crs::from_projjson(&v),
                    Err(e) => Crs::Unparsed(format!("projjson:{key} does not parse: {e}")),
                },
                None => Crs::Unparsed(format!("projjson:{key} names a missing file metadata key")),
            };
        }
        // <authority>:<code>: one colon, a plain authority token, a non-empty code
        if let Some((a, c)) = p.split_once(':')
            && !a.is_empty()
            && a.chars()
                .all(|ch| ch.is_ascii_alphanumeric() || ch == '_' || ch == '-')
            && !c.is_empty()
            && !c.contains(':')
        {
            return Crs::authority(a, c);
        }
        Crs::Unparsed(p.to_string())
    }

    pub fn describe(&self) -> String {
        match self {
            Crs::Undefined => "undefined".into(),
            Crs::Authority(a, c) => format!("{a}:{c}"),
            Crs::Named(n) => format!("PROJJSON without id ({n})"),
            Crs::Unparsed(s) => format!("unparsed ({s})"),
        }
    }
}

/// The PROJJSON object that determines the coordinate system: the object itself, the first
/// component of a CompoundCRS, the source of a BoundCRS, the base of a derived CRS.
fn horizontal(v: &Value) -> &Value {
    match v.get("type").and_then(Value::as_str) {
        Some("CompoundCRS") => v
            .get("components")
            .and_then(Value::as_array)
            .and_then(|a| a.first())
            .map(horizontal)
            .unwrap_or(v),
        Some("BoundCRS") => v.get("source_crs").map(horizontal).unwrap_or(v),
        _ => v,
    }
}

/// Whether coordinates are longitude/latitude (an ellipsoidal coordinate system).
pub fn is_geographic(crs: &Crs, projjson: Option<&Value>) -> bool {
    if let Some(v) = projjson {
        let h = horizontal(v);
        if let Some(sub) = h
            .get("coordinate_system")
            .and_then(|c| c.get("subtype"))
            .and_then(Value::as_str)
        {
            return sub == "ellipsoidal";
        }
        return matches!(
            h.get("type").and_then(Value::as_str),
            Some("GeographicCRS" | "DerivedGeographicCRS")
        );
    }
    *crs == Crs::crs84()
}

/// Whether the CRS declares latitude as its first axis (EPSG:4326 style), longitude first
/// (CRS84 style), or nothing usable. Absent `crs` is OGC:CRS84; null is undefined (None).
pub fn lat_lon_order(col: &Value) -> Option<bool> {
    match col.get("crs") {
        None => Some(false),
        Some(v @ Value::Object(_)) => {
            let h = horizontal(v);
            if !is_geographic(&Crs::from_projjson(h), Some(h)) {
                return Some(false);
            }
            let first = h
                .get("coordinate_system")
                .and_then(|c| c.get("axis"))
                .and_then(Value::as_array)
                .and_then(|a| a.first());
            match first
                .and_then(|a| a.get("direction"))
                .and_then(Value::as_str)
            {
                Some("north" | "south") => Some(true),
                Some("east" | "west") => Some(false),
                _ => match Crs::from_projjson(h) {
                    Crs::Authority(a, c) if a == "EPSG" && c == "4326" => Some(true),
                    c if c == Crs::crs84() => Some(false),
                    _ => None,
                },
            }
        }
        _ => None,
    }
}
