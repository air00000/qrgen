//! Figma API client (ported from app/services/figma.py)

use std::time::Duration;

use reqwest::StatusCode;
use thiserror::Error;

#[derive(Debug, Error)]
pub enum FigmaError {
    #[error("FIGMA_PAT is not set")]
    MissingPat,
    #[error("TEMPLATE_FILE_KEY is not set")]
    MissingFileKey,
    #[error("http: {0}")]
    Http(String),
    #[error("json: {0}")]
    Json(#[from] serde_json::Error),
    #[error("figma api error {status}: {body}")]
    Api { status: StatusCode, body: String },
    #[error("missing image url for node {0}")]
    MissingImageUrl(String),
}

fn figma_api_url() -> String {
    std::env::var("FIGMA_API_URL").unwrap_or_else(|_| "https://api.figma.com/v1".to_string())
}

fn figma_pat() -> Result<String, FigmaError> {
    std::env::var("FIGMA_PAT").map_err(|_| FigmaError::MissingPat)
}

fn template_file_key() -> Result<String, FigmaError> {
    std::env::var("TEMPLATE_FILE_KEY").map_err(|_| FigmaError::MissingFileKey)
}

pub async fn get_template_json(http: &reqwest::Client) -> Result<serde_json::Value, FigmaError> {
    let pat = figma_pat()?;
    let file_key = template_file_key()?;
    get_template_json_with(http, &pat, &file_key).await
}

pub async fn get_template_json_with(
    http: &reqwest::Client,
    pat: &str,
    file_key: &str,
) -> Result<serde_json::Value, FigmaError> {
    let url = format!("{}/files/{}", figma_api_url(), file_key);
    let resp = http
        .get(url)
        .header("X-FIGMA-TOKEN", pat)
        .send()
        .await
        .map_err(|e| FigmaError::Http(e.to_string()))?;

    if !resp.status().is_success() {
        let status = resp.status();
        let body = resp.text().await.unwrap_or_default();
        return Err(FigmaError::Api { status, body });
    }

    let v = resp
        .json::<serde_json::Value>()
        .await
        .map_err(|e| FigmaError::Http(e.to_string()))?;
    Ok(v)
}

/// Find node on a specific page by name (1:1 with Python find_node).
pub fn find_node(file_json: &serde_json::Value, page_name: &str, node_name: &str) -> Option<serde_json::Value> {
    let pages = file_json.get("document")?.get("children")?.as_array()?;
    for page in pages {
        if page.get("name")?.as_str()? == page_name {
            return walk_find_by_name(page, node_name);
        }
    }
    None
}

pub fn find_node_anywhere(file_json: &serde_json::Value, node_name: &str) -> Option<serde_json::Value> {
    walk_find_by_name(file_json.get("document").unwrap_or(file_json), node_name)
}

fn walk_find_by_name(node: &serde_json::Value, node_name: &str) -> Option<serde_json::Value> {
    match node {
        serde_json::Value::Object(map) => {
            if map.get("name").and_then(|v| v.as_str()) == Some(node_name) {
                return Some(node.clone());
            }
            if let Some(children) = map.get("children").and_then(|v| v.as_array()) {
                for ch in children {
                    if let Some(found) = walk_find_by_name(ch, node_name) {
                        return Some(found);
                    }
                }
            }
            None
        }
        serde_json::Value::Array(arr) => {
            for it in arr {
                if let Some(found) = walk_find_by_name(it, node_name) {
                    return Some(found);
                }
            }
            None
        }
        _ => None,
    }
}

/// Export a node/frame as PNG bytes.
///
/// 1) GET /images/{file_key}?ids={node_id}&format=png&scale={scale}
/// 2) download returned URL
pub async fn export_frame_as_png(http: &reqwest::Client, node_id: &str, scale: Option<u32>) -> Result<Vec<u8>, FigmaError> {
    let pat = figma_pat()?;
    let file_key = template_file_key()?;
    export_frame_as_png_with(http, &pat, &file_key, node_id, scale).await
}

pub async fn export_frame_as_png_with(
    http: &reqwest::Client,
    pat: &str,
    file_key: &str,
    node_id: &str,
    scale: Option<u32>,
) -> Result<Vec<u8>, FigmaError> {
    let scale = scale.unwrap_or_else(|| {
        std::env::var("SCALE_FACTOR").ok().and_then(|s| s.parse().ok()).unwrap_or(2)
    });

    let url = format!(
        "{}/images/{}?ids={}&format=png&scale={}",
        figma_api_url(),
        file_key,
        urlencoding::encode(node_id),
        scale
    );

    let mut attempt = 0u32;
    loop {
        attempt += 1;
        let resp = http
            .get(&url)
            .header("X-FIGMA-TOKEN", pat)
            .send()
            .await
            .map_err(|e| FigmaError::Http(e.to_string()))?;

        if resp.status() == StatusCode::TOO_MANY_REQUESTS && attempt < 6 {
            tokio::time::sleep(Duration::from_millis(250 * attempt as u64)).await;
            continue;
        }

        if !resp.status().is_success() {
            let status = resp.status();
            let body = resp.text().await.unwrap_or_default();
            return Err(FigmaError::Api { status, body });
        }

        let json = resp.json::<serde_json::Value>().await.map_err(|e| FigmaError::Http(e.to_string()))?;
        let img_url = json
            .get("images")
            .and_then(|v| v.get(node_id))
            .and_then(|v| v.as_str())
            .ok_or_else(|| FigmaError::MissingImageUrl(node_id.to_string()))?;

        let img = http
            .get(img_url)
            .send()
            .await
            .map_err(|e| FigmaError::Http(e.to_string()))?;
        if !img.status().is_success() {
            return Err(FigmaError::Api { status: img.status(), body: img.text().await.unwrap_or_default() });
        }
        let bytes = img.bytes().await.map_err(|e| FigmaError::Http(e.to_string()))?;
        return Ok(bytes.to_vec());
    }
}
