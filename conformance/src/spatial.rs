//! Spatial-order metric of /conf/distribution/spatial-order: skip rate over sample windows,
//! relative to an ideal grid tiling with the same number of row groups. Parameters are the
//! test suite's, fixed here so the result is reproducible.

pub const WINDOWS: usize = 20;
pub const WINDOW_FRACTION: f64 = 0.10; // window side as a fraction of the extent side
pub const SEED: u64 = 20_260_905;
pub const PASS_RATIO: f64 = 0.70;

pub struct Metric {
    pub row_groups: usize,
    pub file_skip: f64,
    pub ideal_skip: f64,
    pub ratio: f64,
    /// sum of row-group bbox areas over the extent area; 1.0 is a perfect tiling
    pub area_factor: f64,
}

fn intersects(a: &[f64; 4], b: &[f64; 4]) -> bool {
    !(a[2] < b[0] || b[2] < a[0] || a[3] < b[1] || b[3] < a[1])
}

fn skip_rate(boxes: &[[f64; 4]], windows: &[[f64; 4]]) -> f64 {
    let mut total = 0.0;
    for w in windows {
        let skipped = boxes.iter().filter(|b| !intersects(b, w)).count();
        total += skipped as f64 / boxes.len() as f64;
    }
    total / windows.len() as f64
}

pub fn measure(boxes: &[[f64; 4]]) -> Option<Metric> {
    if boxes.len() < 2 {
        return None;
    }
    let ext = boxes
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
    if !(w > 0.0 && h > 0.0) {
        return None;
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
    let n = boxes.len();
    let cols = (n as f64).sqrt().ceil() as usize;
    let rows = n.div_ceil(cols);
    let (cw, ch) = (w / cols as f64, h / rows as f64);
    let mut ideal = Vec::with_capacity(cols * rows);
    for r in 0..rows {
        for c in 0..cols {
            let x0 = ext[0] + c as f64 * cw;
            let y0 = ext[1] + r as f64 * ch;
            ideal.push([x0, y0, x0 + cw, y0 + ch]);
        }
    }
    let file_skip = skip_rate(boxes, &windows);
    let ideal_skip = skip_rate(&ideal, &windows);
    let area_factor = boxes
        .iter()
        .map(|b| (b[2] - b[0]) * (b[3] - b[1]))
        .sum::<f64>()
        / (w * h);
    Some(Metric {
        row_groups: n,
        file_skip,
        ideal_skip,
        ratio: if ideal_skip > 0.0 {
            file_skip / ideal_skip
        } else {
            1.0
        },
        area_factor,
    })
}
