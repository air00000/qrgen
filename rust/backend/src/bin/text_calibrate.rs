use image::{ImageBuffer, Rgba};
use rusttype::{point, Font, Scale};
use serde::Serialize;
use std::{collections::HashMap, path::PathBuf};

#[derive(Debug, Clone)]
struct Args {
    font: String,
    text: String,
    target_w: u32,
    target_h: u32,
    spacing: f32,
    min_px: f32,
    max_px: f32,
    step: f32,
    figma_px: Option<f32>,
}

#[derive(Debug, Serialize)]
struct FitResult {
    font: String,
    text: String,
    target_w: u32,
    target_h: u32,
    spacing: f32,
    best_px: f32,
    rendered_w: u32,
    rendered_h: u32,
    width_error: i32,
    height_error: i32,
    score: f32,
    figma_px: Option<f32>,
    figma_to_rust_ratio: Option<f32>,
}

fn parse_args() -> Result<Args, String> {
    let mut m: HashMap<String, String> = HashMap::new();
    let mut it = std::env::args().skip(1);
    while let Some(k) = it.next() {
        if !k.starts_with("--") {
            return Err(format!("unexpected arg: {k}"));
        }
        let key = k.trim_start_matches("--").to_string();
        let val = it
            .next()
            .ok_or_else(|| format!("missing value for --{key}"))?;
        m.insert(key, val);
    }

    let req = |k: &str| m.get(k).cloned().ok_or_else(|| format!("missing --{k}"));

    Ok(Args {
        font: req("font")?,
        text: req("text")?,
        target_w: req("target-w")?.parse().map_err(|_| "bad --target-w".to_string())?,
        target_h: req("target-h")?.parse().map_err(|_| "bad --target-h".to_string())?,
        spacing: m.get("spacing").map(|s| s.parse()).transpose().map_err(|_| "bad --spacing".to_string())?.unwrap_or(0.0),
        min_px: m.get("min").map(|s| s.parse()).transpose().map_err(|_| "bad --min".to_string())?.unwrap_or(4.0),
        max_px: m.get("max").map(|s| s.parse()).transpose().map_err(|_| "bad --max".to_string())?.unwrap_or(300.0),
        step: m.get("step").map(|s| s.parse()).transpose().map_err(|_| "bad --step".to_string())?.unwrap_or(0.25),
        figma_px: m.get("figma-px").map(|s| s.parse()).transpose().map_err(|_| "bad --figma-px".to_string())?,
    })
}

fn fonts_dir() -> PathBuf {
    let manifest_dir = std::path::Path::new(env!("CARGO_MANIFEST_DIR"));
    manifest_dir.join("../..").join("app").join("assets").join("fonts")
}

fn load_font(name: &str) -> Result<Font<'static>, String> {
    let bytes = std::fs::read(fonts_dir().join(name))
        .map_err(|e| format!("failed to read font {name}: {e}"))?;
    Font::try_from_vec(bytes).ok_or_else(|| format!("failed to parse font {name}"))
}

fn draw_text_mask(font: &Font<'static>, px: f32, text: &str, spacing: f32) -> (u32, u32) {
    let scale = Scale::uniform(px);
    let v = font.v_metrics(scale);

    // large scratch canvas
    let mut img = ImageBuffer::from_pixel(4096, 2048, Rgba([0, 0, 0, 0]));
    let baseline_y = 512.0 + v.ascent;
    let mut caret_x = 8.0;

    for ch in text.chars() {
        let glyph = font.glyph(ch).scaled(scale).positioned(point(caret_x, baseline_y));
        if let Some(bb) = glyph.pixel_bounding_box() {
            glyph.draw(|gx, gy, cov| {
                if cov <= 0.0 {
                    return;
                }
                let x = gx as i32 + bb.min.x;
                let y = gy as i32 + bb.min.y;
                if x < 0 || y < 0 {
                    return;
                }
                let (x, y) = (x as u32, y as u32);
                if x >= img.width() || y >= img.height() {
                    return;
                }
                img.put_pixel(x, y, Rgba([255, 255, 255, 255]));
            });
        }
        caret_x += glyph.unpositioned().h_metrics().advance_width + spacing;
    }

    // bbox from non-transparent pixels
    let mut min_x = u32::MAX;
    let mut min_y = u32::MAX;
    let mut max_x = 0u32;
    let mut max_y = 0u32;
    let mut found = false;

    for y in 0..img.height() {
        for x in 0..img.width() {
            if img.get_pixel(x, y).0[3] > 0 {
                found = true;
                min_x = min_x.min(x);
                min_y = min_y.min(y);
                max_x = max_x.max(x);
                max_y = max_y.max(y);
            }
        }
    }

    if !found {
        return (0, 0);
    }

    (max_x - min_x + 1, max_y - min_y + 1)
}

fn main() -> Result<(), String> {
    let args = parse_args().map_err(|e| {
        format!(
            "{e}\n\nUsage:\n  cargo run -p qrgen-backend --bin text_calibrate -- \\\n    --font ReadexPro-SemiBold.ttf \\\n    --text \"Total to pay\" \\\n    --target-w 640 --target-h 96 \\\n    [--spacing 0.0] [--min 4] [--max 300] [--step 0.25] [--figma-px 56]"
        )
    })?;

    let font = load_font(&args.font)?;

    let mut best: Option<(f32, u32, u32, f32)> = None;
    let mut px = args.min_px;
    while px <= args.max_px {
        let (rw, rh) = draw_text_mask(&font, px, &args.text, args.spacing);
        let dw = (rw as i32 - args.target_w as i32).abs() as f32;
        let dh = (rh as i32 - args.target_h as i32).abs() as f32;
        // Height usually matters more for visual parity in mockups.
        let score = dw * 1.0 + dh * 1.35;

        match best {
            None => best = Some((px, rw, rh, score)),
            Some((_, _, _, s)) if score < s => best = Some((px, rw, rh, score)),
            _ => {}
        }

        px += args.step.max(0.01);
    }

    let (best_px, rw, rh, score) = best.ok_or_else(|| "no fit candidates".to_string())?;
    let width_error = rw as i32 - args.target_w as i32;
    let height_error = rh as i32 - args.target_h as i32;

    let out = FitResult {
        font: args.font,
        text: args.text,
        target_w: args.target_w,
        target_h: args.target_h,
        spacing: args.spacing,
        best_px,
        rendered_w: rw,
        rendered_h: rh,
        width_error,
        height_error,
        score,
        figma_px: args.figma_px,
        figma_to_rust_ratio: args.figma_px.map(|fp| if fp > 0.0 { best_px / fp } else { 1.0 }),
    };

    println!(
        "{}",
        serde_json::to_string_pretty(&out).map_err(|e| format!("json encode failed: {e}"))?
    );

    Ok(())
}
