//! The two places a GeoParquet 2.0 file states its CRS, reduced to something comparable
//! without a CRS library: an authority:code pair, "undefined", or "cannot tell".

use serde_json::Value;
use std::collections::HashMap;

#[derive(Debug, Clone, PartialEq)]
pub enum Crs {
    Undefined,
    Authority(String, String),
    Named(String),
    Unparsed(String),
}

impl Crs {
    pub fn crs84() -> Crs {
        Crs::Authority("OGC".into(), "CRS84".into())
    }

    pub fn authority(a: &str, c: &str) -> Crs {
        let a = a.trim().to_ascii_uppercase();
        let c = c.trim().to_string();
        if (a == "EPSG" && c == "4326") || (a == "OGC" && c.eq_ignore_ascii_case("CRS84")) {
            return Crs::crs84();
        }
        Crs::Authority(a, c)
    }

    pub fn from_projjson(v: &Value) -> Crs {
        if let Some(id) = v.get("id") {
            let auth = id.get("authority").and_then(Value::as_str).unwrap_or("");
            let code = match id.get("code") {
                Some(Value::Number(n)) => n.to_string(),
                Some(Value::String(s)) => s.clone(),
                _ => String::new(),
            };
            if !auth.is_empty() && !code.is_empty() {
                return Crs::authority(auth, &code);
            }
        }
        Crs::Named(
            v.get("name")
                .and_then(Value::as_str)
                .unwrap_or("unnamed")
                .to_string(),
        )
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
        if let Some((a, c)) = p.split_once(':') {
            return Crs::authority(a, c);
        }
        Crs::Unparsed(p.to_string())
    }

    pub fn describe(&self) -> String {
        match self {
            Crs::Undefined => "undefined".into(),
            Crs::Authority(a, c) => format!("{a}:{c}"),
            Crs::Named(n) => format!("PROJJSON without id (\"{n}\")"),
            Crs::Unparsed(s) => format!("unparsed ({s})"),
        }
    }
}

/// Whether coordinates should be longitude/latitude: PROJJSON type, else OGC:CRS84.
pub fn is_geographic(crs: &Crs, projjson: Option<&Value>) -> bool {
    if let Some(t) = projjson.and_then(|v| v.get("type")).and_then(Value::as_str) {
        return t == "GeographicCRS";
    }
    *crs == Crs::crs84()
}
