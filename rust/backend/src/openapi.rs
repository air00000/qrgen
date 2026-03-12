use utoipa::OpenApi;

use crate::api;

#[derive(OpenApi)]
#[openapi(
    paths(
        api::health,
        api::api_status,
        api::get_geo,
        api::generate,
    ),
    components(
        schemas(api::UniversalRequest)
    ),
    tags(
        (name = "qrgen", description = "qrgen backend API")
    )
)]
pub struct ApiDoc;
