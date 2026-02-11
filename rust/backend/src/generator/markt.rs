use std::io::Cursor;

use chrono::Timelike;
use chrono_tz::Tz;
use image::{DynamicImage, GenericImage, GenericImageView, ImageBuffer, ImageEncoder, Rgba};
use rust_decimal::Decimal;
use rust_decimal_macros::dec;
use rusttype::{point, Font, Scale};

use crate::{cache::FigmaCache, figma, qr, util};

use super::GenError;

const PAGE: &str = "Page 2";

// qr logo from python implementation
const QR_LOGO_URL: &str = "https://i.ibb.co/DfXf3X7x/Frame-40.png";

const DELIVERY_FEE: Decimal = dec!(6.25);
const SERVICE_FEE: Decimal = dec!(0.40);
const PROTECTION_RATE: Decimal = dec!(0.05);

#[derive(Clone, Copy, Debug)]
enum Variant {
    Qr,
    EmailRequest,
    PhoneRequest,
    EmailPayment,
    SmsPayment,
}

impl Variant {
    fn parse(s: &str) -> Option<Self> {
        Some(match s {
            "qr" => Variant::Qr,
            "email_request" => Variant::EmailRequest,
            "phone_request" => Variant::PhoneRequest,
            "email_payment" => Variant::EmailPayment,
            "sms_payment" => Variant::SmsPayment,
            _ => return None,
        })
    }

    fn frame_index(self) -> u8 {
        match self {
            Variant::Qr => 1,
            Variant::EmailRequest => 2,
            Variant::PhoneRequest => 3,
            Variant::EmailPayment => 4,
            Variant::SmsPayment => 5,
        }
    }

    fn has_qr(self) -> bool {
        matches!(self, Variant::Qr)
    }

    fn label(self) -> &'static str {
        match self {
            Variant::Qr => "QR",
            Variant::EmailRequest => "Email запрос",
            Variant::PhoneRequest => "Телефон запрос",
            Variant::EmailPayment => "Email оплата",
            Variant::SmsPayment => "SMS оплата",
        }
    }
}

fn tz_for_lang(lang: &str) -> Tz {
    match lang {
        "uk" => chrono_tz::Europe::London,
        "nl" => chrono_tz::Europe::Amsterdam,
        _ => chrono_tz::Europe::Amsterdam,
    }
}

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
    std::path::PathBuf::from(project_root).join("app").join("assets").join("fonts")
}

fn load_font(name: &str) -> Result<Font<'static>, GenError> {
    let bytes = std::fs::read(fonts_dir().join(name))
        .map_err(|e| GenError::Internal(format!("failed to read font {name}: {e}")))?;
    let f = Font::try_from_vec(bytes).ok_or_else(|| GenError::Internal(format!("failed to parse font {name}")))?;
    Ok(f)
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

fn format_price_eur(price: f64) -> String {
    // match python: € 12,34
    let d = Decimal::from_f64_retain(price).unwrap_or(dec!(0));
    let d = d.round_dp_with_strategy(2, rust_decimal::RoundingStrategy::MidpointAwayFromZero);
    format!("€ {:.2}", d).replace('.', ",")
}

fn calc_protection_fee(price: f64) -> Decimal {
    let d = Decimal::from_f64_retain(price).unwrap_or(dec!(0));
    (d * PROTECTION_RATE).round_dp_with_strategy(2, rust_decimal::RoundingStrategy::MidpointAwayFromZero)
}

fn calc_total_price(price: f64) -> Decimal {
    let d = Decimal::from_f64_retain(price).unwrap_or(dec!(0));
    let protection = calc_protection_fee(price);
    (d + protection + DELIVERY_FEE + SERVICE_FEE).round_dp_with_strategy(2, rust_decimal::RoundingStrategy::MidpointAwayFromZero)
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
            let w = bb.width() as f32;
            // This is not perfect but close enough for truncation logic.
            width = width.max((bb.max.x) as f32);
            if i + 1 < glyphs.len() {
                width += letter_spacing;
            }
        }
    }
    width
}

fn truncate_title(font: &Font<'static>, px: f32, text: &str, letter_spacing: f32, max_width: f32) -> String {
    if text_width(font, px, text, letter_spacing) <= max_width {
        return text.to_string();
    }
    let ellipsis = "...";
    let mut trimmed = text.to_string();
    while !trimmed.is_empty() && text_width(font, px, &(trimmed.clone() + ellipsis), letter_spacing) > max_width {
        trimmed.pop();
    }
    if trimmed.is_empty() {
        ellipsis.to_string()
    } else {
        trimmed + ellipsis
    }
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
    // y is top-left in python; rusttype uses baseline.
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
                // alpha blend: src over dst
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

fn rounded_rect_from_b64(photo_b64: &str, w: u32, h: u32, radius: u32) -> Result<Option<DynamicImage>, GenError> {
    let Some(bytes) = util::b64_decode(photo_b64) else {
        return Ok(None);
    };
    let img = image::load_from_memory(&bytes).map_err(|e| GenError::BadRequest(format!("invalid photo: {e}")))?;
    let mut img = img.to_rgba8();
    // crop to square
    let min_dim = img.width().min(img.height());
    let left = (img.width() - min_dim) / 2;
    let top = (img.height() - min_dim) / 2;
    let cropped = image::imageops::crop(&mut img, left, top, min_dim, min_dim).to_image();
    let resized = image::imageops::resize(&cropped, w, h, image::imageops::FilterType::Lanczos3);

    // rounded mask
    let mut out = ImageBuffer::from_pixel(w, h, Rgba([0, 0, 0, 0]));
    for y in 0..h {
        for x in 0..w {
            let inside = rounded_rect_contains(x as i32, y as i32, w as i32, h as i32, radius as i32);
            if inside {
                out.put_pixel(x, y, *resized.get_pixel(x, y));
            }
        }
    }
    Ok(Some(DynamicImage::ImageRgba8(out)))
}

fn rounded_rect_contains(x: i32, y: i32, w: i32, h: i32, r: i32) -> bool {
    // inside central rect
    if x >= r && x < w - r {
        return true;
    }
    if y >= r && y < h - r {
        return true;
    }
    // corners: distance from corner center
    let (cx, cy) = if x < r {
        if y < r { (r - 1, r - 1) } else { (r - 1, h - r) }
    } else {
        if y < r { (w - r, r - 1) } else { (w - r, h - r) }
    };
    let dx = x - cx;
    let dy = y - cy;
    dx * dx + dy * dy <= r * r
}

async fn generate_qr_png(http: &reqwest::Client, url: &str) -> Result<DynamicImage, GenError> {
    let payload = serde_json::json!({
        "text": url,
        "size": 600,
        "margin": 2,
        "colorDark": "#000000",
        "colorLight": "#FFFFFF",
        "logoUrl": QR_LOGO_URL,
        "cornerRadius": 20,
    });
    // call local handler code directly to avoid HTTP
    let req: qr::QrRequest = serde_json::from_value(payload).map_err(|e| GenError::Internal(e.to_string()))?;
    let png = qr::build_qr_png(http, req).await.map_err(|e| GenError::BadRequest(e.to_string()))?;
    let img = image::load_from_memory(&png).map_err(|e| GenError::Internal(e.to_string()))?;
    Ok(img)
}

pub async fn generate_markt(
    http: &reqwest::Client,
    lang: &str,
    method: &str,
    title: &str,
    price: f64,
    photo_b64: Option<&str>,
    url: Option<&str>,
) -> Result<Vec<u8>, GenError> {
    let variant = Variant::parse(method).ok_or_else(|| GenError::BadRequest(format!("unknown markt method: {method}")))?;
    if !matches!(lang, "uk" | "nl") {
        return Err(GenError::BadRequest(format!("unknown markt language: {lang}")));
    }
    if variant.has_qr() && url.map(|s| s.trim().is_empty()).unwrap_or(true) {
        return Err(GenError::BadRequest("url is required for qr".into()));
    }

    let frame_name = format!("markt{}_{}", variant.frame_index(), lang);
    let service_name = format!("markt_{}_{}", method, lang);

    let cache = FigmaCache::new(service_name);
    let (template_json, frame_png, frame_node, used_cache) = if cache.exists() {
        let (structure, png) = cache.load()?;
        let frame_node = figma::find_node(&structure, PAGE, &frame_name);
        if let Some(node) = frame_node {
            (structure, png, node, true)
        } else {
            // fallback to API
            let structure = figma::get_template_json(http).await?;
            let frame_node = figma::find_node(&structure, PAGE, &frame_name)
                .ok_or_else(|| GenError::BadRequest(format!("frame not found: {frame_name}")))?;
            (structure, Vec::new(), frame_node, false)
        }
    } else {
        let structure = figma::get_template_json(http).await?;
        let frame_node = figma::find_node(&structure, PAGE, &frame_name)
            .ok_or_else(|| GenError::BadRequest(format!("frame not found: {frame_name}")))?;
        (structure, Vec::new(), frame_node, false)
    };

    // Get frame image
    let frame_png = if used_cache {
        frame_png
    } else {
        let node_id = frame_node.get("id").and_then(|v| v.as_str()).ok_or_else(|| GenError::Internal("frame node missing id".into()))?;
        let png = figma::export_frame_as_png(http, node_id, None).await?;
        // save cache (structure + template)
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

    let mut out = frame_img; // already RGBA

    // helper to get node by name
    let node = |name: &str| -> Result<serde_json::Value, GenError> {
        figma::find_node(&template_json, PAGE, name)
            .ok_or_else(|| GenError::BadRequest(format!("node not found: {name}")))
    };
    let node_opt = |name: &str| -> Option<serde_json::Value> { figma::find_node(&template_json, PAGE, name) };

    // fonts
    let title_font = load_font("SFProText-Regular.ttf")?;
    let price_font = load_font("SFPROTEXT-MEDIUM.TTF")?;
    let detail_font = load_font("SFProText-Regular.ttf")?;
    let time_font = load_font("SFProText-Semibold.ttf")?;

    let sf = scale_factor();

    // Title
    let title_node = node(&format!("nazv{frame_name}"))?;
    let (tx, ty, _tw, _th) = rel_box(&title_node, &frame_node)?;
    let title_px = 48.0 * sf;
    let title_spacing = title_px * -0.03;
    let max_title_width = 666.0 * sf;
    let truncated = truncate_title(&title_font, title_px, title, title_spacing, max_title_width);
    draw_text_with_letter_spacing(&mut out, &title_font, title_px, tx as i32, ty as i32, hex_color("#000000")?, &truncated, title_spacing);

    // Price
    let price_node = node(&format!("price{frame_name}"))?;
    let (px, py, pw, _ph) = rel_box(&price_node, &frame_node)?;
    let price_px = 42.0 * sf;
    let price_spacing = price_px * 0.02;
    let price_text = format_price_eur(price);
    let width = text_width(&price_font, price_px, &price_text, price_spacing);
    let start_x = (px + pw) as f32 - width;
    draw_text_with_letter_spacing(&mut out, &price_font, price_px, start_x.round() as i32, py as i32, hex_color("#000000")?, &price_text, price_spacing);

    // askprice
    if let Some(n) = node_opt(&format!("askprice{frame_name}")) {
        let (ax, ay, aw, _) = rel_box(&n, &frame_node)?;
        let detail_px = 42.0 * sf;
        let detail_spacing = detail_px * 0.01;
        let width = text_width(&detail_font, detail_px, &price_text, detail_spacing);
        let start_x = (ax + aw) as f32 - width;
        draw_text_with_letter_spacing(&mut out, &detail_font, detail_px, start_x.round() as i32, ay as i32, hex_color("#20394C")?, &price_text, detail_spacing);
    }

    // protect
    if let Some(n) = node_opt(&format!("protect{frame_name}")) {
        let (ax, ay, aw, _) = rel_box(&n, &frame_node)?;
        let detail_px = 42.0 * sf;
        let detail_spacing = detail_px * 0.01;
        let protect = calc_protection_fee(price);
        let protect_text = format!("€ {:.2}", protect).replace('.', ",");
        let width = text_width(&detail_font, detail_px, &protect_text, detail_spacing);
        let start_x = (ax + aw) as f32 - width;
        draw_text_with_letter_spacing(&mut out, &detail_font, detail_px, start_x.round() as i32, ay as i32, hex_color("#20394C")?, &protect_text, detail_spacing);
    }

    // total
    if let Some(n) = node_opt(&format!("totalprice{frame_name}")) {
        let (ax, ay, aw, _) = rel_box(&n, &frame_node)?;
        let detail_px = 42.0 * sf;
        let detail_spacing = detail_px * 0.01;
        let total = calc_total_price(price);
        let total_text = format!("€ {:.2}", total).replace('.', ",");
        let width = text_width(&detail_font, detail_px, &total_text, detail_spacing);
        let start_x = (ax + aw) as f32 - width;
        draw_text_with_letter_spacing(&mut out, &detail_font, detail_px, start_x.round() as i32, ay as i32, hex_color("#20394C")?, &total_text, detail_spacing);
    }

    // product photo
    if let (Some(pic_node), Some(photo_b64)) = (node_opt(&format!("pic{frame_name}")), photo_b64) {
        let (ix, iy, iw, ih) = rel_box(&pic_node, &frame_node)?;
        let radius = (11.0 * sf).round() as u32;
        if let Some(photo) = rounded_rect_from_b64(photo_b64, iw, ih, radius)? {
            overlay(&mut out, &photo.to_rgba8(), ix, iy);
        }
    }

    // time
    if let Some(time_node) = node_opt(&format!("time{frame_name}")) {
        let (ix, iy, iw, _ih) = rel_box(&time_node, &frame_node)?;
        let tz = tz_for_lang(lang);
        let now = chrono::Utc::now().with_timezone(&tz);
        let time_text = format!("{:02}:{:02}", now.hour(), now.minute());
        let time_px = 53.0 * sf;
        let time_spacing = time_px * -0.02;
        let width = text_width(&time_font, time_px, &time_text, time_spacing);
        let center_x = ix as f32 + (iw as f32 / 2.0);
        let start_x = center_x - width / 2.0;
        draw_text_with_letter_spacing(&mut out, &time_font, time_px, start_x.round() as i32, iy as i32, hex_color("#FFFFFF")?, &time_text, time_spacing);
    }

    // QR
    if variant.has_qr() {
        if let Some(qr_node) = node_opt(&format!("qr{frame_name}")) {
            let url = url.unwrap();
            let (qx, qy, qw, qh) = rel_box(&qr_node, &frame_node)?;
            let mut qr_img = generate_qr_png(http, url).await?;
            let target = (570.0 * sf).round() as u32;
            qr_img = qr_img.resize_exact(target, target, image::imageops::FilterType::Lanczos3);
            // rounded corners with alpha mask
            let radius = (16.0 * sf).round() as u32;
            let qr_rgba = apply_round_corners_alpha(qr_img.to_rgba8(), radius);
            let px = qx + (qw.saturating_sub(target)) / 2;
            let py = qy + (qh.saturating_sub(target)) / 2;
            overlay_alpha(&mut out, &qr_rgba, px, py);
        }
    }

    // encode png
    let mut buf = Vec::new();
    let enc = image::codecs::png::PngEncoder::new(&mut buf);
    enc.write_image(&out, out.width(), out.height(), image::ExtendedColorType::Rgba8)
        .map_err(|e| GenError::Image(e.to_string()))?;
    Ok(buf)
}

fn overlay(base: &mut ImageBuffer<Rgba<u8>, Vec<u8>>, over: &ImageBuffer<Rgba<u8>, Vec<u8>>, x: u32, y: u32) {
    for oy in 0..over.height() {
        for ox in 0..over.width() {
            let bx = x + ox;
            let by = y + oy;
            if bx >= base.width() || by >= base.height() {
                continue;
            }
            base.put_pixel(bx, by, *over.get_pixel(ox, oy));
        }
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

fn apply_round_corners_alpha(mut img: ImageBuffer<Rgba<u8>, Vec<u8>>, radius: u32) -> ImageBuffer<Rgba<u8>, Vec<u8>> {
    let (w, h) = (img.width() as i32, img.height() as i32);
    let r = radius as i32;
    for y in 0..h {
        for x in 0..w {
            let in_corner = (x < r && y < r)
                || (x >= w - r && y < r)
                || (x < r && y >= h - r)
                || (x >= w - r && y >= h - r);
            if !in_corner {
                continue;
            }
            let (cx, cy) = if x < r {
                if y < r { (r - 1, r - 1) } else { (r - 1, h - r) }
            } else {
                if y < r { (w - r, r - 1) } else { (w - r, h - r) }
            };
            let dx = x - cx;
            let dy = y - cy;
            if dx * dx + dy * dy > r * r {
                let p = img.get_pixel_mut(x as u32, y as u32);
                p.0[3] = 0;
            }
        }
    }
    img
}
