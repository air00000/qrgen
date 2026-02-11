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
    pub size: Option<u32>,
    pub margin: Option<u32>,
    pub color_dark: Option<String>,
    pub color_light: Option<String>,
    pub logo_url: Option<String>,
    pub logo_scale: Option<f32>,
    pub corner_radius: Option<u32>,
}

#[derive(Debug, Error)]
pub enum QrError {
    #[error("invalid color: {0}")]
    InvalidColor(String),
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
    let size = req.size.unwrap_or(1368).clamp(128, 4096);
    let margin = req.margin.unwrap_or(2).clamp(0, 16);
    let dark = parse_hex_color(req.color_dark.as_deref().unwrap_or("#4B6179"))?;
    let light = parse_hex_color(req.color_light.as_deref().unwrap_or("#FFFFFF"))?;
    let logo_scale = req.logo_scale.unwrap_or(0.22).clamp(0.05, 0.5);
    let corner_radius = req.corner_radius.unwrap_or(30).clamp(0, size / 2);

    let code = QrCode::with_error_correction_level(req.text.as_bytes(), EcLevel::H)
        .map_err(|_| QrError::QrBuild)?;

    let img = render_qr(&code, size, margin, dark, light);
    let mut img = DynamicImage::ImageRgba8(img);

    if let Some(url) = req.logo_url.as_deref() {
        let logo = fetch_logo(http, url).await?;
        img = overlay_logo(img, logo, logo_scale);
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

fn render_qr(code: &QrCode, size: u32, margin: u32, dark: [u8; 3], light: [u8; 3]) -> ImageBuffer<Rgba<u8>, Vec<u8>> {
    let width_modules = code.width() as u32;
    let total_modules = width_modules + 2 * margin;
    let pixels_per_module = (size / total_modules).max(1);
    let actual_size = total_modules * pixels_per_module;

    let mut img = ImageBuffer::from_pixel(
        actual_size,
        actual_size,
        Rgba([light[0], light[1], light[2], 255]),
    );

    for y in 0..width_modules {
        for x in 0..width_modules {
            if matches!(code[(x as usize, y as usize)], qrcode::Color::Dark) {
                let px0 = (x + margin) * pixels_per_module;
                let py0 = (y + margin) * pixels_per_module;
                for py in py0..(py0 + pixels_per_module) {
                    for px in px0..(px0 + pixels_per_module) {
                        img.put_pixel(px, py, Rgba([dark[0], dark[1], dark[2], 255]));
                    }
                }
            }
        }
    }

    if actual_size != size {
        let dyn_img = DynamicImage::ImageRgba8(img);
        dyn_img
            .resize_exact(size, size, FilterType::Lanczos3)
            .to_rgba8()
    } else {
        img
    }
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

fn overlay_logo(qr: DynamicImage, logo: DynamicImage, logo_scale: f32) -> DynamicImage {
    let (w, h) = qr.dimensions();
    let target = ((w.min(h) as f32) * logo_scale) as u32;

    let logo = logo.resize_exact(target, target, FilterType::Lanczos3);

    let x = (w - target) / 2;
    let y = (h - target) / 2;

    let mut base = qr.to_rgba8();
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
