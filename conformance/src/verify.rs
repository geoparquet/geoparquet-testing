//! Regression suite: run every fixture under a directory and compare the failing test ids of
//! each file with a committed manifest (`{"relative/path.parquet": {"fail": [...], "skip": [...]}}`);
//! every test not listed must pass.

use std::collections::BTreeMap;
use std::path::Path;

use anyhow::{Context, Result, bail};
use serde::{Deserialize, Serialize};

use crate::checks::{self, Options, Schemas};
use crate::corpus::walk;
use crate::source::Local;

#[derive(Serialize, Deserialize, Default, PartialEq, Eq)]
struct Expected {
    /// Test identifiers that must fail.
    fail: Vec<String>,
    /// Test identifiers that must be skipped (not applicable or not decidable); the rest must pass.
    skip: Vec<String>,
}

pub fn run(dir: &Path, manifest: &Path, update: bool, schemas: &Schemas) -> Result<()> {
    let mut files = Vec::new();
    walk(dir, &mut files);
    files.sort();
    if files.is_empty() {
        bail!("no .parquet files under {}", dir.display());
    }
    let mut actual: BTreeMap<String, Expected> = BTreeMap::new();
    for f in &files {
        let rel = f
            .strip_prefix(dir)
            .unwrap_or(f)
            .to_string_lossy()
            .replace('\\', "/");
        let r = checks::run(&Local(f.clone()), schemas, &Options::default())
            .with_context(|| format!("checking {rel}"))?;
        let ids = |status: checks::Status| -> Vec<String> {
            let mut v: Vec<String> = r
                .outcomes
                .iter()
                .filter(|o| o.status == status)
                .map(|o| o.id.to_string())
                .collect();
            v.sort();
            v
        };
        actual.insert(
            rel,
            Expected {
                fail: ids(checks::Status::Fail),
                skip: ids(checks::Status::Skip),
            },
        );
    }
    if update {
        std::fs::write(manifest, serde_json::to_string_pretty(&actual)? + "\n")
            .with_context(|| format!("write {}", manifest.display()))?;
        println!("{} files recorded in {}", actual.len(), manifest.display());
        return Ok(());
    }
    let expected: BTreeMap<String, Expected> = serde_json::from_slice(
        &std::fs::read(manifest).with_context(|| format!("read {}", manifest.display()))?,
    )
    .with_context(|| format!("parse {}", manifest.display()))?;
    let mut problems = 0;
    for (name, exp) in &expected {
        match actual.get(name) {
            None => {
                problems += 1;
                println!("  MISSING  {name}: in the manifest but not generated");
            }
            Some(act) if act != exp => {
                problems += 1;
                if act.fail != exp.fail {
                    println!(
                        "  CHANGED  {name}: expected fail {:?}, got {:?}",
                        exp.fail, act.fail
                    );
                } else {
                    println!(
                        "  CHANGED  {name}: expected skip {:?}, got {:?}",
                        exp.skip, act.skip
                    );
                }
            }
            _ => {}
        }
    }
    for name in actual.keys().filter(|n| !expected.contains_key(*n)) {
        problems += 1;
        println!(
            "  NEW      {name}: not in the manifest (run with --update after reviewing its verdicts)"
        );
    }
    println!(
        "{} fixtures checked against {}: {} problem(s)",
        actual.len(),
        manifest.display(),
        problems
    );
    if problems > 0 {
        bail!("{problems} fixture verdict(s) differ from the manifest");
    }
    Ok(())
}
