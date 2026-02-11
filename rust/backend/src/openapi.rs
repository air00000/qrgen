use utoipa::OpenApi;

use crate::api;

#[derive(OpenApi)]
#[openapi(
    paths(
        api::health,
        api::services,
        api::get_geo,
        api::api_status,
        api::generate,
    ),
    components(
        schemas(api::UniversalRequest, api::HealthResponse)
    ),
    tags(
        (name = "qrgen", description = "qrgen Rust backend API")
    )
)]
pub struct ApiDoc;
