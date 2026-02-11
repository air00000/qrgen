use chrono::Timelike;
use image::{DynamicImage, GenericImageView, ImageBuffer, ImageEncoder, Rgba};
use rusttype::{point, Font, Scale};

use crate::{cache::FigmaCache, figma, qr, util};
use crate::perf_scope;

use super::GenError;

const PAGE: &str = "Page 2";

#[derive(Clone, Copy, Debug)]
enum Variant {
    Qr,
    EmailRequest,
    EmailConfirm,
    SmsRequest,
    SmsConfirm,
}

impl Variant {
    fn parse(s: &str) -> Option<Self> {
        Some(match s {
            "qr" => Variant::Qr,
            "email_request" => Variant::EmailRequest,
            "email_confirm" => Variant::EmailConfirm,
            "sms_request" => Variant::SmsRequest,
            "sms_confirm" => Variant::SmsConfirm,
            _ => return None,
        })
    }

    fn frame_name(self) -> &'static str {
        match self {
            Variant::Qr => "subito1",
            Variant::EmailRequest => "subito2",
            Variant::EmailConfirm => "subito3",
            Variant::SmsRequest => "subito4",
            Variant::SmsConfirm => "subito5",
        }
    }

    fn service_name(self) -> &'static str {
        // MUST match Python cache_wrapper service_name to keep app/figma_cache 1:1
        match self {
            Variant::Qr => "subito",
            Variant::EmailRequest => "subito_email_request",
            Variant::EmailConfirm => "subito_email_confirm",
            Variant::SmsRequest => "subito_sms_request",
            Variant::SmsConfirm => "subito_sms_confirm",
        }
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

fn square_photo_from_b64(photo_b64: &str, w: u32, h: u32, radius: u32) -> Result<Option<DynamicImage>, GenError> {
    let Some(bytes) = util::b64_decode(photo_b64) else {
        return Ok(None);
    };
    let img = image::load_from_memory(&bytes)
        .map_err(|e| GenError::BadRequest(format!("invalid photo: {e}")))?;
    let mut img = img.to_rgba8();
    // crop to square
    let min_dim = img.width().min(img.height());
    let left = (img.width() - min_dim) / 2;
    let top = (img.height() - min_dim) / 2;
    let cropped = image::imageops::crop(&mut img, left, top, min_dim, min_dim).to_image();
    let resized = image::imageops::resize(&cropped, w, h, image::imageops::FilterType::Lanczos3);

    let rounded = apply_round_corners_alpha(resized, radius);
    Ok(Some(DynamicImage::ImageRgba8(rounded)))
}

async fn generate_subito_qr_png(http: &reqwest::Client, url: &str, size: u32, corner_radius: u32) -> Result<DynamicImage, GenError> {
    // Generate at target size directly and use local logo via profile + LOGO_DIR.
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

pub async fn generate_subito(
    http: &reqwest::Client,
    method: &str,
    title: &str,
    price: f64,
    photo_b64: Option<&str>,
    url: Option<&str>,
    name: Option<&str>,
    address: Option<&str>,
) -> Result<Vec<u8>, GenError> {
    let _span_total = perf_scope!("gen.subito.total");

    let variant = Variant::parse(method)
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
    let service_name = variant.service_name();

    let cache = FigmaCache::new(service_name);
    let (template_json, frame_png, frame_node, used_cache) = {
        let _span = perf_scope!("gen.subito.figma.load");
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
        // Export at scale=2 to match Figma source of truth (1:1), avoid post-resize.
        let png = figma::export_frame_as_png(http, node_id, Some(2)).await?;
        cache.save(&template_json, &png)?;
        png
    };

    let mut frame_img = {
        let _span = perf_scope!("gen.subito.frame.decode");
        image::load_from_memory(&frame_png)
            .map_err(|e| GenError::Image(e.to_string()))?
            .to_rgba8()
    };

    let (fw, fh) = {
        let (_, _, w, h) = bbox(&frame_node).ok_or_else(|| GenError::Internal("frame missing bbox".into()))?;
        let sf = scale_factor();
        ((w * sf).round() as u32, (h * sf).round() as u32)
    };

    // No frame resize: we render 1:1 as Figma export (scale=2).
    if frame_img.width() != fw || frame_img.height() != fh {
        return Err(GenError::Internal(format!(
            "frame export size mismatch: got {}x{}, expected {}x{}",
            frame_img.width(), frame_img.height(), fw, fh
        )));
    }

    let mut out = frame_img;

    let node = |name: &str| -> Result<serde_json::Value, GenError> {
        figma::find_node(&template_json, PAGE, name)
            .ok_or_else(|| GenError::BadRequest(format!("node not found: {name}")))
    };
    let node_opt = |name: &str| -> Option<serde_json::Value> { figma::find_node(&template_json, PAGE, name) };

    // nodes
    let title_layer = match variant {
        Variant::Qr => "NAZVANIE_SUB1",
        Variant::EmailRequest => "NAZVANIE_SUB2",
        Variant::EmailConfirm => "NAZVANIE_SUB3",
        Variant::SmsRequest => "NAZVANIE_SUB4",
        Variant::SmsConfirm => "NAZVANIE_SUB5",
    };
    let price_layer = match variant {
        Variant::Qr => "PRICE_SUB1",
        Variant::EmailRequest => "PRICE_SUB2",
        Variant::EmailConfirm => "PRICE_SUB3",
        Variant::SmsRequest => "PRICE_SUB4",
        Variant::SmsConfirm => "PRICE_SUB5",
    };
    let total_layer = match variant {
        Variant::Qr => "TOTAL_SUB1",
        Variant::EmailRequest => "TOTAL_SUB2",
        Variant::EmailConfirm => "TOTAL_SUB3",
        Variant::SmsRequest => "TOTAL_SUB4",
        Variant::SmsConfirm => "TOTAL_SUB5",
    };
    let address_layer = match variant {
        Variant::Qr => "ADRESS_SUB1",
        Variant::EmailRequest => "ADRESS_SUB2",
        Variant::EmailConfirm => "ADRESS_SUB3",
        Variant::SmsRequest => "ADRESS_SUB4",
        Variant::SmsConfirm => "ADRESS_SUB5",
    };
    let name_layer = match variant {
        Variant::Qr => "IMYA_SUB1",
        Variant::EmailRequest => "IMYA_SUB2",
        Variant::EmailConfirm => "IMYA_SUB3",
        Variant::SmsRequest => "IMYA_SUB4",
        Variant::SmsConfirm => "IMYA_SUB5",
    };
    let time_layer = match variant {
        Variant::Qr => "TIME_SUB1",
        Variant::EmailRequest => "TIME_SUB2",
        Variant::EmailConfirm => "TIME_SUB3",
        Variant::SmsRequest => "TIME_SUB4",
        Variant::SmsConfirm => "TIME_SUB5",
    };
    let photo_layer = match variant {
        Variant::Qr => "PHOTO_SUB1",
        Variant::EmailRequest => "PHOTO_SUB2",
        Variant::EmailConfirm => "PHOTO_SUB3",
        Variant::SmsRequest => "PHOTO_SUB4",
        Variant::SmsConfirm => "PHOTO_SUB5",
    };

    let title_node = node(title_layer)?;
    let price_node = node(price_layer)?;
    let total_node = node(total_layer)?;
    let time_node = node(time_layer)?;
    let photo_node = node(photo_layer)?;

    let address_node = node_opt(address_layer);
    let name_node = node_opt(name_layer);

    let qr_node = if variant.has_qr() {
        Some(node(match variant {
            Variant::Qr => "QR_SUB1",
            _ => unreachable!(),
        })?)
    } else {
        None
    };

    // fonts (same as python)
    let aktiv = load_font("aktivgroteskcorp_medium.ttf")?;
    let sfpro = load_font("SFProText-Semibold.ttf")?;

    let sf = scale_factor();
    let nazv_px = 96.0 * sf;
    let small_px = 64.0 * sf;
    let time_px = 112.0 * sf;

    let formatted_price = format!("€{:.2}", price);

    // photo
    if let Some(photo_b64) = photo_b64 {
        let _span = perf_scope!("gen.subito.photo");
        let (ix, iy, iw, ih) = rel_box(&photo_node, &frame_node)?;
        let radius = (15.0 * sf).round() as u32;
        if let Some(photo) = square_photo_from_b64(photo_b64, iw, ih, radius)? {
            overlay_alpha(&mut out, &photo.to_rgba8(), ix, iy);
        }
        drop(_span);
    }

    // qr
    if let Some(qr_node) = qr_node {
        let _span = perf_scope!("gen.subito.qr");
        let url = url_trunc.as_deref().unwrap_or("");
        let (qx, qy, qw, qh) = rel_box(&qr_node, &frame_node)?;
        let corner = (15.0 * sf).round() as u32;
        let mut qr_img = generate_subito_qr_png(http, url, qw, corner).await?;
        if qr_img.width() != qw || qr_img.height() != qh {
            qr_img = qr_img.resize_exact(qw, qh, image::imageops::FilterType::Lanczos3);
        }
        overlay_alpha(&mut out, &qr_img.to_rgba8(), qx, qy);
        drop(_span);
    }

    // title
    let (tx, ty, _tw, _th) = rel_box(&title_node, &frame_node)?;
    draw_text_with_letter_spacing(&mut out, &*aktiv, nazv_px, tx as i32, ty as i32, hex_color("#1F262D")?, &title, 0.0);

    // price
    let (px, py, _pw, _ph) = rel_box(&price_node, &frame_node)?;
    draw_text_with_letter_spacing(&mut out, &*aktiv, nazv_px, px as i32, py as i32, hex_color("#838386")?, &formatted_price, 0.0);

    // name
    if let (Some(n), Some(name)) = (name_node, name.as_deref()) {
        if !name.is_empty() {
            let (ix, iy, _iw, _ih) = rel_box(&n, &frame_node)?;
            draw_text_with_letter_spacing(&mut out, &*aktiv, small_px, ix as i32, iy as i32, hex_color("#838386")?, name, 0.0);
        }
    }

    // address
    if let (Some(n), Some(addr)) = (address_node, address.as_deref()) {
        if !addr.is_empty() {
            let (ix, iy, _iw, _ih) = rel_box(&n, &frame_node)?;
            draw_text_with_letter_spacing(&mut out, &*aktiv, small_px, ix as i32, iy as i32, hex_color("#838386")?, addr, 0.0);
        }
    }

    // total (right aligned)
    {
        let (bx, by, bw, _bh) = rel_box(&total_node, &frame_node)?;
        let right_x = (bx + bw) as f32;
        let width = text_width(&*aktiv, nazv_px, &formatted_price, 0.0);
        let start_x = (right_x - width).round() as i32;
        draw_text_with_letter_spacing(&mut out, &*aktiv, nazv_px, start_x, by as i32, hex_color("#838386")?, &formatted_price, 0.0);
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

    // No final resize: return exactly as rendered on the exported Figma frame (scale=2).
    let buf = {
        let _span = perf_scope!("gen.subito.png.encode");
        util::png_encode_rgba8(&out).map_err(GenError::Image)?
    };

    Ok(buf)
}
