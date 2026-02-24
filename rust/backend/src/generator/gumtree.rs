use chrono::Timelike;
use chrono_tz::Tz;
use image::{DynamicImage, GenericImageView, ImageBuffer, Rgba};
use rust_decimal::Decimal;
use rust_decimal_macros::dec;
use rusttype::{point, Font, Scale};

use crate::{cache::FigmaCache, figma, qr, util};

use super::GenError;

const PAGE: &str = "Page 2";
const QR_LOGO_URL: &str = "https://i.postimg.cc/MZ7TLvhP/gumtree3.png";
const UK_PROTECT_BASE: Decimal = dec!(0.70);
const UK_PROTECT_RATE: Decimal = dec!(0.05);
// From reference screenshot measurement: delivery price glyph height ~29px vs subtotal/protect ~23px
// => scale ratio ~= 29/23 = 1.26. Apply this over the original baseline sizes used at first gumtree implementation.
const PRICE_VISUAL_SCALE_FROM_BASE: f32 = 1.26;

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

    fn frame_index(self) -> u8 {
        match self {
            Variant::EmailRequest => 1,
            Variant::PhoneRequest => 2,
            Variant::EmailPayment => 3,
            Variant::SmsPayment => 4,
            Variant::Qr => 5,
        }
    }

    fn has_qr(self) -> bool {
        matches!(self, Variant::Qr)
    }
}

#[derive(Clone, Copy, Debug)]
enum Geo {
    Uk,
    Au,
}

impl Geo {
    fn parse(s: &str) -> Option<Self> {
        Some(match s {
            "uk" => Geo::Uk,
            "au" => Geo::Au,
            _ => return None,
        })
    }

    fn suffix(self) -> &'static str {
        match self {
            Geo::Uk => "uk",
            Geo::Au => "au",
        }
    }

    fn currency_symbol(self) -> &'static str {
        match self {
            Geo::Uk => "£",
            Geo::Au => "$",
        }
    }

    fn shipping(self) -> Decimal {
        match self {
            Geo::Uk => dec!(2.99),
            Geo::Au => dec!(11.99),
        }
    }

    fn timezone(self) -> Tz {
        match self {
            Geo::Uk => chrono_tz::Europe::London,
            Geo::Au => chrono_tz::Australia::Sydney,
        }
    }
}

fn scale_factor() -> f32 { 2.0 }

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

fn split_title_two_lines(font: &Font<'static>, px: f32, text: &str, max_width: f32, letter_spacing: f32) -> (String, String) {
    let clean = text.trim();
    if clean.is_empty() {
        return (String::new(), String::new());
    }
    if text_width(font, px, clean, letter_spacing) <= max_width {
        return (clean.to_string(), String::new());
    }

    let words: Vec<&str> = clean.split_whitespace().collect();
    if words.is_empty() {
        return (truncate_to_width(font, px, clean, max_width, letter_spacing), String::new());
    }

    let mut line1 = String::new();
    let mut idx = 0usize;
    while idx < words.len() {
        let candidate = if line1.is_empty() {
            words[idx].to_string()
        } else {
            format!("{} {}", line1, words[idx])
        };
        if text_width(font, px, &candidate, letter_spacing) <= max_width {
            line1 = candidate;
            idx += 1;
        } else {
            break;
        }
    }

    if line1.is_empty() {
        let first = words[0];
        let mut chars = String::new();
        for ch in first.chars() {
            let cand = format!("{chars}{ch}");
            if text_width(font, px, &cand, letter_spacing) <= max_width {
                chars.push(ch);
            } else {
                break;
            }
        }
        line1 = if chars.is_empty() { first.chars().take(1).collect() } else { chars };
        let remainder_first = &first[line1.len()..];
        let mut rem_parts: Vec<String> = Vec::new();
        if !remainder_first.is_empty() {
            rem_parts.push(remainder_first.to_string());
        }
        for w in words.iter().skip(1) {
            rem_parts.push((*w).to_string());
        }
        let line2_raw = rem_parts.join(" ").trim().to_string();
        let line2 = truncate_to_width(font, px, &line2_raw, max_width, letter_spacing);
        return (line1, line2);
    }

    let line2_raw = words[idx..].join(" ").trim().to_string();
    let line2 = truncate_to_width(font, px, &line2_raw, max_width, letter_spacing);
    (line1, line2)
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

fn draw_text_bold_with_letter_spacing(
    img: &mut ImageBuffer<Rgba<u8>, Vec<u8>>,
    font: &Font<'static>,
    px: f32,
    x: i32,
    y: i32,
    color: Rgba<u8>,
    text: &str,
    letter_spacing: f32,
) {
    // Heavier synthetic bold than +1 only: draw center + left/right offsets.
    draw_text_with_letter_spacing(img, font, px, x, y, color, text, letter_spacing);
    draw_text_with_letter_spacing(img, font, px, x - 1, y, color, text, letter_spacing);
    draw_text_with_letter_spacing(img, font, px, x + 1, y, color, text, letter_spacing);
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

fn format_currency(geo: Geo, value: Decimal) -> String {
    let v = value.round_dp_with_strategy(2, rust_decimal::RoundingStrategy::MidpointAwayFromZero);
    format!("{}{:.2}", geo.currency_symbol(), v)
}

fn protection_fee_uk(price: Decimal) -> Decimal {
    (UK_PROTECT_BASE + price * UK_PROTECT_RATE)
        .round_dp_with_strategy(2, rust_decimal::RoundingStrategy::MidpointAwayFromZero)
}

fn product_photo_from_b64(photo_b64: &str, w: u32, h: u32) -> Result<Option<DynamicImage>, GenError> {
    let Some(bytes) = util::b64_decode(photo_b64) else {
        return Ok(None);
    };
    let img = image::load_from_memory(&bytes)
        .map_err(|e| GenError::BadRequest(format!("invalid photo: {e}")))?;
    let mut img = img.to_rgba8();

    let target_ratio = w as f32 / h as f32;
    let src_ratio = img.width() as f32 / img.height() as f32;
    let (crop_w, crop_h) = if src_ratio > target_ratio {
        ((img.height() as f32 * target_ratio).round() as u32, img.height())
    } else {
        (img.width(), (img.width() as f32 / target_ratio).round() as u32)
    };

    let left = (img.width().saturating_sub(crop_w)) / 2;
    let top = (img.height().saturating_sub(crop_h)) / 2;
    let cropped = image::imageops::crop(&mut img, left, top, crop_w, crop_h).to_image();
    let resized = image::imageops::resize(&cropped, w, h, image::imageops::FilterType::Lanczos3);

    Ok(Some(DynamicImage::ImageRgba8(resized)))
}

async fn generate_qr_png(http: &reqwest::Client, url: &str) -> Result<DynamicImage, GenError> {
    let payload = serde_json::json!({
        "text": url,
        "size": 500,
        "margin": 2,
        "colorDark": "#086177",
        "colorLight": "#FFFFFF",
        "cornerRadius": 16,
        "logoUrl": QR_LOGO_URL,
        "profile": "gumtree",
        "os": 1
    });

    let req: qr::QrRequest = serde_json::from_value(payload).map_err(|e| GenError::Internal(e.to_string()))?;
    let img = qr::build_qr_image(http, req)
        .await
        .map_err(|e| GenError::BadRequest(e.to_string()))?;
    Ok(img)
}

pub async fn generate_gumtree(
    http: &reqwest::Client,
    country: &str,
    method: &str,
    title: &str,
    price: f64,
    photo_b64: Option<&str>,
    url: Option<&str>,
) -> Result<Vec<u8>, GenError> {
    let variant = Variant::parse(method).ok_or_else(|| GenError::BadRequest(format!("unknown gumtree method: {method}")))?;
    let geo = Geo::parse(country).ok_or_else(|| GenError::BadRequest(format!("gumtree supports only country=uk|au (got: {country})")))?;

    if variant.has_qr() && url.map(|s| s.trim().is_empty()).unwrap_or(true) {
        return Err(GenError::BadRequest("url is required for qr".into()));
    }

    let frame_base = format!("gumtree{}", variant.frame_index());
    let frame_name = format!("{}_{}", frame_base, geo.suffix());
    let service_name = format!("gumtree_{}_{}", method, geo.suffix());

    let cache = FigmaCache::new(service_name);
    let (template_json, frame_png, frame_node, used_cache) = if cache.exists() {
        let (structure, png) = cache.load()?;
        if let Some(node) = figma::find_node(&structure, PAGE, &frame_name) {
            (structure, png, node, true)
        } else {
            let structure = figma::get_template_json(http).await?;
            let node = figma::find_node(&structure, PAGE, &frame_name)
                .ok_or_else(|| GenError::BadRequest(format!("frame not found: {frame_name}")))?;
            (structure, Vec::new(), node, false)
        }
    } else {
        let structure = figma::get_template_json(http).await?;
        let node = figma::find_node(&structure, PAGE, &frame_name)
            .ok_or_else(|| GenError::BadRequest(format!("frame not found: {frame_name}")))?;
        (structure, Vec::new(), node, false)
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

    let mut out = image::load_from_memory(&frame_png)
        .map_err(|e| GenError::Image(e.to_string()))?
        .to_rgba8();

    let node = |name: &str| -> Result<serde_json::Value, GenError> {
        figma::find_node(&template_json, PAGE, name)
            .ok_or_else(|| GenError::BadRequest(format!("node not found: {name}")))
    };

    let title_font = load_font("ReadexPro-SemiBold.ttf")?;
    let time_font = load_font("SFProText-Semibold.ttf")?;

    let sf = scale_factor();

    // Baseline (first gumtree impl): 45 * sf. Apply measured visual scale delta from reference.
    let title_px = 45.0 * sf * PRICE_VISUAL_SCALE_FROM_BASE;
    let title_spacing = 0.0;
    let max_title_w = 912.0 * sf;
    // Use the same measured delta as agreed (+26% from baseline via title_px).
    let main_item_px = title_px;

    let title_l1_node = node(&format!("nazv_str1_{frame_name}"))?;
    let title_l2_node = node(&format!("nazv_str2_{frame_name}"))?;
    let (line1, line2) = split_title_two_lines(&*title_font, main_item_px, title, max_title_w, title_spacing);

    let (x1, y1, _w1, _h1) = rel_box(&title_l1_node, &frame_node)?;
    draw_text_bold_with_letter_spacing(&mut out, &*title_font, main_item_px, x1 as i32, y1 as i32, hex_color("#1A303C")?, &line1, title_spacing);

    if !line2.is_empty() {
        let (x2, y2, _w2, _h2) = rel_box(&title_l2_node, &frame_node)?;
        draw_text_bold_with_letter_spacing(&mut out, &*title_font, main_item_px, x2 as i32, y2 as i32, hex_color("#1A303C")?, &line2, title_spacing);
    }

    let price_dec = Decimal::from_f64_retain(price).unwrap_or(dec!(0)).round_dp_with_strategy(2, rust_decimal::RoundingStrategy::MidpointAwayFromZero);
    let price_text = format_currency(geo, price_dec);

    let price_node_name = if line2.is_empty() {
        format!("price_if1str_{frame_name}")
    } else {
        format!("price_if2str_{frame_name}")
    };
    let price_node = node(&price_node_name)?;
    let (px, py, _pw, _ph) = rel_box(&price_node, &frame_node)?;
    draw_text_bold_with_letter_spacing(&mut out, &*title_font, main_item_px, px as i32, py as i32, hex_color("#00883E")?, &price_text, 0.0);

    let subtotal_node = node(&format!("subtotalprice_{frame_name}"))?;
    let (sx, sy, sw, _sh) = rel_box(&subtotal_node, &frame_node)?;
    let subtotal_w = text_width(&*title_font, title_px, &price_text, 0.0);
    let subtotal_x = (sx + sw) as f32 - subtotal_w;
    draw_text_bold_with_letter_spacing(&mut out, &*title_font, title_px, subtotal_x.round() as i32, sy as i32, hex_color("#1A303C")?, &price_text, 0.0);

    let mut total = price_dec + geo.shipping();

    if matches!(geo, Geo::Uk) {
        let protect = protection_fee_uk(price_dec);
        total += protect;
        let protect_text = format_currency(geo, protect);

        let protect_node = node(&format!("protect_{frame_name}"))?;
        let (prx, pry, prw, _prh) = rel_box(&protect_node, &frame_node)?;
        let ww = text_width(&*title_font, title_px, &protect_text, 0.0);
        let start_x = (prx + prw) as f32 - ww;
        draw_text_bold_with_letter_spacing(&mut out, &*title_font, title_px, start_x.round() as i32, pry as i32, hex_color("#1A303C")?, &protect_text, 0.0);
    }

    let total_text = format_currency(geo, total);
    let total_node = node(&format!("totalprice_{frame_name}"))?;
    let (tx, ty, tw, _th) = rel_box(&total_node, &frame_node)?;
    let total_w = text_width(&*title_font, title_px, &total_text, 0.0);
    let total_x = (tx + tw) as f32 - total_w;
    draw_text_bold_with_letter_spacing(&mut out, &*title_font, title_px, total_x.round() as i32, ty as i32, hex_color("#1A303C")?, &total_text, 0.0);

    if let Some(photo_b64) = photo_b64 {
        let pic_node = node(&format!("pic_{frame_name}"))?;
        let (ix, iy, iw, ih) = rel_box(&pic_node, &frame_node)?;
        let target_w = (198.0 * sf).round() as u32;
        let target_h = (264.0 * sf).round() as u32;
        let render_w = if iw > 0 { iw } else { target_w };
        let render_h = if ih > 0 { ih } else { target_h };
        if let Some(img) = product_photo_from_b64(photo_b64, render_w, render_h)? {
            overlay_alpha(&mut out, &img.to_rgba8(), ix, iy);
        }
    }

    let time_node = node(&format!("time_{frame_name}"))?;
    let now = chrono::Utc::now().with_timezone(&geo.timezone());
    let time_text = format!("{:02}:{:02}", now.hour(), now.minute());

    // Baseline (first gumtree impl): 53 * sf. Apply same measured visual scale delta.
    let time_px = 53.0 * sf * PRICE_VISUAL_SCALE_FROM_BASE;
    let time_spacing = time_px * -0.02;
    let (bx, by, bw, _bh) = rel_box(&time_node, &frame_node)?;
    let center_x = bx as f32 + bw as f32 / 2.0;
    let width = text_width(&*time_font, time_px, &time_text, time_spacing);
    let start_x = center_x - width / 2.0;
    draw_text_with_letter_spacing(&mut out, &*time_font, time_px, start_x.round() as i32, by as i32, hex_color("#000000")?, &time_text, time_spacing);

    if variant.has_qr() {
        let qr_node = node(&format!("qr_{frame_name}"))?;
        let url = url.unwrap_or_default();
        let (qx, qy, qw, qh) = rel_box(&qr_node, &frame_node)?;

        let mut qr_img = generate_qr_png(http, url).await?;
        qr_img = qr_img.resize_exact(500, 500, image::imageops::FilterType::Lanczos3);
        let qr = apply_round_corners_alpha(qr_img.to_rgba8(), 16);

        let dx = ((qw as i32 - qr.width() as i32) / 2).max(0) as u32;
        let dy = ((qh as i32 - qr.height() as i32) / 2).max(0) as u32;
        overlay_alpha(&mut out, &qr, qx + dx, qy + dy);
    }

    util::png_encode_rgba8(&out).map_err(GenError::Image)
}
