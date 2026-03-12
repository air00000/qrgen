use harfbuzz_rs::{shape, Face, Font as HbFont, Owned, UnicodeBuffer};

use super::GenError;

#[derive(Debug, Clone)]
pub struct ShapedGlyph {
    pub glyph_id: u32,
    pub cluster: u32,
    pub x_advance: f32,
    pub y_advance: f32,
    pub x_offset: f32,
    pub y_offset: f32,
}

#[derive(Debug, Clone)]
pub struct ShapedText {
    pub glyphs: Vec<ShapedGlyph>,
    pub width: f32,
}

pub fn load_font_harfbuzz(font_bytes: &[u8]) -> Result<Owned<HbFont<'_>>, GenError> {
    let face = Face::from_bytes(font_bytes, 0);
    Ok(HbFont::new(face))
}

pub fn shape_text(
    font_bytes: &[u8],
    text: &str,
    px: f32,
    language: &str,
) -> Result<ShapedText, GenError> {
    if text.is_empty() {
        return Ok(ShapedText {
            glyphs: Vec::new(),
            width: 0.0,
        });
    }

    let mut font = load_font_harfbuzz(font_bytes)?;
    let hb_scale = (px * 64.0).round() as i32;
    font.set_scale(hb_scale, hb_scale);
    font.set_ppem(px.round().max(1.0) as u32, px.round().max(1.0) as u32);

    let mut buffer = UnicodeBuffer::new().add_str(text);
    if let Ok(lang) = language.parse::<harfbuzz_rs::Language>() {
        buffer.set_language(lang);
    }
    let output = shape(&font, buffer, &[]);

    let infos = output.get_glyph_infos();
    let positions = output.get_glyph_positions();

    let mut glyphs = Vec::with_capacity(positions.len());
    let mut total_width = 0.0f32;

    for (info, pos) in infos.iter().zip(positions.iter()) {
        let x_advance = pos.x_advance as f32 / 64.0;
        let y_advance = pos.y_advance as f32 / 64.0;
        let x_offset = pos.x_offset as f32 / 64.0;
        let y_offset = pos.y_offset as f32 / 64.0;

        glyphs.push(ShapedGlyph {
            glyph_id: info.codepoint,
            cluster: info.cluster,
            x_advance,
            y_advance,
            x_offset,
            y_offset,
        });
        total_width += x_advance;
    }

    Ok(ShapedText {
        glyphs,
        width: total_width,
    })
}

pub fn font_line_height(font_bytes: &[u8], px: f32) -> Result<f32, GenError> {
    let mut font = load_font_harfbuzz(font_bytes)?;
    let hb_scale = (px * 64.0).round() as i32;
    font.set_scale(hb_scale, hb_scale);

    let line_height = if let Some(extents) = font.get_font_h_extents() {
        let ascent = extents.ascender as f32 / 64.0;
        let descent = (-extents.descender) as f32 / 64.0;
        let line_gap = extents.line_gap as f32 / 64.0;
        ascent + descent + line_gap
    } else {
        px * 1.2
    };

    Ok(line_height.max(px))
}
