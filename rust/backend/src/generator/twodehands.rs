use chrono::Timelike;
use chrono_tz::Tz;
use image::{DynamicImage, GenericImageView, ImageBuffer, ImageEncoder, Rgba};
use rust_decimal::Decimal;
use rust_decimal_macros::dec;
use rusttype::{point, Font, Scale};

use crate::{cache::FigmaCache, figma, qr, util};

use super::GenError;

const PAGE: &str = "Page 2";

const TARGET_WIDTH: u32 = 1304;
const TARGET_HEIGHT: u32 = 2838;

const QR_COLOR: &str = "#11223E";
// logo is resolved locally by qr::build_qr_png via LOGO_DIR/LOGO_PATH_*

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

    // If transparency: composite on white (python behavior)
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

    // crop to square
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

async fn generate_qr_png(http: &reqwest::Client, url: &str, size: u32, corner_radius: u32, profile: &str) -> Result<DynamicImage, GenError> {
    let payload = serde_json::json!({
        "text": url,
        "profile": profile,
        "size": size,
        "margin": 2,
        "cornerRadius": corner_radius,
        "os": 1
    });
    let req: qr::QrRequest = serde_json::from_value(payload).map_err(|e| GenError::Internal(e.to_string()))?;
    let png = qr::build_qr_png(http, req).await.map_err(|e| GenError::BadRequest(e.to_string()))?;
    let img = image::load_from_memory(&png).map_err(|e| GenError::Internal(e.to_string()))?;
    Ok(img)
}

fn tz_for_service(service: &str) -> Tz {
    match service {
        // python: nl -> Amsterdam, fr -> Paris
        "2dehands" => chrono_tz::Europe::Amsterdam,
        "2ememain" => chrono_tz::Europe::Paris,
        _ => chrono_tz::Europe::Amsterdam,
    }
}

fn format_price_eur(price: f64) -> String {
    let d = Decimal::from_f64_retain(price).unwrap_or(dec!(0));
    let d = d.round_dp_with_strategy(2, rust_decimal::RoundingStrategy::MidpointAwayFromZero);
    format!("€ {:.2}", d).replace('.', ",")
}

pub async fn generate_twodehands(
    http: &reqwest::Client,
    service: &str,
    title: &str,
    price: f64,
    photo_b64: Option<&str>,
    url: &str,
) -> Result<Vec<u8>, GenError> {
    if !matches!(service, "2dehands" | "2ememain") {
        return Err(GenError::BadRequest(format!("unknown twodehands service: {service}")));
    }

    let frame_name = if service == "2dehands" { "2dehands1" } else { "2ememain1" };
    let service_name = frame_name; // python cache key

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

    // nodes
    let nazv = node(&format!("nazv_{frame_name}"))?;
    let price_n = node(&format!("price_{frame_name}"))?;
    let time_n = node(&format!("time_{frame_name}"))?;
    let foto_n = figma::find_node(&template_json, PAGE, &format!("pic_{frame_name}"));
    let qr_n = figma::find_node(&template_json, PAGE, &format!("qr_{frame_name}"));

    // fonts
    let sf = scale_factor();
    let font_reg = load_font("SFProText-Regular.ttf")?;
    let font_semi = load_font("SFProText-Semibold.ttf")?;

    let text_color = hex_color("#001836")?;

    // title
    let (nx, ny, _nw, _nh) = rel_box(&nazv, &frame_node)?;
    let title_px = 42.0 * sf;
    let title_spacing = (-0.04 * (title_px / 2.0)).round();
    draw_text_with_letter_spacing(
        &mut out,
        &font_reg,
        title_px,
        nx as i32,
        (ny as f32 + 2.5 * sf) as i32,
        text_color,
        title,
        title_spacing,
    );

    // price
    let (px, py, _pw, _ph) = rel_box(&price_n, &frame_node)?;
    let price_px = 48.0 * sf;
    let price_spacing = (-0.03 * (price_px / 2.0)).round();
    let price_text = format_price_eur(price);
    draw_text_with_letter_spacing(
        &mut out,
        &font_semi,
        price_px,
        px as i32,
        (py as f32 + 2.5 * sf) as i32,
        text_color,
        &price_text,
        price_spacing,
    );

    // time center
    let (tx, ty, tw, _th) = rel_box(&time_n, &frame_node)?;
    let tz = tz_for_service(service);
    let now = chrono::Utc::now().with_timezone(&tz);
    let time_text = format!("{:02}:{:02}", now.hour(), now.minute());
    let time_px = 54.0 * sf;
    let time_w = text_width(&font_semi, time_px, &time_text, 0.0);
    let center_x = tx as f32 + tw as f32 / 2.0;
    let start_x = center_x - time_w / 2.0;
    draw_text_with_letter_spacing(
        &mut out,
        &font_semi,
        time_px,
        start_x.round() as i32,
        (ty as f32 + 2.5 * sf) as i32,
        hex_color("#FFFFFF")?,
        &time_text,
        0.0,
    );

    // photo
    if let (Some(photo_b64), Some(pic_node)) = (photo_b64, foto_n) {
        let (ix, iy, iw, ih) = rel_box(&pic_node, &frame_node)?;
        let radius = (15.0 * sf).round() as u32;
        if let Some(photo) = process_photo(photo_b64, iw, ih, radius)? {
            overlay_alpha(&mut out, &photo.to_rgba8(), ix, iy);
        }
    }

    // qr
    if let Some(qr_node) = qr_n {
        let (qx, qy, qw, qh) = rel_box(&qr_node, &frame_node)?;
        let corner = (16.0 * sf).round() as u32;
        let mut qr_img = generate_qr_png(http, url, qw, corner, service).await?;
        if qr_img.width() != qw || qr_img.height() != qh {
            qr_img = qr_img.resize_exact(qw, qh, image::imageops::FilterType::Lanczos3);
        }
        overlay_alpha(&mut out, &qr_img.to_rgba8(), qx, qy);
    }

    // final resize + white background
    let out_img = DynamicImage::ImageRgba8(out)
        .resize_exact(TARGET_WIDTH, TARGET_HEIGHT, image::imageops::FilterType::Lanczos3)
        .to_rgba8();
    let mut rgb = ImageBuffer::from_pixel(TARGET_WIDTH, TARGET_HEIGHT, Rgba([255, 255, 255, 255]));
    overlay_alpha(&mut rgb, &out_img, 0, 0);

    let mut buf = Vec::new();
    let enc = image::codecs::png::PngEncoder::new(&mut buf);
    enc.write_image(&rgb, rgb.width(), rgb.height(), image::ExtendedColorType::Rgba8)
        .map_err(|e| GenError::Image(e.to_string()))?;
    Ok(buf)
}
