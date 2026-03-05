use chrono::{Datelike, Timelike};
use chrono_tz::Tz;
use image::{codecs::png::PngDecoder, ImageBuffer, Rgba};
use printpdf::{
    Actions, BorderArray, BuiltinFont, ColorArray, HighlightingMode, Image as PdfImage,
    ImageTransform, LinkAnnotation, Mm, PdfDocument, Rect,
};

use crate::{cache::FigmaCache, figma};

use super::GenError;

const PAGE: &str = "Page 2";

fn tz_for_lang(lang: &str) -> Tz {
    match lang {
        "en" => chrono_tz::Europe::London,
        "it" => chrono_tz::Europe::Rome,
        "fr" => chrono_tz::Europe::Paris,
        "es" => chrono_tz::Europe::Madrid,
        "pr" => chrono_tz::Europe::Lisbon,
        "de" => chrono_tz::Europe::Berlin,
        "nl" => chrono_tz::Europe::Amsterdam,
        _ => chrono_tz::Europe::London,
    }
}

fn format_date_for_lang(lang: &str) -> String {
    let now = chrono::Utc::now().with_timezone(&tz_for_lang(lang));
    match lang {
        "it" => {
            let months = ["gen", "feb", "mar", "apr", "mag", "giu", "lug", "ago", "set", "ott", "nov", "dic"];
            format!("{} {} {}", now.day(), months[now.month0() as usize], now.year())
        }
        "fr" => {
            let months = ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc."];
            format!("{} {} {}", now.day(), months[now.month0() as usize], now.year())
        }
        "es" => {
            let months = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sept", "oct", "nov", "dic"];
            format!("{} {} {}", now.day(), months[now.month0() as usize], now.year())
        }
        "pr" => {
            let months = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"];
            format!("{} {} {}", now.day(), months[now.month0() as usize], now.year())
        }
        "de" => {
            let months = ["Jan", "Feb", "Mär", "Apr", "Mai", "Jun", "Jul", "Aug", "Sep", "Okt", "Nov", "Dez"];
            format!("{}. {} {}", now.day(), months[now.month0() as usize], now.year())
        }
        "nl" => {
            let months = ["jan", "feb", "mrt", "apr", "mei", "jun", "jul", "aug", "sep", "okt", "nov", "dec"];
            format!("{} {} {}", now.day(), months[now.month0() as usize], now.year())
        }
        _ => {
            let months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
            format!("{} {} {}", now.day(), months[now.month0() as usize], now.year())
        }
    }
}

fn bbox(v: &serde_json::Value) -> Option<(f64, f64, f64, f64)> {
    let bb = v.get("absoluteBoundingBox")?;
    Some((
        bb.get("x")?.as_f64()?,
        bb.get("y")?.as_f64()?,
        bb.get("width")?.as_f64()?,
        bb.get("height")?.as_f64()?,
    ))
}

fn rel_box(node: &serde_json::Value, frame_node: &serde_json::Value) -> Result<(f64, f64, f64, f64), GenError> {
    let (x, y, w, h) = bbox(node).ok_or_else(|| GenError::Internal("missing absoluteBoundingBox".into()))?;
    let (fx, fy, _fw, _fh) = bbox(frame_node).ok_or_else(|| GenError::Internal("missing frame absoluteBoundingBox".into()))?;
    Ok((x - fx, y - fy, w, h))
}

fn find_node_any(template_json: &serde_json::Value, names: &[&str]) -> Option<serde_json::Value> {
    for n in names {
        if let Some(v) = figma::find_node(template_json, PAGE, n) {
            return Some(v);
        }
    }
    None
}

fn draw_text(_img: &mut ImageBuffer<Rgba<u8>, Vec<u8>>, _x: i32, _y: i32, _text: &str) {
    // Kept for future 1:1 text rendering; currently background frame already contains static text.
}

fn mm_from_px(px: f64) -> f32 {
    (px * 25.4 / 96.0) as f32
}

fn pdf_rect_from_figma(frame_h: f64, x: f64, y: f64, w: f64, h: f64) -> Rect {
    Rect::new(
        Mm(mm_from_px(x)),
        Mm(mm_from_px(frame_h - (y + h))),
        Mm(mm_from_px(x + w)),
        Mm(mm_from_px(frame_h - y)),
    )
}

pub async fn generate_booking(
    http: &reqwest::Client,
    lang: &str,
    title: &str,
    price: f64,
    knopbook1: Option<&str>,
    knopbook2: Option<&str>,
) -> Result<Vec<u8>, GenError> {
    if !matches!(lang, "en" | "it" | "fr" | "es" | "pr" | "de" | "nl") {
        return Err(GenError::BadRequest(format!("unknown booking language: {lang}")));
    }

    let frame_name = format!("book_{lang}");
    let cache = FigmaCache::new(format!("booking_{lang}"));

    let (template_json, frame_png, frame_node, used_cache) = if cache.exists() {
        let (structure, png) = cache.load()?;
        let frame_node = figma::find_node(&structure, PAGE, &frame_name);
        if let Some(node) = frame_node {
            (structure, png, node, true)
        } else {
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

    let frame_png = if used_cache {
        frame_png
    } else {
        let node_id = frame_node
            .get("id")
            .and_then(|v| v.as_str())
            .ok_or_else(|| GenError::Internal("frame node missing id".into()))?;
        let png = figma::export_frame_as_png(http, node_id, Some(1)).await?;
        cache.save(&template_json, &png)?;
        png
    };

    let mut img = image::load_from_memory(&frame_png)
        .map_err(|e| GenError::Image(e.to_string()))?
        .to_rgba8();

    let (_fx, _fy, fw, fh) = bbox(&frame_node).ok_or_else(|| GenError::Internal("frame missing bbox".into()))?;

    // Hooks for TZ-specific dynamic text nodes if present
    let _now = chrono::Utc::now().with_timezone(&tz_for_lang(lang));
    let date_text = format_date_for_lang(lang);
    let _time_text = _now.format("%H:%M").to_string();
    let _price_text = format!("{price:.2}").replace('.', ",");
    let _title = title;

    if let Some(date_node) = find_node_any(&template_json, &[&format!("databook_{lang}"), &format!("datebook_{lang}"), &format!("data_book_{lang}")]) {
        if let Ok((x, y, _w, _h)) = rel_box(&date_node, &frame_node) {
            draw_text(&mut img, x.round() as i32, y.round() as i32, &date_text);
        }
    }

    let mut png_buf = Vec::new();
    {
        let mut cur = std::io::Cursor::new(&mut png_buf);
        image::DynamicImage::ImageRgba8(img)
            .write_to(&mut cur, image::ImageFormat::Png)
            .map_err(|e| GenError::Image(e.to_string()))?;
    }

    let (doc, page1, layer1) = PdfDocument::new("booking", Mm(mm_from_px(fw)), Mm(mm_from_px(fh)), "Layer 1");
    let current_layer = doc.get_page(page1).get_layer(layer1);

    let mut png_reader = std::io::Cursor::new(png_buf);
    let decoder = PngDecoder::new(&mut png_reader).map_err(|e| GenError::Image(e.to_string()))?;
    let pdf_img = PdfImage::try_from(decoder).map_err(|e| GenError::Image(e.to_string()))?;
    pdf_img.add_to_layer(
        current_layer.clone(),
        ImageTransform {
            translate_x: Some(Mm(0.0)),
            translate_y: Some(Mm(0.0)),
            rotate: None,
            scale_x: None,
            scale_y: None,
            dpi: Some(96.0),
        },
    );

    let add_link = |url: &str, node_name: &str| -> Result<(), GenError> {
        if url.trim().is_empty() {
            return Ok(());
        }
        if let Some(node) = figma::find_node(&template_json, PAGE, node_name) {
            let (x, y, w, h) = rel_box(&node, &frame_node)?;
            let rect = pdf_rect_from_figma(fh, x, y, w, h);
            current_layer.add_link_annotation(LinkAnnotation::new(
                rect,
                Some(BorderArray::default()),
                Some(ColorArray::default()),
                Actions::uri(url.to_string()),
                Some(HighlightingMode::Invert),
            ));
        }
        Ok(())
    };

    add_link(knopbook1.unwrap_or(""), &format!("knopbook1_{lang}"))?;
    add_link(knopbook2.unwrap_or(""), &format!("knopbook2_{lang}"))?;

    // keep builtin font referenced to avoid older readers quirks
    let _ = doc.add_builtin_font(BuiltinFont::Helvetica)
        .map_err(|e| GenError::Internal(format!("pdf font error: {e}")))?;

    let mut out = Vec::<u8>::new();
    {
        let cursor = std::io::Cursor::new(&mut out);
        let mut writer = std::io::BufWriter::new(cursor);
        doc.save(&mut writer)
            .map_err(|e| GenError::Internal(format!("pdf save error: {e}")))?;
    }

    Ok(out)
}
