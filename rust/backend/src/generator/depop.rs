use chrono::Timelike;
use image::{DynamicImage, GenericImageView, ImageBuffer, ImageEncoder, Rgba};
use rusttype::{point, Font, Scale};

use crate::{cache::FigmaCache, figma, qr, util};

use super::GenError;

const PAGE: &str = "Page 2";

const TARGET_WIDTH: u32 = 1320;
const TARGET_HEIGHT: u32 = 2868;

const SHIPPING_COST: f64 = 8.0;

const QR_COLOR: &str = "#CF2C2D";

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

fn process_square_photo(photo_b64: &str, w: u32, h: u32, corner_radius: u32) -> Result<Option<DynamicImage>, GenError> {
    let Some(bytes) = util::b64_decode(photo_b64) else {
        return Ok(None);
    };
    let img = image::load_from_memory(&bytes).map_err(|e| GenError::BadRequest(format!("invalid photo: {e}")))?;
    let mut img = img.to_rgba8();

    // composite any transparency on white
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

    // crop square
    let min_dim = img.width().min(img.height());
    let left = (img.width() - min_dim) / 2;
    let top = (img.height() - min_dim) / 2;
    let cropped = image::imageops::crop(&mut img, left, top, min_dim, min_dim).to_image();
    let resized = image::imageops::resize(&cropped, w, h, image::imageops::FilterType::Lanczos3);

    let mut out = ImageBuffer::from_pixel(w, h, Rgba([0, 0, 0, 0]));
    let r = corner_radius as i32;
    for y in 0..h {
        for x in 0..w {
            let inside = if corner_radius == 0 {
                true
            } else {
                rounded_rect_contains(x as i32, y as i32, w as i32, h as i32, r)
            };
            if inside {
                out.put_pixel(x, y, *resized.get_pixel(x, y));
            }
        }
    }
    Ok(Some(DynamicImage::ImageRgba8(out)))
}

fn make_circle(mut img: ImageBuffer<Rgba<u8>, Vec<u8>>) -> ImageBuffer<Rgba<u8>, Vec<u8>> {
    let (w, h) = (img.width() as i32, img.height() as i32);
    let cx = (w - 1) as f32 / 2.0;
    let cy = (h - 1) as f32 / 2.0;
    let r = (w.min(h) as f32) / 2.0;
    for y in 0..h {
        for x in 0..w {
            let dx = x as f32 - cx;
            let dy = y as f32 - cy;
            if (dx * dx + dy * dy).sqrt() > r {
                let p = img.get_pixel_mut(x as u32, y as u32);
                p.0[3] = 0;
            }
        }
    }
    img
}

async fn generate_qr_png(http: &reqwest::Client, url: &str, size: u32, corner_radius: u32) -> Result<DynamicImage, GenError> {
    let payload = serde_json::json!({
        "text": url,
        "profile": "depop",
        "size": size,
        "margin": 2,
        "cornerRadius": corner_radius,
        "os": 1
    });
    let req: qr::QrRequest = serde_json::from_value(payload).map_err(|e| GenError::Internal(e.to_string()))?;
    let img = qr::build_qr_image(http, req)
        .await
        .map_err(|e| GenError::BadRequest(e.to_string()))?;
    Ok(img)
}

fn truncate_2_lines(font: &Font<'static>, px: f32, text: &str, max_width: f32) -> Vec<String> {
    if text.trim().is_empty() {
        return vec![];
    }
    let mut lines: Vec<String> = Vec::new();
    let mut current: Vec<&str> = Vec::new();

    for word in text.split_whitespace() {
        let mut test = current.clone();
        test.push(word);
        let test_line = test.join(" ");
        if text_width(font, px, &test_line, 0.0) <= max_width {
            current.push(word);
        } else {
            if !current.is_empty() {
                lines.push(current.join(" "));
            }
            current = vec![word];
            if lines.len() >= 2 {
                break;
            }
        }
    }
    if !current.is_empty() && lines.len() < 2 {
        lines.push(current.join(" "));
    }

    if lines.len() > 2 {
        lines.truncate(2);
    }

    // ellipsis on 2nd line if needed
    if lines.len() == 2 {
        let mut second = lines[1].clone();
        while !second.is_empty() && text_width(font, px, &(second.clone() + "..."), 0.0) > max_width {
            // remove last word or char
            if let Some((head, _tail)) = second.rsplit_once(' ') {
                second = head.to_string();
            } else {
                second.pop();
            }
        }
        if second != lines[1] {
            lines[1] = if second.is_empty() { "...".to_string() } else { second + "..." };
        }
    }

    lines
}

fn draw_text_center(img: &mut ImageBuffer<Rgba<u8>, Vec<u8>>, font: &Font<'static>, px: f32, cx: f32, cy: f32, color: Rgba<u8>, text: &str) {
    let w = text_width(font, px, text, 0.0);
    let scale = Scale::uniform(px);
    let vm = font.v_metrics(scale);
    let height = (vm.ascent - vm.descent).max(1.0);
    let x = (cx - w / 2.0).round() as i32;
    let y = (cy - height / 2.0).round() as i32;
    draw_text_with_letter_spacing(img, font, px, x, y, color, text, 0.0);
}

pub async fn generate_depop(
    http: &reqwest::Client,
    title: &str,
    price: f64,
    seller_name: &str,
    photo_b64: Option<&str>,
    seller_photo_b64: Option<&str>,
    url: &str,
) -> Result<Vec<u8>, GenError> {
    let sf = scale_factor();

    let frame_name = "depop1_au";
    let service_name = "depop_au";

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

    let nazv_n = figma::find_node(&template_json, PAGE, "nazvanie_depop1_au");
    let price_n = figma::find_node(&template_json, PAGE, "price_depop1_au");
    let subtotal_n = figma::find_node(&template_json, PAGE, "subtotalprice_depop1_au");
    let total_n = figma::find_node(&template_json, PAGE, "totalprice_depop1_au");
    let seller_n = figma::find_node(&template_json, PAGE, "name_depop1_au");
    let time_n = figma::find_node(&template_json, PAGE, "time_depop1_au");
    let photo_n = figma::find_node(&template_json, PAGE, "pic_depop1_au");
    let avatar_n = figma::find_node(&template_json, PAGE, "avatarka_depop1_au");
    let qr_n = figma::find_node(&template_json, PAGE, "qr_depop1_au");

    // fonts
    let outer_light = load_font("MADE Outer Sans Light.ttf")?;
    let outer_light_48 = load_font("MADE Outer Sans Light.ttf")?;
    let outer_medium = load_font("MADE Outer Sans Medium.ttf")?;
    let outer_medium_40 = load_font("MADE Outer Sans Medium.ttf")?;
    let sfpro = load_font("SFProText-Semibold.ttf")?;

    let offset_base = (2.5 * sf).round() as i32;

    let price_str = format!("${:.2}", price);
    let total_price = price + SHIPPING_COST;
    let total_str = format!("${:.2}", total_price);

    // title: two lines, max width 564
    if let Some(n) = nazv_n {
        let (x, y, _w, _h) = rel_box(&n, &frame_node)?;
        let px_font = 42.0 * sf;
        let max_w = 564.0 * sf;
        let lines = truncate_2_lines(&*outer_light, px_font, title, max_w);
        let line_h = (42.0 * sf * 1.45).round() as i32;
        for (i, line) in lines.iter().enumerate() {
            draw_text_with_letter_spacing(
                &mut out,
                &*outer_light,
                px_font,
                x as i32,
                y as i32 + offset_base + (i as i32) * line_h,
                hex_color("#262626")?,
                line,
                0.0,
            );
        }
    }

    // price right aligned
    let price_offset_y = (14.0 * sf / 2.0).round() as i32; // scale offset a bit
    let price_offset_x = (2.0 * sf / 2.0).round() as i32;
    let price_px = 48.0 * sf;

    let draw_right = |img: &mut ImageBuffer<Rgba<u8>, Vec<u8>>, node_opt: Option<serde_json::Value>, text: &str, font: &Font<'static>, bold: bool| -> Result<(), GenError> {
        if let Some(n) = node_opt {
            let (x, y, w, _h) = rel_box(&n, &frame_node)?;
            let right_x = (x + w) as i32 + price_offset_x;
            let start_x = (right_x as f32 - text_width(font, price_px, text, 0.0)).round() as i32;
            let y = y as i32 + offset_base + price_offset_y;
            let _ = bold;
            draw_text_with_letter_spacing(img, font, price_px, start_x, y, hex_color("#000000")?, text, 0.0);
        }
        Ok(())
    };

    draw_right(&mut out, price_n, &price_str, &*outer_light_48, false)?;
    draw_right(&mut out, subtotal_n, &total_str, &*outer_light_48, false)?;
    draw_right(&mut out, total_n, &total_str, &*outer_medium, true)?;

    // seller name
    if let Some(n) = seller_n {
        let (x, y, _w, _h) = rel_box(&n, &frame_node)?;
        draw_text_with_letter_spacing(
            &mut out,
            &*outer_medium_40,
            40.0 * sf,
            x as i32,
            y as i32 + offset_base + (8.0 * sf / 2.0).round() as i32,
            hex_color("#000000")?,
            seller_name,
            0.0,
        );
    }

    // time center (Sydney)
    if let Some(n) = time_n {
        let (x, y, w, h) = rel_box(&n, &frame_node)?;
        let now = chrono::Utc::now().with_timezone(&chrono_tz::Australia::Sydney);
        let time_text = format!("{:02}:{:02}", now.hour(), now.minute());
        let cx = x as f32 + w as f32 / 2.0 - 3.0;
        let cy = (y as f32 + offset_base as f32 + 64.0 * sf / 2.0) + (h as f32 / 2.0);
        draw_text_center(&mut out, &*sfpro, 50.0 * sf, cx, cy, hex_color("#000000")?, &time_text);
    }

    // product photo (python rel_y includes BASE_TEXT_OFFSET)
    if let (Some(photo_b64), Some(n)) = (photo_b64, photo_n) {
        let (x, y, w, h) = rel_box(&n, &frame_node)?;
        let corner = (12.0 * sf).round() as u32;
        if let Some(photo) = process_square_photo(photo_b64, w, h, corner)? {
            let y = (y + offset_base as u32).saturating_sub(1);
            overlay_alpha(&mut out, &photo.to_rgba8(), x, y);
        }
    }

    // avatar circle
    if let (Some(avatar_b64), Some(n)) = (seller_photo_b64, avatar_n) {
        let (x, y, w, h) = rel_box(&n, &frame_node)?;
        if let Some(avatar) = process_square_photo(avatar_b64, w, h, 0)? {
            let circ = make_circle(avatar.to_rgba8());
            overlay_alpha(&mut out, &circ, x, y + offset_base as u32);
        }
    }

    // qr
    if let Some(n) = qr_n {
        let (x, y, w, h) = rel_box(&n, &frame_node)?;
        // Match legacy Python behavior: generate QR and resize to a fixed box, then center it.
        // Python constants: QR_RESIZE=(1086,1068), QR_CORNER_RADIUS=16 (at SCALE_FACTOR=2).
        let (qw, qh) = (1086u32, 1068u32);
        let qx = x + (w.saturating_sub(qw)) / 2;
        let qy = y + (h.saturating_sub(qh)) / 2;

        let corner = 16u32;
        let mut qr_img = generate_qr_png(http, url, qw, corner).await?;
        if qr_img.width() != qw || qr_img.height() != qh {
            qr_img = qr_img.resize_exact(qw, qh, image::imageops::FilterType::Lanczos3);
        }

        // QR node position in Figma already includes the base layout; do not apply BASE_TEXT_OFFSET here.
        overlay_alpha(&mut out, &qr_img.to_rgba8(), qx, qy);
    }

    // final resize + white background
    let out_img = DynamicImage::ImageRgba8(out)
        .resize_exact(TARGET_WIDTH, TARGET_HEIGHT, util::final_resize_filter())
        .to_rgba8();
    let mut rgb = ImageBuffer::from_pixel(TARGET_WIDTH, TARGET_HEIGHT, Rgba([255, 255, 255, 255]));
    overlay_alpha(&mut rgb, &out_img, 0, 0);

    let buf = util::png_encode_rgba8(&rgb).map_err(GenError::Image)?;
    Ok(buf)
}

pub async fn generate_depop_variant(
    http: &reqwest::Client,
    method: &str,
    title: &str,
    price: f64,
    photo_b64: Option<&str>,
) -> Result<Vec<u8>, GenError> {
    let (frame_name, service_name) = match method {
        "email_request" => ("depop2_au", "depop_au_email_request"),
        "email_confirm" => ("depop3_au", "depop_au_email_confirm"),
        "sms_request" => ("depop4_au", "depop_au_sms_request"),
        "sms_confirm" => ("depop5_au", "depop_au_sms_confirm"),
        other => return Err(GenError::BadRequest(format!("unknown depop method: {other}"))),
    };

    let sf = scale_factor();

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
        ((w * sf).round() as u32, (h * sf).round() as u32)
    };
    if frame_img.width() != fw || frame_img.height() != fh {
        frame_img = image::imageops::resize(&frame_img, fw, fh, image::imageops::FilterType::Lanczos3);
    }

    let mut out = frame_img;

    // nodes
    let nazv_n = figma::find_node(&template_json, PAGE, &format!("nazvanie_{frame_name}"));
    let price_n = figma::find_node(&template_json, PAGE, &format!("price_{frame_name}"));
    let subtotal_n = figma::find_node(&template_json, PAGE, &format!("subtotalprice_{frame_name}"));
    let total_n = figma::find_node(&template_json, PAGE, &format!("totalprice_{frame_name}"));
    let time_n = figma::find_node(&template_json, PAGE, &format!("time_{frame_name}"));
    let photo_n = figma::find_node(&template_json, PAGE, &format!("pic_{frame_name}"));

    // clear template areas (except time)
    let mut clear_boxes = vec![
        ("nazvanie", nazv_n.clone()),
        ("price", price_n.clone()),
        ("subtotal", subtotal_n.clone()),
        ("total", total_n.clone()),
        ("photo", photo_n.clone()),
    ];

    for (k, node_opt) in clear_boxes.drain(..) {
        let _ = k;
        if let Some(n) = node_opt {
            let (x, y, w, h) = rel_box(&n, &frame_node)?;
            let pad = 5u32;
            let x0 = x.saturating_sub(pad);
            let y0 = y.saturating_sub(pad);
            let x1 = (x + w + pad).min(out.width());
            let y1 = (y + h + pad).min(out.height());
            for yy in y0..y1 {
                for xx in x0..x1 {
                    out.put_pixel(xx, yy, Rgba([255, 255, 255, 255]));
                }
            }
        }
    }

    // fonts
    let outer_light = load_font("MADE Outer Sans Light.ttf")?;
    let outer_light_48 = load_font("MADE Outer Sans Light.ttf")?;
    let outer_medium = load_font("MADE Outer Sans Medium.ttf")?;
    let sfpro = load_font("SFProText-Semibold.ttf")?;

    let offset_base = (2.5 * sf).round() as i32;

    let price_str = format!("${:.2}", price);
    let total_price = price + SHIPPING_COST;
    let total_str = format!("${:.2}", total_price);

    // title (max width 452)
    if let Some(n) = nazv_n {
        let (x, y, _w, _h) = rel_box(&n, &frame_node)?;
        let px_font = 42.0 * sf;
        let max_w = 452.0 * sf;
        let lines = truncate_2_lines(&*outer_light, px_font, title, max_w);
        let line_h = (42.0 * sf * 1.472).round() as i32;
        for (i, line) in lines.iter().enumerate() {
            draw_text_with_letter_spacing(
                &mut out,
                &*outer_light,
                px_font,
                x as i32,
                y as i32 + offset_base + (i as i32) * line_h,
                hex_color("#262626")?,
                line,
                0.0,
            );
        }
    }

    // prices right aligned
    let price_offset_y = (14.0 * sf / 2.0).round() as i32;
    let price_offset_x = (2.0 * sf / 2.0).round() as i32;
    let price_px = 48.0 * sf;

    let draw_right = |img: &mut ImageBuffer<Rgba<u8>, Vec<u8>>, node_opt: Option<serde_json::Value>, text: &str, font: &Font<'static>| -> Result<(), GenError> {
        if let Some(n) = node_opt {
            let (x, y, w, _h) = rel_box(&n, &frame_node)?;
            let right_x = (x + w) as i32 + price_offset_x;
            let start_x = (right_x as f32 - text_width(font, price_px, text, 0.0)).round() as i32;
            let y = y as i32 + offset_base + price_offset_y;
            draw_text_with_letter_spacing(img, font, price_px, start_x, y, hex_color("#000000")?, text, 0.0);
        }
        Ok(())
    };

    draw_right(&mut out, price_n, &price_str, &*outer_light_48)?;
    draw_right(&mut out, subtotal_n, &total_str, &*outer_light_48)?;
    draw_right(&mut out, total_n, &total_str, &*outer_medium)?;

    // time center (python uses Rome)
    if let Some(n) = time_n {
        let (x, y, w, h) = rel_box(&n, &frame_node)?;
        let now = chrono::Utc::now().with_timezone(&chrono_tz::Europe::Rome);
        let time_text = format!("{:02}:{:02}", now.hour(), now.minute());
        let cx = x as f32 + w as f32 / 2.0 - 3.0;
        let cy = (y as f32 + offset_base as f32 + 64.0 * sf / 2.0) + (h as f32 / 2.0);
        draw_text_center(&mut out, &*sfpro, 50.0 * sf, cx, cy, hex_color("#000000")?, &time_text);
    }

    // photo y -5 (python rel_y includes BASE_TEXT_OFFSET)
    if let (Some(photo_b64), Some(n)) = (photo_b64, photo_n) {
        let (x, y, w, h) = rel_box(&n, &frame_node)?;
        let corner = (12.0 * sf).round() as u32;
        if let Some(photo) = process_square_photo(photo_b64, w, h, corner)? {
            let y = (y + offset_base as u32).saturating_sub(5);
            overlay_alpha(&mut out, &photo.to_rgba8(), x, y);
        }
    }

    // final resize + white background
    let out_img = DynamicImage::ImageRgba8(out)
        .resize_exact(TARGET_WIDTH, TARGET_HEIGHT, util::final_resize_filter())
        .to_rgba8();
    let mut rgb = ImageBuffer::from_pixel(TARGET_WIDTH, TARGET_HEIGHT, Rgba([255, 255, 255, 255]));
    overlay_alpha(&mut rgb, &out_img, 0, 0);

    let buf = util::png_encode_rgba8(&rgb).map_err(GenError::Image)?;
    Ok(buf)
}
