//! GeoParquet 2.0 conformance checks: the abstract tests of the OGC draft, on top of the Apache
//! Arrow Rust `parquet` crate. The CLI lives in `main.rs`; `wasm.rs` exposes the same checks to
//! a browser.

pub mod checks;
pub mod corpus;
pub mod crs;
pub mod source;
pub mod spatial;
pub mod verify;
#[cfg(feature = "wasm")]
pub mod wasm;
pub mod wkb;
