use serde::Deserialize;
use std::{
    collections::HashMap,
    fs,
    path::{Path, PathBuf},
    sync::Arc,
};

#[derive(Clone)]
pub struct AppState {
    pub api_keys: Arc<HashMap<String, String>>, // api_key -> name
    pub api_keys_path: Arc<PathBuf>,
}

#[derive(thiserror::Error, Debug)]
pub enum StateError {
    #[error("failed to read api keys file at {path}: {source}")]
    ReadApiKeys { path: PathBuf, source: std::io::Error },

    #[error("failed to parse api keys JSON at {path}: {source}")]
    ParseApiKeys { path: PathBuf, source: serde_json::Error },
}

impl AppState {
    pub fn load() -> Result<Self, StateError> {
        let api_keys_path = std::env::var("API_KEYS_PATH")
            .map(PathBuf::from)
            .unwrap_or_else(|_| PathBuf::from("app/data/api_keys.json"));

        let api_keys = load_api_keys(&api_keys_path)?;

        Ok(Self {
            api_keys: Arc::new(api_keys),
            api_keys_path: Arc::new(api_keys_path),
        })
    }

    pub fn key_name(&self, api_key: &str) -> Option<&str> {
        self.api_keys.get(api_key).map(|s| s.as_str())
    }
}

fn load_api_keys(path: &Path) -> Result<HashMap<String, String>, StateError> {
    // Mirror Python behavior: missing file -> empty set of keys.
    let content = match fs::read_to_string(path) {
        Ok(s) => s,
        Err(e) if e.kind() == std::io::ErrorKind::NotFound => return Ok(HashMap::new()),
        Err(e) => {
            return Err(StateError::ReadApiKeys {
                path: path.to_path_buf(),
                source: e,
            })
        }
    };

    serde_json::from_str::<HashMap<String, String>>(&content).map_err(|e| StateError::ParseApiKeys {
        path: path.to_path_buf(),
        source: e,
    })
}
