use axum::{
    extract::State,
    http::{header, HeaderMap, StatusCode},
    response::IntoResponse,
    Json,
};
use image::{
    imageops::FilterType,
    DynamicImage,
    GenericImageView,
    ImageBuffer,
    ImageEncoder,
    Rgba,
};

use crate::qr_render::{FinderCornerStyle, FinderInnerCorner, RenderOpts};
use crate::perf_scope;
use qrcode::{EcLevel, QrCode};
use serde::Deserialize;
use utoipa::ToSchema;
use std::{collections::HashMap, path::PathBuf, sync::Arc};
use thiserror::Error;

use once_cell::sync::Lazy;
use parking_lot::Mutex;

use crate::AppState;

#[derive(Debug, Deserialize, ToSchema)]
#[serde(rename_all = "camelCase")]
pub struct QrRequest {
    pub text: String,

    /// Optional style profile name (service-specific defaults).
    /// Supported: depop, markt, 2dehands, 2ememain, wallapop, subito, kleinanzeigen.
    pub profile: Option<String>,

    pub size: Option<u32>,
    pub margin: Option<u32>,

    pub color_dark: Option<String>,
    pub color_light: Option<String>,

    /// Oversampling factor (render at size*os and downscale with Lanczos).
    pub os: Option<u32>,

    /// Module roundness in [0..0.5]. 0 = square; 0.5 = circle.
    pub module_roundness: Option<f32>,

    /// Finder inner corner behavior: "outerOnly" (default) or "both".
    pub finder_inner_corner: Option<String>,

    pub logo_url: Option<String>,
    pub logo_scale: Option<f32>,

    /// Draw a solid badge circle behind logo (helps readability).
    pub logo_badge: Option<bool>,
    pub logo_badge_scale: Option<f32>,
    pub logo_badge_color: Option<String>,

    pub corner_radius: Option<u32>,
}

#[derive(Debug, Error)]
pub enum QrError {
    #[error("invalid color: {0}")]
    InvalidColor(String),
    #[error("invalid option: {0}")]
    InvalidOption(String),
    #[error("failed to encode png")]
    PngEncode,
    #[error("failed to build qr")]
    QrBuild,
    #[error("failed to fetch logo: {0}")]
    LogoFetch(String),
    #[error("failed to decode logo")]
    LogoDecode,
}

impl IntoResponse for QrError {
    fn into_response(self) -> axum::response::Response {
        (StatusCode::BAD_REQUEST, self.to_string()).into_response()
    }
}

// NOTE: HTTP endpoint `/qr` removed. QR generation is available via `/generate` with service="qr".

/// Build QR image (RGBA). Shared by HTTP handler and generators.
/// This avoids extra PNG encode/decode work inside template generators.
pub async fn build_qr_image(http: &reqwest::Client, req: QrRequest) -> Result<DynamicImage, QrError> {
    let _span_total = perf_scope!("qr.build_image.total");
    let profile = req.profile.as_deref().unwrap_or("");

    // Keep historical sizes: wallapop base 800, others 1368.
    let default_size = if profile.eq_ignore_ascii_case("wallapop") { 800 } else { 1368 };
    let size = req.size.unwrap_or(default_size).clamp(128, 4096);

    let margin = req.margin.unwrap_or(2).clamp(0, 16);

    let default_dark = match profile.to_ascii_lowercase().as_str() {
        // Most templates use black; fall back to old default for generic usage.
        "wallapop" | "markt" | "depop" | "kleinanzeigen" => "#000000",
        "subito" => "#FF6E69",
        // 2dehands / 2ememain use a dark navy (matches legacy/Python screenshots).
        "2dehands" | "2ememain" => "#11223E",
        _ => "#4B6179",
    };

    let default_light = match profile.to_ascii_lowercase().as_str() {
        "subito" => "#FFF1F1",
        _ => "#FFFFFF",
    };

    let dark = parse_hex_color(req.color_dark.as_deref().unwrap_or(default_dark))?;
    let light = parse_hex_color(req.color_light.as_deref().unwrap_or(default_light))?;

    let os_default_env = std::env::var("QR_OS")
        .ok()
        .and_then(|s| s.parse::<u32>().ok());
    // Default oversampling: OS=1 for performance. Can be overridden via request or QR_OS env.
    // Allowed values: 1/2/3/5.
    let os = req.os.or(os_default_env).unwrap_or(1);
    if !matches!(os, 1 | 2 | 3 | 5) {
        return Err(QrError::InvalidOption(format!("os={os} (allowed: 1,2,3,5)")));
    }
    let default_module_roundness = if profile.eq_ignore_ascii_case("wallapop") { 0.50 } else { 0.45 };
    let module_roundness = req
        .module_roundness
        .unwrap_or(default_module_roundness)
        .clamp(0.0, 0.5);

    let default_finder_inner = if profile.eq_ignore_ascii_case("2dehands")
        || profile.eq_ignore_ascii_case("2ememain")
        || profile.eq_ignore_ascii_case("wallapop")
    {
        "both"
    } else {
        "outerOnly"
    };

    let finder_inner_corner = match req
        .finder_inner_corner
        .as_deref()
        .unwrap_or(default_finder_inner)
    { 
        "outerOnly" | "outer_only" | "outer" => FinderInnerCorner::OuterOnly,
        "both" => FinderInnerCorner::Both,
        other => return Err(QrError::InvalidOption(format!("finderInnerCorner={other}"))),
    };

    // Subito logo tends to be visually heavy; default a bit smaller to avoid covering modules.
    let default_logo_scale = if profile.eq_ignore_ascii_case("subito") { 0.18 } else { 0.22 };
    let logo_scale = req.logo_scale.unwrap_or(default_logo_scale).clamp(0.05, 0.5);
    let logo_badge = req.logo_badge.unwrap_or(false);
    let logo_badge_scale = req.logo_badge_scale.unwrap_or(1.25).clamp(1.0, 2.0);
    let logo_badge_color = parse_hex_color(req.logo_badge_color.as_deref().unwrap_or("#FFFFFF"))?;

    // Wallapop reference QR has square corners (no transparency in corners),
    // so default to 0 to avoid "black corner" artifacts in some viewers.
    let default_corner_radius = if profile.eq_ignore_ascii_case("wallapop") { 0 } else { 30 };
    let corner_radius = req
        .corner_radius
        .unwrap_or(default_corner_radius)
        .clamp(0, size / 2);

    let code = QrCode::with_error_correction_level(req.text.as_bytes(), EcLevel::H)
        .map_err(|_| QrError::QrBuild)?;

    let img = {
        let _span = perf_scope!("qr.render");
        let finder_outer_roundness = if profile.eq_ignore_ascii_case("2dehands")
            || profile.eq_ignore_ascii_case("2ememain")
        {
            0.48
        } else if profile.eq_ignore_ascii_case("wallapop") {
            1.35
        } else if profile.eq_ignore_ascii_case("subito") {
            0.42
        } else {
            0.35
        };

        let finder_corner_style = if profile.eq_ignore_ascii_case("wallapop") {
            FinderCornerStyle::InnerSharp
        } else if profile.eq_ignore_ascii_case("subito") {
            FinderCornerStyle::InnerBoost
        } else {
            FinderCornerStyle::Uniform
        };

        let finder_inner_boost = if profile.eq_ignore_ascii_case("subito") { 0.45 } else { 0.0 };

        render_qr(
            &code,
            size,
            margin,
            os,
            module_roundness,
            finder_inner_corner,
            dark,
            light,
            finder_outer_roundness,
            finder_corner_style,
            finder_inner_boost,
        )
    };
    let mut img = DynamicImage::ImageRgba8(img);

    // Logo overlay priority:
    // 1) Subito -> local repo logo (app/data/logos/subito.png) with embedded fallback
    // 2) Known profile -> fixed default URL
    // 3) Back-compat: if request provides logoUrl -> use it (http fetch or local file)
    // 4) Otherwise: no logo (do not fail)

    if profile.eq_ignore_ascii_case("subito") {
        let _span = perf_scope!("qr.logo.subito.local");
        let logo = embedded_subito_logo()?;
        img = overlay_logo(img, logo, logo_scale, logo_badge, logo_badge_scale, logo_badge_color);
        drop(_span);
    } else if let Some(url) = profile_default_logo_url(profile) {
        // Remote logos are allowed by default. If you need to hard-disable network fetches, set DISABLE_REMOTE_LOGO=1.
        let disable = std::env::var("DISABLE_REMOTE_LOGO").unwrap_or_default();
        if disable == "1" || disable.eq_ignore_ascii_case("true") {
            return Err(QrError::LogoFetch(
                "remote logoUrl is disabled by DISABLE_REMOTE_LOGO=1".to_string(),
            ));
        }

        let _span = perf_scope!("qr.logo.http");
        let logo = fetch_logo_http_cached(http, url).await?;
        img = overlay_logo(img, logo, logo_scale, logo_badge, logo_badge_scale, logo_badge_color);
        drop(_span);
    } else if let Some(logo_url) = req.logo_url.as_deref() {
        let disable = std::env::var("DISABLE_REMOTE_LOGO").unwrap_or_default();
        if disable == "1" || disable.eq_ignore_ascii_case("true") {
            return Err(QrError::LogoFetch(
                "remote logoUrl is disabled by DISABLE_REMOTE_LOGO=1".to_string(),
            ));
        }

        if logo_url.starts_with("http://") || logo_url.starts_with("https://") {
            let _span = perf_scope!("qr.logo.http");
            let logo = fetch_logo_http_cached(http, logo_url).await?;
            img = overlay_logo(img, logo, logo_scale, logo_badge, logo_badge_scale, logo_badge_color);
            drop(_span);
        } else if let Some(path) = resolve_logo_path(profile, Some(logo_url)) {
            let _span = perf_scope!("qr.logo.disk");
            let logo = load_logo_from_disk_cached(&path)?;
            img = overlay_logo(img, logo, logo_scale, logo_badge, logo_badge_scale, logo_badge_color);
            drop(_span);
        }
    }

    if corner_radius > 0 {
        let _span = perf_scope!("qr.round_corners");
        img = round_corners(img, corner_radius);
        drop(_span);
    }

    Ok(img)
}

/// Build QR PNG bytes. Used by HTTP handler.
pub async fn build_qr_png(http: &reqwest::Client, req: QrRequest) -> Result<Vec<u8>, QrError> {
    let img = build_qr_image(http, req).await?;

    let mut png = Vec::new();
    {
        let _span = perf_scope!("qr.png.encode");
        let encoder = image::codecs::png::PngEncoder::new(&mut png);
        encoder
            .write_image(
                img.as_bytes(),
                img.width(),
                img.height(),
                img.color().into(),
            )
            .map_err(|_| QrError::PngEncode)?;
        drop(_span);
    }

    Ok(png)
}

fn render_qr(
    code: &QrCode,
    size: u32,
    margin: u32,
    os: u32,
    module_roundness: f32,
    finder_inner_corner: FinderInnerCorner,
    dark: [u8; 3],
    light: [u8; 3],
    finder_outer_roundness: f32,
    finder_corner_style: FinderCornerStyle,
    finder_inner_boost: f32,
) -> ImageBuffer<Rgba<u8>, Vec<u8>> {
    let opts = RenderOpts {
        size,
        margin,
        os,
        dark,
        light,
        module_roundness,
        finder_inner_corner,
        finder_outer_roundness,
        finder_corner_style,
        finder_inner_boost,
    };

    let os_img = crate::qr_render::render_stylized(code, opts);

    // Fast path: when os=1 and the renderer already hit the requested size.
    if os == 1 && os_img.width() == size && os_img.height() == size {
        return os_img;
    }

    // Only resample when needed (os>1 anti-aliasing, or renderer rounded to a nearby size).
    let dyn_img = DynamicImage::ImageRgba8(os_img);
    dyn_img.resize_exact(size, size, FilterType::Lanczos3).to_rgba8()
}

static LOGO_CACHE: Lazy<Mutex<HashMap<String, Arc<DynamicImage>>>> =
    Lazy::new(|| Mutex::new(HashMap::new()));

fn profile_default_logo_url(profile: &str) -> Option<&'static str> {
    match profile.to_ascii_lowercase().as_str() {
        // Restored from original Python services (fixed URLs)
        "markt" => Some("https://i.ibb.co/DfXf3X7x/Frame-40.png"),
        "wallapop" => Some("https://i.ibb.co/pvwMgd8k/Rectangle-355.png"),
        "2dehands" | "2ememain" | "twodehands" => Some("https://i.ibb.co/6crPXzDJ/2dehlogo.png"),
        "depop" => Some("https://i.ibb.co/v7N8Sbs/Frame-38.png"),
        // "kleize" in python maps to kleinanzeigen generator here
        "kleinanzeigen" | "kleize" => Some("https://i.ibb.co/mV9pQDLS/Frame-36.png"),
        // Subito: use embedded logo from repo (qrgen/app/assets/logos/subito.jpg)
        "subito" => Some("embedded:subito"),
        _ => None,
    }
}

fn embedded_subito_logo() -> Result<DynamicImage, QrError> {
    // Prefer runtime logo from repo-local app/data/logos (requested behavior),
    // fallback to embedded asset if the file is missing.
    let p = PathBuf::from("app/data/logos/subito.png");
    if p.exists() {
        return load_logo_from_disk_cached(&p);
    }

    static BYTES: &[u8] = include_bytes!("../../../app/assets/logos/subito.png");
    image::load_from_memory(BYTES).map_err(|_| QrError::LogoDecode)
}

fn profile_logo_default_filename(profile: &str) -> Option<&'static str> {
    match profile.to_ascii_lowercase().as_str() {
        "depop" => Some("depop.png"),
        "markt" => Some("markt.png"),
        "wallapop" => Some("wallapop.png"),
        "kleinanzeigen" => Some("kleinanzeigen.png"),
        "subito" => Some("subito.png"),
        "2dehands" => Some("2dehands.png"),
        "2ememain" => Some("2ememain.png"),
        "twodehands" => Some("2dehands.png"),
        _ => None,
    }
}

fn env_key_for_profile(prefix: &str, profile: &str) -> String {
    // profile is expected to be ascii-ish; keep digits.
    let up = profile
        .chars()
        .map(|c| if c.is_ascii_alphanumeric() { c.to_ascii_uppercase() } else { '_' })
        .collect::<String>();
    format!("{prefix}{up}")
}

fn resolve_logo_path(profile: &str, logo_url: Option<&str>) -> Option<PathBuf> {
    // 1) Explicit per-profile absolute path: LOGO_PATH_<PROFILE>
    let key = env_key_for_profile("LOGO_PATH_", profile);
    if let Ok(p) = std::env::var(&key) {
        if !p.trim().is_empty() {
            return Some(PathBuf::from(p));
        }
    }

    // 2) If request provided a logoUrl, treat it as a file name/path when it is not http(s).
    if let Some(u) = logo_url {
        let u = u.trim();
        if !u.is_empty() && !(u.starts_with("http://") || u.starts_with("https://")) {
            // Relative path is resolved against LOGO_DIR when set.
            if let Ok(dir) = std::env::var("LOGO_DIR") {
                let dir = dir.trim();
                if !dir.is_empty() {
                    return Some(PathBuf::from(dir).join(u));
                }
            }
            return Some(PathBuf::from(u));
        }
    }

    // 3) Per-profile filename in LOGO_DIR: LOGO_FILE_<PROFILE>
    let key = env_key_for_profile("LOGO_FILE_", profile);
    if let Ok(f) = std::env::var(&key) {
        let f = f.trim();
        if !f.is_empty() {
            if let Ok(dir) = std::env::var("LOGO_DIR") {
                let dir = dir.trim();
                if !dir.is_empty() {
                    return Some(PathBuf::from(dir).join(f));
                }
            }
            return Some(PathBuf::from(f));
        }
    }

    // 4) Default file name in LOGO_DIR (or fallback to repo-local ./app/data/logos).
    let dir = std::env::var("LOGO_DIR")
        .ok()
        .map(|s| s.trim().to_string())
        .filter(|s| !s.is_empty())
        .map(PathBuf::from)
        .or_else(|| {
            // Convenience fallback: when running from repo root (common in dev), keep logos inside the project.
            let p = PathBuf::from("app/data/logos");
            if p.exists() { Some(p) } else { None }
        })?;

    let fname = profile_logo_default_filename(profile)?;
    Some(dir.join(fname))
}

fn load_logo_from_disk_cached(path: &PathBuf) -> Result<DynamicImage, QrError> {
    let key = path.to_string_lossy().to_string();
    if let Some(img) = LOGO_CACHE.lock().get(&key) {
        return Ok((**img).clone());
    }

    let bytes = std::fs::read(path).map_err(|e| QrError::LogoFetch(format!("read {}: {e}", key)))?;
    let img = image::load_from_memory(&bytes).map_err(|_| QrError::LogoDecode)?;

    LOGO_CACHE.lock().insert(key, Arc::new(img.clone()));
    Ok(img)
}

async fn fetch_logo_http_cached(http: &reqwest::Client, url: &str) -> Result<DynamicImage, QrError> {
    if let Some(img) = LOGO_CACHE.lock().get(url) {
        return Ok((**img).clone());
    }

    let resp = http
        .get(url)
        .send()
        .await
        .map_err(|e| QrError::LogoFetch(e.to_string()))?;
    if !resp.status().is_success() {
        return Err(QrError::LogoFetch(format!("http {}", resp.status())));
    }
    let bytes = resp
        .bytes()
        .await
        .map_err(|e| QrError::LogoFetch(e.to_string()))?;

    let img = image::load_from_memory(&bytes).map_err(|_| QrError::LogoDecode)?;

    LOGO_CACHE
        .lock()
        .insert(url.to_string(), Arc::new(img.clone()));
    Ok(img)
}

fn overlay_logo(
    qr: DynamicImage,
    logo: DynamicImage,
    logo_scale: f32,
    badge: bool,
    badge_scale: f32,
    badge_color: [u8; 3],
) -> DynamicImage {

    let (w, h) = qr.dimensions();
    let target = ((w.min(h) as f32) * logo_scale) as u32;

    let logo = logo.resize_exact(target, target, FilterType::Lanczos3);

    let x = (w - target) / 2;
    let y = (h - target) / 2;

    let mut base = qr.to_rgba8();

    if badge {
        let badge_d = ((target as f32) * badge_scale).round() as u32;
        let badge_d = badge_d.clamp(target, w.min(h));
        let r = (badge_d as i32) / 2;
        let cx = (w as i32) / 2;
        let cy = (h as i32) / 2;
        let col = Rgba([badge_color[0], badge_color[1], badge_color[2], 255]);

        for yy in (cy - r).max(0)..(cy + r).min(h as i32) {
            for xx in (cx - r).max(0)..(cx + r).min(w as i32) {
                let dx = xx - cx;
                let dy = yy - cy;
                if dx * dx + dy * dy <= r * r {
                    base.put_pixel(xx as u32, yy as u32, col);
                }
            }
        }
    }

    let overlay = logo.to_rgba8();

    for oy in 0..target {
        for ox in 0..target {
            let p = overlay.get_pixel(ox, oy);
            let a = p[3] as f32 / 255.0;
            if a <= 0.0 {
                continue;
            }
            let bx = x + ox;
            let by = y + oy;
            let bp = base.get_pixel_mut(bx, by);
            let inv = 1.0 - a;
            bp.0[0] = (p[0] as f32 * a + bp.0[0] as f32 * inv) as u8;
            bp.0[1] = (p[1] as f32 * a + bp.0[1] as f32 * inv) as u8;
            bp.0[2] = (p[2] as f32 * a + bp.0[2] as f32 * inv) as u8;
            bp.0[3] = 255;
        }
    }

    DynamicImage::ImageRgba8(base)
}

fn round_corners(img: DynamicImage, radius: u32) -> DynamicImage {
    let (w, h) = img.dimensions();
    let mut rgba = img.to_rgba8();

    let r = radius as i32;
    for y in 0..(h as i32) {
        for x in 0..(w as i32) {
            let dx_left = x;
            let dx_right = (w as i32 - 1) - x;
            let dy_top = y;
            let dy_bottom = (h as i32 - 1) - y;

            let mut alpha = 255u8;
            if dx_left < r && dy_top < r {
                alpha = corner_alpha(dx_left, dy_top, r);
            } else if dx_right < r && dy_top < r {
                alpha = corner_alpha(dx_right, dy_top, r);
            } else if dx_left < r && dy_bottom < r {
                alpha = corner_alpha(dx_left, dy_bottom, r);
            } else if dx_right < r && dy_bottom < r {
                alpha = corner_alpha(dx_right, dy_bottom, r);
            }

            if alpha < 255 {
                let p = rgba.get_pixel_mut(x as u32, y as u32);
                p.0[3] = ((p.0[3] as u16 * alpha as u16) / 255) as u8;
            }
        }
    }

    DynamicImage::ImageRgba8(rgba)
}

fn corner_alpha(dx: i32, dy: i32, r: i32) -> u8 {
    let cx = r - 1;
    let cy = r - 1;
    let dist2 = (dx - cx) * (dx - cx) + (dy - cy) * (dy - cy);
    let r2 = r * r;
    if dist2 <= r2 { 255 } else { 0 }
}

fn parse_hex_color(s: &str) -> Result<[u8; 3], QrError> {
    let s = s.trim();
    let s = s.strip_prefix('#').unwrap_or(s);
    if s.len() != 6 {
        return Err(QrError::InvalidColor(s.to_string()));
    }
    let bytes = hex::decode(s).map_err(|_| QrError::InvalidColor(s.to_string()))?;
    Ok([bytes[0], bytes[1], bytes[2]])
}

