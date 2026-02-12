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

    // Defaults: keep PNG lossless but reasonably small.
    // PNG_FAST=1 trades size for speed.
    let fast = std::env::var("PNG_FAST").unwrap_or_else(|_| "1".to_string());
    let fast = !(fast == "0" || fast.eq_ignore_ascii_case("false"));

    let (comp, filter) = if fast {
        // Still speed-first, but Adaptive filter often reduces PNG size massively
        // with small CPU overhead compared to NoFilter.
        (CompressionType::Fast, PngFilter::Adaptive)
    } else {
        (CompressionType::Best, PngFilter::Adaptive)
    };

    let enc = image::codecs::png::PngEncoder::new_with_quality(&mut buf, comp, filter);
    enc.write_image(img, img.width(), img.height(), image::ExtendedColorType::Rgba8)
        .map_err(|e| e.to_string())?;

    // Post-optimize losslessly, but only when it matters.
    // oxipng can be CPU-heavy on large, photo-rich images (depop/wallapop).
    // Enable with PNG_OXIPNG=1 (default is OFF for speed).
    let oxi = std::env::var("PNG_OXIPNG").unwrap_or_else(|_| "0".to_string());
    let oxi = !(oxi == "0" || oxi.eq_ignore_ascii_case("false"));

    // Only run oxipng if the PNG is above a threshold (default ~1.8MB).
    let min_bytes = std::env::var("PNG_OXIPNG_MIN_BYTES")
        .ok()
        .and_then(|v| v.parse::<usize>().ok())
        .unwrap_or(1_800_000);

    if oxi && buf.len() >= min_bytes {
        // Default to a moderate preset to keep latency reasonable.
        let level = std::env::var("PNG_OXIPNG_LEVEL")
            .ok()
            .and_then(|v| v.parse::<u8>().ok())
            .unwrap_or(2)
            .min(6);

        let mut opts = oxipng::Options::from_preset(level);
        opts.fix_errors = true;

        match oxipng::optimize_from_memory(&buf, &opts) {
            Ok(out) => Ok(out),
            Err(_) => Ok(buf),
        }
    } else {
        Ok(buf)
    }
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
