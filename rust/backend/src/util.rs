use base64::Engine;

use image::{
    codecs::png::CompressionType,
    codecs::png::FilterType as PngFilter,
    ImageBuffer,
    ImageEncoder,
    Rgba,
};

pub fn parse_data_uri(input: &str) -> Option<String> {
    let s = input.trim();
    if s.is_empty() {
        return None;
    }
    if let Some(rest) = s.strip_prefix("data:") {
        // data:image/png;base64,....
        let (_, b64) = rest.split_once(",")?;
        return Some(b64.trim().to_string());
    }
    // assume plain base64
    Some(s.to_string())
}

pub fn b64_decode(input: &str) -> Option<Vec<u8>> {
    let b64 = parse_data_uri(input)?;
    let engine = base64::engine::general_purpose::STANDARD;
    engine.decode(b64.as_bytes()).ok()
}

pub fn truncate_with_ellipsis(mut s: String, max_len: usize) -> String {
    if s.len() <= max_len {
        return s;
    }
    if max_len <= 3 {
        return "...".to_string();
    }
    s.truncate(max_len - 3);
    s.push_str("...");
    s
}

pub fn png_encode_rgba8(img: &ImageBuffer<Rgba<u8>, Vec<u8>>) -> Result<Vec<u8>, String> {
    let mut buf = Vec::new();

    // Fast defaults: smaller CPU cost, slightly larger PNG.
    // Can be overridden by PNG_FAST=0.
    let fast = std::env::var("PNG_FAST").unwrap_or_else(|_| "1".to_string());
    let fast = !(fast == "0" || fast.eq_ignore_ascii_case("false"));

    if fast {
        let enc = image::codecs::png::PngEncoder::new_with_quality(
            &mut buf,
            CompressionType::Fast,
            PngFilter::NoFilter,
        );
        enc.write_image(img, img.width(), img.height(), image::ExtendedColorType::Rgba8)
            .map_err(|e| e.to_string())?;
    } else {
        let enc = image::codecs::png::PngEncoder::new(&mut buf);
        enc.write_image(img, img.width(), img.height(), image::ExtendedColorType::Rgba8)
            .map_err(|e| e.to_string())?;
    }

    Ok(buf)
}

pub fn final_resize_filter() -> image::imageops::FilterType {
    // Performance default: Triangle is much faster than Lanczos3 for large downscales.
    // Set FINAL_RESIZE_FILTER=lanczos3 for max quality.
    match std::env::var("FINAL_RESIZE_FILTER")
        .unwrap_or_else(|_| "triangle".to_string())
        .to_ascii_lowercase()
        .as_str()
    {
        "nearest" => image::imageops::FilterType::Nearest,
        "triangle" | "bilinear" => image::imageops::FilterType::Triangle,
        "catmullrom" | "catmull" => image::imageops::FilterType::CatmullRom,
        "gaussian" => image::imageops::FilterType::Gaussian,
        "lanczos3" | "lanczos" => image::imageops::FilterType::Lanczos3,
        _ => image::imageops::FilterType::Triangle,
    }
}
