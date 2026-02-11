use once_cell::sync::Lazy;
use parking_lot::Mutex;
use rusttype::Font;
use std::{collections::HashMap, path::PathBuf, sync::Arc};

use super::GenError;

static FONT_CACHE: Lazy<Mutex<HashMap<String, Arc<Font<'static>>>>> =
    Lazy::new(|| Mutex::new(HashMap::new()));

fn fonts_dir() -> PathBuf {
    let project_root = std::env::var("PROJECT_ROOT").ok().unwrap_or_else(|| {
        let manifest_dir = std::path::Path::new(env!("CARGO_MANIFEST_DIR"));
        manifest_dir.join("../..").to_string_lossy().to_string()
    });
    PathBuf::from(project_root)
        .join("app")
        .join("assets")
        .join("fonts")
}

pub fn load_font_cached(name: &str) -> Result<Arc<Font<'static>>, GenError> {
    if let Some(f) = FONT_CACHE.lock().get(name) {
        return Ok(Arc::clone(f));
    }

    let bytes = std::fs::read(fonts_dir().join(name))
        .map_err(|e| GenError::Internal(format!("failed to read font {name}: {e}")))?;
    let f = Font::try_from_vec(bytes)
        .ok_or_else(|| GenError::Internal(format!("failed to parse font {name}")))?;

    let f = Arc::new(f);
    FONT_CACHE
        .lock()
        .insert(name.to_string(), Arc::clone(&f));
    Ok(f)
}
