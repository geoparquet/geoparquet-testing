//! Browser entry points. The page's Web Worker provides two synchronous JavaScript functions,
//! `gpqHeadLength(url)` and `gpqFetchRange(url, start, end)`, implemented with synchronous
//! XMLHttpRequest, so the same range-request reader works on a URL from inside the browser.

use bytes::Bytes;
use js_sys::Uint8Array;
use parquet::errors::{ParquetError, Result as PResult};
use wasm_bindgen::prelude::*;

use crate::checks::{self, Options, Schemas};
use crate::source::{InMemory, Ranged};

#[wasm_bindgen]
extern "C" {
    #[wasm_bindgen(catch, js_name = gpqHeadLength)]
    fn js_head_length(url: &str) -> Result<f64, JsValue>;
    #[wasm_bindgen(catch, js_name = gpqFetchRange)]
    fn js_fetch_range(url: &str, start: f64, end: f64) -> Result<Uint8Array, JsValue>;
}

fn err(e: impl std::fmt::Display) -> JsValue {
    JsValue::from_str(&e.to_string())
}

/// Run the abstract tests on a file held in memory; returns the report as JSON.
#[wasm_bindgen]
pub fn check_bytes(name: &str, bytes: Vec<u8>) -> Result<String, JsValue> {
    let schemas = Schemas::load().map_err(err)?;
    let src = InMemory {
        name: name.to_string(),
        bytes: Bytes::from(bytes),
    };
    let report =
        checks::run(&src, &schemas, &Options::default()).map_err(|e| err(format!("{e:#}")))?;
    serde_json::to_string(&report).map_err(err)
}

/// Run the abstract tests on a URL through the worker's range-request callbacks; `max_rows`
/// of 0 means every row.
#[wasm_bindgen]
pub fn check_url(url: &str, max_rows: u32) -> Result<String, JsValue> {
    let schemas = Schemas::load().map_err(err)?;
    let len = js_head_length(url)? as u64;
    let target = url.to_string();
    let fetch = move |a: u64, b: u64| -> PResult<Bytes> {
        let arr = js_fetch_range(&target, a as f64, b as f64).map_err(|e| {
            ParquetError::External(
                e.as_string()
                    .unwrap_or_else(|| "range request failed".into())
                    .into(),
            )
        })?;
        Ok(Bytes::from(arr.to_vec()))
    };
    let src = Ranged::new(url.to_string(), len, Box::new(fetch));
    let opts = Options {
        max_rows: (max_rows > 0).then_some(max_rows as usize),
    };
    let report = checks::run(&src, &schemas, &opts).map_err(|e| err(format!("{e:#}")))?;
    serde_json::to_string(&report).map_err(err)
}
