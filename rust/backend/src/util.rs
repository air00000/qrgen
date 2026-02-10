use base64::Engine;

pub fn parse_data_uri(input: &str) -> Option<String> {
    let s = input.trim();
    if s.is_empty() {
        return None;
    }
    if let Some(rest) = s.strip_prefix("data:") {
        // data:image/png;base64,....
        let (_, b64) = rest.split_once(",")?;
        return Some(b64.trim().to_string());
    }
    // assume plain base64
    Some(s.to_string())
}

pub fn b64_decode(input: &str) -> Option<Vec<u8>> {
    let b64 = parse_data_uri(input)?;
    let engine = base64::engine::general_purpose::STANDARD;
    engine.decode(b64.as_bytes()).ok()
}

pub fn truncate_with_ellipsis(mut s: String, max_len: usize) -> String {
    if s.len() <= max_len {
        return s;
    }
    if max_len <= 3 {
        return "...".to_string();
    }
    s.truncate(max_len - 3);
    s.push_str("...");
    s
}
