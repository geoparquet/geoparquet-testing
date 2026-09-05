//! Minimal ISO WKB decoder: enough to know a value's type and dimension, its coordinate
//! ranges, its XY vertices and its polygon rings. Rejects EWKB.

#[derive(Clone, Copy, PartialEq, Eq, Debug)]
#[allow(clippy::upper_case_acronyms)]
pub enum Dim {
    XY,
    XYZ,
    XYM,
    XYZM,
}

impl Dim {
    fn from_code(c: u32) -> Option<Dim> {
        match c {
            0 => Some(Dim::XY),
            1 => Some(Dim::XYZ),
            2 => Some(Dim::XYM),
            3 => Some(Dim::XYZM),
            _ => None,
        }
    }
    pub fn suffix(self) -> &'static str {
        match self {
            Dim::XY => "",
            Dim::XYZ => " Z",
            Dim::XYM => " M",
            Dim::XYZM => " ZM",
        }
    }
}

pub const BASE_NAMES: [&str; 7] = [
    "Point",
    "LineString",
    "Polygon",
    "MultiPoint",
    "MultiLineString",
    "MultiPolygon",
    "GeometryCollection",
];

/// `geometry_types` string for a WKB integer code (1001 -> "Point Z").
pub fn type_name(code: u32) -> Option<String> {
    let dim = Dim::from_code(code / 1000)?;
    let base = code % 1000;
    if !(1..=7).contains(&base) {
        return None;
    }
    Some(format!(
        "{}{}",
        BASE_NAMES[(base - 1) as usize],
        dim.suffix()
    ))
}

pub struct Geom {
    pub base: u32,
    pub dim: Dim,
    /// min/max per axis x, y, z, m; None when absent or empty
    pub range: [Option<(f64, f64)>; 4],
    pub xy: Vec<(f64, f64)>,
    /// polygons -> rings -> (start index in `xy`, number of points)
    pub polygons: Vec<Vec<(usize, usize)>>,
}

impl Geom {
    pub fn type_name(&self) -> String {
        format!(
            "{}{}",
            BASE_NAMES[(self.base - 1) as usize],
            self.dim.suffix()
        )
    }
}

struct Cur<'a> {
    b: &'a [u8],
    pos: usize,
}

impl<'a> Cur<'a> {
    fn take(&mut self, n: usize) -> Result<&'a [u8], String> {
        if self.pos + n > self.b.len() {
            return Err(format!(
                "truncated WKB: need {n} bytes at offset {}, have {}",
                self.pos,
                self.b.len()
            ));
        }
        let s = &self.b[self.pos..self.pos + n];
        self.pos += n;
        Ok(s)
    }
    fn u8(&mut self) -> Result<u8, String> {
        Ok(self.take(1)?[0])
    }
    fn u32(&mut self, le: bool) -> Result<u32, String> {
        let s: [u8; 4] = self.take(4)?.try_into().unwrap();
        Ok(if le {
            u32::from_le_bytes(s)
        } else {
            u32::from_be_bytes(s)
        })
    }
    fn f64(&mut self, le: bool) -> Result<f64, String> {
        let s: [u8; 8] = self.take(8)?.try_into().unwrap();
        Ok(if le {
            f64::from_le_bytes(s)
        } else {
            f64::from_be_bytes(s)
        })
    }
}

pub fn parse(bytes: &[u8]) -> Result<Geom, String> {
    let mut cur = Cur { b: bytes, pos: 0 };
    let mut g = Geom {
        base: 0,
        dim: Dim::XY,
        range: [None; 4],
        xy: Vec::new(),
        polygons: Vec::new(),
    };
    parse_geom(&mut cur, &mut g, true, 0)?;
    if cur.pos != bytes.len() {
        return Err(format!(
            "{} trailing bytes after the geometry",
            bytes.len() - cur.pos
        ));
    }
    Ok(g)
}

fn parse_geom(cur: &mut Cur, g: &mut Geom, top: bool, depth: u32) -> Result<(), String> {
    if depth > 32 {
        return Err("geometry nesting deeper than 32".into());
    }
    let le = match cur.u8()? {
        0 => false,
        1 => true,
        b => return Err(format!("invalid byte order marker {b}")),
    };
    let t = cur.u32(le)?;
    if t & 0xE000_0000 != 0 {
        return Err(format!(
            "EWKB flag bits in type 0x{t:08x}; ISO WKB uses 1000/2000/3000 offsets"
        ));
    }
    let dim = Dim::from_code(t / 1000).ok_or_else(|| format!("unknown geometry type code {t}"))?;
    let base = t % 1000;
    if !(1..=7).contains(&base) {
        return Err(format!("unknown geometry type code {t}"));
    }
    if top {
        g.base = base;
        g.dim = dim;
    }
    match base {
        1 => read_point(cur, le, dim, g)?,
        2 => {
            let n = cur.u32(le)?;
            for _ in 0..n {
                read_point(cur, le, dim, g)?;
            }
        }
        3 => {
            let nrings = cur.u32(le)?;
            let mut rings = Vec::with_capacity(nrings as usize);
            for _ in 0..nrings {
                let npts = cur.u32(le)?;
                let start = g.xy.len();
                for _ in 0..npts {
                    read_point(cur, le, dim, g)?;
                }
                rings.push((start, g.xy.len() - start));
            }
            g.polygons.push(rings);
        }
        _ => {
            let n = cur.u32(le)?;
            for _ in 0..n {
                parse_geom(cur, g, false, depth + 1)?;
            }
        }
    }
    Ok(())
}

fn read_point(cur: &mut Cur, le: bool, dim: Dim, g: &mut Geom) -> Result<(), String> {
    let x = cur.f64(le)?;
    let y = cur.f64(le)?;
    let (z, m) = match dim {
        Dim::XY => (None, None),
        Dim::XYZ => (Some(cur.f64(le)?), None),
        Dim::XYM => (None, Some(cur.f64(le)?)),
        Dim::XYZM => {
            let z = cur.f64(le)?;
            (Some(z), Some(cur.f64(le)?))
        }
    };
    if x.is_nan() || y.is_nan() {
        return Ok(()); // POINT EMPTY
    }
    g.xy.push((x, y));
    for (i, v) in [Some(x), Some(y), z, m].into_iter().enumerate() {
        if let Some(v) = v {
            if v.is_nan() {
                continue;
            }
            g.range[i] = Some(match g.range[i] {
                None => (v, v),
                Some((lo, hi)) => (lo.min(v), hi.max(v)),
            });
        }
    }
    Ok(())
}

/// Twice the signed area of a ring; positive means counterclockwise.
pub fn signed_area2(pts: &[(f64, f64)]) -> f64 {
    pts.iter()
        .zip(pts.iter().cycle().skip(1))
        .map(|(a, b)| a.0 * b.1 - b.0 * a.1)
        .sum()
}
