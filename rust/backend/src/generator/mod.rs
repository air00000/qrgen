pub mod conto;
pub mod depop;
pub mod gumtree;
#[cfg(feature = "skia_hb")]
pub mod gumtree_skia_hb;
pub mod kleinanzeigen;
pub mod markt;
pub mod subito;
pub mod twodehands;
pub mod wallapop;

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
