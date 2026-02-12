//! File cache layer (ported from app/cache/figma_cache.py)
//!
//! On-disk layout MUST stay compatible with the legacy Python implementation:
//!   qrgen/app/figma_cache/{service}_structure.json
//!   qrgen/app/figma_cache/{service}_template.png

use std::path::{Path, PathBuf};

use thiserror::Error;

#[derive(Debug, Error)]
pub enum CacheError {
    #[error("io: {0}")]
    Io(#[from] std::io::Error),
    #[error("json: {0}")]
    Json(#[from] serde_json::Error),
    #[error("cache miss for service: {0}")]
    Miss(String),
}

#[derive(Clone, Debug)]
pub struct FigmaCache {
    service_name: String,
    structure_path: PathBuf,
    template_path: PathBuf,
}

impl FigmaCache {
    pub fn new(service_name: impl Into<String>) -> Self {
        let service_name = service_name.into();
        let dir = cache_dir();
        let structure_path = dir.join(format!("{service_name}_structure.json"));
        let template_path = dir.join(format!("{service_name}_template.png"));
        Self { service_name, structure_path, template_path }
    }

    pub fn exists(&self) -> bool {
        self.structure_path.exists() && self.template_path.exists()
    }

    pub fn load(&self) -> Result<(serde_json::Value, Vec<u8>), CacheError> {
        if !self.exists() {
            return Err(CacheError::Miss(self.service_name.clone()));
        }
        let structure_str = std::fs::read_to_string(&self.structure_path)?;
        let structure: serde_json::Value = serde_json::from_str(&structure_str)?;
        let png = std::fs::read(&self.template_path)?;
        Ok((structure, png))
    }

    pub fn save(&self, structure: &serde_json::Value, template_png: &[u8]) -> Result<(), CacheError> {
        if let Some(parent) = self.structure_path.parent() {
            std::fs::create_dir_all(parent)?;
        }
        let structure_pretty = serde_json::to_string_pretty(structure)?;
        std::fs::write(&self.structure_path, structure_pretty)?;

        // Optimize Figma template PNG once at cache time (speed-first at request time).
        // Can be disabled with FIGMA_CACHE_OPTIMIZE=0.
        let optimize = std::env::var("FIGMA_CACHE_OPTIMIZE").unwrap_or_else(|_| "1".to_string());
        let optimize = !(optimize == "0" || optimize.eq_ignore_ascii_case("false"));

        let png_out: Vec<u8> = if optimize {
            // oxipng is lossless but CPU-heavy; cache is written rarely so it's OK here.
            // Moderate preset by default; override with FIGMA_CACHE_OXIPNG_LEVEL.
            let level = std::env::var("FIGMA_CACHE_OXIPNG_LEVEL")
                .ok()
                .and_then(|v| v.parse::<u8>().ok())
                .unwrap_or(4)
                .min(6);

            let mut opts = oxipng::Options::from_preset(level);
            opts.fix_errors = true;

            match oxipng::optimize_from_memory(template_png, &opts) {
                Ok(out) => out,
                Err(_) => template_png.to_vec(),
            }
        } else {
            template_png.to_vec()
        };

        std::fs::write(&self.template_path, png_out)?;
        Ok(())
    }

    pub fn structure_path(&self) -> &Path { &self.structure_path }
    pub fn template_path(&self) -> &Path { &self.template_path }
}

/// Legacy-compatible cache directory.
///
/// Python version uses: Path(CFG.BASE_DIR) / "figma_cache" where BASE_DIR is qrgen/app.
/// In Rust backend we default to: {PROJECT_ROOT}/app/figma_cache.
pub fn cache_dir() -> PathBuf {
    if let Ok(p) = std::env::var("FIGMA_CACHE_DIR") {
        return PathBuf::from(p);
    }

    let project_root = std::env::var("PROJECT_ROOT").ok().unwrap_or_else(|| {
        // rust/backend -> ../.. == qrgen/
        let manifest_dir = Path::new(env!("CARGO_MANIFEST_DIR"));
        manifest_dir.join("../..").to_string_lossy().to_string()
    });
    PathBuf::from(project_root).join("app").join("figma_cache")
}
