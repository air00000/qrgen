pub mod markt;
pub mod subito;
pub mod wallapop;
pub mod twodehands;
pub mod kleinanzeigen;
pub mod conto;
pub mod depop;

mod font_cache;

use thiserror::Error;

#[derive(Debug, Error)]
pub enum GenError {
    #[error("bad request: {0}")]
    BadRequest(String),
    #[error("not implemented: {0}")]
    NotImplemented(String),
    #[error("figma: {0}")]
    Figma(#[from] crate::figma::FigmaError),
    #[error("cache: {0}")]
    Cache(#[from] crate::cache::CacheError),
    #[error("image: {0}")]
    Image(String),
    #[error("internal: {0}")]
    Internal(String),
}
