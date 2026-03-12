use utoipa::OpenApi;

use crate::api;

#[derive(OpenApi)]
#[openapi(
    paths(
        api::health,
        api::api_status,
        api::get_geo,
        api::get_booking_geo,
        api::generate,
        api::generate_booking_endpoint,
    ),
    components(
        schemas(api::UniversalRequest, api::BookingRequest)
    ),
    tags(
        (name = "qrgen", description = "qrgen backend API"),
        (name = "booking", description = "booking-specific endpoints")
    )
)]
pub struct ApiDoc;
