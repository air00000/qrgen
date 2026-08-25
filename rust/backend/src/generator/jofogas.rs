use chrono::Timelike;
use image::{DynamicImage, GenericImageView, ImageBuffer, ImageEncoder, Rgba};
use rusttype::{point, Font, Scale};

use crate::{cache::FigmaCache, figma, util};

use super::GenError;

const PAGE: &str = "Page 2";
const DELIVERY_FEE: u64 = 1499;
const JOFOGAS_TEXT_MULTIPLIER: f32 = 1.2;

fn scale_factor() -> f32 {
    2.0
}

#[inline]
fn dynamic_text_px(px: f32) -> f32 {
    px * JOFOGAS_TEXT_MULTIPLIER
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

fn process_photo_rect(photo_b64: &str, w: u32, h: u32) -> Result<Option<DynamicImage>, GenError> {
    let Some(bytes) = util::b64_decode(photo_b64) else {
        return Ok(None);
    };
    let img = image::load_from_memory(&bytes).map_err(|e| GenError::BadRequest(format!("invalid photo: {e}")))?;
    let mut img = img.to_rgba8();

    // Composite any transparency on white before cropping/resizing.
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

    // Crop to target aspect ratio (center crop) then resize, matching Subito/Gumtree.
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

    Ok(Some(DynamicImage::ImageRgba8(resized)))
}

fn format_price_ft(amount: u64) -> String {
    let s = amount.to_string();
    let mut result = String::new();
    let mut count = 0;
    for c in s.chars().rev() {
        if count > 0 && count % 3 == 0 {
            result.push(' ');
        }
        result.push(c);
        count += 1;
    }
    result.chars().rev().collect::<String>() + " Ft"
}

fn calc_defend_price(price: f64) -> u64 {
    (price.max(0.0) * 0.01 + 100.0).round() as u64
}

fn truncate_to_width(
    font: &Font<'static>,
    px: f32,
    text: &str,
    letter_spacing: f32,
    max_width: f32,
) -> String {
    if text_width(font, px, text, letter_spacing) <= max_width {
        return text.to_string();
    }

    let ellipsis = "...";
    let mut result = text.to_string();
    while !result.is_empty()
        && text_width(font, px, &(result.clone() + ellipsis), letter_spacing) > max_width
    {
        result.pop();
    }
    result.trim_end().to_string() + ellipsis
}

fn truncate_title_2_lines(font: &Font<'static>, px: f32, text: &str, letter_spacing: f32, max_width: f32) -> Vec<String> {
    if text.trim().is_empty() {
        return vec![];
    }
    let words: Vec<&str> = text.split_whitespace().collect();
    let mut lines: Vec<String> = Vec::new();
    let mut current = String::new();

    for word in words {
        let test = if current.is_empty() {
            word.to_string()
        } else {
            format!("{} {}", current, word)
        };
        if text_width(font, px, &test, letter_spacing) <= max_width {
            current = test;
        } else {
            if !current.is_empty() {
                lines.push(current);
                current = word.to_string();
            } else {
                current = word.to_string();
            }
            if lines.len() >= 2 {
                break;
            }
        }
    }
    if !current.is_empty() && lines.len() < 2 {
        lines.push(current);
    }

    if lines.len() > 2 {
        lines.truncate(2);
    }

    if lines.len() == 2 {
        let mut second = lines[1].clone();
        while !second.is_empty() && text_width(font, px, &(second.clone() + "..."), letter_spacing) > max_width {
            if let Some((head, _)) = second.rsplit_once(' ') {
                second = head.to_string();
            } else {
                second.pop();
            }
        }
        if second.len() < lines[1].len() {
            lines[1] = if second.is_empty() { "...".to_string() } else { second + "..." };
        }
    }

    lines
}

pub async fn generate_jofogas(
    http: &reqwest::Client,
    title: &str,
    price: f64,
    photo_b64: Option<&str>,
    surname: &str,
    name: &str,
    address: &str,
) -> Result<Vec<u8>, GenError> {
    // Keep compatibility with clients that send the full name in `name`.
    let (surname, name) = if surname.trim().is_empty() {
        let mut parts = name.split_whitespace();
        let parsed_surname = parts.next().unwrap_or("");
        let parsed_name = parts.collect::<Vec<_>>().join(" ");
        (parsed_surname.to_string(), parsed_name)
    } else {
        (surname.trim().to_string(), name.trim().to_string())
    };

    let frame_name = "jofogas3_hu";
    let service_name = "jofogas3_hu";

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

    let node_opt = |name: &str| -> Option<serde_json::Value> { figma::find_node(&template_json, PAGE, name) };

    let sf = scale_factor();

    let font_reg = load_font("SFProText-Regular.ttf")?;
    let font_medium = load_font("SFPROTEXT-MEDIUM.TTF")?;
    let font_semibold = load_font("SFProText-Semibold.ttf")?;

    let base_price = price.max(0.0) as u64;
    let defend_price = calc_defend_price(price);
    let full_price = base_price + defend_price;
    let total_price = full_price + DELIVERY_FEE;

    // Title (nazv) - left aligned, 2 lines max, ellipsis
    if let Some(n) = node_opt(&format!("nazv_{frame_name}")) {
        let (x, y, _w, _h) = rel_box(&n, &frame_node)?;
        let title_px = dynamic_text_px(39.0 * sf);
        let title_spacing = (title_px * -0.007).round();
        let max_width = 880.0 * sf;
        let lines = truncate_title_2_lines(&font_reg, title_px, title, title_spacing, max_width);
        let line_h = (title_px * 1.2).round() as i32;
        for (i, line) in lines.iter().enumerate() {
            draw_text_with_letter_spacing(
                &mut out,
                &font_reg,
                title_px,
                x as i32,
                y as i32 + (i as i32) * line_h,
                hex_color("#666666")?,
                line,
                title_spacing,
            );
        }
    }

    // Price (full price without delivery) - left aligned, orange
    if let Some(n) = node_opt(&format!("price_{frame_name}")) {
        let (x, y, _w, _h) = rel_box(&n, &frame_node)?;
        let price_px = dynamic_text_px(45.0 * sf);
        let price_spacing = (price_px * -0.017).round();
        let text = format_price_ft(full_price);
        draw_text_with_letter_spacing(
            &mut out,
            &font_semibold,
            price_px,
            x as i32,
            y as i32,
            hex_color("#F07330")?,
            &text,
            price_spacing,
        );
    }

    // Familiya - right aligned
    if let Some(n) = node_opt(&format!("familiya_{frame_name}")) {
        let (x, y, w, _h) = rel_box(&n, &frame_node)?;
        let px = dynamic_text_px(45.0 * sf);
        let spacing = (px * -0.017).round();
        let surname = truncate_to_width(&font_medium, px, &surname, spacing, 671.0 * sf);
        let width = text_width(&font_medium, px, &surname, spacing);
        let start_x = (x + w) as f32 - width;
        draw_text_with_letter_spacing(
            &mut out,
            &font_medium,
            px,
            start_x.round() as i32,
            y as i32,
            hex_color("#666666")?,
            &surname,
            spacing,
        );
    }

    // Imya - right aligned
    if let Some(n) = node_opt(&format!("imya_{frame_name}")) {
        let (x, y, w, _h) = rel_box(&n, &frame_node)?;
        let px = dynamic_text_px(45.0 * sf);
        let spacing = (px * -0.017).round();
        let name = truncate_to_width(&font_medium, px, &name, spacing, 642.0 * sf);
        let width = text_width(&font_medium, px, &name, spacing);
        let start_x = (x + w) as f32 - width;
        draw_text_with_letter_spacing(
            &mut out,
            &font_medium,
            px,
            start_x.round() as i32,
            y as i32,
            hex_color("#666666")?,
            &name,
            spacing,
        );
    }

    // Adres - right aligned
    if let Some(n) = node_opt(&format!("adres_{frame_name}")) {
        let (x, y, w, _h) = rel_box(&n, &frame_node)?;
        let px = dynamic_text_px(45.0 * sf);
        let spacing = (px * -0.017).round();
        let address = truncate_to_width(&font_medium, px, address, spacing, 828.0 * sf);
        let width = text_width(&font_medium, px, &address, spacing);
        let start_x = (x + w) as f32 - width;
        draw_text_with_letter_spacing(
            &mut out,
            &font_medium,
            px,
            start_x.round() as i32,
            y as i32,
            hex_color("#666666")?,
            &address,
            spacing,
        );
    }

    // Tovarprice - right aligned
    if let Some(n) = node_opt(&format!("tovarprice_{frame_name}")) {
        let (x, y, w, _h) = rel_box(&n, &frame_node)?;
        let px = dynamic_text_px(45.0 * sf);
        let spacing = (px * -0.017).round();
        let text = format_price_ft(base_price);
        let width = text_width(&font_medium, px, &text, spacing);
        let start_x = (x + w) as f32 - width;
        draw_text_with_letter_spacing(
            &mut out,
            &font_medium,
            px,
            start_x.round() as i32,
            y as i32,
            hex_color("#242424")?,
            &text,
            spacing,
        );
    }

    // Defendprice - right aligned
    if let Some(n) = node_opt(&format!("defendprice_{frame_name}")) {
        let (x, y, w, _h) = rel_box(&n, &frame_node)?;
        let px = dynamic_text_px(45.0 * sf);
        let spacing = (px * -0.017).round();
        let text = format_price_ft(defend_price);
        let width = text_width(&font_medium, px, &text, spacing);
        let start_x = (x + w) as f32 - width;
        draw_text_with_letter_spacing(
            &mut out,
            &font_medium,
            px,
            start_x.round() as i32,
            y as i32,
            hex_color("#242424")?,
            &text,
            spacing,
        );
    }

    // Dostavkaprice - right aligned
    if let Some(n) = node_opt(&format!("dostavkaprice_{frame_name}")) {
        let (x, y, w, _h) = rel_box(&n, &frame_node)?;
        let px = dynamic_text_px(45.0 * sf);
        let spacing = (px * -0.017).round();
        let text = format_price_ft(DELIVERY_FEE);
        let width = text_width(&font_medium, px, &text, spacing);
        let start_x = (x + w) as f32 - width;
        draw_text_with_letter_spacing(
            &mut out,
            &font_medium,
            px,
            start_x.round() as i32,
            y as i32,
            hex_color("#666666")?,
            &text,
            spacing,
        );
    }

    // Itogoprice - right aligned, orange
    if let Some(n) = node_opt(&format!("itogoprice_{frame_name}")) {
        let (x, y, w, _h) = rel_box(&n, &frame_node)?;
        let px = dynamic_text_px(45.0 * sf);
        let spacing = (px * -0.017).round();
        let text = format_price_ft(total_price);
        let width = text_width(&font_medium, px, &text, spacing);
        let start_x = (x + w) as f32 - width;
        draw_text_with_letter_spacing(
            &mut out,
            &font_medium,
            px,
            start_x.round() as i32,
            y as i32,
            hex_color("#F07330")?,
            &text,
            spacing,
        );
    }

    // Time - right aligned, Budapest timezone
    if let Some(n) = node_opt(&format!("time_{frame_name}")) {
        let (x, y, w, _h) = rel_box(&n, &frame_node)?;
        let tz = chrono_tz::Europe::Budapest;
        let now = chrono::Utc::now().with_timezone(&tz);
        let time_text = format!("{:02}:{:02}", now.hour(), now.minute());
        let time_px = dynamic_text_px(53.0 * sf);
        let time_spacing = (time_px * -0.02).round();
        let width = text_width(&font_semibold, time_px, &time_text, time_spacing);
        let start_x = (x + w) as f32 - width;
        draw_text_with_letter_spacing(
            &mut out,
            &font_semibold,
            time_px,
            start_x.round() as i32,
            y as i32,
            hex_color("#000000")?,
            &time_text,
            time_spacing,
        );
    }

    // Photo - no rounded corners
    if let (Some(photo_b64), Some(n)) = (photo_b64, node_opt(&format!("pic_{frame_name}"))) {
        let (x, y, w, h) = rel_box(&n, &frame_node)?;
        if let Some(photo) = process_photo_rect(photo_b64, w, h)? {
            overlay_alpha(&mut out, &photo.to_rgba8(), x, y);
        }
    }

    let buf = util::png_encode_rgba8(&out).map_err(GenError::Image)?;
    Ok(buf)
}
