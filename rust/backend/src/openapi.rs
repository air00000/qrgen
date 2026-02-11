use utoipa::OpenApi;

use crate::{api, qr};

#[derive(OpenApi)]
#[openapi(
    paths(
        api::health,
        api::api_status,
        api::get_geo,
        api::generate,
        qr::qr_png,
    ),
    components(
        schemas(api::UniversalRequest, qr::QrRequest)
    ),
    tags(
        (name = "qrgen", description = "qrgen backend API")
    )
)]
pub struct ApiDoc;
