use chrono::Timelike;
use image::{DynamicImage, GenericImageView, ImageBuffer, ImageEncoder, Rgba};
use rand::Rng;
use rand_distr::{Distribution, Normal};
use rusttype::{point, Font, Scale};

use crate::{cache::FigmaCache, figma, qr, util};

use super::GenError;

const PAGE: &str = "Page 2";

const TARGET_WIDTH: u32 = 1304;
const TARGET_HEIGHT: u32 = 2838;

const QR_COLOR: &str = "#0C0C0B";

// "fixed coords" workaround from python (enabled)
const FIXED_PHOTO_X: f32 = 90.0;
const FIXED_PHOTO_Y: f32 = 542.0;
const FIXED_PHOTO_W: f32 = 240.0;
const FIXED_PHOTO_H: f32 = 240.0;

fn scale_factor() -> f32 {
    std::env::var("SCALE_FACTOR")
        .ok()
        .and_then(|s| s.parse::<f32>().ok())
        .unwrap_or(2.0)
}

fn fonts_dir() -> std::path::PathBuf {
    let project_root = std::env::var("PROJECT_ROOT").ok().unwrap_or_else(|| {
        let manifest_dir = std::path::Path::new(env!("CARGO_MANIFEST_DIR"));
        manifest_dir.join("../..").to_string_lossy().to_string()
    });
    std::path::PathBuf::from(project_root)
        .join("app")
        .join("assets")
        .join("fonts")
}

fn load_font(name: &str) -> Result<Font<'static>, GenError> {
    let bytes = std::fs::read(fonts_dir().join(name))
        .map_err(|e| GenError::Internal(format!("failed to read font {name}: {e}")))?;
    Font::try_from_vec(bytes).ok_or_else(|| GenError::Internal(format!("failed to parse font {name}")))
}

fn bbox(v: &serde_json::Value) -> Option<(f32, f32, f32, f32)> {
    let bb = v.get("absoluteBoundingBox")?;
    Some((
        bb.get("x")?.as_f64()? as f32,
        bb.get("y")?.as_f64()? as f32,
        bb.get("width")?.as_f64()? as f32,
        bb.get("height")?.as_f64()? as f32,
    ))
}

fn rel_box(node: &serde_json::Value, frame_node: &serde_json::Value) -> Result<(u32, u32, u32, u32), GenError> {
    let (x, y, w, h) = bbox(node).ok_or_else(|| GenError::Internal("missing absoluteBoundingBox".into()))?;
    let (fx, fy, _fw, _fh) = bbox(frame_node).ok_or_else(|| GenError::Internal("missing frame absoluteBoundingBox".into()))?;
    let sf = scale_factor();
    Ok((
        ((x - fx) * sf).round() as u32,
        ((y - fy) * sf).round() as u32,
        (w * sf).round() as u32,
        (h * sf).round() as u32,
    ))
}

fn hex_color(s: &str) -> Result<Rgba<u8>, GenError> {
    let s = s.trim().trim_start_matches('#');
    if s.len() != 6 {
        return Err(GenError::BadRequest(format!("invalid color: {s}")));
    }
    let b = hex::decode(s).map_err(|_| GenError::BadRequest(format!("invalid color: {s}")))?;
    Ok(Rgba([b[0], b[1], b[2], 255]))
}

fn draw_text_with_letter_spacing(
    img: &mut ImageBuffer<Rgba<u8>, Vec<u8>>,
    font: &Font<'static>,
    px: f32,
    x: i32,
    y: i32,
    color: Rgba<u8>,
    text: &str,
    letter_spacing: f32,
) {
    let scale = Scale::uniform(px);
    let v_metrics = font.v_metrics(scale);
    let mut caret_x = x as f32;
    let baseline_y = y as f32 + v_metrics.ascent;

    for ch in text.chars() {
        let glyph = font.glyph(ch).scaled(scale).positioned(point(caret_x, baseline_y));
        if let Some(bb) = glyph.pixel_bounding_box() {
            glyph.draw(|gx, gy, v| {
                let px = gx as i32 + bb.min.x;
                let py = gy as i32 + bb.min.y;
                if px < 0 || py < 0 {
                    return;
                }
                let (px, py) = (px as u32, py as u32);
                if px >= img.width() || py >= img.height() {
                    return;
                }
                let a = (v * 255.0) as u8;
                if a == 0 {
                    return;
                }
                let dst = img.get_pixel_mut(px, py);
                let sa = a as f32 / 255.0;
                let inv = 1.0 - sa;
                dst.0[0] = (color.0[0] as f32 * sa + dst.0[0] as f32 * inv) as u8;
                dst.0[1] = (color.0[1] as f32 * sa + dst.0[1] as f32 * inv) as u8;
                dst.0[2] = (color.0[2] as f32 * sa + dst.0[2] as f32 * inv) as u8;
                dst.0[3] = 255;
            });
        }
        caret_x += glyph.unpositioned().h_metrics().advance_width + letter_spacing;
    }
}

fn overlay_alpha(base: &mut ImageBuffer<Rgba<u8>, Vec<u8>>, over: &ImageBuffer<Rgba<u8>, Vec<u8>>, x: u32, y: u32) {
    for oy in 0..over.height() {
        for ox in 0..over.width() {
            let p = over.get_pixel(ox, oy);
            let a = p.0[3] as f32 / 255.0;
            if a <= 0.0 {
                continue;
            }
            let bx = x + ox;
            let by = y + oy;
            if bx >= base.width() || by >= base.height() {
                continue;
            }
            let dst = base.get_pixel_mut(bx, by);
            let inv = 1.0 - a;
            dst.0[0] = (p.0[0] as f32 * a + dst.0[0] as f32 * inv) as u8;
            dst.0[1] = (p.0[1] as f32 * a + dst.0[1] as f32 * inv) as u8;
            dst.0[2] = (p.0[2] as f32 * a + dst.0[2] as f32 * inv) as u8;
            dst.0[3] = 255;
        }
    }
}

fn rounded_rect_contains(x: i32, y: i32, w: i32, h: i32, r: i32) -> bool {
    if x >= r && x < w - r {
        return true;
    }
    if y >= r && y < h - r {
        return true;
    }
    let (cx, cy) = if x < r {
        if y < r {
            (r - 1, r - 1)
        } else {
            (r - 1, h - r)
        }
    } else if y < r {
        (w - r, r - 1)
    } else {
        (w - r, h - r)
    };
    let dx = x - cx;
    let dy = y - cy;
    dx * dx + dy * dy <= r * r
}

fn process_photo(photo_b64: &str, w: u32, h: u32, radius: u32) -> Result<Option<DynamicImage>, GenError> {
    let Some(bytes) = util::b64_decode(photo_b64) else {
        return Ok(None);
    };
    let img = image::load_from_memory(&bytes).map_err(|e| GenError::BadRequest(format!("invalid photo: {e}")))?;
    let mut img = img.to_rgba8();

    // composite any transparency on white
    for p in img.pixels_mut() {
        if p.0[3] < 255 {
            let a = p.0[3] as f32 / 255.0;
            let inv = 1.0 - a;
            p.0[0] = (p.0[0] as f32 * a + 255.0 * inv) as u8;
            p.0[1] = (p.0[1] as f32 * a + 255.0 * inv) as u8;
            p.0[2] = (p.0[2] as f32 * a + 255.0 * inv) as u8;
            p.0[3] = 255;
        }
    }

    let min_dim = img.width().min(img.height());
    let left = (img.width() - min_dim) / 2;
    let top = (img.height() - min_dim) / 2;
    let cropped = image::imageops::crop(&mut img, left, top, min_dim, min_dim).to_image();
    let resized = image::imageops::resize(&cropped, w, h, image::imageops::FilterType::Lanczos3);

    let mut out = ImageBuffer::from_pixel(w, h, Rgba([0, 0, 0, 0]));
    let r = radius as i32;
    for y in 0..h {
        for x in 0..w {
            if rounded_rect_contains(x as i32, y as i32, w as i32, h as i32, r) {
                out.put_pixel(x, y, *resized.get_pixel(x, y));
            }
        }
    }
    Ok(Some(DynamicImage::ImageRgba8(out)))
}

async fn generate_qr_png(http: &reqwest::Client, url: &str, size: u32, corner_radius: u32) -> Result<DynamicImage, GenError> {
    let payload = serde_json::json!({
        "text": url,
        "profile": "kleinanzeigen",
        "size": size,
        "margin": 2,
        "colorDark": QR_COLOR,
        "colorLight": "#FFFFFF",
        "cornerRadius": corner_radius,
    });
    let req: qr::QrRequest = serde_json::from_value(payload).map_err(|e| GenError::Internal(e.to_string()))?;
    let img = qr::build_qr_image(http, req)
        .await
        .map_err(|e| GenError::BadRequest(e.to_string()))?;
    Ok(img)
}

fn rgb_to_hsv_pil(r: u8, g: u8, b: u8) -> (u8, u8, u8) {
    // match PIL HSV: H,S,V in [0..255]
    let rf = r as f32 / 255.0;
    let gf = g as f32 / 255.0;
    let bf = b as f32 / 255.0;

    let max = rf.max(gf).max(bf);
    let min = rf.min(gf).min(bf);
    let delta = max - min;

    let mut h = 0.0f32;
    if delta > 0.0 {
        if (max - rf).abs() < 1e-6 {
            h = (gf - bf) / delta;
        } else if (max - gf).abs() < 1e-6 {
            h = 2.0 + (bf - rf) / delta;
        } else {
            h = 4.0 + (rf - gf) / delta;
        }
        h *= 60.0;
        if h < 0.0 {
            h += 360.0;
        }
    }

    let s = if max <= 0.0 { 0.0 } else { delta / max };
    let v = max;

    let hp = (h / 360.0) * 255.0;
    ((hp.round() as i32).clamp(0, 255) as u8, (s * 255.0).round() as u8, (v * 255.0).round() as u8)
}

fn hsv_pil_to_rgb(h: u8, s: u8, v: u8) -> (u8, u8, u8) {
    let hf = h as f32 / 255.0 * 360.0;
    let sf = s as f32 / 255.0;
    let vf = v as f32 / 255.0;

    if sf <= 0.0 {
        let x = (vf * 255.0).round() as u8;
        return (x, x, x);
    }

    let c = vf * sf;
    let x = c * (1.0 - ((hf / 60.0) % 2.0 - 1.0).abs());
    let m = vf - c;

    let (r1, g1, b1) = match hf {
        h if (0.0..60.0).contains(&h) => (c, x, 0.0),
        h if (60.0..120.0).contains(&h) => (x, c, 0.0),
        h if (120.0..180.0).contains(&h) => (0.0, c, x),
        h if (180.0..240.0).contains(&h) => (0.0, x, c),
        h if (240.0..300.0).contains(&h) => (x, 0.0, c),
        _ => (c, 0.0, x),
    };

    (
        ((r1 + m) * 255.0).round() as u8,
        ((g1 + m) * 255.0).round() as u8,
        ((b1 + m) * 255.0).round() as u8,
    )
}

fn apply_unique(img: &mut ImageBuffer<Rgba<u8>, Vec<u8>>) {
    let mut rng = rand::thread_rng();

    let hue_shift: i32 = rng.gen_range(-10..=10);
    let sat_mul: f32 = 1.0 + rng.gen_range(-0.15f32..=0.10f32);
    let bri_mul: f32 = 1.0 + rng.gen_range(0.0f32..=0.03f32);

    let noise_level: f32 = rng.gen_range(0.0f32..=0.025f32);
    let normal = Normal::new(0.0, (noise_level * 255.0) as f64).ok();

    for p in img.pixels_mut() {
        let (mut h, mut s, mut v) = rgb_to_hsv_pil(p.0[0], p.0[1], p.0[2]);
        h = (((h as i32) + hue_shift).rem_euclid(256)) as u8;
        s = ((s as f32 * sat_mul).round() as i32).clamp(0, 255) as u8;
        v = ((v as f32 * bri_mul).round() as i32).clamp(0, 255) as u8;
        let (mut r, mut g, mut b) = hsv_pil_to_rgb(h, s, v);

        if let Some(n) = &normal {
            let nr = n.sample(&mut rng) as i32;
            let ng = n.sample(&mut rng) as i32;
            let nb = n.sample(&mut rng) as i32;
            r = (r as i32 + nr).clamp(0, 255) as u8;
            g = (g as i32 + ng).clamp(0, 255) as u8;
            b = (b as i32 + nb).clamp(0, 255) as u8;
        }

        p.0[0] = r;
        p.0[1] = g;
        p.0[2] = b;
        p.0[3] = 255;
    }
}

pub async fn generate_kleinanzeigen(
    http: &reqwest::Client,
    title: &str,
    price: f64,
    photo_b64: Option<&str>,
    url: &str,
) -> Result<Vec<u8>, GenError> {
    let frame_name = "kleinan2";
    let service_name = "kleize"; // python cache key

    let cache = FigmaCache::new(service_name);
    let (template_json, frame_png, frame_node, used_cache) = if cache.exists() {
        let (structure, png) = cache.load()?;
        let frame_node = figma::find_node(&structure, PAGE, frame_name);
        if let Some(node) = frame_node {
            (structure, png, node, true)
        } else {
            let structure = figma::get_template_json(http).await?;
            let frame_node = figma::find_node(&structure, PAGE, frame_name)
                .ok_or_else(|| GenError::BadRequest(format!("frame not found: {frame_name}")))?;
            (structure, Vec::new(), frame_node, false)
        }
    } else {
        let structure = figma::get_template_json(http).await?;
        let frame_node = figma::find_node(&structure, PAGE, frame_name)
            .ok_or_else(|| GenError::BadRequest(format!("frame not found: {frame_name}")))?;
        (structure, Vec::new(), frame_node, false)
    };

    let frame_png = if used_cache {
        frame_png
    } else {
        let node_id = frame_node
            .get("id")
            .and_then(|v| v.as_str())
            .ok_or_else(|| GenError::Internal("frame node missing id".into()))?;
        let png = figma::export_frame_as_png(http, node_id, None).await?;
        cache.save(&template_json, &png)?;
        png
    };

    let mut frame_img = image::load_from_memory(&frame_png)
        .map_err(|e| GenError::Image(e.to_string()))?
        .to_rgba8();

    let (fw, fh) = {
        let (_, _, w, h) = bbox(&frame_node).ok_or_else(|| GenError::Internal("frame missing bbox".into()))?;
        let sf = scale_factor();
        ((w * sf).round() as u32, (h * sf).round() as u32)
    };
    if frame_img.width() != fw || frame_img.height() != fh {
        frame_img = image::imageops::resize(&frame_img, fw, fh, image::imageops::FilterType::Lanczos3);
    }

    let mut out = frame_img;

    let node = |name: &str| -> Result<serde_json::Value, GenError> {
        figma::find_node(&template_json, PAGE, name)
            .ok_or_else(|| GenError::BadRequest(format!("node not found: {name}")))
    };

    let nazv_n = node("nazv_kleinan2")?;
    let price_n = node("price_kleinan2")?;
    let time_n = node("time_kleinan2")?;
    let qr_n = figma::find_node(&template_json, PAGE, "qr_kleinan2");

    // fonts
    let sf = scale_factor();
    let rebond_med = load_font("RebondGrotesqueMedium.ttf")?;
    let rebond_semibold = load_font("RebondGrotesqueSemibold.ttf")?;
    let sfpro_semibold = load_font("SFProText-Semibold.ttf")?;

    // photo (fixed coords)
    if let Some(photo_b64) = photo_b64 {
        let pw = (FIXED_PHOTO_W * sf).round() as u32;
        let ph = (FIXED_PHOTO_H * sf).round() as u32;
        let px = (FIXED_PHOTO_X * sf).round() as u32;
        let py = (FIXED_PHOTO_Y * sf).round() as u32;
        let radius = (15.0 * sf).round() as u32;
        if let Some(photo) = process_photo(photo_b64, pw, ph, radius)? {
            overlay_alpha(&mut out, &photo.to_rgba8(), px, py);
        }
    }

    // qr
    if let Some(qr_node) = qr_n {
        let (qx, qy, qw, qh) = rel_box(&qr_node, &frame_node)?;
        let corner = (16.0 * sf).round() as u32;
        let mut qr_img = generate_qr_png(http, url, qw, corner).await?;
        if qr_img.width() != qw || qr_img.height() != qh {
            qr_img = qr_img.resize_exact(qw, qh, image::imageops::FilterType::Lanczos3);
        }
        overlay_alpha(&mut out, &qr_img.to_rgba8(), qx, qy);
    }

    let offset_y = (2.5 * sf).round() as i32;

    // title
    let (nx, ny, _nw, _nh) = rel_box(&nazv_n, &frame_node)?;
    let title_px = 42.0 * sf;
    let title_spacing = (0.02 * 42.0 * sf).round();
    draw_text_with_letter_spacing(
        &mut out,
        &rebond_med,
        title_px,
        nx as i32,
        ny as i32 + offset_y,
        hex_color("#FCFCFC")?,
        title,
        title_spacing,
    );

    // price
    let (px, py, _pw, _ph) = rel_box(&price_n, &frame_node)?;
    let total_price = price + 6.99;
    let mut price_text = format!("{:.2} €", total_price).replace('.', ",");
    price_text.push_str(" (inkl Versand. 6.99 €)");

    let price_px = 48.0 * sf;
    let price_spacing = (-0.02 * 48.0 * sf).round();
    draw_text_with_letter_spacing(
        &mut out,
        &rebond_semibold,
        price_px,
        px as i32,
        py as i32 + offset_y,
        hex_color("#D3F28D")?,
        &price_text,
        price_spacing,
    );

    // time (Berlin)
    let (tx, ty, tw, _th) = rel_box(&time_n, &frame_node)?;
    let now = chrono::Utc::now().with_timezone(&chrono_tz::Europe::Berlin);
    let time_text = format!("{:02}:{:02}", now.hour(), now.minute());
    let time_px = 54.0 * sf;
    // center align
    let time_w = {
        let scale = Scale::uniform(time_px);
        let v_metrics = sfpro_semibold.v_metrics(scale);
        let glyphs: Vec<_> = sfpro_semibold.layout(&time_text, scale, point(0.0, v_metrics.ascent)).collect();
        glyphs
            .iter()
            .filter_map(|g| g.pixel_bounding_box().map(|bb| bb.max.x as f32))
            .fold(0.0, f32::max)
    };
    let center_x = tx as f32 + tw as f32 / 2.0;
    let start_x = center_x - time_w / 2.0;
    draw_text_with_letter_spacing(
        &mut out,
        &sfpro_semibold,
        time_px,
        start_x.round() as i32,
        ty as i32 + offset_y,
        hex_color("#FFFFFF")?,
        &time_text,
        0.0,
    );

    // final resize + white background
    let mut final_rgba = DynamicImage::ImageRgba8(out)
        .resize_exact(TARGET_WIDTH, TARGET_HEIGHT, image::imageops::FilterType::Lanczos3)
        .to_rgba8();

    // unique tweaks (python "unique")
    apply_unique(&mut final_rgba);

    let mut rgb = ImageBuffer::from_pixel(TARGET_WIDTH, TARGET_HEIGHT, Rgba([255, 255, 255, 255]));
    overlay_alpha(&mut rgb, &final_rgba, 0, 0);

    let mut buf = Vec::new();
    let enc = image::codecs::png::PngEncoder::new(&mut buf);
    enc.write_image(&rgb, rgb.width(), rgb.height(), image::ExtendedColorType::Rgba8)
        .map_err(|e| GenError::Image(e.to_string()))?;
    Ok(buf)
}
