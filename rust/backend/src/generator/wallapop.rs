use chrono::Timelike;
use chrono_tz::Tz;
use image::{DynamicImage, GenericImageView, ImageBuffer, ImageEncoder, Rgba};
use rust_decimal::prelude::ToPrimitive;
use rust_decimal::Decimal;
use rusttype::{point, Font, Scale};

use crate::{cache::FigmaCache, figma, qr, util};

use super::GenError;

const PAGE: &str = "Page 2";

// qr logo from python implementation
const QR_LOGO_URL: &str = "https://i.ibb.co/pvwMgd8k/Rectangle-355.png";

#[derive(Clone, Copy, Debug)]
enum Variant {
    EmailRequest,
    PhoneRequest,
    EmailPayment,
    SmsPayment,
    Qr,
}

impl Variant {
    fn parse(method: &str) -> Option<Self> {
        Some(match method {
            "email_request" => Variant::EmailRequest,
            // legacy python naming is phone_request; accept sms_request as alias
            "phone_request" | "sms_request" => Variant::PhoneRequest,
            "email_payment" => Variant::EmailPayment,
            "sms_payment" => Variant::SmsPayment,
            "qr" => Variant::Qr,
            _ => return None,
        })
    }

    fn frame_index(self) -> u8 {
        match self {
            Variant::EmailRequest => 3,
            Variant::PhoneRequest => 4,
            Variant::EmailPayment => 5,
            Variant::SmsPayment => 6,
            Variant::Qr => 7,
        }
    }

    /// Service name used for cache keys.
    /// MUST match python service_name to keep app/figma_cache compatible.
    fn cache_method_name(self) -> &'static str {
        match self {
            Variant::EmailRequest => "email_request",
            Variant::PhoneRequest => "phone_request",
            Variant::EmailPayment => "email_payment",
            Variant::SmsPayment => "sms_payment",
            Variant::Qr => "qr",
        }
    }

    fn has_big_price(self) -> bool {
        matches!(self, Variant::EmailPayment | Variant::SmsPayment)
    }

    fn has_qr(self) -> bool {
        matches!(self, Variant::Qr)
    }
}

fn normalize_lang(lang: &str) -> &str {
    // Some clients send pt; templates are pr.
    if lang == "pt" { "pr" } else { lang }
}

fn tz_for_lang(lang: &str) -> Tz {
    match lang {
        "uk" => chrono_tz::Europe::London,
        "es" => chrono_tz::Europe::Madrid,
        "it" => chrono_tz::Europe::Rome,
        "fr" => chrono_tz::Europe::Paris,
        "pr" | "pt" => chrono_tz::Europe::Lisbon,
        _ => chrono_tz::Europe::Madrid,
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

    let mut width = 0.0;
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

fn truncate_title_by_width(font: &Font<'static>, px: f32, text: &str, letter_spacing: f32) -> String {
    let sf = scale_factor();
    let max_width = (666.0 * sf).round();
    let max_width_with_ellipsis = (735.0 * sf).round();

    if text_width(font, px, text, letter_spacing) <= max_width {
        return text.to_string();
    }

    let ellipsis = "...";
    let mut trimmed = text.to_string();
    while !trimmed.is_empty()
        && text_width(font, px, &(trimmed.clone() + ellipsis), letter_spacing) > max_width_with_ellipsis
    {
        trimmed.pop();
    }
    trimmed + ellipsis
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

fn crop_to_aspect_center(img: &mut ImageBuffer<Rgba<u8>, Vec<u8>>, target_w: u32, target_h: u32) -> ImageBuffer<Rgba<u8>, Vec<u8>> {
    let iw = img.width();
    let ih = img.height();
    if iw == 0 || ih == 0 {
        return ImageBuffer::from_pixel(target_w, target_h, Rgba([0, 0, 0, 0]));
    }

    let target_aspect = target_w as f32 / target_h as f32;
    let in_aspect = iw as f32 / ih as f32;

    let (crop_w, crop_h) = if in_aspect > target_aspect {
        // too wide
        let ch = ih;
        let cw = (ch as f32 * target_aspect).round().max(1.0) as u32;
        (cw.min(iw), ch)
    } else {
        // too tall
        let cw = iw;
        let ch = (cw as f32 / target_aspect).round().max(1.0) as u32;
        (cw, ch.min(ih))
    };

    let left = (iw - crop_w) / 2;
    let top = (ih - crop_h) / 2;
    image::imageops::crop(img, left, top, crop_w, crop_h).to_image()
}

fn rounded_rect_from_b64(photo_b64: &str, w: u32, h: u32, radius: u32) -> Result<Option<DynamicImage>, GenError> {
    let Some(bytes) = util::b64_decode(photo_b64) else {
        return Ok(None);
    };
    let img = image::load_from_memory(&bytes).map_err(|e| GenError::BadRequest(format!("invalid photo: {e}")))?;
    let mut img = img.to_rgba8();

    // ImageOps.fit equivalent
    let cropped = crop_to_aspect_center(&mut img, w, h);
    let resized = image::imageops::resize(&cropped, w, h, image::imageops::FilterType::Lanczos3);

    let rounded = apply_round_corners_alpha(resized, radius);
    Ok(Some(DynamicImage::ImageRgba8(rounded)))
}

fn circle_from_b64(photo_b64: &str, size: u32) -> Result<Option<DynamicImage>, GenError> {
    let Some(bytes) = util::b64_decode(photo_b64) else {
        return Ok(None);
    };
    let img = image::load_from_memory(&bytes).map_err(|e| GenError::BadRequest(format!("invalid photo: {e}")))?;
    let mut img = img.to_rgba8();

    let cropped = crop_to_aspect_center(&mut img, size, size);
    let mut resized = image::imageops::resize(&cropped, size, size, image::imageops::FilterType::Lanczos3);

    // circle alpha mask
    let (w, h) = (size as i32, size as i32);
    let r = (size as f32 / 2.0).floor() as i32;
    let cx = r;
    let cy = r;
    for y in 0..h {
        for x in 0..w {
            let dx = x - cx;
            let dy = y - cy;
            if dx * dx + dy * dy > r * r {
                let p = resized.get_pixel_mut(x as u32, y as u32);
                p.0[3] = 0;
            }
        }
    }

    Ok(Some(DynamicImage::ImageRgba8(resized)))
}

fn format_price_eur(price: f64) -> String {
    // python: ROUND_DOWN and suffix " €"
    let d = Decimal::from_f64_retain(price).unwrap_or(Decimal::ZERO);
    let d = d.round_dp_with_strategy(2, rust_decimal::RoundingStrategy::ToZero);
    format!("{:.2}", d).replace('.', ",") + " €"
}

fn split_price(price: f64) -> (String, String) {
    let d = Decimal::from_f64_retain(price).unwrap_or(Decimal::ZERO);
    let d = d.round_dp_with_strategy(2, rust_decimal::RoundingStrategy::ToZero);
    let euros = d.trunc();
    let cents = ((d - euros) * Decimal::from(100u32)).trunc();
    let euros_i = euros.to_i64().unwrap_or(0);
    let cents_i = cents.to_i64().unwrap_or(0);
    (format!("{}", euros_i), format!("{:02}€", cents_i))
}

async fn generate_wallapop_qr_png(http: &reqwest::Client, url: &str) -> Result<DynamicImage, GenError> {
    let payload = serde_json::json!({
        "text": url,
        "size": 800,
        "margin": 2,
        "colorDark": "#000000",
        "colorLight": "#FFFFFF",
        "logoUrl": QR_LOGO_URL,
        "cornerRadius": 0,
    });
    let req: qr::QrRequest = serde_json::from_value(payload).map_err(|e| GenError::Internal(e.to_string()))?;
    let png = qr::build_qr_png(http, req)
        .await
        .map_err(|e| GenError::BadRequest(e.to_string()))?;
    let img = image::load_from_memory(&png).map_err(|e| GenError::Internal(e.to_string()))?;
    Ok(img)
}

fn wallapop_figma_pat() -> Result<String, GenError> {
    std::env::var("WALLAPOP_EMAIL_FIGMA_PAT")
        .map_err(|_| GenError::Internal("WALLAPOP_EMAIL_FIGMA_PAT is not set".into()))
}

fn wallapop_file_key() -> Result<String, GenError> {
    std::env::var("WALLAPOP_EMAIL_FILE_KEY")
        .map_err(|_| GenError::Internal("WALLAPOP_EMAIL_FILE_KEY is not set".into()))
}

pub async fn generate_wallapop(
    http: &reqwest::Client,
    lang: &str,
    method: &str,
    title: &str,
    price: f64,
    photo_b64: Option<&str>,
    seller_name: Option<&str>,
    seller_photo_b64: Option<&str>,
    url: Option<&str>,
) -> Result<Vec<u8>, GenError> {
    let variant = Variant::parse(method)
        .ok_or_else(|| GenError::BadRequest(format!("unknown wallapop method: {method}")))?;

    let lang = normalize_lang(lang);
    if !matches!(lang, "uk" | "es" | "it" | "fr" | "pr") {
        return Err(GenError::BadRequest(format!("unknown wallapop language: {lang}")));
    }

    if variant.has_qr() && url.map(|s| s.trim().is_empty()).unwrap_or(true) {
        return Err(GenError::BadRequest("url is required for qr".into()));
    }

    // python truncation rules are char-count based
    let title = util::truncate_with_ellipsis(title.to_string(), 25);
    let seller_name = seller_name
        .unwrap_or("")
        .to_string();
    let seller_name = util::truncate_with_ellipsis(seller_name, 50);
    let url_trunc = url.map(|s| util::truncate_with_ellipsis(s.to_string(), 500));

    let idx = variant.frame_index();
    let frame_name = format!("wallapop{idx}_{lang}");
    let service_name = format!("wallapop_{}_{}", variant.cache_method_name(), lang);

    let pat = wallapop_figma_pat()?;
    let file_key = wallapop_file_key()?;

    let cache = FigmaCache::new(service_name);

    let (template_json, frame_png, frame_node, used_cache) = if cache.exists() {
        let (structure, png) = cache.load()?;
        let frame_node = figma::find_node(&structure, PAGE, &frame_name);
        if let Some(node) = frame_node {
            (structure, png, node, true)
        } else {
            let structure = figma::get_template_json_with(http, &pat, &file_key).await?;
            let frame_node = figma::find_node(&structure, PAGE, &frame_name)
                .ok_or_else(|| GenError::BadRequest(format!("frame not found: {frame_name}")))?;
            (structure, Vec::new(), frame_node, false)
        }
    } else {
        let structure = figma::get_template_json_with(http, &pat, &file_key).await?;
        let frame_node = figma::find_node(&structure, PAGE, &frame_name)
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
        let png = figma::export_frame_as_png_with(http, &pat, &file_key, node_id, None).await?;
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

    // Required nodes
    let title_node = node(&format!("nazvwal{idx}_{lang}"))?;
    let price_node = node(&format!("pricewal{idx}_{lang}"))?;
    let name_node = node(&format!("namewal{idx}_{lang}"))?;
    let time_node = node(&format!("timewal{idx}_{lang}"))?;
    let photo_node = node(&format!("picwal{idx}_{lang}"))?;
    let avatar_node = node(&format!("avapicwal{idx}_{lang}"))?;

    let big_price_node = if variant.has_big_price() {
        Some(node(&format!("bigpricewal{idx}_{lang}"))?)
    } else {
        None
    };

    let qr_node = if variant.has_qr() {
        Some(node(&format!("qrwal{idx}_{lang}"))?)
    } else {
        None
    };

    // fonts (same as python)
    let title_font = load_font("MEGABYTEREGULAR.ttf")?;
    let price_font = load_font("MEGABYTEMEDIUM.ttf")?;
    let name_font = load_font("MEGABYTEBOLD.ttf")?;
    let time_font = load_font("SFProText-Semibold.ttf")?;
    let big_price_font = load_font("Montserrat-SemiBold.ttf")?;
    let big_price_small_font = load_font("Montserrat-SemiBold.ttf")?;

    let sf = scale_factor();

    // sizes from python
    let title_px = 46.0 * sf;
    let price_px = 64.0 * sf;
    let name_px = 48.0 * sf;
    let time_px = 53.0 * sf;
    let big_px = 230.0 * sf;
    let big_small_px = 137.0 * sf;

    let title_spacing = (46.0 * sf * 0.01).round();
    let price_spacing = (64.0 * sf * -0.02).round();
    let time_spacing = (53.0 * sf * -0.02).round();

    // Title
    let title = truncate_title_by_width(&title_font, title_px, &title, title_spacing);
    let (tx, ty, _tw, _th) = rel_box(&title_node, &frame_node)?;
    draw_text_with_letter_spacing(
        &mut out,
        &title_font,
        title_px,
        tx as i32,
        ty as i32,
        hex_color("#000000")?,
        &title,
        title_spacing,
    );

    // Price
    let price_text = format_price_eur(price);
    let (px, py, _pw, _ph) = rel_box(&price_node, &frame_node)?;
    draw_text_with_letter_spacing(
        &mut out,
        &price_font,
        price_px,
        px as i32,
        py as i32,
        hex_color("#000000")?,
        &price_text,
        price_spacing,
    );

    // Seller name
    let (nx, ny, _nw, _nh) = rel_box(&name_node, &frame_node)?;
    draw_text_with_letter_spacing(
        &mut out,
        &name_font,
        name_px,
        nx as i32,
        ny as i32,
        hex_color("#5C7A89")?,
        &seller_name,
        0.0,
    );

    // Time (centered)
    {
        let tz = tz_for_lang(lang);
        let now = chrono::Utc::now().with_timezone(&tz);
        let time_text = format!("{:02}:{:02}", now.hour(), now.minute());

        let (ix, iy, iw, _ih) = rel_box(&time_node, &frame_node)?;
        let total_w = text_width(&time_font, time_px, &time_text, time_spacing);
        let center_x = ix as f32 + (iw as f32 / 2.0);
        let start_x = center_x - total_w / 2.0;
        draw_text_with_letter_spacing(
            &mut out,
            &time_font,
            time_px,
            start_x.round() as i32,
            iy as i32,
            hex_color("#000000")?,
            &time_text,
            time_spacing,
        );
    }

    // Product photo (rounded rect, fixed size)
    if let Some(photo_b64) = photo_b64 {
        let (ix, iy, _iw, _ih) = rel_box(&photo_node, &frame_node)?;
        let pw = (427.0 * sf).round() as u32;
        let ph = (525.0 * sf).round() as u32;
        let radius = (14.0 * sf).round() as u32;
        if let Some(photo) = rounded_rect_from_b64(photo_b64, pw, ph, radius)? {
            overlay_alpha(&mut out, &photo.to_rgba8(), ix, iy);
        }
    }

    // Seller avatar (circle, fixed size)
    if let Some(avatar_b64) = seller_photo_b64 {
        let (ax, ay, _aw, _ah) = rel_box(&avatar_node, &frame_node)?;
        let s = (146.0 * sf).round() as u32;
        if let Some(avatar) = circle_from_b64(avatar_b64, s)? {
            overlay_alpha(&mut out, &avatar.to_rgba8(), ax, ay);
        }
    }

    // Big price (centered in node)
    if let Some(big_node) = big_price_node {
        let (bx, by, bw, _bh) = rel_box(&big_node, &frame_node)?;
        let (euros, cents) = split_price(price);

        let big_w = text_width(&big_price_font, big_px, &euros, 0.0);
        let small_w = text_width(&big_price_small_font, big_small_px, &cents, 0.0);
        let total = big_w + small_w;
        let start_x = bx as f32 + (bw as f32 - total) / 2.0;

        draw_text_with_letter_spacing(
            &mut out,
            &big_price_font,
            big_px,
            start_x.round() as i32,
            by as i32,
            hex_color("#172E36")?,
            &euros,
            0.0,
        );

        draw_text_with_letter_spacing(
            &mut out,
            &big_price_small_font,
            big_small_px,
            (start_x + big_w).round() as i32,
            by as i32,
            hex_color("#172E36")?,
            &cents,
            0.0,
        );
    }

    // QR
    if let Some(qr_node) = qr_node {
        let url = url_trunc.as_deref().unwrap_or("");
        let (qx, qy, qw, qh) = rel_box(&qr_node, &frame_node)?;
        let mut qr_img = generate_wallapop_qr_png(http, url).await?;
        let target = (738.0 * sf).round() as u32;
        qr_img = qr_img.resize_exact(target, target, image::imageops::FilterType::Lanczos3);
        let radius = (16.0 * sf).round() as u32;
        let qr_rgba = apply_round_corners_alpha(qr_img.to_rgba8(), radius);

        let px = qx + (qw.saturating_sub(target)) / 2;
        let py = qy + (qh.saturating_sub(target)) / 2;
        overlay_alpha(&mut out, &qr_rgba, px, py);
    }

    let mut buf = Vec::new();
    let enc = image::codecs::png::PngEncoder::new(&mut buf);
    enc.write_image(&out, out.width(), out.height(), image::ExtendedColorType::Rgba8)
        .map_err(|e| GenError::Image(e.to_string()))?;
    Ok(buf)
}
