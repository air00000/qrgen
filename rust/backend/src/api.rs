use std::sync::Arc;

use axum::{
    extract::State,
    http::{HeaderMap, StatusCode},
    response::IntoResponse,
    Json,
};
use serde::{Deserialize, Serialize};
use utoipa::ToSchema;

use crate::{services, AppState};

#[derive(Debug, Deserialize, ToSchema)]
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
}

#[derive(Debug, Serialize, ToSchema)]
pub struct HealthResponse {
    pub status: String,
}

#[utoipa::path(get, path = "/health", tag = "qrgen", responses((status=200, body=HealthResponse)))]
pub async fn health() -> impl IntoResponse {
    Json(HealthResponse { status: "ok".into() })
}

fn extract_api_key(headers: &HeaderMap) -> Option<String> {
    headers
        .get("X-API-Key")
        .or_else(|| headers.get("x-api-key"))
        .and_then(|v| v.to_str().ok())
        .map(|s| s.to_string())
}

fn verify_api_key(st: &AppState, headers: &HeaderMap) -> Result<String, (StatusCode, String)> {
    let key = extract_api_key(headers).ok_or((
        StatusCode::UNAUTHORIZED,
        "API key required. Please provide X-API-Key header".to_string(),
    ))?;
    if !st.api_keys.validate(&key) {
        return Err((StatusCode::UNAUTHORIZED, "Invalid API key".to_string()));
    }
    Ok(st.api_keys.name(&key).unwrap_or_else(|| "default".into()))
}

#[utoipa::path(
    get,
    path = "/api/status",
    tag = "qrgen",
    params(("X-API-Key" = String, Header, description = "API key")),
    responses((status=200, body=serde_json::Value), (status=401, description="Unauthorized"))
)]
pub async fn api_status(
    State(st): State<Arc<AppState>>,
    headers: HeaderMap,
) -> Result<impl IntoResponse, (StatusCode, String)> {
    let key_name = verify_api_key(&st, &headers)?;
    Ok(Json(serde_json::json!({
        "status": "active",
        "key_name": key_name,
        "message": "API key is valid"
    })))
}

#[utoipa::path(
    get,
    path = "/get-geo",
    tag = "qrgen",
    params(("X-API-Key" = String, Header, description = "API key")),
    responses((status=200, body=serde_json::Value), (status=401, description="Unauthorized"))
)]
pub async fn get_geo(
    State(st): State<Arc<AppState>>,
    headers: HeaderMap,
) -> Result<impl IntoResponse, (StatusCode, String)> {
    let _ = verify_api_key(&st, &headers)?;
    Ok(Json(services::geo_config()))
}

#[utoipa::path(
    get,
    path = "/services",
    tag = "qrgen",
    responses((status=200, body=serde_json::Value))
)]
pub async fn services() -> impl IntoResponse {
    Json(services::services_index())
}

#[utoipa::path(
    post,
    path = "/generate",
    tag = "qrgen",
    request_body = UniversalRequest,
    params(("X-API-Key" = String, Header, description = "API key")),
    responses(
        (status=200, description="Generated PNG", content_type="image/png"),
        (status=400, description="Bad request"),
        (status=401, description="Unauthorized"),
        (status=501, description="Not implemented")
    )
)]
pub async fn generate(
    State(st): State<Arc<AppState>>,
    headers: HeaderMap,
    Json(req): Json<UniversalRequest>,
) -> Result<impl IntoResponse, (StatusCode, String)> {
    let _ = verify_api_key(&st, &headers)?;

    let title = req.title.as_deref().unwrap_or("");
    let price = req.price.unwrap_or(0.0);

    let png = services::generate(
        &st.http,
        &req.country,
        &req.service,
        &req.method,
        title,
        price,
        req.url.as_deref(),
        req.photo.as_deref(),
        req.name.as_deref(),
        req.address.as_deref(),
        req.seller_name.as_deref(),
        req.seller_photo.as_deref(),
    )
    .await;

    match png {
        Ok(png) => Ok(([(axum::http::header::CONTENT_TYPE, "image/png")], png)),
        Err(services::GenError::BadRequest(msg)) => Err((StatusCode::BAD_REQUEST, msg)),
        Err(services::GenError::NotImplemented(msg)) => Err((StatusCode::NOT_IMPLEMENTED, msg)),
        Err(e) => Err((StatusCode::INTERNAL_SERVER_ERROR, e.to_string())),
    }
}
