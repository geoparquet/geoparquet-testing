mod checks;
mod corpus;
mod crs;
mod source;
mod spatial;
mod wkb;

use std::path::PathBuf;

use anyhow::{Context, Result};
use clap::{Parser, Subcommand, ValueEnum};
use url::Url;

use checks::{Options, Report, Status};
use source::{Local, Remote, RemoteOptions};

#[derive(Parser)]
#[command(
    name = "geoparquet-conf",
    about = "GeoParquet 2.0 OGC abstract tests, in Rust, without DuckDB"
)]
struct Cli {
    #[command(subcommand)]
    cmd: Cmd,
}

#[derive(Clone, Copy, PartialEq, Eq, ValueEnum)]
enum Class {
    All,
    Core,
    Covering,
    Distribution,
}

impl Class {
    fn includes(self, class: &str) -> bool {
        match self {
            Class::All => true,
            Class::Core => class == "core",
            Class::Covering => class == "covering",
            Class::Distribution => class == "distribution",
        }
    }
}

#[derive(Subcommand)]
enum Cmd {
    /// Run the abstract tests on a file, a directory, or an object-store URL or prefix
    /// (s3://, gs://, az://, https://; a prefix ends with '/')
    Check {
        target: String,
        #[arg(long)]
        json: bool,
        /// Which conformance class decides the exit code and is printed
        #[arg(long, value_enum, default_value_t = Class::All)]
        class: Class,
        /// Read only the first N rows (whole row groups) of each file; data tests are then sampled
        #[arg(long)]
        max_rows: Option<usize>,
        /// For a directory or prefix, check at most N files
        #[arg(long, default_value_t = 20)]
        max_files: usize,
        /// AWS region for s3:// URLs (default: AWS_REGION, AWS_DEFAULT_REGION, then us-east-1)
        #[arg(long)]
        s3_region: Option<String>,
        /// Extra object_store option as key=value, repeatable (e.g. aws_endpoint=http://localhost:9000)
        #[arg(long = "opt")]
        opts: Vec<String>,
    },
    /// Run over a geoparquet-testing checkout (data/ and bad_data/)
    Corpus {
        dir: PathBuf,
        #[arg(long)]
        verbose: bool,
    },
}

fn counts(r: &Report, class: &str) -> (usize, usize, usize) {
    let mut c = (0, 0, 0);
    for o in r.outcomes.iter().filter(|o| o.class() == class) {
        match o.status {
            Status::Pass => c.0 += 1,
            Status::Fail => c.1 += 1,
            Status::Skip => c.2 += 1,
        }
    }
    c
}

fn extras(r: &Report) -> String {
    let mut s = String::new();
    if let Some((bytes, reqs)) = r.traffic {
        s.push_str(&format!(
            "  remote: {:.1} MB in {reqs} range requests",
            bytes as f64 / 1e6
        ));
    }
    if r.sampled {
        s.push_str("  (data tests sampled: --max-rows)");
    }
    s
}

fn print_text(r: &Report, class: Class) {
    println!("{}", r.file);
    for c in ["core", "covering", "distribution"] {
        if !class.includes(c) {
            continue;
        }
        for o in r.outcomes.iter().filter(|o| o.class() == c) {
            let tag = match o.status {
                Status::Pass => "PASS",
                Status::Fail => "FAIL",
                Status::Skip => "skip",
            };
            if o.message.is_empty() {
                println!("  {tag}  {}", o.id);
            } else {
                println!("  {tag}  {}  -- {}", o.id, o.message);
            }
        }
        let (p, f, s) = counts(r, c);
        let verdict = if f > 0 {
            "NOT CONFORMANT"
        } else if p == 0 {
            "not claimed"
        } else {
            "conformant"
        };
        println!("  => {c}: {p} pass, {f} fail, {s} skipped: {verdict}");
    }
    let e = extras(r);
    if !e.is_empty() {
        println!("{e}");
    }
}

fn print_summary(r: &Report) {
    let mut line = r.file.clone();
    for c in ["core", "covering", "distribution"] {
        let (p, f, s) = counts(r, c);
        line.push_str(&format!("  {c} {p}/{f}/{s}"));
    }
    let fails: Vec<&str> = r
        .outcomes
        .iter()
        .filter(|o| o.status == Status::Fail)
        .map(|o| o.id)
        .collect();
    if !fails.is_empty() {
        line.push_str(&format!("  FAIL {}", fails.join(" ")));
    }
    line.push_str(&extras(r));
    println!("{line}");
}

/// Exit codes: 0 conformant, 1 a test failed, 2 the tool could not run on some input.
fn check(
    target: String,
    json: bool,
    class: Class,
    options: Options,
    max_files: usize,
    ropts: RemoteOptions,
) -> Result<i32> {
    let schemas = checks::Schemas::load()?;
    let mut reports: Vec<Report> = Vec::new();
    let mut tool_errors = 0;
    let multi = if source::is_remote(&target) {
        target.ends_with('/')
    } else {
        PathBuf::from(&target).is_dir()
    };
    let mut record = |r: Result<Report>, what: &str, reports: &mut Vec<Report>| match r {
        Ok(r) => {
            if !json && multi {
                print_summary(&r);
            }
            reports.push(r);
        }
        Err(e) => {
            eprintln!("error: {what}: {e:#}");
            tool_errors += 1;
        }
    };
    if source::is_remote(&target) {
        let url = Url::parse(&target).with_context(|| format!("parse {target}"))?;
        if multi {
            let urls = source::list(&url, &ropts)?;
            eprintln!(
                "{} parquet objects under {target}; checking {}",
                urls.len(),
                urls.len().min(max_files)
            );
            for u in urls.iter().take(max_files) {
                let r =
                    Remote::open(u, &ropts).and_then(|src| checks::run(&src, &schemas, &options));
                record(r, u.as_str(), &mut reports);
            }
        } else {
            let r =
                Remote::open(&url, &ropts).and_then(|src| checks::run(&src, &schemas, &options));
            record(r, &target, &mut reports);
        }
    } else {
        let path = PathBuf::from(&target);
        if multi {
            let mut files = Vec::new();
            corpus::walk(&path, &mut files);
            files.sort();
            eprintln!(
                "{} parquet files under {target}; checking {}",
                files.len(),
                files.len().min(max_files)
            );
            for f in files.iter().take(max_files) {
                let r = checks::run(&Local(f.clone()), &schemas, &options);
                record(r, &f.display().to_string(), &mut reports);
            }
        } else {
            let r = checks::run(&Local(path), &schemas, &options);
            record(r, &target, &mut reports);
        }
    }
    if json {
        if multi {
            println!("{}", serde_json::to_string_pretty(&reports)?);
        } else if let Some(r) = reports.first() {
            println!("{}", serde_json::to_string_pretty(r)?);
        }
    } else if !multi && let Some(r) = reports.first() {
        print_text(r, class);
    }
    let failed = reports.iter().any(|r| {
        r.outcomes
            .iter()
            .any(|o| o.status == Status::Fail && class.includes(o.class()))
    });
    Ok(if tool_errors > 0 {
        2
    } else if failed {
        1
    } else {
        0
    })
}

fn main() {
    let cli = Cli::parse();
    let code = match cli.cmd {
        Cmd::Check {
            target,
            json,
            class,
            max_rows,
            max_files,
            s3_region,
            opts,
        } => {
            let ropts = RemoteOptions {
                s3_region,
                extra: opts
                    .iter()
                    .filter_map(|kv| {
                        kv.split_once('=')
                            .map(|(k, v)| (k.to_string(), v.to_string()))
                    })
                    .collect(),
            };
            check(target, json, class, Options { max_rows }, max_files, ropts)
        }
        Cmd::Corpus { dir, verbose } => checks::Schemas::load()
            .and_then(|schemas| corpus::run(&dir, &schemas, verbose))
            .map(|_| 0),
    };
    match code {
        Ok(c) => std::process::exit(c),
        Err(e) => {
            eprintln!("error: {e:#}");
            std::process::exit(2);
        }
    }
}
