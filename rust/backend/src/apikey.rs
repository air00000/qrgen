use parking_lot::RwLock;
use std::{collections::HashMap, fs, path::PathBuf, time::SystemTime};

/// Matches Python logic in `app/services/apikey.py`.
///
/// Python stores API keys in JSON file `app/data/api_keys.json` as:
/// `{ "api_xxx": "Name" }`.
///
/// We keep a small in-memory cache and auto-reload when the file mtime changes.
#[derive(Default)]
pub struct ApiKeys {
    path: PathBuf,
    mtime: RwLock<Option<SystemTime>>,
    inner: RwLock<HashMap<String, String>>, // key -> name
}

impl ApiKeys {
    pub fn load(path: Option<&str>) -> std::io::Result<Self> {
        let path = path
            .map(PathBuf::from)
            .unwrap_or_else(|| PathBuf::from("app/data/api_keys.json"));

        let this = Self {
            path,
            mtime: RwLock::new(None),
            inner: RwLock::new(HashMap::new()),
        };
        // best-effort preload
        this.refresh();
        Ok(this)
    }

    fn refresh(&self) {
        let meta = match fs::metadata(&self.path) {
            Ok(m) => m,
            Err(_) => {
                *self.inner.write() = HashMap::new();
                *self.mtime.write() = None;
                return;
            }
        };

        let mtime = meta.modified().ok();
        let prev = *self.mtime.read();
        if mtime.is_some() && mtime == prev {
            return;
        }

        if let Ok(text) = fs::read_to_string(&self.path) {
            if let Ok(map) = serde_json::from_str::<HashMap<String, String>>(&text) {
                *self.inner.write() = map;
                *self.mtime.write() = mtime;
                return;
            }
        }

        // If JSON is broken, treat as empty (same spirit as Python best-effort)
        *self.inner.write() = HashMap::new();
        *self.mtime.write() = mtime;
    }

    pub fn validate(&self, key: &str) -> bool {
        self.refresh();
        self.inner.read().contains_key(key)
    }

    pub fn name(&self, key: &str) -> Option<String> {
        self.refresh();
        self.inner.read().get(key).cloned()
    }
}
