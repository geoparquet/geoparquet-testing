//! Runs the suite over the geoparquet-testing corpus: every file under data/ must pass Core
//! (and Covering when claimed); every file in bad_data/manifest.json must fail the test that
//! corresponds to its `expected_failure`.

use std::path::{Path, PathBuf};

use anyhow::{Context, Result};
use serde_json::Value;

use crate::checks::{self, Report, Schemas, Status};

fn walk(dir: &Path, out: &mut Vec<PathBuf>) {
    if let Ok(rd) = std::fs::read_dir(dir) {
        for e in rd.flatten() {
            let p = e.path();
            if p.is_dir() {
                walk(&p, out);
            } else if p.extension().is_some_and(|x| x == "parquet") {
                out.push(p);
            }
        }
    }
}

/// Which OGC abstract tests should catch a corpus `expected_failure`; empty = no OGC requirement.
fn expected_tests(kind: &str) -> &'static [&'static str] {
    match kind {
        "bbox_mismatch" => &[checks::BBOX_EXTENT],
        "crs_mismatch" => &[checks::CRS_CONSISTENCY],
        "geometry_column_undeclared" | "primary_column_mismatch" => &[checks::COLUMN_METADATA],
        "geometry_type_mismatch" | "zm_mismatch" => &[checks::GEOMETRY_TYPES],
        "metadata_invalid_json" | "metadata_invalid_utf8" | "metadata_missing" => {
            &[checks::GEO_METADATA]
        }
        "schema_validation_error" => &[checks::GEO_METADATA, checks::CRS_PROJJSON],
        "orientation_mismatch" => &[checks::ORIENTATION_RINGS],
        "version_feature_mismatch" | "version_unknown" => &[checks::FILE_METADATA],
        "wkb_parse_error" => &[checks::WKB],
        _ => &[],
    }
}

fn core_and_covering_failures(r: &Report) -> Vec<&'static str> {
    let mut v = r.failed("core");
    v.extend(r.failed("covering"));
    v
}

pub fn run(dir: &Path, schemas: &Schemas, verbose: bool) -> Result<()> {
    let mut good = Vec::new();
    walk(&dir.join("data"), &mut good);
    good.sort();
    let (mut ok, mut bad_good) = (0, 0);
    let (mut stats_pass, mut order_pass, mut order_skip) = (0, 0, 0);
    println!(
        "== data/ ({} files): every file must pass Core (+ Covering when claimed)",
        good.len()
    );
    for p in &good {
        let r = checks::run(p, schemas);
        let fails = core_and_covering_failures(&r);
        let rel = p.strip_prefix(dir).unwrap_or(p).display();
        if fails.is_empty() {
            ok += 1;
            if verbose {
                println!("  ok    {rel}");
            }
        } else {
            bad_good += 1;
            println!("  FAIL  {rel}");
            for id in fails {
                println!(
                    "        {id}: {}",
                    r.get(id).map(|o| o.message.as_str()).unwrap_or("")
                );
            }
        }
        if r.get(checks::DIST_STATS)
            .is_some_and(|o| o.status == Status::Pass)
        {
            stats_pass += 1;
        }
        match r.get(checks::DIST_SPATIAL_ORDER).map(|o| o.status) {
            Some(Status::Pass) => order_pass += 1,
            Some(Status::Skip) => order_skip += 1,
            _ => {}
        }
    }
    println!(
        "  {ok} pass, {bad_good} unexpected failures; distribution: {stats_pass} have geospatial statistics, spatial order {order_pass} pass / {order_skip} not measurable\n"
    );

    let manifest: Value = serde_json::from_reader(
        std::fs::File::open(dir.join("bad_data/manifest.json"))
            .context("bad_data/manifest.json")?,
    )?;
    let entries = manifest.as_object().context("manifest is not an object")?;
    println!(
        "== bad_data/ ({} files): each must fail the test matching its expected_failure",
        entries.len()
    );
    let (mut detected, mut missed, mut no_req) = (0, 0, 0);
    for (name, entry) in entries {
        let kind = entry
            .get("expected_failure")
            .and_then(Value::as_str)
            .unwrap_or("?");
        let r = checks::run(&dir.join("bad_data").join(name), schemas);
        let fails = core_and_covering_failures(&r);
        let expected = expected_tests(kind);
        let hit: Vec<&str> = fails
            .iter()
            .copied()
            .filter(|f| expected.contains(f))
            .collect();
        if expected.is_empty() {
            no_req += 1;
            println!("  n/a   {name} [{kind}]: no OGC requirement; failed {fails:?}");
        } else if !hit.is_empty() {
            detected += 1;
            let msg = r.get(hit[0]).map(|o| o.message.as_str()).unwrap_or("");
            println!(
                "  ok    {name} [{kind}] -> {}: {}",
                hit[0],
                msg.chars().take(150).collect::<String>()
            );
            if verbose && fails.len() > hit.len() {
                println!("        also failed {fails:?}");
            }
        } else {
            missed += 1;
            println!("  MISS  {name} [{kind}]: expected {expected:?}, failed {fails:?}");
        }
    }
    println!("  {detected} detected, {missed} missed, {no_req} without an OGC requirement");
    if bad_good > 0 || missed > 0 {
        anyhow::bail!("{bad_good} valid file(s) failed, {missed} defect(s) missed");
    }
    Ok(())
}
