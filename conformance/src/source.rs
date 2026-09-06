//! Where a file comes from: a local path, an in-memory buffer, or an object read with range
//! requests behind a small cache (object stores with the `remote` feature; a JavaScript fetch
//! callback in the browser build).

use std::io::Read;
use std::path::PathBuf;
use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::{Arc, Mutex};

use anyhow::{Context, Result};
use bytes::Bytes;
use parquet::errors::{ParquetError, Result as PResult};
use parquet::file::reader::{ChunkReader, Length};

pub trait Source {
    type R: ChunkReader + 'static;
    fn open(&self) -> Result<Self::R>;
    fn describe(&self) -> String;
    /// (bytes fetched, range requests made) for remote sources.
    fn traffic(&self) -> Option<(u64, u64)> {
        None
    }
    /// Byte ranges (start, length) the caller is about to read, typically whole column chunks,
    /// so a remote source can fetch each of them in one go instead of page by page.
    fn hint_ranges(&self, _ranges: Vec<(u64, u64)>) {}
}

pub struct Local(pub PathBuf);

impl Source for Local {
    type R = std::fs::File;
    fn open(&self) -> Result<std::fs::File> {
        std::fs::File::open(&self.0).with_context(|| format!("open {}", self.0.display()))
    }
    fn describe(&self) -> String {
        self.0.display().to_string()
    }
}

/// A whole file already in memory (browser uploads).
pub struct InMemory {
    pub name: String,
    pub bytes: Bytes,
}

impl Source for InMemory {
    type R = Bytes;
    fn open(&self) -> Result<Bytes> {
        Ok(self.bytes.clone())
    }
    fn describe(&self) -> String {
        self.name.clone()
    }
}

/// Fetches `[start, end)` of the object.
pub type Fetch = dyn Fn(u64, u64) -> PResult<Bytes> + Send + Sync;

const WINDOW: u64 = 8 << 20;
const WINDOWS_KEPT: usize = 4;
/// A hinted range is fetched in parts of this size.
const PART: u64 = 16 << 20;

struct Inner {
    name: String,
    len: u64,
    fetch: Box<Fetch>,
    windows: Mutex<Vec<(u64, Bytes)>>,
    hinted: Mutex<Vec<(u64, u64)>>,
    bytes: AtomicU64,
    requests: AtomicU64,
}

impl Inner {
    fn get(&self, start: u64, length: usize) -> PResult<Bytes> {
        let end = start + length as u64;
        if end > self.len {
            return Err(ParquetError::EOF(format!(
                "range {start}..{end} beyond object length {}",
                self.len
            )));
        }
        {
            let windows = self.windows.lock().unwrap();
            for (ws, b) in windows.iter() {
                if start >= *ws && end <= ws + b.len() as u64 {
                    return Ok(b.slice((start - ws) as usize..(end - ws) as usize));
                }
            }
        }
        // A request inside a hinted range (a column chunk) fetches the whole chunk, in parts of
        // PART bytes. Otherwise fetch a window of at least WINDOW bytes; near the end of the
        // object pull the tail instead, so the footer and its neighbours come in one request.
        let hinted = self
            .hinted
            .lock()
            .unwrap()
            .iter()
            .find(|(hs, hl)| start >= *hs && end <= hs + hl)
            .copied();
        let (ws, we) = match hinted {
            Some((hs, hl)) => (hs, hs + hl),
            None => {
                let want = (length as u64).max(WINDOW);
                let ws = if start + want > self.len {
                    self.len.saturating_sub(want).min(start)
                } else {
                    start
                };
                (ws, (ws + want).min(self.len))
            }
        };
        let mut buf = Vec::with_capacity((we - ws) as usize);
        let mut a = ws;
        while a < we {
            let b = (a + PART).min(we);
            buf.extend_from_slice(&(self.fetch)(a, b)?);
            self.requests.fetch_add(1, Ordering::Relaxed);
            a = b;
        }
        let data = Bytes::from(buf);
        self.bytes.fetch_add(data.len() as u64, Ordering::Relaxed);
        let out = data.slice((start - ws) as usize..(end - ws) as usize);
        let mut windows = self.windows.lock().unwrap();
        if windows.len() >= WINDOWS_KEPT {
            windows.remove(0);
        }
        windows.push((ws, data));
        Ok(out)
    }
}

/// One remote object read through range requests. Cloning shares the cache and the counters.
#[derive(Clone)]
pub struct Ranged(Arc<Inner>);

impl Ranged {
    pub fn new(name: String, len: u64, fetch: Box<Fetch>) -> Ranged {
        Ranged(Arc::new(Inner {
            name,
            len,
            fetch,
            windows: Mutex::new(Vec::new()),
            hinted: Mutex::new(Vec::new()),
            bytes: AtomicU64::new(0),
            requests: AtomicU64::new(0),
        }))
    }
}

pub struct RangedRead {
    inner: Arc<Inner>,
    pos: u64,
}

impl Read for RangedRead {
    fn read(&mut self, buf: &mut [u8]) -> std::io::Result<usize> {
        let remaining = self.inner.len.saturating_sub(self.pos);
        if remaining == 0 || buf.is_empty() {
            return Ok(0);
        }
        let n = (buf.len() as u64).min(remaining) as usize;
        let b = self.inner.get(self.pos, n).map_err(std::io::Error::other)?;
        buf[..n].copy_from_slice(&b);
        self.pos += n as u64;
        Ok(n)
    }
}

impl Length for Ranged {
    fn len(&self) -> u64 {
        self.0.len
    }
}

impl ChunkReader for Ranged {
    type T = RangedRead;
    fn get_read(&self, start: u64) -> PResult<RangedRead> {
        Ok(RangedRead {
            inner: self.0.clone(),
            pos: start,
        })
    }
    fn get_bytes(&self, start: u64, length: usize) -> PResult<Bytes> {
        self.0.get(start, length)
    }
}

impl Source for Ranged {
    type R = Ranged;
    fn open(&self) -> Result<Ranged> {
        Ok(self.clone())
    }
    fn describe(&self) -> String {
        self.0.name.clone()
    }
    fn traffic(&self) -> Option<(u64, u64)> {
        Some((
            self.0.bytes.load(Ordering::Relaxed),
            self.0.requests.load(Ordering::Relaxed),
        ))
    }
    fn hint_ranges(&self, ranges: Vec<(u64, u64)>) {
        // Column chunks of one row group are usually adjacent; merge ranges separated by less
        // than a megabyte so they come down in one request (split into PART-sized pieces).
        let mut sorted = ranges;
        sorted.sort_unstable();
        let mut merged: Vec<(u64, u64)> = Vec::with_capacity(sorted.len());
        for (s, l) in sorted {
            match merged.last_mut() {
                Some((ms, ml)) if s <= *ms + *ml + (1 << 20) => {
                    *ml = (s + l).max(*ms + *ml) - *ms;
                }
                _ => merged.push((s, l)),
            }
        }
        *self.0.hinted.lock().unwrap() = merged;
    }
}

#[cfg(feature = "remote")]
pub use remote::{RemoteOptions, is_remote, list, open_remote};

#[cfg(feature = "remote")]
mod remote {
    //! S3 / GCS / Azure / HTTP(S) objects through the `object_store` crate.
    use std::sync::Arc;

    use anyhow::{Context, Result, anyhow};
    use bytes::Bytes;
    use futures::StreamExt;
    use object_store::path::Path as ObjPath;
    use object_store::{ObjectStore, ObjectStoreExt};
    use parquet::errors::{ParquetError, Result as PResult};
    use url::Url;

    use super::Ranged;

    #[derive(Clone, Default)]
    pub struct RemoteOptions {
        pub s3_region: Option<String>,
        /// extra object_store configuration keys, e.g. ("aws_endpoint", "http://localhost:9000")
        pub extra: Vec<(String, String)>,
    }

    pub fn is_remote(target: &str) -> bool {
        matches!(
            target.split_once("://").map(|(s, _)| s),
            Some("s3" | "s3a" | "gs" | "az" | "abfs" | "abfss" | "http" | "https")
        )
    }

    fn build_store(url: &Url, opts: &RemoteOptions) -> Result<(Arc<dyn ObjectStore>, ObjPath)> {
        let mut kv: Vec<(String, String)> = Vec::new();
        match url.scheme() {
            "s3" | "s3a" => {
                if std::env::var_os("AWS_ACCESS_KEY_ID").is_none() {
                    kv.push(("aws_skip_signature".into(), "true".into()));
                }
                let region = opts
                    .s3_region
                    .clone()
                    .or_else(|| std::env::var("AWS_REGION").ok())
                    .or_else(|| std::env::var("AWS_DEFAULT_REGION").ok())
                    .unwrap_or_else(|| "us-east-1".into());
                kv.push(("aws_region".into(), region));
            }
            "gs" if std::env::var_os("GOOGLE_APPLICATION_CREDENTIALS").is_none()
                && std::env::var_os("GOOGLE_SERVICE_ACCOUNT").is_none() =>
            {
                kv.push(("google_skip_signature".into(), "true".into()));
            }
            _ => {}
        }
        kv.extend(opts.extra.iter().cloned());
        let (store, path) =
            object_store::parse_url_opts(url, kv).with_context(|| format!("open {url}"))?;
        Ok((Arc::from(store), path))
    }

    fn runtime() -> Result<tokio::runtime::Runtime> {
        Ok(tokio::runtime::Builder::new_current_thread()
            .enable_all()
            .build()?)
    }

    /// Open one object; the size comes from a HEAD request.
    pub fn open_remote(url: &Url, opts: &RemoteOptions) -> Result<Ranged> {
        let (store, path) = build_store(url, opts)?;
        let rt = runtime()?;
        let meta = rt
            .block_on(store.head(&path))
            .with_context(|| format!("HEAD {url}"))?;
        let fetch = move |a: u64, b: u64| -> PResult<Bytes> {
            rt.block_on(store.get_range(&path, a..b))
                .map_err(|e| ParquetError::External(Box::new(e)))
        };
        Ok(Ranged::new(url.to_string(), meta.size, Box::new(fetch)))
    }

    /// The `.parquet` objects under a prefix, as URLs, sorted.
    pub fn list(url: &Url, opts: &RemoteOptions) -> Result<Vec<Url>> {
        let (store, prefix) = build_store(url, opts)?;
        let rt = runtime()?;
        let metas: Vec<object_store::Result<object_store::ObjectMeta>> =
            rt.block_on(async { store.list(Some(&prefix)).collect::<Vec<_>>().await });
        let mut paths: Vec<String> = Vec::new();
        for m in metas {
            let m = m.with_context(|| format!("list {url}"))?;
            let p = m.location.to_string();
            if p.ends_with(".parquet") {
                paths.push(p);
            }
        }
        paths.sort();
        let host = url.host_str().ok_or_else(|| anyhow!("{url} has no host"))?;
        paths
            .iter()
            .map(|p| Url::parse(&format!("{}://{}/{}", url.scheme(), host, p)).map_err(Into::into))
            .collect()
    }
}
