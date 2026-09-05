mod checks;
mod corpus;
mod crs;
mod spatial;
mod wkb;

use std::path::PathBuf;

use anyhow::Result;
use clap::{Parser, Subcommand};

use checks::{Report, Status};

#[derive(Parser)]
#[command(
    name = "geoparquet-conf",
    about = "GeoParquet 2.0 OGC abstract tests, in Rust, without DuckDB"
)]
struct Cli {
    #[command(subcommand)]
    cmd: Cmd,
}

#[derive(Subcommand)]
enum Cmd {
    /// Run the abstract tests on one file
    Check {
        file: PathBuf,
        #[arg(long)]
        json: bool,
        /// core, covering, distribution or all
        #[arg(long, default_value = "all")]
        class: String,
    },
    /// Run over a geoparquet-testing checkout (data/ and bad_data/)
    Corpus {
        dir: PathBuf,
        #[arg(long)]
        verbose: bool,
    },
}

fn print_text(r: &Report, class: &str) {
    println!("{}", r.file);
    for c in ["core", "covering", "distribution"] {
        if class != "all" && class != c {
            continue;
        }
        let (mut p, mut f, mut s) = (0, 0, 0);
        for o in r.outcomes.iter().filter(|o| o.class() == c) {
            let tag = match o.status {
                Status::Pass => {
                    p += 1;
                    "PASS"
                }
                Status::Fail => {
                    f += 1;
                    "FAIL"
                }
                Status::Skip => {
                    s += 1;
                    "skip"
                }
            };
            if o.message.is_empty() {
                println!("  {tag}  {}", o.id);
            } else {
                println!("  {tag}  {}  -- {}", o.id, o.message);
            }
        }
        let verdict = if f > 0 {
            "NOT CONFORMANT"
        } else if p == 0 {
            "not claimed"
        } else {
            "conformant"
        };
        println!("  => {c}: {p} pass, {f} fail, {s} skipped: {verdict}");
    }
}

fn main() -> Result<()> {
    let cli = Cli::parse();
    let schemas = checks::Schemas::load()?;
    match cli.cmd {
        Cmd::Check { file, json, class } => {
            let r = checks::run(&file, &schemas);
            if json {
                println!("{}", serde_json::to_string_pretty(&r)?);
            } else {
                print_text(&r, &class);
            }
            if r.outcomes
                .iter()
                .any(|o| o.status == Status::Fail && (class == "all" || o.class() == class))
            {
                std::process::exit(1);
            }
        }
        Cmd::Corpus { dir, verbose } => corpus::run(&dir, &schemas, verbose)?,
    }
    Ok(())
}
