# app/services/subito_variants.py
"""
Генерация для Subito — фреймы subito6–10 (uk / nl).

subito6  — mail запрос
subito7  — телефон запрос
subito8  — mail оплата
subito9  — sms оплата
subito10 — qr
"""

import os
import io
import base64
import datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

from pytz import timezone
from PIL import Image, ImageDraw, ImageFont, ImageOps

from app.config import CFG
from app.services.pdf import (
    draw_text_with_letter_spacing,
    FigmaNodeNotFoundError,
)
from app.services.figma import find_node as _figma_find_node
from app.services.cache_wrapper import load_template_with_cache, get_frame_image

# ── Константы ────────────────────────────────────────────────────────────────

_SUBITO_NEW_FRAMES = {
    "email_request":  6,
    "phone_request":  7,
    "email_payment":  8,
    "sms_payment":    9,
    "qr":            10,
}

_SUBITO_DELIVERY_FEE = Decimal("6.85")


# ── Шрифты ───────────────────────────────────────────────────────────────────

def _sn_get_font(font_name: str, size: int) -> ImageFont.FreeTypeFont:
    path = os.path.join(CFG.FONTS_DIR, font_name)
    if os.path.exists(path):
        return ImageFont.truetype(path, size)
    return ImageFont.load_default()


# ── Ширина текста с letter-spacing ───────────────────────────────────────────

def _sn_text_width(font, text: str, spacing: int) -> float:
    if not text:
        return 0.0
    widths = [font.getbbox(ch)[2] for ch in text]
    return sum(widths) + spacing * (len(text) - 1)


def _sn_truncate(text: str, font, spacing: int, max_px: int) -> str:
    if _sn_text_width(font, text, spacing) <= max_px:
        return text
    ellipsis = "..."
    t = text
    while t and _sn_text_width(font, t + ellipsis, spacing) > max_px:
        t = t[:-1]
    return t + ellipsis if t else ellipsis


# ── Рисование текста ─────────────────────────────────────────────────────────

def _sn_draw_left(draw, text, font, x, y, fill, spacing=0):
    draw_text_with_letter_spacing(draw, text, font, x, y, fill, letter_spacing=spacing)


def _sn_draw_right(draw, text, font, right_x, y, fill, spacing=0):
    w = _sn_text_width(font, text, spacing)
    draw_text_with_letter_spacing(draw, text, font, right_x - w, y, fill, letter_spacing=spacing)


def _sn_draw_center(draw, text, font, cx, y, fill, spacing=0):
    w = _sn_text_width(font, text, spacing)
    draw_text_with_letter_spacing(draw, text, font, cx - w / 2, y, fill, letter_spacing=spacing)


# ── Форматирование цены ───────────────────────────────────────────────────────

def _sn_format_price_main(price: float) -> str:
    d = Decimal(str(price)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if d % 1 == 0:
        return f"{int(d)} \u20ac"
    return f"{d:.2f}".replace(".", ",") + " \u20ac"


def _sn_format_price_always(price: float) -> str:
    d = Decimal(str(price)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return f"{d:.2f}".replace(".", ",") + " \u20ac"


def _sn_format_total(price: float) -> str:
    d = Decimal(str(price)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    total = (d + _SUBITO_DELIVERY_FEE).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return f"{total:.2f}".replace(".", ",") + " \u20ac"


# ── Фото ─────────────────────────────────────────────────────────────────────

def _sn_photo_rounded(photo_b64: str, w: int, h: int, radius: int) -> Optional[Image.Image]:
    from app.utils.helpers import parse_data_uri
    data = parse_data_uri(photo_b64)
    if not data:
        return None
    try:
        img = Image.open(io.BytesIO(base64.b64decode(data))).convert("RGBA")
        img = ImageOps.fit(img, (w, h), Image.Resampling.LANCZOS)
        mask = Image.new("L", (w, h), 0)
        d = ImageDraw.Draw(mask)
        d.rounded_rectangle([(0, 0), (w, h)], radius=radius, fill=255)
        out = Image.new("RGBA", (w, h), (255, 255, 255, 0))
        out.paste(img, (0, 0), mask)
        return out
    except Exception:
        return None


# ── QR ───────────────────────────────────────────────────────────────────────

def _sn_generate_qr(url: str, gen_size: int = 500, final_size: int = 431) -> Optional[Image.Image]:
    import tempfile
    from app.services.qr_local import generate_qr
    with tempfile.TemporaryDirectory() as tmp:
        path = generate_qr(
            url=url, temp_dir=tmp,
            target_size=(gen_size, gen_size),
            color_dark="#4B6179", color_bg="#FFFFFF",
            corner_radius=0, logo_path=None,
        )
        img = Image.open(path).convert("RGBA")
    img = img.resize((final_size, final_size), Image.Resampling.LANCZOS)
    mask = Image.new("L", (final_size, final_size), 0)
    d = ImageDraw.Draw(mask)
    d.rounded_rectangle([(0, 0), (final_size, final_size)], radius=16, fill=255)
    img.putalpha(mask)
    return img


# ── Ядро генерации ────────────────────────────────────────────────────────────

def _create_subito_new(variant: str, lang: str, title: str, price: float,
                       photo: str = None, url: str = "") -> bytes:
    frame_idx  = _SUBITO_NEW_FRAMES[variant]
    frame_name = f"subito{frame_idx}"
    service_key = f"subito_{variant}_{lang}"

    template_json, frame_img_cached, frame_node, use_cache = load_template_with_cache(
        service_key, "Page 2", frame_name
    )
    if not frame_node:
        raise FigmaNodeNotFoundError(f"Frame {frame_name} not found")

    frame_img = get_frame_image(frame_node, frame_img_cached, use_cache)
    w = int(frame_node["absoluteBoundingBox"]["width"]  * CFG.SCALE_FACTOR)
    h = int(frame_node["absoluteBoundingBox"]["height"] * CFG.SCALE_FACTOR)
    frame_img = frame_img.resize((w, h), Image.Resampling.LANCZOS)

    result = Image.new("RGBA", (w, h), (255, 255, 255, 0))
    result.paste(frame_img, (0, 0))
    draw = ImageDraw.Draw(result)

    def _node(name):
        return _figma_find_node(template_json, "Page 2", name)

    def _box(node):
        b  = node["absoluteBoundingBox"]
        fb = frame_node["absoluteBoundingBox"]
        return (
            int((b["x"] - fb["x"]) * CFG.SCALE_FACTOR),
            int((b["y"] - fb["y"]) * CFG.SCALE_FACTOR),
            int(b["width"]  * CFG.SCALE_FACTOR),
            int(b["height"] * CFG.SCALE_FACTOR),
        )

    nazv_font  = _sn_get_font("LFTEticaSb.ttf",         int(48 * CFG.SCALE_FACTOR))
    ogg_font   = _sn_get_font("LFTEticaBk.ttf",         int(50 * CFG.SCALE_FACTOR))
    total_font = _sn_get_font("LFTEticaSb.ttf",         int(50 * CFG.SCALE_FACTOR))
    time_font  = _sn_get_font("SFProText-Semibold.ttf", int(53 * CFG.SCALE_FACTOR))

    nazv_sp  = 0
    price_sp = 0
    ogg_sp   = int(50 * CFG.SCALE_FACTOR * -0.01)
    total_sp = int(50 * CFG.SCALE_FACTOR * -0.01)
    time_sp  = int(53 * CFG.SCALE_FACTOR * -0.02)
    max_w    = int(880 * CFG.SCALE_FACTOR)

    n = _node(f"nazv_{frame_name}")
    if n:
        nx, ny, _, _ = _box(n)
        _sn_draw_left(draw, _sn_truncate(title or "", nazv_font, nazv_sp, max_w),
                      nazv_font, nx, ny, "#3C4858", nazv_sp)

    n = _node(f"price_{frame_name}")
    if n:
        px, py, _, _ = _box(n)
        _sn_draw_left(draw, _sn_format_price_main(price), nazv_font, px, py, "#F9423A", price_sp)

    n = _node(f"oggetto_{frame_name}")
    if n:
        ox, oy, ow, _ = _box(n)
        _sn_draw_right(draw, _sn_format_price_always(price), ogg_font, ox + ow, oy, "#3C4858", ogg_sp)

    n = _node(f"totalprice_{frame_name}")
    if n:
        tx, ty, tw, _ = _box(n)
        _sn_draw_right(draw, _sn_format_total(price), total_font, tx + tw, ty, "#3C4858", total_sp)

    n = _node(f"pic_{frame_name}")
    if n and photo:
        pic_x, pic_y, _, _ = _box(n)
        cw = int(186 * CFG.SCALE_FACTOR)
        ch = int(138 * CFG.SCALE_FACTOR)
        photo_img = _sn_photo_rounded(photo, cw, ch, int(8 * CFG.SCALE_FACTOR))
        if photo_img:
            result.paste(photo_img, (pic_x, pic_y), photo_img)

    if variant == "qr" and url:
        n = _node(f"qr_{frame_name}")
        if n:
            qr_x, qr_y, qr_w, qr_h = _box(n)
            qr_img = _sn_generate_qr(url)
            if qr_img:
                result.paste(qr_img,
                             (qr_x + (qr_w - qr_img.width) // 2,
                              qr_y + (qr_h - qr_img.height) // 2),
                             qr_img)

    n = _node(f"time_{frame_name}")
    if n:
        time_x, time_y, time_w, _ = _box(n)
        now = datetime.datetime.now(timezone("Europe/Rome"))
        _sn_draw_center(draw, f"{now.hour:02d}:{now.minute:02d}",
                        time_font, time_x + time_w / 2, time_y, "#FFFFFF", time_sp)

    buf = io.BytesIO()
    result.convert("RGB").save(buf, format="PNG", optimize=True)
    return buf.getvalue()


# ── Публичные функции ────────────────────────────────────────────────────────

def create_subito_new_email_request(lang: str, title: str, price: float, photo: str = None) -> bytes:
    return _create_subito_new("email_request", lang, title, price, photo)

def create_subito_new_phone_request(lang: str, title: str, price: float, photo: str = None) -> bytes:
    return _create_subito_new("phone_request", lang, title, price, photo)

def create_subito_new_email_payment(lang: str, title: str, price: float, photo: str = None) -> bytes:
    return _create_subito_new("email_payment", lang, title, price, photo)

def create_subito_new_sms_payment(lang: str, title: str, price: float, photo: str = None) -> bytes:
    return _create_subito_new("sms_payment", lang, title, price, photo)

def create_subito_new_qr(lang: str, title: str, price: float, photo: str = None, url: str = "") -> bytes:
    return _create_subito_new("qr", lang, title, price, photo, url)
