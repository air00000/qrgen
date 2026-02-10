use chrono::{Datelike, Timelike};
use image::{DynamicImage, ImageBuffer, ImageEncoder, Rgba};
use rand::Rng;
use rand_distr::{Distribution, Normal};
use rusttype::{point, Font, Scale};

use crate::{cache::FigmaCache, figma};

use super::GenError;

const PAGE: &str = "Page 2";

const TARGET_WIDTH: u32 = 1304;
const TARGET_HEIGHT: u32 = 2838;

const MAX_TEXT_WIDTH: f32 = 1085.0;

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

fn text_width(font: &Font<'static>, px: f32, text: &str, letter_spacing: f32) -> f32 {
    if text.is_empty() {
        return 0.0;
    }
    let scale = Scale::uniform(px);
    let v_metrics = font.v_metrics(scale);
    let glyphs: Vec<_> = font.layout(text, scale, point(0.0, v_metrics.ascent)).collect();
    let mut width: f32 = 0.0;
    for (i, g) in glyphs.iter().enumerate() {
        if let Some(bb) = g.pixel_bounding_box() {
            width = width.max(bb.max.x as f32);
        }
        if i + 1 < glyphs.len() {
            width += letter_spacing;
        }
    }
    width
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

fn wrap_text(text: &str, font: &Font<'static>, px: f32, max_width: f32, spacing: f32) -> Vec<String> {
    let mut lines = Vec::new();
    let mut current: Vec<&str> = Vec::new();

    for word in text.split_whitespace() {
        let mut test = current.clone();
        test.push(word);
        let test_line = test.join(" ");
        let w = text_width(font, px, &test_line, spacing);
        if w <= max_width {
            current.push(word);
        } else {
            if !current.is_empty() {
                lines.push(current.join(" "));
            }
            current = vec![word];
        }
    }
    if !current.is_empty() {
        lines.push(current.join(" "));
    }
    lines
}

fn italian_date() -> String {
    let now = chrono::Utc::now().with_timezone(&chrono_tz::Europe::Rome);
    let months = [
        "Gen", "Feb", "Mar", "Apr", "Mag", "Giu", "Lug", "Ago", "Set", "Ott", "Nov", "Dic",
    ];
    let m = months[(now.month0()) as usize];
    format!("{} {} {}", now.day(), m, now.year())
}

fn apply_unique(img: &mut ImageBuffer<Rgba<u8>, Vec<u8>>) {
    let mut rng = rand::thread_rng();
    let hue_shift: i32 = rng.gen_range(-10..=10);
    let sat_mul: f32 = 1.0 + rng.gen_range(-0.15f32..=0.10f32);
    let bri_mul: f32 = 1.0 + rng.gen_range(0.0f32..=0.03f32);
    let noise_level: f32 = rng.gen_range(0.0f32..=0.025f32);
    let normal = Normal::new(0.0, (noise_level * 255.0) as f64).ok();

    // fast-ish RGB->HSV and back in PIL scale
    fn rgb_to_hsv_pil(r: u8, g: u8, b: u8) -> (u8, u8, u8) {
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

    let mut rng2 = rand::thread_rng();
    for p in img.pixels_mut() {
        let (mut h, mut s, mut v) = rgb_to_hsv_pil(p.0[0], p.0[1], p.0[2]);
        h = (((h as i32) + hue_shift).rem_euclid(256)) as u8;
        s = ((s as f32 * sat_mul).round() as i32).clamp(0, 255) as u8;
        v = ((v as f32 * bri_mul).round() as i32).clamp(0, 255) as u8;
        let (mut r, mut g, mut b) = hsv_pil_to_rgb(h, s, v);
        if let Some(n) = &normal {
            r = (r as i32 + n.sample(&mut rng2) as i32).clamp(0, 255) as u8;
            g = (g as i32 + n.sample(&mut rng2) as i32).clamp(0, 255) as u8;
            b = (b as i32 + n.sample(&mut rng2) as i32).clamp(0, 255) as u8;
        }
        p.0[0] = r;
        p.0[1] = g;
        p.0[2] = b;
        p.0[3] = 255;
    }
}

pub async fn generate_conto(
    http: &reqwest::Client,
    title: &str,
    price: f64,
) -> Result<Vec<u8>, GenError> {
    let sf = scale_factor();

    // determine frame by wrapped text lines
    let full_text = format!(
        "Pagamento per il prodotto \"{}\" tramite transazione sicura Subito",
        title
    );

    let title_font = load_font("SFProText-Semibold.ttf")?;
    let title_px = 50.0 * sf;
    let title_spacing = (-0.005 * 50.0 * sf).round();
    let lines = wrap_text(&full_text, &title_font, title_px, MAX_TEXT_WIDTH * sf, title_spacing);
    let frame_name = if lines.len() <= 2 { "conto1_short" } else { "conto1_long" };
    let service_name = format!("conto_{frame_name}"); // python cache key

    let cache = FigmaCache::new(&service_name);
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

    // ensure scaled
    let (fw, fh) = {
        let (_, _, w, h) = bbox(&frame_node).ok_or_else(|| GenError::Internal("frame missing bbox".into()))?;
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

    let tovar = node(&format!("tovar{frame_name}"))?;
    let price_n = node(&format!("price{frame_name}"))?;
    let time_n = node(&format!("time{frame_name}"))?;
    let date_n = node(&format!("data{frame_name}"))?;

    // other fonts
    let f_time = load_font("SFProText-Semibold.ttf")?;
    let f_date = load_font("SFProText-Regular.ttf")?;
    let f_int = load_font("Inter-SemiBold.ttf")?;
    let f_dec = load_font("Inter-SemiBold.ttf")?;

    let offset_y = (2.5 * sf).round() as i32;

    // multi-line title
    let (nx, ny, _nw, _nh) = rel_box(&tovar, &frame_node)?;
    let line_h = (62.0 * sf).round() as i32;
    for (i, line) in lines.iter().enumerate() {
        draw_text_with_letter_spacing(
            &mut out,
            &title_font,
            title_px,
            nx as i32,
            ny as i32 + offset_y + (i as i32) * line_h,
            hex_color("#000000")?,
            line,
            title_spacing,
        );
    }

    // price with raised decimals
    let (px, py, _pw, _ph) = rel_box(&price_n, &frame_node)?;
    let mut price_str = format!("-{:.2} €", price).replace('.', ",");
    // python had a quirky replace for ",-"; keep simple
    if let Some((int_part, dec_part)) = price_str.split_once(',') {
        let integer_part = int_part.to_string();
        let decimal_part = format!(",{}", dec_part);

        let int_px = 100.0 * sf;
        let dec_px = 55.0 * sf;

        // draw integer
        draw_text_with_letter_spacing(
            &mut out,
            &f_int,
            int_px,
            px as i32,
            py as i32 + offset_y,
            hex_color("#000000")?,
            &integer_part,
            0.0,
        );

        // measure integer width
        let int_w = text_width(&f_int, int_px, &integer_part, 0.0);

        // descent-ish adjustment
        let big_vm = f_int.v_metrics(Scale::uniform(int_px));
        let small_vm = f_dec.v_metrics(Scale::uniform(dec_px));
        let big_descent = -big_vm.descent;
        let small_descent = -small_vm.descent;

        let dec_x = px as f32 + int_w;
        let dec_y = (py as f32 + offset_y as f32 + (big_descent - small_descent) - (10.0 * sf)).round() as i32;

        draw_text_with_letter_spacing(
            &mut out,
            &f_dec,
            dec_px,
            dec_x.round() as i32,
            dec_y,
            hex_color("#000000")?,
            &decimal_part,
            0.0,
        );
    } else {
        // fallback
        draw_text_with_letter_spacing(
            &mut out,
            &f_int,
            100.0 * sf,
            px as i32,
            py as i32 + offset_y,
            hex_color("#000000")?,
            &price_str,
            0.0,
        );
    }

    // time (Rome), centered
    let (tx, ty, tw, _th) = rel_box(&time_n, &frame_node)?;
    let now = chrono::Utc::now().with_timezone(&chrono_tz::Europe::Rome);
    let time_text = format!("{:02}:{:02}", now.hour(), now.minute());
    let time_px = 54.0 * sf;
    let time_spacing = (-0.03 * 54.0 * sf).round();
    let time_w = text_width(&f_time, time_px, &time_text, time_spacing);
    let center_x = tx as f32 + tw as f32 / 2.0;
    let start_x = center_x - time_w / 2.0;
    draw_text_with_letter_spacing(
        &mut out,
        &f_time,
        time_px,
        start_x.round() as i32,
        ty as i32 + offset_y,
        hex_color("#000000")?,
        &time_text,
        time_spacing,
    );

    // date
    let (dx, dy, _dw, _dh) = rel_box(&date_n, &frame_node)?;
    let date_px = 50.0 * sf;
    let date_spacing = (-0.005 * 50.0 * sf).round();
    draw_text_with_letter_spacing(
        &mut out,
        &f_date,
        date_px,
        dx as i32,
        dy as i32 + offset_y,
        hex_color("#000000")?,
        &italian_date(),
        date_spacing,
    );

    // final resize
    let mut final_rgba = DynamicImage::ImageRgba8(out)
        .resize_exact(TARGET_WIDTH, TARGET_HEIGHT, image::imageops::FilterType::Lanczos3)
        .to_rgba8();

    // python converts to RGB and then applies unique; do on RGBA but keep opaque
    apply_unique(&mut final_rgba);

    let mut rgb = ImageBuffer::from_pixel(TARGET_WIDTH, TARGET_HEIGHT, Rgba([255, 255, 255, 255]));
    overlay_alpha(&mut rgb, &final_rgba, 0, 0);

    let mut buf = Vec::new();
    let enc = image::codecs::png::PngEncoder::new(&mut buf);
    enc.write_image(&rgb, rgb.width(), rgb.height(), image::ExtendedColorType::Rgba8)
        .map_err(|e| GenError::Image(e.to_string()))?;
    Ok(buf)
}
