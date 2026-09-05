//! Spatial-order metric of /conf/distribution/spatial-order: skip rate over sample windows,
//! relative to an ideal tiling of the extent into the same number of row groups. Parameters
//! follow `gpio check spatial` (geoparquet-io PR #774): 20 windows spanning 10 % of each
//! dimension, seed 42, pass at 0.70 of the ideal, verdict withheld below five row groups. The
//! window sequence itself differs from gpio's (different random generator), so verdicts near
//! the threshold can differ between the two tools.

pub const WINDOWS: usize = 20;
pub const WINDOW_FRACTION: f64 = 0.10; // window side as a fraction of the extent side
pub const SEED: u64 = 42;
pub const PASS_RATIO: f64 = 0.70;
/// Below this many row groups an ideal grid is a poor model of what a sort can achieve; the
/// numbers are reported but no verdict is given (gpio #774 does the same).
pub const MIN_ROW_GROUPS: usize = 5;

pub struct Metric {
    pub row_groups: usize,
    pub file_skip: f64,
    pub ideal_skip: f64,
    pub ratio: f64,
    /// sum of row-group bbox areas (lengths, for a one-dimensional extent) over the extent
    pub area_factor: f64,
}

fn intersects(a: &[f64; 4], b: &[f64; 4]) -> bool {
    !(a[2] < b[0] || b[2] < a[0] || a[3] < b[1] || b[3] < a[1])
}

fn skip_rate(boxes: &[[f64; 4]], windows: &[[f64; 4]]) -> f64 {
    windows
        .iter()
        .map(|w| boxes.iter().filter(|b| !intersects(b, w)).count() as f64 / boxes.len() as f64)
        .sum::<f64>()
        / windows.len() as f64
}

/// Exactly `n` tiles covering the extent: a grid of `cols` columns; the last row holds the
/// remainder, stretched across the full width.
fn ideal_tiling(ext: &[f64; 4], n: usize) -> Vec<[f64; 4]> {
    let (w, h) = (ext[2] - ext[0], ext[3] - ext[1]);
    if h == 0.0 || w == 0.0 {
        // one-dimensional extent: n equal strips along the non-degenerate axis
        return (0..n)
            .map(|i| {
                let (a, b) = (i as f64 / n as f64, (i + 1) as f64 / n as f64);
                if h == 0.0 {
                    [ext[0] + a * w, ext[1], ext[0] + b * w, ext[3]]
                } else {
                    [ext[0], ext[1] + a * h, ext[2], ext[1] + b * h]
                }
            })
            .collect();
    }
    let cols = (n as f64).sqrt().ceil() as usize;
    let full_rows = n / cols;
    let rest = n % cols;
    let rows = full_rows + usize::from(rest > 0);
    let rh = h / rows as f64;
    let mut tiles = Vec::with_capacity(n);
    for r in 0..rows {
        let ncols = if r < full_rows { cols } else { rest };
        let cw = w / ncols as f64;
        for c in 0..ncols {
            let (x0, y0) = (ext[0] + c as f64 * cw, ext[1] + r as f64 * rh);
            tiles.push([x0, y0, x0 + cw, y0 + rh]);
        }
    }
    tiles
}

/// `boxes` are the row-group statistics bounding boxes [xmin, ymin, xmax, ymax]; a box with
/// xmin > xmax wraps the antimeridian and is split in two for the measurement.
pub fn measure(boxes: &[[f64; 4]]) -> Result<Metric, String> {
    let n = boxes.len();
    if n < 2 {
        return Err(format!("{n} row group(s): pruning cannot be measured"));
    }
    if n < MIN_ROW_GROUPS {
        return Err(format!(
            "{n} row groups: verdict withheld below {MIN_ROW_GROUPS} (an ideal grid is a poor model for so few; see geoparquet-io #774)"
        ));
    }
    if let Some(i) = boxes.iter().position(|b| b.iter().any(|v| !v.is_finite())) {
        return Err(format!(
            "row group {i} has non-finite geospatial statistics"
        ));
    }
    let mut parts: Vec<[f64; 4]> = Vec::with_capacity(n);
    for b in boxes {
        if b[0] > b[2] {
            parts.push([b[0], b[1], 180.0, b[3]]);
            parts.push([-180.0, b[1], b[2], b[3]]);
        } else {
            parts.push(*b);
        }
    }
    let ext = parts
        .iter()
        .fold([f64::MAX, f64::MAX, f64::MIN, f64::MIN], |e, b| {
            [
                e[0].min(b[0]),
                e[1].min(b[1]),
                e[2].max(b[2]),
                e[3].max(b[3]),
            ]
        });
    let (w, h) = (ext[2] - ext[0], ext[3] - ext[1]);
    if w == 0.0 && h == 0.0 {
        return Err("all row groups share a single point; there is nothing to prune".into());
    }
    let mut state = SEED;
    let mut rnd = || {
        state = state
            .wrapping_mul(6364136223846793005)
            .wrapping_add(1442695040888963407);
        (state >> 11) as f64 / (1u64 << 53) as f64
    };
    let (ww, wh) = (w * WINDOW_FRACTION, h * WINDOW_FRACTION);
    let windows: Vec<[f64; 4]> = (0..WINDOWS)
        .map(|_| {
            let x0 = ext[0] + rnd() * (w - ww);
            let y0 = ext[1] + rnd() * (h - wh);
            [x0, y0, x0 + ww, y0 + wh]
        })
        .collect();
    let ideal = ideal_tiling(&ext, n);
    let file_skip = skip_rate(&parts, &windows);
    let ideal_skip = skip_rate(&ideal, &windows);
    let measure = |b: &[f64; 4]| {
        if w == 0.0 {
            b[3] - b[1]
        } else if h == 0.0 {
            b[2] - b[0]
        } else {
            (b[2] - b[0]) * (b[3] - b[1])
        }
    };
    let extent = if w == 0.0 {
        h
    } else if h == 0.0 {
        w
    } else {
        w * h
    };
    Ok(Metric {
        row_groups: n,
        file_skip,
        ideal_skip,
        ratio: if ideal_skip > 0.0 {
            file_skip / ideal_skip
        } else {
            1.0
        },
        area_factor: parts.iter().map(measure).sum::<f64>() / extent,
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    fn grid(side: usize) -> Vec<[f64; 4]> {
        (0..side * side)
            .map(|i| {
                let (c, r) = ((i % side) as f64, (i / side) as f64);
                [c, r, c + 1.0, r + 1.0]
            })
            .collect()
    }

    #[test]
    fn perfect_grids_score_one_and_strips_score_high() {
        for side in [3usize, 4, 5] {
            let m = measure(&grid(side)).unwrap();
            assert!(
                (m.ratio - 1.0).abs() < 1e-9,
                "n={} ratio={}",
                side * side,
                m.ratio
            );
            assert!((m.area_factor - 1.0).abs() < 1e-9);
        }
        // equal strips are a tiling too, but a grid prunes square windows better: high, not 1.0
        let strips: Vec<[f64; 4]> = (0..6)
            .map(|i| [i as f64, 0.0, i as f64 + 1.0, 1.0])
            .collect();
        let m = measure(&strips).unwrap();
        assert!(m.ratio > 0.75 && m.ratio <= 1.0, "ratio={}", m.ratio);
    }

    #[test]
    fn tiling_has_exactly_n_tiles_and_covers_the_extent() {
        for n in 2..40 {
            let t = ideal_tiling(&[0.0, 0.0, 4.0, 2.0], n);
            assert_eq!(t.len(), n);
            let area: f64 = t.iter().map(|b| (b[2] - b[0]) * (b[3] - b[1])).sum();
            assert!((area - 8.0).abs() < 1e-9, "n={n}");
        }
    }

    #[test]
    fn identical_boxes_fail_and_bad_input_is_rejected() {
        assert!(measure(&vec![[0.0, 0.0, 1.0, 1.0]; 6]).unwrap().ratio < 0.01);
        let mut inf = grid(3);
        inf[4][2] = f64::INFINITY;
        assert!(measure(&inf).unwrap_err().contains("non-finite"));
        assert!(
            measure(&vec![[0.0, 0.0, 0.0, 0.0]; 6])
                .unwrap_err()
                .contains("single point")
        );
        assert!(measure(&grid(2)).unwrap_err().contains("withheld"));
        assert!(
            measure(&[[0.0, 0.0, 1.0, 1.0]])
                .unwrap_err()
                .contains("cannot be measured")
        );
        // one-dimensional extent still measurable
        let strips: Vec<[f64; 4]> = (0..6)
            .map(|i| [0.0, i as f64, 0.0, i as f64 + 1.0])
            .collect();
        assert!(measure(&strips).unwrap().ratio > 0.99);
    }
}
