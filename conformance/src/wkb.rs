//! Minimal ISO WKB decoder: enough to know a value's type and dimension, its coordinate
//! ranges, its XY vertices and its polygon rings. Rejects EWKB, members of the wrong type or
//! dimension, and counts that the remaining bytes cannot hold. Never allocates from a count.

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
    pub fn size(self) -> usize {
        match self {
            Dim::XY => 2,
            Dim::XYZ | Dim::XYM => 3,
            Dim::XYZM => 4,
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

#[derive(Debug)]
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

const MAX_DEPTH: u32 = 1000;
const HEADER: u64 = 5; // byte order + type code

struct Cur<'a> {
    b: &'a [u8],
    pos: usize,
}

impl<'a> Cur<'a> {
    fn remaining(&self) -> u64 {
        (self.b.len() - self.pos) as u64
    }
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
    /// A count read from the file, checked against the bytes each item needs at minimum.
    fn count(&mut self, le: bool, what: &str, min_item_bytes: u64) -> Result<u32, String> {
        let n = self.u32(le)?;
        if n as u64 * min_item_bytes > self.remaining() {
            return Err(format!(
                "WKB claims {n} {what} but only {} bytes remain",
                self.remaining()
            ));
        }
        Ok(n)
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
    parse_geom(&mut cur, &mut g, None, None, 0)?;
    if cur.pos != bytes.len() {
        return Err(format!(
            "{} trailing bytes after the geometry",
            bytes.len() - cur.pos
        ));
    }
    Ok(g)
}

/// `expected`: the member base type a Multi* parent requires; `parent_dim`: the parent's dimension.
fn parse_geom(
    cur: &mut Cur,
    g: &mut Geom,
    expected: Option<u32>,
    parent_dim: Option<Dim>,
    depth: u32,
) -> Result<(), String> {
    if depth > MAX_DEPTH {
        return Err(format!(
            "geometry nesting deeper than {MAX_DEPTH}; not decoded"
        ));
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
    if let Some(e) = expected
        && base != e
    {
        return Err(format!(
            "Multi{} member is a {}",
            BASE_NAMES[(e - 1) as usize],
            BASE_NAMES[(base - 1) as usize]
        ));
    }
    if let Some(pd) = parent_dim
        && dim != pd
    {
        return Err(format!(
            "member dimension{} differs from its parent's{}",
            dim.suffix(),
            pd.suffix()
        ));
    }
    if depth == 0 {
        g.base = base;
        g.dim = dim;
    }
    let point_bytes = dim.size() as u64 * 8;
    match base {
        1 => read_point(cur, le, dim, g, true)?,
        2 => {
            let n = cur.count(le, "points", point_bytes)?;
            for _ in 0..n {
                read_point(cur, le, dim, g, false)?;
            }
        }
        3 => {
            let nrings = cur.count(le, "rings", 4)?;
            let mut rings = Vec::new();
            for _ in 0..nrings {
                let npts = cur.count(le, "ring points", point_bytes)?;
                let start = g.xy.len();
                for _ in 0..npts {
                    read_point(cur, le, dim, g, false)?;
                }
                rings.push((start, g.xy.len() - start));
            }
            g.polygons.push(rings);
        }
        _ => {
            let n = cur.count(le, "members", HEADER)?;
            let member = match base {
                4 => Some(1),
                5 => Some(2),
                6 => Some(3),
                _ => None,
            };
            for _ in 0..n {
                parse_geom(cur, g, member, Some(dim), depth + 1)?;
            }
        }
    }
    Ok(())
}

fn read_point(
    cur: &mut Cur,
    le: bool,
    dim: Dim,
    g: &mut Geom,
    standalone: bool,
) -> Result<(), String> {
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
        if standalone {
            return Ok(()); // POINT EMPTY
        }
        return Err("NaN coordinate in a LineString or Polygon vertex".into());
    }
    g.xy.push((x, y));
    for (i, v) in [Some(x), Some(y), z, m].into_iter().enumerate() {
        if let Some(v) = v
            && !v.is_nan()
        {
            g.range[i] = Some(match g.range[i] {
                None => (v, v),
                Some((lo, hi)) => (lo.min(v), hi.max(v)),
            });
        }
    }
    Ok(())
}

/// Twice the signed area of a ring, computed relative to its first vertex so that large
/// projected coordinates do not cancel; positive means counterclockwise.
pub fn signed_area2(pts: &[(f64, f64)]) -> f64 {
    let Some(&(ox, oy)) = pts.first() else {
        return 0.0;
    };
    pts.iter()
        .zip(pts.iter().cycle().skip(1))
        .map(|(a, b)| (a.0 - ox) * (b.1 - oy) - (b.0 - ox) * (a.1 - oy))
        .sum()
}

#[cfg(test)]
mod tests {
    use super::*;

    fn le(t: u32, body: &[f64]) -> Vec<u8> {
        let mut v = vec![1u8];
        v.extend(t.to_le_bytes());
        for f in body {
            v.extend(f.to_le_bytes());
        }
        v
    }

    #[test]
    fn point_and_point_z() {
        let g = parse(&le(1, &[1.0, 2.0])).unwrap();
        assert_eq!(g.type_name(), "Point");
        assert_eq!(g.range[0], Some((1.0, 1.0)));
        let g = parse(&le(1001, &[1.0, 2.0, 3.0])).unwrap();
        assert_eq!(g.type_name(), "Point Z");
        assert_eq!(g.range[2], Some((3.0, 3.0)));
        assert_eq!(type_name(3006).as_deref(), Some("MultiPolygon ZM"));
        assert_eq!(type_name(8), None);
    }

    #[test]
    fn empty_point_is_fine_but_nan_vertex_is_not() {
        let g = parse(&le(1, &[f64::NAN, f64::NAN])).unwrap();
        assert!(g.xy.is_empty());
        let mut v = vec![1u8];
        v.extend(2u32.to_le_bytes());
        v.extend(2u32.to_le_bytes());
        for f in [0.0, 0.0, f64::NAN, 1.0] {
            v.extend(f.to_le_bytes());
        }
        assert!(parse(&v).unwrap_err().contains("NaN"));
    }

    #[test]
    fn polygon_orientation_survives_large_offsets() {
        let ring = [
            (1e7, 1e7),
            (1e7 + 1e-6, 1e7),
            (1e7 + 1e-6, 1e7 + 1e-6),
            (1e7, 1e7 + 1e-6),
            (1e7, 1e7),
        ];
        assert!(signed_area2(&ring) > 0.0);
        let cw: Vec<_> = ring.iter().rev().copied().collect();
        assert!(signed_area2(&cw) < 0.0);
    }

    #[test]
    fn rejects_ewkb_truncation_trailing_and_bombs() {
        let mut ewkb = le(0x2000_0001, &[]);
        ewkb.extend(4326u32.to_le_bytes());
        assert!(parse(&ewkb).unwrap_err().contains("EWKB"));
        assert!(parse(&le(1, &[1.0])).unwrap_err().contains("truncated"));
        let mut trailing = le(1, &[1.0, 2.0]);
        trailing.push(0);
        assert!(parse(&trailing).unwrap_err().contains("trailing"));
        let mut bomb = vec![1u8];
        bomb.extend(3u32.to_le_bytes());
        bomb.extend(u32::MAX.to_le_bytes());
        assert!(parse(&bomb).unwrap_err().contains("claims"));
    }

    #[test]
    fn multi_members_must_match_type_and_dimension() {
        let mut mp = vec![1u8];
        mp.extend(6u32.to_le_bytes()); // MultiPolygon
        mp.extend(1u32.to_le_bytes());
        mp.extend(le(1, &[0.0, 0.0])); // ... containing a Point
        assert!(parse(&mp).unwrap_err().contains("member is a Point"));
        let mut mpt = vec![1u8];
        mpt.extend(4u32.to_le_bytes()); // MultiPoint XY
        mpt.extend(1u32.to_le_bytes());
        mpt.extend(le(1001, &[0.0, 0.0, 1.0])); // ... containing a Point Z
        assert!(parse(&mpt).unwrap_err().contains("dimension"));
        let mut gc = Vec::new();
        for _ in 0..40 {
            gc.push(1u8);
            gc.extend(7u32.to_le_bytes());
            gc.extend(1u32.to_le_bytes());
        }
        gc.extend(le(1, &[0.0, 0.0]));
        assert_eq!(parse(&gc).unwrap().type_name(), "GeometryCollection");
    }
}
