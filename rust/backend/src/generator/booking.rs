use chrono::{Datelike, NaiveDate, Timelike, Weekday};
use chrono_tz::Tz;
use image::{DynamicImage, ImageBuffer, Rgba};
use printpdf::{
    Actions, BorderArray, BuiltinFont, ColorArray, ColorBits, ColorSpace, HighlightingMode,
    Image as PdfImage, ImageTransform, ImageXObject, LinkAnnotation, Mm, PdfDocument, Px, Rect,
};
use rand::Rng;
use rusttype::{point, Font, Scale};

use crate::{cache::FigmaCache, figma};

use super::{font_cache::load_font_cached, GenError};

const PAGE: &str = "Page 2";
// Pillow-like font px to rusttype size conversion (same idea as in gumtree).
const PILLOW_TO_RUSTTYPE_MULTIPLIER: f32 = 1.3;
const RIGHT_BLOCK_SHIFT_PX: i32 = -24;
const CONFIRM_PIN_GAP_PX: i32 = 14;
const CONFIRM_PIN_TO_LOCK_NUDGE_PX: i32 = 18;
// Extra right tail for PIN row to account for lock icon width in visual alignment.
const PIN_LOCK_TAIL_PX: i32 = 26;
const CONFIRM_ROW_RIGHT_EXTRA_PX: i32 = 20;
const SOLID_TEXT_THRESHOLD: f32 = 0.35;

fn pillow_size_to_rusttype(pillow_px: f32) -> f32 {
    pillow_px * PILLOW_TO_RUSTTYPE_MULTIPLIER
}

#[derive(Debug, Clone)]
pub struct BookingInput<'a> {
    pub guest_name: Option<&'a str>,
    pub city: Option<&'a str>,
    pub hotel_name: Option<&'a str>,
    pub hotel_address: Option<&'a str>,
    pub phone: Option<&'a str>,
    pub nights: Option<i32>,
    pub beds: Option<i32>,
    pub checkin_date: Option<&'a str>,
    pub checkout_date: Option<&'a str>,
    pub checkin_time: Option<&'a str>,
    pub checkout_time: Option<&'a str>,
    pub confirmation_number: Option<&'a str>,
    pub pin_code: Option<&'a str>,
}

fn tz_for_lang(lang: &str) -> Tz {
    match lang {
        "en" => chrono_tz::Europe::London,
        "it" => chrono_tz::Europe::Rome,
        "fr" => chrono_tz::Europe::Paris,
        "es" => chrono_tz::Europe::Madrid,
        "pr" => chrono_tz::Europe::Lisbon,
        "de" => chrono_tz::Europe::Berlin,
        "nl" => chrono_tz::Europe::Amsterdam,
        _ => chrono_tz::Europe::London,
    }
}

fn bbox(v: &serde_json::Value) -> Option<(f64, f64, f64, f64)> {
    let bb = v.get("absoluteBoundingBox")?;
    Some((
        bb.get("x")?.as_f64()?,
        bb.get("y")?.as_f64()?,
        bb.get("width")?.as_f64()?,
        bb.get("height")?.as_f64()?,
    ))
}

fn rel_box(node: &serde_json::Value, frame_node: &serde_json::Value) -> Result<(u32, u32, u32, u32), GenError> {
    let (x, y, w, h) = bbox(node).ok_or_else(|| GenError::Internal("missing absoluteBoundingBox".into()))?;
    let (fx, fy, _fw, _fh) = bbox(frame_node).ok_or_else(|| GenError::Internal("missing frame absoluteBoundingBox".into()))?;
    Ok((((x - fx).max(0.0)).round() as u32, ((y - fy).max(0.0)).round() as u32, w.round() as u32, h.round() as u32))
}

fn mm_from_px(px: f64) -> f32 {
    (px * 25.4 / 96.0) as f32
}

fn pdf_rect_from_figma(frame_h: f64, x: f64, y: f64, w: f64, h: f64) -> Rect {
    Rect::new(
        Mm(mm_from_px(x)),
        Mm(mm_from_px(frame_h - (y + h))),
        Mm(mm_from_px(x + w)),
        Mm(mm_from_px(frame_h - y)),
    )
}

fn parse_date(s: &str) -> Option<NaiveDate> {
    NaiveDate::parse_from_str(s, "%Y-%m-%d")
        .ok()
        .or_else(|| chrono::DateTime::parse_from_rfc3339(s).ok().map(|d| d.date_naive()))
}

fn month_short(lang: &str, m: u32) -> &'static str {
    let idx = (m.saturating_sub(1).min(11)) as usize;
    match lang {
        "it" => ["Gen","Feb","Mar","Apr","Mag","Giu","Lug","Ago","Set","Ott","Nov","Dic"][idx],
        "fr" => ["janvier","février","mars","avril","mai","juin","juillet","août","septembre","octobre","novembre","décembre"][idx],
        "es" => ["Ene","Feb","Mar","Abr","May","Jun","Jul","Ago","Sep","Oct","Nov","Dic"][idx],
        "pr" => ["Janeiro","Fevereiro","Março","Abril","Maio","Junho","Julho","Agosto","Setembro","Outubro","Novembro","Dezembro"][idx],
        "de" => ["Januar","Februar","März","April","Mai","Juni","Juli","August","September","Oktober","November","Dezember"][idx],
        "nl" => ["Jan","Feb","Mrt","Apr","Mei","Jun","Jul","Aug","Sep","Okt","Nov","Dec"][idx],
        _ => ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"][idx],
    }
}

fn weekday_name(lang: &str, w: Weekday) -> &'static str {
    let i = w.num_days_from_monday() as usize;
    match lang {
        "it" => ["Lunedì","Martedì","Mercoledì","Giovedì","Venerdì","Sabato","Domenica"][i],
        "fr" => ["Lundi","Mardi","Mercredi","Jeudi","Vendredi","Samedi","Dimanche"][i],
        "es" => ["Lunes","Martes","Miércoles","Jueves","Viernes","Sábado","Domingo"][i],
        "pr" => ["Segunda-feira","Terça-feira","Quarta-feira","Quinta-feira","Sexta-feira","Sábado","Domingo"][i],
        "de" => ["Montag","Dienstag","Mittwoch","Donnerstag","Freitag","Samstag","Sonntag"][i],
        "nl" => ["Maandag","Dinsdag","Woensdag","Donderdag","Vrijdag","Zaterdag","Zondag"][i],
        _ => ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"][i],
    }
}

fn format_time_hhmm_to_fr(time: &str) -> String {
    if let Some((h, m)) = time.split_once(':') {
        format!("{}h{}", h, m)
    } else {
        time.to_string()
    }
}

fn human_check_date(lang: &str, d: NaiveDate, is_checkin: bool, time: &str) -> String {
    match lang {
        "it" => format!(
            "{} {} {} {} ({})",
            weekday_name(lang, d.weekday()),
            d.day(),
            month_short(lang, d.month()),
            d.year(),
            if is_checkin {
                format!("dalle {}", time)
            } else {
                format!("fino alle {}", time)
            }
        ),
        "fr" => {
            let day = if d.day() == 1 { "1er".to_string() } else { d.day().to_string() };
            let t = format_time_hhmm_to_fr(time);
            format!(
                "{} {} {} {} ({})",
                weekday_name(lang, d.weekday()),
                day,
                month_short(lang, d.month()),
                d.year(),
                if is_checkin {
                    format!("à partir de {}", t)
                } else {
                    format!("jusqu'à {}", t)
                }
            )
        }
        "es" => format!(
            "{} {} {} {} ({})",
            weekday_name(lang, d.weekday()),
            d.day(),
            month_short(lang, d.month()),
            d.year(),
            if is_checkin {
                format!("a partir de las {}", time)
            } else {
                format!("hasta las {}", time)
            }
        ),
        "pr" => format!(
            "{}, {} de {} de {} ({})",
            weekday_name(lang, d.weekday()),
            d.day(),
            month_short(lang, d.month()),
            d.year(),
            if is_checkin {
                format!("a partir das {}", time)
            } else {
                format!("até às {}h", time)
            }
        ),
        "de" => format!(
            "{}, {}. {} {} ({})",
            weekday_name(lang, d.weekday()),
            d.day(),
            month_short(lang, d.month()),
            d.year(),
            if is_checkin {
                format!("ab {} Uhr", time)
            } else {
                format!("bis {} Uhr", time)
            }
        ),
        "nl" => format!(
            "{} {} {} {} ({})",
            weekday_name(lang, d.weekday()),
            d.day(),
            month_short(lang, d.month()),
            d.year(),
            if is_checkin {
                format!("vanaf {}", time)
            } else {
                format!("tot {}", time)
            }
        ),
        _ => format!(
            "{} {} {} {} ({})",
            weekday_name(lang, d.weekday()),
            d.day(),
            month_short(lang, d.month()),
            d.year(),
            if is_checkin {
                format!("from {}", time)
            } else {
                format!("until {}", time)
            }
        ),
    }
}

fn hex_color(s: &str) -> Result<Rgba<u8>, GenError> {
    let s = s.trim_start_matches('#');
    let b = hex::decode(s).map_err(|_| GenError::BadRequest(format!("invalid color: {s}")))?;
    if b.len() != 3 {
        return Err(GenError::BadRequest(format!("invalid color: {s}")));
    }
    Ok(Rgba([b[0], b[1], b[2], 255]))
}

fn text_width(font: &Font<'static>, px: f32, text: &str, spacing: f32) -> f32 {
    if text.is_empty() { return 0.0; }
    let scale = Scale::uniform(px);
    let v = font.v_metrics(scale);
    let glyphs: Vec<_> = font.layout(text, scale, point(0.0, v.ascent)).collect();
    let mut width = 0.0f32;
    for (i, g) in glyphs.iter().enumerate() {
        if let Some(bb) = g.pixel_bounding_box() {
            width = width.max(bb.max.x as f32);
            if i + 1 < glyphs.len() { width += spacing; }
        }
    }
    width
}

fn draw_text(img: &mut ImageBuffer<Rgba<u8>, Vec<u8>>, font: &Font<'static>, px: f32, x: i32, y: i32, color: Rgba<u8>, text: &str, spacing: f32) {
    let scale = Scale::uniform(px);
    let v_metrics = font.v_metrics(scale);
    let mut caret = x as f32;
    let baseline_y = y as f32 + v_metrics.ascent;
    for ch in text.chars() {
        let glyph = font.glyph(ch).scaled(scale).positioned(point(caret, baseline_y));
        if let Some(bb) = glyph.pixel_bounding_box() {
            glyph.draw(|gx, gy, gv| {
                if gv < SOLID_TEXT_THRESHOLD { return; }
                let px = bb.min.x + gx as i32;
                let py = bb.min.y + gy as i32;
                if px < 0 || py < 0 { return; }
                let (pxu, pyu) = (px as u32, py as u32);
                if pxu >= img.width() || pyu >= img.height() { return; }
                let dst = img.get_pixel_mut(pxu, pyu);
                dst.0[0] = color[0];
                dst.0[1] = color[1];
                dst.0[2] = color[2];
                dst.0[3] = 255;
            });
        }
        caret += glyph.unpositioned().h_metrics().advance_width + spacing;
    }
}

fn wrap_lines(font: &Font<'static>, px: f32, text: &str, spacing: f32, max_w: f32) -> Vec<String> {
    let mut out = Vec::<String>::new();
    let mut cur = String::new();
    for w in text.split_whitespace() {
        let cand = if cur.is_empty() { w.to_string() } else { format!("{} {}", cur, w) };
        if text_width(font, px, &cand, spacing) <= max_w || cur.is_empty() {
            cur = cand;
        } else {
            out.push(cur);
            cur = w.to_string();
        }
    }
    if !cur.is_empty() { out.push(cur); }
    out
}

fn text_for<'a>(lang: &str, key: &'a str) -> &'a str {
    match (lang, key) {
        ("it", "hello") => "Ciao, {name}!",
        ("fr", "hello") => "Bonjour, {name}!",
        ("es", "hello") => "¡Hola {name}!",
        ("pr", "hello") => "Olá, {name}!",
        ("de", "hello") => "Hallo, {name}!",
        ("nl", "hello") => "Hallo, {name}!",
        (_, "hello") => "Hello, {name}!",

        ("it", "confirm_city") => "La tua prenotazione in {city} deve essere confermata.",
        ("fr", "confirm_city") => "Votre réservation dans {city} doit être confirmée.",
        ("es", "confirm_city") => "Su reserva en {city} debe estar confirmada.",
        ("pr", "confirm_city") => "A sua reserva em {city} deve ser confirmada.",
        ("de", "confirm_city") => "Ihre Buchung in {city} muss bestätigt werden.",
        ("nl", "confirm_city") => "Uw boeking bij {city} moet bevestigd worden.",
        (_, "confirm_city") => "Your booking in {city} must be confirmed.",

        ("it", "book_date") => "{hotel} ti aspetterà {date} dopo la conferma",
        ("fr", "book_date") => "{hotel} vous attendra {date} après confirmation",
        ("es", "book_date") => "{hotel} te estará esperando {date} después de la confirmación.",
        ("pr", "book_date") => "O {hotel} estará à sua espera no {date} após a confirmação",
        ("de", "book_date") => "{hotel} erwartet Sie {date} nach Bestätigung",
        ("nl", "book_date") => "{hotel} staat na bevestiging {date} voor u klaar",
        (_, "book_date") => "{hotel} will be waiting for you on {date} after confirmation",

        ("it", "pay") => "Il *pagamento* sarà gestito da {hotel}.",
        ("fr", "pay") => "Votre *paiement* sera traité par {hotel}.",
        ("es", "pay") => "Su *pago* será gestionado por {hotel}.",
        ("pr", "pay") => "O seu *pagamento* será gerido pelo {hotel}.",
        ("de", "pay") => "Ihre *Zahlung* wird von {hotel} abgewickelt.",
        ("nl", "pay") => "Uw *betaling* wordt verwerkt door {hotel}.",
        (_, "pay") => "Your *payment* will be handled by {hotel}.",

        ("it", "phone") => "Phone:",
        ("fr", "phone") => "Phone:",
        ("es", "phone") => "Phone:",
        ("pr", "phone") => "Phone:",
        ("de", "phone") => "Phone:",
        ("nl", "phone") => "Phone:",
        (_, "phone") => "Phone:",

        ("it", "confirm_label") => "Numero di conferma:",
        ("fr", "confirm_label") => "Numéro de confirmation :",
        ("es", "confirm_label") => "Número de confirmación:",
        ("pr", "confirm_label") => "Número de confirmação:",
        ("de", "confirm_label") => "Bestätigungsnummer:",
        ("nl", "confirm_label") => "Bevestigingsnummer:",
        (_, "confirm_label") => "Confirmation number:",

        ("it", "pin_label") => "Codice PIN:",
        ("fr", "pin_label") => "Code PIN :",
        ("es", "pin_label") => "Código PIN:",
        ("pr", "pin_label") => "Código PIN:",
        ("de", "pin_label") => "PIN-Code:",
        ("nl", "pin_label") => "PIN-Code:",
        (_, "pin_label") => "PIN code:",
        _ => "",
    }
}

fn nights_text(lang: &str, nights: i32, beds: i32) -> String {
    match lang {
        "it" => format!("{} {}, {} {}", nights, if nights == 1 { "notte" } else { "notti" }, beds, if beds == 1 { "letto" } else { "letti" }),
        "fr" => format!("{} {}, {} {}", nights, if nights == 1 { "nuit" } else { "nuits" }, beds, if beds == 1 { "lit" } else { "lits" }),
        "es" => format!("{} {}, {} {}", nights, if nights == 1 { "noche" } else { "noches" }, beds, if beds == 1 { "cama" } else { "camas" }),
        "pr" => format!("{} {}, {} {}", nights, if nights == 1 { "noite" } else { "noites" }, beds, if beds == 1 { "cama" } else { "camas" }),
        "de" => format!("{} {}, {} {}", nights, if nights == 1 { "Nacht" } else { "Nächte" }, beds, if beds == 1 { "Bett" } else { "Betten" }),
        "nl" => format!("{} {}, {} {}", nights, if nights == 1 { "nacht" } else { "nachten" }, beds, if beds == 1 { "bed" } else { "bedden" }),
        _ => format!("{} {}, {} {}", nights, if nights == 1 { "night" } else { "nights" }, beds, if beds == 1 { "dormitory bed" } else { "dormitory beds" }),
    }
}

fn draw_in_node_left(img: &mut ImageBuffer<Rgba<u8>, Vec<u8>>, frame_node: &serde_json::Value, template: &serde_json::Value, node_name: &str, text: &str, font: &Font<'static>, px: f32, color: Rgba<u8>, spacing_pct: f32) -> Result<(), GenError> {
    if let Some(n) = figma::find_node(template, PAGE, node_name) {
        let (x, y, w, _h) = rel_box(&n, frame_node)?;
        let spacing = px * spacing_pct;
        let lines = wrap_lines(font, px, text, spacing, w as f32);
        let line_h = (px * 1.25).round() as i32;
        for (i, line) in lines.iter().enumerate() {
            draw_text(img, font, px, x as i32, y as i32 + (i as i32) * line_h, color, line, spacing);
        }
    }
    Ok(())
}

fn draw_in_node_right(img: &mut ImageBuffer<Rgba<u8>, Vec<u8>>, frame_node: &serde_json::Value, template: &serde_json::Value, node_name: &str, text: &str, font: &Font<'static>, px: f32, color: Rgba<u8>, spacing_pct: f32, shift_px: i32) -> Result<(), GenError> {
    if let Some(n) = figma::find_node(template, PAGE, node_name) {
        let (x, y, w, _h) = rel_box(&n, frame_node)?;
        let spacing = px * spacing_pct;
        let tw = text_width(font, px, text, spacing);
        let sx = (x as f32 + w as f32 - tw).round() as i32 + shift_px;
        draw_text(img, font, px, sx, y as i32, color, text, spacing);
    }
    Ok(())
}

fn book_date_segments(lang: &str, hotel: &str, date: &str) -> Vec<(String, bool)> {
    match lang {
        "it" => vec![(hotel.to_string(), true), (" ti aspetterà ".to_string(), false), (date.to_string(), true), (" dopo la conferma".to_string(), false)],
        "fr" => vec![(hotel.to_string(), true), (" vous attendra ".to_string(), false), (date.to_string(), true), (" après confirmation".to_string(), false)],
        "es" => vec![(hotel.to_string(), true), (" te estará esperando ".to_string(), false), (date.to_string(), true), (" después de la confirmación.".to_string(), false)],
        "pr" => vec![("O ".to_string(), false), (hotel.to_string(), true), (" estará à sua espera no ".to_string(), false), (date.to_string(), true), (" após a confirmação".to_string(), false)],
        "de" => vec![(hotel.to_string(), true), (" erwartet Sie ".to_string(), false), (date.to_string(), true), (" nach Bestätigung".to_string(), false)],
        "nl" => vec![(hotel.to_string(), true), (" staat na bevestiging ".to_string(), false), (date.to_string(), true), (" voor u klaar".to_string(), false)],
        _ => vec![(hotel.to_string(), true), (" will be waiting for you on ".to_string(), false), (date.to_string(), true), (" after confirmation".to_string(), false)],
    }
}

fn draw_in_node_left_rich_bookdate(
    img: &mut ImageBuffer<Rgba<u8>, Vec<u8>>,
    frame_node: &serde_json::Value,
    template: &serde_json::Value,
    node_name: &str,
    lang: &str,
    hotel: &str,
    date: &str,
    regular_font: &Font<'static>,
    bold_font: &Font<'static>,
    px: f32,
    color: Rgba<u8>,
    spacing_pct: f32,
) -> Result<(), GenError> {
    if let Some(n) = figma::find_node(template, PAGE, node_name) {
        let (x, y, w, _h) = rel_box(&n, frame_node)?;
        let spacing = px * spacing_pct;
        let line_h = (px * 1.25).round() as i32;

        let mut cx = x as i32;
        let mut cy = y as i32;

        for (seg_text, is_bold) in book_date_segments(lang, hotel, date) {
            for token in seg_text.split_inclusive(' ') {
                let f = if is_bold { bold_font } else { regular_font };
                let token_w = text_width(f, px, token, spacing).round() as i32;
                if (cx - x as i32) + token_w > w as i32 {
                    cx = x as i32;
                    cy += line_h;
                }
                draw_text(img, f, px, cx, cy, color, token, spacing);
                cx += token_w;
            }
        }
    }
    Ok(())
}

pub async fn generate_booking(
    http: &reqwest::Client,
    lang: &str,
    title: &str,
    _price: f64,
    knopbook1: Option<&str>,
    knopbook2: Option<&str>,
    input: BookingInput<'_>,
) -> Result<Vec<u8>, GenError> {
    if !matches!(lang, "en" | "it" | "fr" | "es" | "pr" | "de" | "nl") {
        return Err(GenError::BadRequest(format!("unknown booking language: {lang}")));
    }

    let frame_name = format!("book_{lang}");
    let file_key = std::env::var("TEMPLATE_FILE_KEY").unwrap_or_else(|_| "default".to_string());
    let cache = FigmaCache::new(format!("figma_{}_{}_{}", file_key, PAGE.replace(' ', "_"), frame_name));

    let (template_json, frame_png, frame_node, used_cache) = if cache.exists() {
        let (structure, png) = cache.load()?;
        let frame_node = figma::find_node(&structure, PAGE, &frame_name);
        if let Some(node) = frame_node {
            (structure, png, node, true)
        } else {
            let structure = figma::get_template_json(http).await?;
            let frame_node = figma::find_node(&structure, PAGE, &frame_name)
                .ok_or_else(|| GenError::BadRequest(format!("frame not found: {frame_name}")))?;
            (structure, Vec::new(), frame_node, false)
        }
    } else {
        let structure = figma::get_template_json(http).await?;
        let frame_node = figma::find_node(&structure, PAGE, &frame_name)
            .ok_or_else(|| GenError::BadRequest(format!("frame not found: {frame_name}")))?;
        (structure, Vec::new(), frame_node, false)
    };

    let frame_png = if used_cache {
        frame_png
    } else {
        let node_id = frame_node
            .get("id")
            .and_then(|v| v.as_str())
            .ok_or_else(|| GenError::Internal("frame node missing id".into()))?;
        let png = figma::export_frame_as_png(http, node_id, Some(1)).await?;
        cache.save(&template_json, &png)?;
        png
    };

    let mut img = image::load_from_memory(&frame_png)
        .map_err(|e| GenError::Image(e.to_string()))?
        .to_rgba8();

    let (_fx, _fy, fw, fh) = bbox(&frame_node).ok_or_else(|| GenError::Internal("frame missing bbox".into()))?;

    let roboto_bold = load_font_cached("Roboto-Bold.ttf")?;
    let roboto_regular = load_font_cached("Roboto-Regular.ttf")?;

    let guest = input.guest_name.unwrap_or("Guest");
    let city = input.city.unwrap_or("City");
    let hotel = input.hotel_name.or(Some(title)).unwrap_or("Hotel");
    let address = input.hotel_address.unwrap_or("");
    let phone = input.phone.unwrap_or("-");

    let now = chrono::Utc::now().with_timezone(&tz_for_lang(lang));
    let nights = input.nights.unwrap_or(1);
    let beds = input.beds.unwrap_or(1);
    let checkin_time = input.checkin_time.unwrap_or("13:00");
    let checkout_time = input.checkout_time.unwrap_or("13:00");

    let checkin_date = input
        .checkin_date
        .and_then(parse_date)
        .unwrap_or_else(|| now.date_naive());
    let checkout_date = input
        .checkout_date
        .and_then(parse_date)
        .unwrap_or_else(|| now.date_naive().succ_opt().unwrap_or(now.date_naive()));

    let confirm_number = input.confirmation_number.map(str::to_string).unwrap_or_else(|| {
        let mut rng = rand::thread_rng();
        rng.gen_range(3_860_070_132u64..=3_890_070_985u64).to_string()
    });
    let pin = input.pin_code.map(str::to_string).unwrap_or_else(|| {
        let mut rng = rand::thread_rng();
        format!("{:04}", rng.gen_range(0u32..=9999u32))
    });

    let hello = text_for(lang, "hello").replace("{name}", guest);
    let confirm_city = text_for(lang, "confirm_city").replace("{city}", city);
    let print_date = format!("{} {} {}", checkin_date.day(), month_short(lang, checkin_date.month()), checkin_date.year());
    let book_pay = text_for(lang, "pay").replace("{hotel}", hotel);
    let nights_line = nights_text(lang, nights, beds);
    let checkin_line = human_check_date(lang, checkin_date, true, checkin_time);
    let checkout_line = human_check_date(lang, checkout_date, false, checkout_time);

    let name_px = pillow_size_to_rusttype(51.0);
    let confirm_px = pillow_size_to_rusttype(63.0);
    let common_px = pillow_size_to_rusttype(47.0);
    let confirm_small_px = pillow_size_to_rusttype(42.5);

    draw_in_node_left(&mut img, &frame_node, &template_json, &format!("NAME_{lang}"), &hello, &roboto_bold, name_px, hex_color("#3B3637")?, 0.04)?;
    draw_in_node_left(&mut img, &frame_node, &template_json, &format!("BOOKCONFIRM_{lang}"), &confirm_city, &roboto_bold, confirm_px, hex_color("#3B3637")?, 0.04)?;
    draw_in_node_left_rich_bookdate(
        &mut img,
        &frame_node,
        &template_json,
        &format!("BOOKDATE_{lang}"),
        lang,
        hotel,
        &print_date,
        &roboto_regular,
        &roboto_bold,
        common_px,
        hex_color("#3B3637")?,
        0.017,
    )?;

    // BOOKPAY with bold word between *...*
    if let Some(n) = figma::find_node(&template_json, PAGE, &format!("BOOKPAY_{lang}")) {
        let (x, y, _w, _h) = rel_box(&n, &frame_node)?;
        let mut cursor = x as i32;
        let spacing = common_px * 0.017;
        for seg in book_pay.split('*').enumerate() {
            let (i, part) = seg;
            let f = if i % 2 == 1 { &*roboto_bold } else { &*roboto_regular };
            draw_text(&mut img, f, common_px, cursor, y as i32, hex_color("#3B3637")?, part, spacing);
            cursor += text_width(f, common_px, part, spacing).round() as i32;
        }
    }

    draw_in_node_left(&mut img, &frame_node, &template_json, &format!("HOTELNAME_{lang}"), hotel, &roboto_bold, confirm_px, hex_color("#0278CD")?, 0.04)?;
    draw_in_node_left(&mut img, &frame_node, &template_json, &format!("ADRESS_{lang}"), address, &roboto_regular, common_px, hex_color("#3B3637")?, 0.01)?;

    // Phone: label bold + number regular
    if let Some(n) = figma::find_node(&template_json, PAGE, &format!("PHONENUM_{lang}")) {
        let (x, y, _w, _h) = rel_box(&n, &frame_node)?;
        let label = text_for(lang, "phone");
        let spacing = common_px * 0.01;
        draw_text(&mut img, &roboto_bold, common_px, x as i32, y as i32, hex_color("#3B3637")?, label, spacing);
        let lx = x as i32 + text_width(&roboto_bold, common_px, &(label.to_string() + " "), spacing).round() as i32 + 10;
        draw_text(&mut img, &roboto_regular, common_px, lx, y as i32, hex_color("#3B3637")?, phone, spacing);
    }

    draw_in_node_right(&mut img, &frame_node, &template_json, &format!("NIGHTS_{lang}"), &nights_line, &roboto_bold, common_px, hex_color("#000000")?, 0.01, RIGHT_BLOCK_SHIFT_PX)?;
    draw_in_node_right(&mut img, &frame_node, &template_json, &format!("CHECKIN_{lang}"), &checkin_line, &roboto_regular, common_px, hex_color("#5B5B5B")?, 0.01, RIGHT_BLOCK_SHIFT_PX)?;
    draw_in_node_right(&mut img, &frame_node, &template_json, &format!("CHECKOUT_{lang}"), &checkout_line, &roboto_regular, common_px, hex_color("#5B5B5B")?, 0.01, RIGHT_BLOCK_SHIFT_PX)?;

    // CONFIRM + PIN aligned to the same right edge (lock side) with equal label-number gap.
    let confirm_node = figma::find_node(&template_json, PAGE, &format!("CONFIRM_{lang}"));
    let pin_node = figma::find_node(&template_json, PAGE, &format!("PIN_{lang}"));
    if let (Some(cn), Some(pn)) = (confirm_node, pin_node) {
        let (_cx, cy, _cw, _ch) = rel_box(&cn, &frame_node)?;
        let (px, py, pw, _ph) = rel_box(&pn, &frame_node)?;

        let spacing = 0.0f32;
        let gap = CONFIRM_PIN_GAP_PX; // hard-equal gap for both rows

        // Anchor by the second row right edge (closer to lock), then align both rows to it.
        // Visual right edge is where the lock icon ends (second row, as requested).
        let visual_right_edge = (px as i32 + pw as i32)
            + CONFIRM_PIN_TO_LOCK_NUDGE_PX;

        let confirm_label = format!("{}", text_for(lang, "confirm_label"));
        let pin_label = format!("{}", text_for(lang, "pin_label"));

        // First row ends exactly at visual_right_edge.
        let confirm_num_w = text_width(&roboto_bold, confirm_small_px, &confirm_number, spacing).round() as i32;
        let confirm_num_x = visual_right_edge - confirm_num_w + CONFIRM_ROW_RIGHT_EXTRA_PX;
        let confirm_label_right_x = confirm_num_x - gap;
        let confirm_label_w = text_width(&roboto_regular, confirm_small_px, &confirm_label, spacing).round() as i32;
        let confirm_label_x = confirm_label_right_x - confirm_label_w;

        draw_text(&mut img, &roboto_regular, confirm_small_px, confirm_label_x, cy as i32, hex_color("#E6FFFF")?, &confirm_label, spacing);
        draw_text(&mut img, &roboto_bold, confirm_small_px, confirm_num_x, cy as i32, hex_color("#E6FFFF")?, &confirm_number, spacing);

        // Second row includes lock icon, so code ends earlier by lock tail width.
        let pin_code_right_edge = visual_right_edge - PIN_LOCK_TAIL_PX;
        let pin_num_w = text_width(&roboto_bold, confirm_small_px, &pin, spacing).round() as i32;
        let pin_num_x = pin_code_right_edge - pin_num_w;
        let pin_label_right_x = pin_num_x - gap;
        let pin_label_w = text_width(&roboto_regular, confirm_small_px, &pin_label, spacing).round() as i32;
        let pin_label_x = pin_label_right_x - pin_label_w;

        draw_text(&mut img, &roboto_regular, confirm_small_px, pin_label_x, py as i32, hex_color("#E6FFFF")?, &pin_label, spacing);
        draw_text(&mut img, &roboto_bold, confirm_small_px, pin_num_x, py as i32, hex_color("#E6FFFF")?, &pin, spacing);
    } else {
        // Fallback to independent rendering if one of nodes is missing.
        if let Some(n) = figma::find_node(&template_json, PAGE, &format!("CONFIRM_{lang}")) {
            let (x, y, w, _h) = rel_box(&n, &frame_node)?;
            let base = format!("{} {}", text_for(lang, "confirm_label"), confirm_number);
            let spacing = 0.0f32;
            let tw = text_width(&roboto_regular, confirm_small_px, &base, spacing);
            let sx = (x as f32 + w as f32 - tw).round() as i32 + RIGHT_BLOCK_SHIFT_PX;
            let label = format!("{} ", text_for(lang, "confirm_label"));
            draw_text(&mut img, &roboto_regular, confirm_small_px, sx, y as i32, hex_color("#E6FFFF")?, &label, spacing);
            let nx = sx + text_width(&roboto_regular, confirm_small_px, &label, spacing).round() as i32;
            draw_text(&mut img, &roboto_bold, confirm_small_px, nx, y as i32, hex_color("#E6FFFF")?, &confirm_number, spacing);
        }
        if let Some(n) = figma::find_node(&template_json, PAGE, &format!("PIN_{lang}")) {
            let (x, y, w, _h) = rel_box(&n, &frame_node)?;
            let label_txt = format!("{} ", text_for(lang, "pin_label"));
            let base = format!("{}{}", label_txt, pin);
            let spacing = 0.0f32;
            let tw = text_width(&roboto_regular, confirm_small_px, &base, spacing);
            let sx = (x as f32 + w as f32 - tw).round() as i32 + RIGHT_BLOCK_SHIFT_PX;
            draw_text(&mut img, &roboto_regular, confirm_small_px, sx, y as i32, hex_color("#E6FFFF")?, &label_txt, spacing);
            let nx = sx + text_width(&roboto_regular, confirm_small_px, &label_txt, spacing).round() as i32;
            draw_text(&mut img, &roboto_bold, confirm_small_px, nx, y as i32, hex_color("#E6FFFF")?, &pin, spacing);
        }
    }

    let rgb = DynamicImage::ImageRgba8(img).to_rgb8();
    let (iw, ih) = rgb.dimensions();
    let pdf_img = PdfImage::from(ImageXObject {
        width: Px(iw as usize),
        height: Px(ih as usize),
        color_space: ColorSpace::Rgb,
        bits_per_component: ColorBits::Bit8,
        interpolate: true,
        image_data: rgb.into_raw(),
        image_filter: None,
        smask: None,
        clipping_bbox: None,
    });

    let (doc, page1, layer1) = PdfDocument::new("booking", Mm(mm_from_px(fw)), Mm(mm_from_px(fh)), "Layer 1");
    let current_layer = doc.get_page(page1).get_layer(layer1);

    pdf_img.add_to_layer(
        current_layer.clone(),
        ImageTransform {
            translate_x: Some(Mm(0.0)),
            translate_y: Some(Mm(0.0)),
            rotate: None,
            scale_x: None,
            scale_y: None,
            dpi: Some(96.0),
        },
    );

    let add_link = |url: &str, node_name: &str| -> Result<(), GenError> {
        if url.trim().is_empty() {
            return Ok(());
        }
        if let Some(node) = figma::find_node(&template_json, PAGE, node_name) {
            let (x, y, w, h) = bbox(&node).ok_or_else(|| GenError::Internal("missing absoluteBoundingBox".into()))?;
            let (fx, fy, _fw, _fh) = bbox(&frame_node).ok_or_else(|| GenError::Internal("missing frame absoluteBoundingBox".into()))?;
            let rect = pdf_rect_from_figma(fh, x - fx, y - fy, w, h);
            current_layer.add_link_annotation(LinkAnnotation::new(
                rect,
                Some(BorderArray::default()),
                Some(ColorArray::default()),
                Actions::uri(url.to_string()),
                Some(HighlightingMode::Invert),
            ));
        }
        Ok(())
    };

    add_link(knopbook1.unwrap_or(""), &format!("knopbook1_{lang}"))?;
    add_link(knopbook2.unwrap_or("https://www.booking.com/"), &format!("knopbook2_{lang}"))?;

    let _ = doc
        .add_builtin_font(BuiltinFont::Helvetica)
        .map_err(|e| GenError::Internal(format!("pdf font error: {e}")))?;

    let mut out = Vec::<u8>::new();
    {
        let cursor = std::io::Cursor::new(&mut out);
        let mut writer = std::io::BufWriter::new(cursor);
        doc.save(&mut writer)
            .map_err(|e| GenError::Internal(format!("pdf save error: {e}")))?;
    }

    Ok(out)
}
