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
enum Variant {
    EmailRequest,
    PhoneRequest,
    EmailPayment,
    SmsPayment,
    Qr,
}

impl Variant {
    fn parse(s: &str) -> Option<Self> {
        Some(match s {
            "email_request" => Variant::EmailRequest,
            "phone_request" => Variant::PhoneRequest,
            "email_payment" => Variant::EmailPayment,
            "sms_payment" => Variant::SmsPayment,
            "qr" => Variant::Qr,
            _ => return None,
        })
    }

    fn frame_base(self) -> &'static str {
        match self {
            Variant::EmailRequest => "subito6",
            Variant::PhoneRequest => "subito7",
            Variant::EmailPayment => "subito8",
            Variant::SmsPayment => "subito9",
            Variant::Qr => "subito10",
        }
    }

    fn cache_service_name(self, lang: &str) -> String {
        // MUST stay compatible with Python cache layout: app/figma_cache/{service}_*.{json,png}
        match self {
            Variant::EmailRequest => format!("subito_email_request_{lang}"),
            Variant::PhoneRequest => format!("subito_phone_request_{lang}"),
            Variant::EmailPayment => format!("subito_email_payment_{lang}"),
            Variant::SmsPayment => format!("subito_sms_payment_{lang}"),
            Variant::Qr => format!("subito_qr_{lang}"),
        }
    }

    fn needs_url(self) -> bool {
        matches!(self, Variant::Qr)
    }

    fn has_qr(self) -> bool {
        matches!(self, Variant::Qr)
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

fn purge_legacy_subito_cache() {
    use std::sync::OnceLock;
    static ONCE: OnceLock<()> = OnceLock::new();
    ONCE.get_or_init(|| {
        let dir = cache::cache_dir();
        let legacy = [
            "subito",
            "subito_email_request",
            "subito_email_confirm",
            "subito_sms_request",
            "subito_sms_confirm",
        ];
        for s in legacy {
            let sp = dir.join(format!("{s}_structure.json"));
            let tp = dir.join(format!("{s}_template.png"));
            let _ = std::fs::remove_file(sp);
            let _ = std::fs::remove_file(tp);
        }
    });
}

pub async fn generate_subito(
    http: &reqwest::Client,
    country_or_lang: &str,
    method: &str,
    title: &str,
    price: f64,
    photo_b64: Option<&str>,
    url: Option<&str>,
    _name: Option<&str>,
    _address: Option<&str>,
) -> Result<Vec<u8>, GenError> {
    let _span_total = perf_scope!("gen.subito.total");

    purge_legacy_subito_cache();

    let variant = Variant::parse(method).ok_or_else(|| GenError::BadRequest(format!("unknown subito method: {method}")))?;

    let lang = match country_or_lang.to_lowercase().as_str() {
        "uk" | "nl" => country_or_lang.to_lowercase(),
        other if other.starts_with("uk") => "uk".to_string(),
        other if other.starts_with("nl") => "nl".to_string(),
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
            let candidate1 = format!("{frame_base}_{lang}");
            if let Some(n) = figma::find_node(structure, PAGE, &candidate1) {
                return Some((n, candidate1));
            }
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
        let target_size = (431.0 * sf).round() as u32;
        let corner = (16.0 * sf).round() as u32;

        let mut qr_img = generate_subito_qr_png(http, url, gen_size, corner).await?;
        qr_img = qr_img.resize_exact(target_size, target_size, image::imageops::FilterType::Lanczos3);

        // Fit into Figma node box (should already match, but keep safe).
        if qr_img.width() != w || qr_img.height() != h {
            qr_img = qr_img.resize_exact(w, h, image::imageops::FilterType::Lanczos3);
        }
        overlay_alpha(&mut out, &qr_img.to_rgba8(), x, y);
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
