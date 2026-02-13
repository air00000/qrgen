use chrono::Timelike;
use image::{DynamicImage, GenericImageView, ImageBuffer, Rgba};
use rusttype::{point, Font, Scale};

use crate::{cache, cache::FigmaCache, figma, qr, util};
use crate::perf_scope;

use super::GenError;

const PAGE: &str = "Page 2";

/// New Subito variants (frames subito6..subito10).
///
/// Methods are part of the public API contract:
/// - qr
/// - email_request
/// - phone_request
/// - email_payment
/// - sms_payment
#[derive(Clone, Copy, Debug)]
enum NewVariant {
    EmailRequest,
    PhoneRequest,
    EmailPayment,
    SmsPayment,
    Qr,
}

impl NewVariant {
    fn parse(s: &str) -> Option<Self> {
        Some(match s {
            "email_request" => NewVariant::EmailRequest,
            "phone_request" => NewVariant::PhoneRequest,
            "email_payment" => NewVariant::EmailPayment,
            "sms_payment" => NewVariant::SmsPayment,
            "qr" => NewVariant::Qr,
            _ => return None,
        })
    }

    fn frame_base(self) -> &'static str {
        match self {
            NewVariant::EmailRequest => "subito6",
            NewVariant::PhoneRequest => "subito7",
            NewVariant::EmailPayment => "subito8",
            NewVariant::SmsPayment => "subito9",
            NewVariant::Qr => "subito10",
        }
    }

    fn cache_service_name(self, lang: &str) -> String {
        // MUST stay compatible with Python cache layout: app/figma_cache/{service}_*.{json,png}
        match self {
            NewVariant::EmailRequest => format!("subito_email_request_{lang}"),
            NewVariant::PhoneRequest => format!("subito_phone_request_{lang}"),
            NewVariant::EmailPayment => format!("subito_email_payment_{lang}"),
            NewVariant::SmsPayment => format!("subito_sms_payment_{lang}"),
            NewVariant::Qr => format!("subito_qr_{lang}"),
        }
    }

    fn needs_url(self) -> bool {
        matches!(self, NewVariant::Qr)
    }

    fn has_qr(self) -> bool {
        matches!(self, NewVariant::Qr)
    }
}

// Legacy Subito variants (Italian frames subito1..subito5).
#[derive(Clone, Copy, Debug)]
enum ItVariant {
    Qr,
    EmailRequest,
    EmailConfirm,
    SmsRequest,
    SmsConfirm,
}

impl ItVariant {
    fn parse(s: &str) -> Option<Self> {
        Some(match s {
            "qr" => ItVariant::Qr,
            "email_request" => ItVariant::EmailRequest,
            "email_confirm" => ItVariant::EmailConfirm,
            "sms_request" => ItVariant::SmsRequest,
            "sms_confirm" => ItVariant::SmsConfirm,
            _ => return None,
        })
    }

    fn frame_name(self) -> &'static str {
        match self {
            ItVariant::Qr => "subito1",
            ItVariant::EmailRequest => "subito2",
            ItVariant::EmailConfirm => "subito3",
            ItVariant::SmsRequest => "subito4",
            ItVariant::SmsConfirm => "subito5",
        }
    }

    fn cache_service_name(self) -> &'static str {
        // MUST match Python cache keys to keep app/figma_cache 1:1
        match self {
            ItVariant::Qr => "subito",
            ItVariant::EmailRequest => "subito_email_request",
            ItVariant::EmailConfirm => "subito_email_confirm",
            ItVariant::SmsRequest => "subito_sms_request",
            ItVariant::SmsConfirm => "subito_sms_confirm",
        }
    }

    fn has_qr(self) -> bool {
        matches!(self, ItVariant::Qr)
    }
}

fn scale_factor() -> f32 {
    std::env::var("SCALE_FACTOR")
        .ok()
        .and_then(|s| s.parse::<f32>().ok())
        .unwrap_or(2.0)
}

fn load_font(name: &str) -> Result<std::sync::Arc<Font<'static>>, GenError> {
    super::font_cache::load_font_cached(name)
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
    let (fx, fy, _fw, _fh) =
        bbox(frame_node).ok_or_else(|| GenError::Internal("missing frame absoluteBoundingBox".into()))?;
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

fn truncate_to_width(font: &Font<'static>, px: f32, text: &str, max_width: f32, letter_spacing: f32) -> String {
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
        format!("{trimmed}{ellipsis}")
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
            if dx * dx + dy * dy > r * r {
                let p = img.get_pixel_mut(x as u32, y as u32);
                p.0[3] = 0;
            }
        }
    }
    img
}

fn square_photo_from_b64(photo_b64: &str, w: u32, h: u32, radius: u32) -> Result<Option<DynamicImage>, GenError> {
    let Some(bytes) = util::b64_decode(photo_b64) else {
        return Ok(None);
    };
    let img = image::load_from_memory(&bytes)
        .map_err(|e| GenError::BadRequest(format!("invalid photo: {e}")))?;
    let mut img = img.to_rgba8();

    // Crop to square (center)
    let min_dim = img.width().min(img.height());
    let left = (img.width().saturating_sub(min_dim)) / 2;
    let top = (img.height().saturating_sub(min_dim)) / 2;
    let cropped = image::imageops::crop(&mut img, left, top, min_dim, min_dim).to_image();
    let resized = image::imageops::resize(&cropped, w, h, image::imageops::FilterType::Lanczos3);

    let rounded = apply_round_corners_alpha(resized, radius);
    Ok(Some(DynamicImage::ImageRgba8(rounded)))
}

fn rect_photo_from_b64(photo_b64: &str, w: u32, h: u32, radius: u32) -> Result<Option<DynamicImage>, GenError> {
    let Some(bytes) = util::b64_decode(photo_b64) else {
        return Ok(None);
    };
    let img = image::load_from_memory(&bytes).map_err(|e| GenError::BadRequest(format!("invalid photo: {e}")))?;
    let mut img = img.to_rgba8();

    // Crop to target aspect ratio (center crop).
    let target_ratio = w as f32 / h as f32;
    let src_ratio = img.width() as f32 / img.height() as f32;

    let (crop_w, crop_h) = if src_ratio > target_ratio {
        // too wide
        ((img.height() as f32 * target_ratio).round() as u32, img.height())
    } else {
        // too tall
        (img.width(), (img.width() as f32 / target_ratio).round() as u32)
    };

    let left = (img.width().saturating_sub(crop_w)) / 2;
    let top = (img.height().saturating_sub(crop_h)) / 2;
    let cropped = image::imageops::crop(&mut img, left, top, crop_w, crop_h).to_image();
    let resized = image::imageops::resize(&cropped, w, h, image::imageops::FilterType::Lanczos3);

    let rounded = apply_round_corners_alpha(resized, radius);
    Ok(Some(DynamicImage::ImageRgba8(rounded)))
}

async fn generate_subito_qr_png(
    http: &reqwest::Client,
    url: &str,
    size: u32,
    corner_radius: u32,
) -> Result<DynamicImage, GenError> {
    // EXACT legacy settings (qrgen-4.1-qr baseline):
    // - profile: subito (logo + finder style)
    // - margin: 2
    // - explicit colors to avoid drift
    // - cornerRadius: supplied by template spec
    let payload = serde_json::json!({
        "text": url,
        "profile": "subito",
        "size": size,
        "margin": 0,
        "colorDark": "#FF6E69",
        "colorLight": "#FFFFFF",
        "cornerRadius": corner_radius,
        "os": 1
    });

    let req: qr::QrRequest = serde_json::from_value(payload)
        .map_err(|e| GenError::Internal(e.to_string()))?;
    let img = qr::build_qr_image(http, req)
        .await
        .map_err(|e| GenError::BadRequest(e.to_string()))?;
    Ok(img)
}

async fn generate_subito_it_qr_png(
    http: &reqwest::Client,
    url: &str,
    size: u32,
    corner_radius: u32,
) -> Result<DynamicImage, GenError> {
    // Legacy Subito (IT) QR settings (subito1..5).
    let payload = serde_json::json!({
        "text": url,
        "profile": "subito",
        "size": size,
        "margin": 2,
        "colorDark": "#FF6E69",
        "colorLight": "#FFFFFF",
        "cornerRadius": corner_radius,
        "os": 1
    });

    let req: qr::QrRequest = serde_json::from_value(payload)
        .map_err(|e| GenError::Internal(e.to_string()))?;

    let img = qr::build_qr_image(http, req)
        .await
        .map_err(|e| GenError::BadRequest(e.to_string()))?;
    Ok(img)
}

async fn generate_subito_it(
    http: &reqwest::Client,
    method: &str,
    title: &str,
    price: f64,
    photo_b64: Option<&str>,
    url: Option<&str>,
    name: Option<&str>,
    address: Option<&str>,
) -> Result<Vec<u8>, GenError> {
    let _span_total = perf_scope!("gen.subito_it.total");

    let variant = ItVariant::parse(method)
        .ok_or_else(|| GenError::BadRequest(format!("unknown subito method: {method}")))?;

    if variant.has_qr() && url.map(|s| s.trim().is_empty()).unwrap_or(true) {
        return Err(GenError::BadRequest("url is required for qr".into()));
    }

    // Python truncation rules are char-count based
    let title = util::truncate_with_ellipsis(title.to_string(), 25);
    let name = name.map(|s| util::truncate_with_ellipsis(s.to_string(), 50));
    let address = address.map(|s| util::truncate_with_ellipsis(s.to_string(), 100));
    let url_trunc = url.map(|s| util::truncate_with_ellipsis(s.to_string(), 500));

    let frame_name = variant.frame_name();
    let service_name = variant.cache_service_name();

    let cache = FigmaCache::new(service_name);
    let (template_json, frame_png, frame_node, used_cache) = {
        let _span = perf_scope!("gen.subito_it.figma.load");
        if cache.exists() {
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
        }
    };

    let frame_png = if used_cache {
        frame_png
    } else {
        let node_id = frame_node
            .get("id")
            .and_then(|v| v.as_str())
            .ok_or_else(|| GenError::Internal("frame node missing id".into()))?;
        let png = figma::export_frame_as_png(http, node_id, Some(2)).await?;
        cache.save(&template_json, &png)?;
        png
    };

    let mut out = {
        let _span = perf_scope!("gen.subito_it.frame.decode");
        image::load_from_memory(&frame_png)
            .map_err(|e| GenError::Image(e.to_string()))?
            .to_rgba8()
    };

    // nodes
    let node = |name: &str| -> Result<serde_json::Value, GenError> {
        figma::find_node(&template_json, PAGE, name)
            .ok_or_else(|| GenError::BadRequest(format!("node not found: {name}")))
    };
    let node_opt = |name: &str| -> Option<serde_json::Value> { figma::find_node(&template_json, PAGE, name) };

    let title_layer = match variant {
        ItVariant::Qr => "NAZVANIE_SUB1",
        ItVariant::EmailRequest => "NAZVANIE_SUB2",
        ItVariant::EmailConfirm => "NAZVANIE_SUB3",
        ItVariant::SmsRequest => "NAZVANIE_SUB4",
        ItVariant::SmsConfirm => "NAZVANIE_SUB5",
    };
    let price_layer = match variant {
        ItVariant::Qr => "PRICE_SUB1",
        ItVariant::EmailRequest => "PRICE_SUB2",
        ItVariant::EmailConfirm => "PRICE_SUB3",
        ItVariant::SmsRequest => "PRICE_SUB4",
        ItVariant::SmsConfirm => "PRICE_SUB5",
    };
    let total_layer = match variant {
        ItVariant::Qr => "TOTAL_SUB1",
        ItVariant::EmailRequest => "TOTAL_SUB2",
        ItVariant::EmailConfirm => "TOTAL_SUB3",
        ItVariant::SmsRequest => "TOTAL_SUB4",
        ItVariant::SmsConfirm => "TOTAL_SUB5",
    };
    let address_layer = match variant {
        ItVariant::Qr => "ADRESS_SUB1",
        ItVariant::EmailRequest => "ADRESS_SUB2",
        ItVariant::EmailConfirm => "ADRESS_SUB3",
        ItVariant::SmsRequest => "ADRESS_SUB4",
        ItVariant::SmsConfirm => "ADRESS_SUB5",
    };
    let name_layer = match variant {
        ItVariant::Qr => "IMYA_SUB1",
        ItVariant::EmailRequest => "IMYA_SUB2",
        ItVariant::EmailConfirm => "IMYA_SUB3",
        ItVariant::SmsRequest => "IMYA_SUB4",
        ItVariant::SmsConfirm => "IMYA_SUB5",
    };
    let time_layer = match variant {
        ItVariant::Qr => "TIME_SUB1",
        ItVariant::EmailRequest => "TIME_SUB2",
        ItVariant::EmailConfirm => "TIME_SUB3",
        ItVariant::SmsRequest => "TIME_SUB4",
        ItVariant::SmsConfirm => "TIME_SUB5",
    };
    let photo_layer = match variant {
        ItVariant::Qr => "PHOTO_SUB1",
        ItVariant::EmailRequest => "PHOTO_SUB2",
        ItVariant::EmailConfirm => "PHOTO_SUB3",
        ItVariant::SmsRequest => "PHOTO_SUB4",
        ItVariant::SmsConfirm => "PHOTO_SUB5",
    };

    let title_node = node(title_layer)?;
    let price_node = node(price_layer)?;
    let total_node = node(total_layer)?;
    let time_node = node(time_layer)?;
    let photo_node = node(photo_layer)?;

    let address_node = node_opt(address_layer);
    let name_node = node_opt(name_layer);

    let qr_node = if variant.has_qr() {
        Some(node("QR_SUB1")?)
    } else {
        None
    };

    // fonts
    let aktiv = load_font("aktivgroteskcorp_medium.ttf")?;
    let sfpro = load_font("SFProText-Semibold.ttf")?;

    let sf = scale_factor();
    let nazv_px = 96.0 * sf;
    let small_px = 64.0 * sf;
    let time_px = 112.0 * sf;

    let formatted_price = format!("€{:.2}", price);

    // photo
    if let Some(photo_b64) = photo_b64 {
        let _span = perf_scope!("gen.subito_it.photo");
        let (ix, iy, iw, ih) = rel_box(&photo_node, &frame_node)?;
        let radius = (15.0 * sf).round() as u32;
        if let Some(photo) = square_photo_from_b64(photo_b64, iw, ih, radius)? {
            overlay_alpha(&mut out, &photo.to_rgba8(), ix, iy);
        }
        drop(_span);
    }

    // qr
    if let Some(qr_node) = qr_node {
        let _span = perf_scope!("gen.subito_it.qr");
        let url = url_trunc.as_deref().unwrap_or("");
        let (qx, qy, qw, qh) = rel_box(&qr_node, &frame_node)?;
        let corner = (15.0 * sf).round() as u32;
        let mut qr_img = generate_subito_it_qr_png(http, url, qw, corner).await?;
        if qr_img.width() != qw || qr_img.height() != qh {
            qr_img = qr_img.resize_exact(qw, qh, image::imageops::FilterType::Lanczos3);
        }
        overlay_alpha(&mut out, &qr_img.to_rgba8(), qx, qy);
        drop(_span);
    }

    // title
    {
        let (tx, ty, _tw, _th) = rel_box(&title_node, &frame_node)?;
        draw_text_with_letter_spacing(
            &mut out,
            &*aktiv,
            nazv_px,
            tx as i32,
            ty as i32,
            hex_color("#1F262D")?,
            &title,
            0.0,
        );
    }

    // price
    {
        let (px, py, _pw, _ph) = rel_box(&price_node, &frame_node)?;
        draw_text_with_letter_spacing(
            &mut out,
            &*aktiv,
            nazv_px,
            px as i32,
            py as i32,
            hex_color("#838386")?,
            &formatted_price,
            0.0,
        );
    }

    // name
    if let (Some(n), Some(name)) = (name_node, name.as_deref()) {
        if !name.is_empty() {
            let (ix, iy, _iw, _ih) = rel_box(&n, &frame_node)?;
            draw_text_with_letter_spacing(
                &mut out,
                &*aktiv,
                small_px,
                ix as i32,
                iy as i32,
                hex_color("#838386")?,
                name,
                0.0,
            );
        }
    }

    // address
    if let (Some(n), Some(addr)) = (address_node, address.as_deref()) {
        if !addr.is_empty() {
            let (ix, iy, _iw, _ih) = rel_box(&n, &frame_node)?;
            draw_text_with_letter_spacing(
                &mut out,
                &*aktiv,
                small_px,
                ix as i32,
                iy as i32,
                hex_color("#838386")?,
                addr,
                0.0,
            );
        }
    }

    // total (right aligned)
    {
        let (bx, by, bw, _bh) = rel_box(&total_node, &frame_node)?;
        let right_x = (bx + bw) as f32;
        let width = text_width(&*aktiv, nazv_px, &formatted_price, 0.0);
        let start_x = (right_x - width).round() as i32;
        draw_text_with_letter_spacing(
            &mut out,
            &*aktiv,
            nazv_px,
            start_x,
            by as i32,
            hex_color("#838386")?,
            &formatted_price,
            0.0,
        );
    }

    // time (right aligned with letter spacing)
    {
        let rome_tz = chrono_tz::Europe::Rome;
        let now = chrono::Utc::now().with_timezone(&rome_tz);
        let time_text = format!("{}:{:02}", now.hour(), now.minute());

        let (bx, by, bw, _bh) = rel_box(&time_node, &frame_node)?;
        let right_x = (bx + bw) as f32;
        let letter_spacing = (time_px * 0.02).round();
        let width = text_width(&*sfpro, time_px, &time_text, letter_spacing);
        let start_x = (right_x - width).round() as i32;
        draw_text_with_letter_spacing(
            &mut out,
            &*sfpro,
            time_px,
            start_x,
            by as i32,
            hex_color("#FFFFFF")?,
            &time_text,
            letter_spacing,
        );
    }

    // Match legacy Python output size (Telegram-friendly): downscale to 1304x2838.
    // Old Python generator resized to this exact size at the end.
    out = image::imageops::resize(&out, 1304, 2838, image::imageops::FilterType::Lanczos3);

    let buf = {
        let _span = perf_scope!("gen.subito_it.png.encode");
        util::png_encode_rgba8(&out).map_err(GenError::Image)?
    };

    Ok(buf)
}

fn format_price_main(price: f64) -> String {
    // Format: XX,XX € but drop decimals if cents are zero.
    let cents_total = (price * 100.0).round() as i64;
    let euros = cents_total / 100;
    let cents = (cents_total.abs() % 100) as i64;
    if cents == 0 {
        format!("{} €", euros)
    } else {
        format!("{},{} €", euros, format!("{:02}", cents))
    }
    .replace('.', ",")
}

fn format_price_2dec(price: f64) -> String {
    let cents_total = (price * 100.0).round() as i64;
    let euros = cents_total / 100;
    let cents = (cents_total.abs() % 100) as i64;
    format!("{},{} €", euros, format!("{:02}", cents)).replace('.', ",")
}

// legacy cache purge removed: we support subito1..5 again

pub async fn generate_subito(
    http: &reqwest::Client,
    country_or_lang: &str,
    method: &str,
    title: &str,
    price: f64,
    photo_b64: Option<&str>,
    url: Option<&str>,
    name: Option<&str>,
    address: Option<&str>,
) -> Result<Vec<u8>, GenError> {
    let _span_total = perf_scope!("gen.subito.total");

    let variant = NewVariant::parse(method)
        .ok_or_else(|| GenError::BadRequest(format!("unknown subito method: {method}")))?;

    let lang = match country_or_lang.to_lowercase().as_str() {
        "uk" | "nl" | "it" => country_or_lang.to_lowercase(),
        other if other.starts_with("uk") => "uk".to_string(),
        other if other.starts_with("nl") => "nl".to_string(),
        other if other.starts_with("it") => "it".to_string(),
        _ => "uk".to_string(),
    };

    if variant.needs_url() && url.map(|s| s.trim().is_empty()).unwrap_or(true) {
        return Err(GenError::BadRequest("url is required for qr".into()));
    }

    let frame_base = variant.frame_base();
    let cache_service = variant.cache_service_name(&lang);

    let cache = FigmaCache::new(cache_service);

    let (template_json, frame_png, frame_node, used_cache, frame_name) = {
        let _span = perf_scope!("gen.subito.figma.load");

        let try_find_frame = |structure: &serde_json::Value| -> Option<(serde_json::Value, String)> {
            // Prefer language-specific frames.
            // Current naming in Figma: subito6_uk / subito6_nl.
            let candidate1 = format!("{frame_base}_{lang}");
            if let Some(n) = figma::find_node(structure, PAGE, &candidate1) {
                return Some((n, candidate1));
            }

            // Back-compat: some experiments used subito6uk / subito6nl.
            let candidate0 = format!("{frame_base}{lang}");
            if let Some(n) = figma::find_node(structure, PAGE, &candidate0) {
                return Some((n, candidate0));
            }

            // IMPORTANT: For uk/nl we should NOT silently fall back to the base frame,
            // because that can mix languages when an old cache exists.
            if lang == "uk" || lang == "nl" {
                return None;
            }

            // Fallback: frame without lang suffix (used for it or older templates).
            if let Some(n) = figma::find_node(structure, PAGE, frame_base) {
                return Some((n, frame_base.to_string()));
            }
            None
        };

        if cache.exists() {
            let (structure, png) = cache.load()?;
            if let Some((node, name)) = try_find_frame(&structure) {
                (structure, png, node, true, name)
            } else {
                // cache structure is stale
                let structure = figma::get_template_json(http).await?;
                let (node, name) = try_find_frame(&structure)
                    .ok_or_else(|| GenError::BadRequest(format!("frame not found: {frame_base} (lang={lang})")))?;
                (structure, Vec::new(), node, false, name)
            }
        } else {
            let structure = figma::get_template_json(http).await?;
            let (node, name) = try_find_frame(&structure)
                .ok_or_else(|| GenError::BadRequest(format!("frame not found: {frame_base} (lang={lang})")))?;
            (structure, Vec::new(), node, false, name)
        }
    };

    let frame_png = if used_cache {
        frame_png
    } else {
        let node_id = frame_node
            .get("id")
            .and_then(|v| v.as_str())
            .ok_or_else(|| GenError::Internal("frame node missing id".into()))?;
        // Export at scale=2 (source of truth).
        let png = figma::export_frame_as_png(http, node_id, Some(2)).await?;
        cache.save(&template_json, &png)?;
        png
    };

    let mut out = {
        let _span = perf_scope!("gen.subito.frame.decode");
        image::load_from_memory(&frame_png)
            .map_err(|e| GenError::Image(e.to_string()))?
            .to_rgba8()
    };

    // Validate export size matches bbox*scale
    let (fw, fh) = {
        let (_, _, w, h) = bbox(&frame_node).ok_or_else(|| GenError::Internal("frame missing bbox".into()))?;
        let sf = scale_factor();
        ((w * sf).round() as u32, (h * sf).round() as u32)
    };
    if out.width() != fw || out.height() != fh {
        return Err(GenError::Internal(format!(
            "frame export size mismatch for {frame_name}: got {}x{}, expected {}x{}",
            out.width(),
            out.height(),
            fw,
            fh
        )));
    }

    let node = |name: &str| -> Result<serde_json::Value, GenError> {
        figma::find_node(&template_json, PAGE, name)
            .ok_or_else(|| GenError::BadRequest(format!("node not found: {name}")))
    };
    let node_opt = |name: &str| -> Option<serde_json::Value> { figma::find_node(&template_json, PAGE, name) };

    // Nodes are named like nazv_subito6, price_subito7, ...
    let title_node = node(&format!("nazv_{frame_base}"))?;
    let price_node = node_opt(&format!("price_{frame_base}"));
    let oggetto_node = node_opt(&format!("oggetto_{frame_base}"));
    let totalprice_node = node_opt(&format!("totalprice_{frame_base}"));
    let time_node = node_opt(&format!("time_{frame_base}")).ok_or_else(|| {
        GenError::BadRequest(format!("node not found: time_{frame_base}"))
    })?;
    let pic_node = node_opt(&format!("pic_{frame_base}"));
    let qr_node = if variant.has_qr() {
        Some(node(&format!("qr_{frame_base}"))?)
    } else {
        None
    };

    // Fonts & styles from TЗ
    let ft_sb = load_font("LFTEticaSb.ttf")?;
    let ft_bk = load_font("LFTEticaBk.ttf")?;
    let sfpro = load_font("SFProText-Semibold.ttf")?;

    let sf = scale_factor();

    // Title
    {
        let title_px = 48.0 * sf;
        let max_width = 880.0 * sf;
        let title_color = hex_color("#3C4858")?;

        let title = truncate_to_width(&*ft_sb, title_px, title, max_width, 0.0);
        let (x, y, _w, _h) = rel_box(&title_node, &frame_node)?;
        draw_text_with_letter_spacing(&mut out, &*ft_sb, title_px, x as i32, y as i32, title_color, &title, 0.0);
    }

    // Price (left aligned, red)
    if let Some(n) = price_node {
        let price_px = 48.0 * sf;
        let (x, y, _w, _h) = rel_box(&n, &frame_node)?;
        let text = format_price_main(price);
        draw_text_with_letter_spacing(
            &mut out,
            &*ft_sb,
            price_px,
            x as i32,
            y as i32,
            hex_color("#F9423A")?,
            &text,
            0.0,
        );
    }

    // oggetto (right aligned, -1%)
    if let Some(n) = oggetto_node {
        let px = 50.0 * sf;
        let letter_spacing = px * (-0.01);
        let text = format_price_2dec(price);

        let (bx, by, bw, _bh) = rel_box(&n, &frame_node)?;
        let right_x = (bx + bw) as f32;
        let width = text_width(&*ft_bk, px, &text, letter_spacing);
        let start_x = (right_x - width).round() as i32;
        draw_text_with_letter_spacing(
            &mut out,
            &*ft_bk,
            px,
            start_x,
            by as i32,
            hex_color("#3C4858")?,
            &text,
            letter_spacing,
        );
    }

    // totalprice = price + 6.85 (right aligned, -1%)
    if let Some(n) = totalprice_node {
        let px = 50.0 * sf;
        let letter_spacing = px * (-0.01);
        let total = price + 6.85;
        let text = format_price_2dec(total);

        let (bx, by, bw, _bh) = rel_box(&n, &frame_node)?;
        let right_x = (bx + bw) as f32;
        let width = text_width(&*ft_sb, px, &text, letter_spacing);
        let start_x = (right_x - width).round() as i32;
        draw_text_with_letter_spacing(
            &mut out,
            &*ft_sb,
            px,
            start_x,
            by as i32,
            hex_color("#3C4858")?,
            &text,
            letter_spacing,
        );
    }

    // Photo: 186x138, radius 8
    if let (Some(n), Some(photo_b64)) = (pic_node, photo_b64) {
        let (x, y, w, h) = rel_box(&n, &frame_node)?;
        // Spec says 186x138, but we respect the node box size (should match).
        let radius = (8.0 * sf).round() as u32;
        if let Some(img) = rect_photo_from_b64(photo_b64, w, h, radius)? {
            overlay_alpha(&mut out, &img.to_rgba8(), x, y);
        }
    }

    // QR: переносим legacy-настройки QR (цвета/профиль/лого/стиль) и применяем новые размеры макета.
    // ТЗ: generate 500x500 -> resize 431x431 -> corner radius 16.
    // В рендере мы работаем в scale=2, поэтому все пиксельные размеры умножаем на sf.
    if let Some(qr_node) = qr_node {
        let _span = perf_scope!("gen.subito.qr");
        let url = url.unwrap_or("");

        let (x, y, w, h) = rel_box(&qr_node, &frame_node)?;

        let gen_size = (500.0 * sf).round() as u32;
        // Make QR slightly smaller than the placeholder to avoid covering the mockup.
        // Requested: ~5px smaller (at scale=1). We render at scale=2, so subtract 5*sf.
        let target_size = ((431.0 - 15.0) * sf).round() as u32;
        let corner = (16.0 * sf).round() as u32;

        let mut qr_img = generate_subito_qr_png(http, url, gen_size, corner).await?;
        qr_img = qr_img.resize_exact(target_size, target_size, image::imageops::FilterType::Lanczos3);

        // Center inside the Figma node box (do NOT stretch back to full size).
        let dx = ((w as i32 - qr_img.width() as i32) / 2).max(0) as u32;
        let dy = ((h as i32 - qr_img.height() as i32) / 2).max(0) as u32;
        overlay_alpha(&mut out, &qr_img.to_rgba8(), x + dx, y + dy);
        drop(_span);
    }

    // Time: centered, Rome TZ, -2%
    {
        let rome_tz = chrono_tz::Europe::Rome;
        let now = chrono::Utc::now().with_timezone(&rome_tz);
        let time_text = format!("{:02}:{:02}", now.hour(), now.minute());

        let px = 53.0 * sf;
        let letter_spacing = px * (-0.02);

        let (bx, by, bw, _bh) = rel_box(&time_node, &frame_node)?;
        let center_x = (bx as f32 + bw as f32 / 2.0);
        let width = text_width(&*sfpro, px, &time_text, letter_spacing);
        let start_x = (center_x - width / 2.0).round() as i32;

        draw_text_with_letter_spacing(
            &mut out,
            &*sfpro,
            px,
            start_x,
            by as i32,
            hex_color("#FFFFFF")?,
            &time_text,
            letter_spacing,
        );
    }

    let buf = {
        let _span = perf_scope!("gen.subito.png.encode");
        util::png_encode_rgba8(&out).map_err(GenError::Image)?
    };
    Ok(buf)
}
