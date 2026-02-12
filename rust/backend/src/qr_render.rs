use image::{ImageBuffer, Rgba};
use qrcode::QrCode;

#[derive(Clone, Copy, Debug)]
pub enum FinderInnerCorner {
    /// Only the outer corners of the outer ring are rounded.
    /// Inner hole corners remain square (matches "outer-only" requirement).
    OuterOnly,
    /// Both outer and inner corners are rounded.
    Both,
}

#[derive(Clone, Copy, Debug)]
pub struct RenderOpts {
    pub size: u32,
    pub margin: u32,
    pub os: u32,
    pub dark: [u8; 3],
    pub light: [u8; 3],
    /// 0..0.5-ish. 0 = square modules; 0.5 = circles.
    pub module_roundness: f32,
    pub finder_inner_corner: FinderInnerCorner,
    /// 0..0.5-ish. Controls rounding of the *finder outer ring* (eyes).
    pub finder_outer_roundness: f32,
}

fn is_finder_module(x: u32, y: u32, w: u32) -> bool {
    let in_tl = x < 7 && y < 7;
    let in_tr = x + 7 >= w && y < 7;
    let in_bl = x < 7 && y + 7 >= w;
    in_tl || in_tr || in_bl
}

fn carve_round_corner(
    img: &mut ImageBuffer<Rgba<u8>, Vec<u8>>,
    x0: u32,
    y0: u32,
    r: u32,
    corner: (i32, i32),
    light: Rgba<u8>,
) {
    // Carve a quarter circle of radius r in an r×r block.
    // Important: use a half-pixel centered circle to avoid jaggy/"spike" artifacts
    // on outer rounded corners when connectivity-aware merging is enabled.
    if r == 0 {
        return;
    }

    let (sx, sy) = corner;
    let r_f = r as f32;
    // Center at half-pixel for symmetry.
    let cx = r_f - 0.5;
    let cy = r_f - 0.5;
    // Slightly shrink threshold to reduce corner "nibbles" at small radii.
    let thr2 = (r_f - 0.25) * (r_f - 0.25);

    for dy in 0..r {
        for dx in 0..r {
            // Map local corner coords into the correct quadrant.
            let lx = if sx < 0 { dx as f32 } else { (r - 1 - dx) as f32 };
            let ly = if sy < 0 { dy as f32 } else { (r - 1 - dy) as f32 };

            let ddx = lx - cx;
            let ddy = ly - cy;
            if ddx * ddx + ddy * ddy >= thr2 {
                let px = x0 + dx;
                let py = y0 + dy;
                if px < img.width() && py < img.height() {
                    img.put_pixel(px, py, light);
                }
            }
        }
    }
}

fn fill_cell_blob(
    img: &mut ImageBuffer<Rgba<u8>, Vec<u8>>,
    cell_x: u32,
    cell_y: u32,
    module_px: u32,
    r: u32,
    dark: Rgba<u8>,
    light: Rgba<u8>,
    neigh_n: bool,
    neigh_s: bool,
    neigh_w: bool,
    neigh_e: bool,
) {
    // Fill full cell.
    let x0 = cell_x * module_px;
    let y0 = cell_y * module_px;
    for py in y0..(y0 + module_px) {
        for px in x0..(x0 + module_px) {
            img.put_pixel(px, py, dark);
        }
    }

    // Carve only outer corners (no adjacent module on both sides of the corner)
    // This produces fully merged shapes when modules touch.
    let should_nw = !neigh_n && !neigh_w;
    let should_ne = !neigh_n && !neigh_e;
    let should_sw = !neigh_s && !neigh_w;
    let should_se = !neigh_s && !neigh_e;

    if should_nw {
        carve_round_corner(img, x0, y0, r, (-1, -1), light);
    }
    if should_ne {
        carve_round_corner(img, x0 + module_px - r, y0, r, (1, -1), light);
    }
    if should_sw {
        carve_round_corner(img, x0, y0 + module_px - r, r, (-1, 1), light);
    }
    if should_se {
        carve_round_corner(img, x0 + module_px - r, y0 + module_px - r, r, (1, 1), light);
    }
}

fn fill_rounded_rect(
    img: &mut ImageBuffer<Rgba<u8>, Vec<u8>>,
    x0: u32,
    y0: u32,
    w: u32,
    h: u32,
    r: u32,
    color: Rgba<u8>,
) {
    // fast path
    if r == 0 {
        for y in y0..(y0 + h) {
            for x in x0..(x0 + w) {
                img.put_pixel(x, y, color);
            }
        }
        return;
    }

    let r_i = r as i32;
    let (w_i, h_i) = (w as i32, h as i32);
    for yy in 0..h_i {
        for xx in 0..w_i {
            let mut inside = true;
            // Check 4 rounded corners using circle equation.
            if xx < r_i && yy < r_i {
                let dx = xx - (r_i - 1);
                let dy = yy - (r_i - 1);
                inside = dx * dx + dy * dy <= r_i * r_i;
            } else if xx >= w_i - r_i && yy < r_i {
                let dx = xx - (w_i - r_i);
                let dy = yy - (r_i - 1);
                inside = dx * dx + dy * dy <= r_i * r_i;
            } else if xx < r_i && yy >= h_i - r_i {
                let dx = xx - (r_i - 1);
                let dy = yy - (h_i - r_i);
                inside = dx * dx + dy * dy <= r_i * r_i;
            } else if xx >= w_i - r_i && yy >= h_i - r_i {
                let dx = xx - (w_i - r_i);
                let dy = yy - (h_i - r_i);
                inside = dx * dx + dy * dy <= r_i * r_i;
            }
            if inside {
                img.put_pixel(x0 + xx as u32, y0 + yy as u32, color);
            }
        }
    }
}

fn draw_finder(
    img: &mut ImageBuffer<Rgba<u8>, Vec<u8>>,
    start_x_mod: u32,
    start_y_mod: u32,
    module_px: u32,
    outer_r: u32,
    opts: RenderOpts,
) {
    let dark = Rgba([opts.dark[0], opts.dark[1], opts.dark[2], 255]);
    let light = Rgba([opts.light[0], opts.light[1], opts.light[2], 255]);

    // Outer ring: 7x7 dark
    let x0 = start_x_mod * module_px;
    let y0 = start_y_mod * module_px;
    let outer = 7 * module_px;

    fill_rounded_rect(img, x0, y0, outer, outer, outer_r, dark);

    // Inner hole: 5x5 light
    let inner = 5 * module_px;
    let ix0 = x0 + module_px;
    let iy0 = y0 + module_px;
    let inner_r = match opts.finder_inner_corner {
        FinderInnerCorner::OuterOnly => 0,
        // Round the inner contour corners as well (makes the dark ring corners rounded).
        FinderInnerCorner::Both => outer_r,
    };
    fill_rounded_rect(img, ix0, iy0, inner, inner, inner_r, light);

    // Center: 3x3 dark
    let center = 3 * module_px;
    let cx0 = x0 + 2 * module_px;
    let cy0 = y0 + 2 * module_px;
    // Keep the center square for wallapop-style eyes (no rounding).
    fill_rounded_rect(img, cx0, cy0, center, center, 0, dark);
}

pub fn render_stylized(code: &QrCode, opts: RenderOpts) -> ImageBuffer<Rgba<u8>, Vec<u8>> {
    let width_modules = code.width() as u32;
    let total_modules = width_modules + 2 * opts.margin;

    let os = opts.os.clamp(1, 8);
    let target_os = opts.size.saturating_mul(os).max(opts.size);

    let module_px = (target_os / total_modules).max(1);
    let actual_os = total_modules * module_px;

    let light = Rgba([opts.light[0], opts.light[1], opts.light[2], 255]);
    let dark = Rgba([opts.dark[0], opts.dark[1], opts.dark[2], 255]);

    let mut img = ImageBuffer::from_pixel(actual_os, actual_os, light);

    let roundness = opts.module_roundness.clamp(0.0, 0.5);
    let r = ((module_px as f32) * roundness).round() as u32;

    // Data modules (skip finders; drawn separately)
    for y in 0..width_modules {
        for x in 0..width_modules {
            if is_finder_module(x, y, width_modules) {
                continue;
            }
            if !matches!(code[(x as usize, y as usize)], qrcode::Color::Dark) {
                continue;
            }

            // Neighbor connectivity in QR module space.
            let n = y > 0 && matches!(code[(x as usize, (y - 1) as usize)], qrcode::Color::Dark);
            let s = y + 1 < width_modules && matches!(code[(x as usize, (y + 1) as usize)], qrcode::Color::Dark);
            let w = x > 0 && matches!(code[((x - 1) as usize, y as usize)], qrcode::Color::Dark);
            let e = x + 1 < width_modules && matches!(code[((x + 1) as usize, y as usize)], qrcode::Color::Dark);

            // Margin shift.
            let cx = x + opts.margin;
            let cy = y + opts.margin;

            fill_cell_blob(&mut img, cx, cy, module_px, r, dark, light, n, s, w, e);
        }
    }

    // Finder patterns (eyes)
    // Finder (eye) rounding can be stronger than module rounding.
    // Allow up to 1.0 => radius up to 1×module_px for a more "app-like" look.
    let finder_roundness = opts.finder_outer_roundness.clamp(0.0, 1.0);
    let outer_r = ((module_px as f32) * finder_roundness).round() as u32;
    // top-left
    draw_finder(&mut img, opts.margin, opts.margin, module_px, outer_r, opts);
    // top-right
    draw_finder(
        &mut img,
        opts.margin + (width_modules - 7),
        opts.margin,
        module_px,
        outer_r,
        opts,
    );
    // bottom-left
    draw_finder(
        &mut img,
        opts.margin,
        opts.margin + (width_modules - 7),
        module_px,
        outer_r,
        opts,
    );

    img
}
