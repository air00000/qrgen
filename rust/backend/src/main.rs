mod api;
mod apikey;
mod geo;
mod qr;
mod qr_render;
mod util;
mod figma;
mod cache;
mod openapi;
mod generator;

use std::{net::SocketAddr, sync::Arc};

use axum::{routing::{get, post}, Router};
use tracing::info;
use utoipa_swagger_ui::SwaggerUi;
use utoipa::OpenApi;

#[derive(Clone)]
pub struct AppState {
    pub http: reqwest::Client,
    pub api_keys: Arc<apikey::ApiKeys>,
}

#[tokio::main]
async fn main() {
    tracing_subscriber::fmt()
        .with_env_filter(tracing_subscriber::EnvFilter::from_default_env())
        .init();

    let host = std::env::var("BACKEND_HOST").unwrap_or_else(|_| "0.0.0.0".to_string());
    let port: u16 = std::env::var("BACKEND_PORT")
        .ok()
        .and_then(|s| s.parse().ok())
        .unwrap_or(8080);

    let api_keys_path = std::env::var("APIKEYS").ok();
    let api_keys = Arc::new(
        apikey::ApiKeys::load(api_keys_path.as_deref())
            .expect("failed to load api keys")
    );

    let state = AppState {
        http: reqwest::Client::new(),
        api_keys,
    };

    let openapi = openapi::ApiDoc::openapi();

    let app = Router::new()
        // Swagger UI + OpenAPI schema
        .merge(
            SwaggerUi::new("/docs")
                .url("/openapi.json", openapi)
        )

        // API
        .route("/get-geo", get(api::get_geo))
        .route("/generate", post(api::generate))
        .route("/api/status", get(api::api_status))
        // internal QR endpoint used by generators too
        .route("/qr", post(qr::qr_png))
        .route("/health", get(api::health))
        .with_state(Arc::new(state));

    let addr: SocketAddr = format!("{host}:{port}").parse().expect("bind addr");
    info!("Starting qrgen-backend on http://{addr}");

    let listener = tokio::net::TcpListener::bind(addr).await.unwrap();
    axum::serve(listener, app).await.unwrap();
}
