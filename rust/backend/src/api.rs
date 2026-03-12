use std::sync::Arc;

use axum::{
    extract::State,
    http::{HeaderMap, StatusCode},
    response::IntoResponse,
    Json,
};
use serde::Deserialize;
use utoipa::ToSchema;

use crate::{geo, qr, AppState};

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
    pub phone: Option<String>,
    pub address: Option<String>,
    pub seller_name: Option<String>,
    pub seller_photo: Option<String>,
    pub knopbook1: Option<String>,
    pub knopbook2: Option<String>,

    // booking fields
    pub city: Option<String>,
    pub hotel_name: Option<String>,
    pub checkin_date: Option<String>,
    pub checkout_date: Option<String>,
    pub checkin_time: Option<String>,
    pub checkout_time: Option<String>,
    pub nights: Option<i32>,
    pub beds: Option<i32>,
    pub confirmation_number: Option<String>,
    pub pin_code: Option<String>,

    // QR-only params are not part of /generate schema.
}

#[utoipa::path(
    get,
    path = "/health",
    tag = "qrgen",
    responses(
        (status = 200, description = "Health check", body = serde_json::Value)
    )
)]
pub async fn health() -> impl IntoResponse {
    Json(serde_json::json!({"status":"ok"}))
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
    path = "/get-geo",
    tag = "qrgen",
    params(
        ("X-API-Key" = String, Header, description = "API key")
    ),
    responses(
        (status = 200, description = "Geo config", body = serde_json::Value),
        (status = 401, description = "Unauthorized")
    )
)]
pub async fn get_geo(
    State(st): State<Arc<AppState>>,
    headers: HeaderMap,
) -> Result<impl IntoResponse, (StatusCode, String)> {
    let _key_name = verify_api_key(&st, &headers)?;
    Ok(Json(geo::geo_config()))
}

#[utoipa::path(
    get,
    path = "/api/status",
    tag = "qrgen",
    params(
        ("X-API-Key" = String, Header, description = "API key")
    ),
    responses(
        (status = 200, description = "API key status", body = serde_json::Value),
        (status = 401, description = "Unauthorized")
    )
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
    post,
    path = "/generate",
    tag = "qrgen",
    request_body = UniversalRequest,
    params(
        ("X-API-Key" = String, Header, description = "API key")
    ),
    responses(
        (status = 200, description = "Generated PNG", content_type = "image/png"),
        (status = 400, description = "Bad request"),
        (status = 401, description = "Unauthorized"),
        (status = 500, description = "Internal error")
    )
)]
pub async fn generate(
    State(st): State<Arc<AppState>>,
    headers: HeaderMap,
    Json(req): Json<UniversalRequest>,
) -> Result<impl IntoResponse, (StatusCode, String)> {
    let _key_name = verify_api_key(&st, &headers)?;

    let title = req.title.as_deref().unwrap_or("");
    let price = req.price.unwrap_or(0.0);

    let data = match req.service.as_str() {
        // QR-only generation moved from /qr to /generate.
        // Usage: service="qr", method=<profile>, url=<text>.
        // Style is inferred by profile; no per-request QR style fields are accepted.
        "qr" => {
            let text = req.url.as_deref().unwrap_or(title);
            let payload = serde_json::json!({
                "text": text,
                "profile": req.method
            });

            let qr_req: qr::QrRequest = match serde_json::from_value(payload) {
                Ok(v) => v,
                Err(e) => return Err((StatusCode::INTERNAL_SERVER_ERROR, e.to_string())),
            };

            qr::build_qr_png(&st.http, qr_req)
                .await
                .map_err(|e| crate::generator::GenError::BadRequest(e.to_string()))
        }
        "markt" => {
            crate::generator::markt::generate_markt(
                &st.http,
                &req.country,
                &req.method,
                title,
                price,
                req.photo.as_deref(),
                req.url.as_deref(),
            )
            .await
        }
        "subito" => {
            crate::generator::subito::generate_subito(
                &st.http,
                &req.country,
                &req.method,
                title,
                price,
                req.photo.as_deref(),
                req.url.as_deref(),
                req.name.as_deref(),
                req.address.as_deref(),
            )
            .await
        }
        "wallapop" => {
            crate::generator::wallapop::generate_wallapop(
                &st.http,
                &req.country,
                &req.method,
                title,
                price,
                req.photo.as_deref(),
                req.seller_name.as_deref(),
                req.seller_photo.as_deref(),
                req.url.as_deref(),
            )
            .await
        }
        "2dehands" | "2ememain" => {
            let url = req.url.as_deref().unwrap_or("");
            crate::generator::twodehands::generate_twodehands(
                &st.http,
                &req.service,
                title,
                price,
                req.photo.as_deref(),
                url,
            )
            .await
        }
        "kleinanzeigen" => {
            let url = req.url.as_deref().unwrap_or("");
            crate::generator::kleinanzeigen::generate_kleinanzeigen(
                &st.http,
                title,
                price,
                req.photo.as_deref(),
                url,
            )
            .await
        }
        "conto" => {
            crate::generator::conto::generate_conto(&st.http, title, price).await
        }
        "depop" => {
            match req.method.as_str() {
                "qr" => {
                    let url = req.url.as_deref().unwrap_or("");
                    crate::generator::depop::generate_depop(
                        &st.http,
                        title,
                        price,
                        req.seller_name.as_deref().unwrap_or(""),
                        req.photo.as_deref(),
                        req.seller_photo.as_deref(),
                        url,
                    )
                    .await
                }
                other => {
                    crate::generator::depop::generate_depop_variant(
                        &st.http,
                        other,
                        title,
                        price,
                        req.photo.as_deref(),
                    )
                    .await
                }
            }
        }
        "gumtree" => {
            crate::generator::gumtree::generate_gumtree(
                &st.http,
                &req.country,
                &req.method,
                title,
                price,
                req.photo.as_deref(),
                req.url.as_deref(),
            )
            .await
        }
        "booking" => {
            crate::generator::booking::generate_booking(
                &st.http,
                &req.country,
                title,
                price,
                req.knopbook1.as_deref(),
                req.knopbook2.as_deref(),
                crate::generator::booking::BookingInput {
                    guest_name: req.name.as_deref(),
                    city: req.city.as_deref(),
                    hotel_name: req.hotel_name.as_deref(),
                    hotel_address: req.address.as_deref(),
                    phone: req.phone.as_deref(),
                    nights: req.nights,
                    beds: req.beds,
                    checkin_date: req.checkin_date.as_deref(),
                    checkout_date: req.checkout_date.as_deref(),
                    checkin_time: req.checkin_time.as_deref(),
                    checkout_time: req.checkout_time.as_deref(),
                    confirmation_number: req.confirmation_number.as_deref(),
                    pin_code: req.pin_code.as_deref(),
                },
            ).await
        }
        other => Err(crate::generator::GenError::NotImplemented(format!(
            "service not implemented in Rust yet: {other}"
        ))),
    };

    match data {
        Ok(bytes) => {
            let ctype = if req.service == "booking" { "application/pdf" } else { "image/png" };
            Ok(([(axum::http::header::CONTENT_TYPE, ctype)], bytes))
        }
        Err(crate::generator::GenError::BadRequest(msg)) => Err((StatusCode::BAD_REQUEST, msg)),
        Err(crate::generator::GenError::NotImplemented(msg)) => Err((StatusCode::BAD_REQUEST, msg)),
        Err(e) => Err((StatusCode::INTERNAL_SERVER_ERROR, e.to_string())),
    }
}
