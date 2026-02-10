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

use crate::qr_render::{FinderInnerCorner, RenderOpts};
use qrcode::{EcLevel, QrCode};
use serde::Deserialize;
use utoipa::ToSchema;
use std::sync::Arc;
use thiserror::Error;

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

#[utoipa::path(
    post,
    path = "/qr",
    tag = "qrgen",
    request_body = QrRequest,
    responses(
        (status = 200, description = "QR PNG", content_type = "image/png"),
        (status = 400, description = "Bad request")
    )
)]
pub async fn qr_png(
    State(st): State<Arc<AppState>>,
    Json(req): Json<QrRequest>,
) -> Result<impl IntoResponse, QrError> {
    let png = build_qr_png(&st.http, req).await?;

    let mut headers = HeaderMap::new();
    headers.insert(header::CONTENT_TYPE, header::HeaderValue::from_static("image/png"));
    Ok((headers, png))
}

/// Build QR PNG bytes. Shared by HTTP handler and generators.
pub async fn build_qr_png(http: &reqwest::Client, req: QrRequest) -> Result<Vec<u8>, QrError> {
    let profile = req.profile.as_deref().unwrap_or("");

    // Keep historical sizes: wallapop base 800, others 1368.
    let default_size = if profile.eq_ignore_ascii_case("wallapop") { 800 } else { 1368 };
    let size = req.size.unwrap_or(default_size).clamp(128, 4096);

    let margin = req.margin.unwrap_or(2).clamp(0, 16);

    let default_dark = match profile.to_ascii_lowercase().as_str() {
        // Most templates use black; fall back to old default for generic usage.
        "wallapop" | "markt" | "subito" | "depop" | "kleinanzeigen" | "2dehands" | "2ememain" => "#000000",
        _ => "#4B6179",
    };

    let dark = parse_hex_color(req.color_dark.as_deref().unwrap_or(default_dark))?;
    let light = parse_hex_color(req.color_light.as_deref().unwrap_or("#FFFFFF"))?;

    let os = req.os.unwrap_or(3).clamp(1, 8);
    let module_roundness = req.module_roundness.unwrap_or(0.45).clamp(0.0, 0.5);

    let finder_inner_corner = match req.finder_inner_corner.as_deref().unwrap_or("outerOnly") {
        "outerOnly" | "outer_only" | "outer" => FinderInnerCorner::OuterOnly,
        "both" => FinderInnerCorner::Both,
        other => return Err(QrError::InvalidOption(format!("finderInnerCorner={other}"))),
    };

    let logo_scale = req.logo_scale.unwrap_or(0.22).clamp(0.05, 0.5);
    let logo_badge = req.logo_badge.unwrap_or(false);
    let logo_badge_scale = req.logo_badge_scale.unwrap_or(1.25).clamp(1.0, 2.0);
    let logo_badge_color = parse_hex_color(req.logo_badge_color.as_deref().unwrap_or("#FFFFFF"))?;

    let corner_radius = req.corner_radius.unwrap_or(30).clamp(0, size / 2);

    let code = QrCode::with_error_correction_level(req.text.as_bytes(), EcLevel::H)
        .map_err(|_| QrError::QrBuild)?;

    let img = render_qr(&code, size, margin, os, module_roundness, finder_inner_corner, dark, light);
    let mut img = DynamicImage::ImageRgba8(img);

    if let Some(url) = req.logo_url.as_deref() {
        let logo = fetch_logo(http, url).await?;
        img = overlay_logo(img, logo, logo_scale, logo_badge, logo_badge_scale, logo_badge_color);
    }

    if corner_radius > 0 {
        img = round_corners(img, corner_radius);
    }

    let mut png = Vec::new();
    let encoder = image::codecs::png::PngEncoder::new(&mut png);
    encoder
        .write_image(
            img.as_bytes(),
            img.width(),
            img.height(),
            img.color().into(),
        )
        .map_err(|_| QrError::PngEncode)?;

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
) -> ImageBuffer<Rgba<u8>, Vec<u8>> {
    let opts = RenderOpts {
        size,
        margin,
        os,
        dark,
        light,
        module_roundness,
        finder_inner_corner,
    };

    let os_img = crate::qr_render::render_stylized(code, opts);

    // Always downscale to requested size for anti-aliasing and predictable output.
    let dyn_img = DynamicImage::ImageRgba8(os_img);
    dyn_img.resize_exact(size, size, FilterType::Lanczos3).to_rgba8()
}

async fn fetch_logo(http: &reqwest::Client, url: &str) -> Result<DynamicImage, QrError> {
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

    image::load_from_memory(&bytes).map_err(|_| QrError::LogoDecode)
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
