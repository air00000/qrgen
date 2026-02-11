use serde_json::Value;
use thiserror::Error;

#[derive(Debug, Error)]
pub enum GenError {
    #[error("bad request: {0}")]
    BadRequest(String),
    #[error("not implemented: {0}")]
    NotImplemented(String),
    #[error("internal: {0}")]
    Internal(String),
}

pub fn geo_config() -> Value {
    // TODO: move to a shared JSON file and keep 1:1 with Python GEO_CONFIG.
    serde_json::json!({})
}

pub fn services_index() -> Value {
    geo_config()
}

#[allow(clippy::too_many_arguments)]
pub async fn generate(
    _http: &reqwest::Client,
    _country: &str,
    _service: &str,
    _method: &str,
    _title: &str,
    _price: f64,
    _url: Option<&str>,
    _photo: Option<&str>,
    _name: Option<&str>,
    _address: Option<&str>,
    _seller_name: Option<&str>,
    _seller_photo: Option<&str>,
) -> Result<Vec<u8>, GenError> {
    Err(GenError::NotImplemented(
        "Rust generators are not implemented yet (rust-only reset)".into(),
    ))
}
