use crate::openapi::ApiDoc;
use axum::{
    body::Body,
    extract::{Json, State},
    http::{header, HeaderMap, HeaderValue, Request, StatusCode},
    middleware::Next,
    response::{IntoResponse, Response},
};
use serde::{Deserialize, Serialize};
use serde_json::json;

use crate::openapi::GEO_CONFIG;
use crate::state::AppState;

#[derive(Debug, Deserialize, Serialize, utoipa::ToSchema)]
pub struct UniversalRequest {
    pub country: String,
    pub service: String,
    pub method: String,

    pub title: Option<String>,
    pub price: Option<f64>,
    pub url: Option<String>,
    pub photo: Option<String>,
    pub name: Option<String>,
    pub address: Option<String>,
    pub seller_name: Option<String>,
    pub seller_photo: Option<String>,

    // Unknown fields are allowed by default in serde.
}

/// Injected into request extensions by auth middleware.
#[derive(Clone, Debug)]
pub struct KeyName(pub String);

pub async fn auth_middleware(
    State(state): State<AppState>,
    mut req: Request<Body>,
    next: Next,
) -> Response {
    let key = match req.headers().get("x-api-key").and_then(|v| v.to_str().ok()) {
        Some(v) if !v.is_empty() => v,
        _ => {
            return (
                StatusCode::UNAUTHORIZED,
                Json(json!({
                    "detail": "API key required. Please provide X-API-Key header"
                })),
            )
                .into_response()
        }
    };

    match state.key_name(key) {
        Some(name) => {
            req.extensions_mut().insert(KeyName(name.to_string()));
            next.run(req).await
        }
        None => (
            StatusCode::UNAUTHORIZED,
            Json(json!({"detail": "Invalid API key"})),
        )
            .into_response(),
    }
}

#[utoipa::path(
    get,
    path = "/health",
    responses(
        (status = 200, description = "Health check", body = serde_json::Value)
    )
)]
pub async fn health() -> impl IntoResponse {
    Json(json!({"status": "ok"}))
}

#[utoipa::path(
    get,
    path = "/services",
    security(
        ("api_key" = [])
    ),
    responses(
        (status = 200, description = "GEO config / services", body = serde_json::Value),
        (status = 401, description = "Unauthorized")
    )
)]
pub async fn services() -> impl IntoResponse {
    Json(GEO_CONFIG.clone())
}

const ONE_BY_ONE_PNG: &[u8] = include_bytes!("../assets/1x1.png");

#[utoipa::path(
    post,
    path = "/generate",
    request_body = UniversalRequest,
    security(
        ("api_key" = [])
    ),
    responses(
        (status = 200, description = "Generated image", content_type = "image/png", body = Vec<u8>),
        (status = 400, description = "Invalid request", body = serde_json::Value),
        (status = 401, description = "Unauthorized"),
        (status = 500, description = "Internal error", body = serde_json::Value)
    )
)]
pub async fn generate(
    State(_state): State<AppState>,
    Json(req): Json<UniversalRequest>,
) -> impl IntoResponse {
    // Normalize
    let country = req.country.to_lowercase();
    let service = req.service.to_lowercase();
    let method = req.method.to_lowercase();

    // Validate against GEO_CONFIG like Python does
    let country_obj = GEO_CONFIG.get(&country);
    if country_obj.is_none() {
        return (
            StatusCode::BAD_REQUEST,
            Json(json!({
                "detail": format!("Unknown country: {country}. Available: {}", available_countries())
            })),
        )
            .into_response();
    }

    let services = &country_obj.unwrap()["services"];
    if services.get(&service).is_none() {
        let available = services
            .as_object()
            .map(|o| o.keys().cloned().collect::<Vec<_>>())
            .unwrap_or_default();
        return (
            StatusCode::BAD_REQUEST,
            Json(json!({
                "detail": format!("Unknown service '{service}' for country '{country}'. Available: {available:?}")
            })),
        )
            .into_response();
    }

    let methods = &services[&service]["methods"];
    if methods.get(&method).is_none() {
        let available = methods
            .as_object()
            .map(|o| o.keys().cloned().collect::<Vec<_>>())
            .unwrap_or_default();
        return (
            StatusCode::BAD_REQUEST,
            Json(json!({
                "detail": format!("Unknown method '{method}' for service '{service}'. Available: {available:?}")
            })),
        )
            .into_response();
    }

    // TODO: Implement generation logic in Rust.
    // For now return a valid PNG placeholder so clients can integrate/test.
    let mut headers = HeaderMap::new();
    headers.insert(
        header::CONTENT_TYPE,
        HeaderValue::from_static("image/png"),
    );

    (StatusCode::OK, headers, ONE_BY_ONE_PNG).into_response()
}

fn available_countries() -> String {
    let keys = GEO_CONFIG
        .as_object()
        .map(|o| o.keys().cloned().collect::<Vec<_>>())
        .unwrap_or_default();
    format!("{keys:?}")
}

// Ensure ApiDoc is referenced so it isn't optimized away in some builds.
#[allow(dead_code)]
fn _openapi_sanity() {
    let _ = ApiDoc::openapi();
}
