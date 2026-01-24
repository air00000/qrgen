# app/services/wallapop_variants.py
import base64
import datetime
import io
import os
from decimal import Decimal, ROUND_DOWN
from typing import Optional

import requests
from PIL import Image, ImageDraw, ImageFont, ImageOps
from pytz import timezone

from app.config import CFG
from app.services.figma import find_node
from app.services.cache_wrapper import load_template_with_cache, get_frame_image
from app.services.pdf import (
    PDFGenerationError,
    FigmaNodeNotFoundError,
    QRGenerationError,
    draw_text_with_letter_spacing,
    create_rounded_mask,
)

WALLAPOP_VARIANTS = {
    "email_request": {"frame_index": 3, "label": "Email запрос", "has_big_price": False, "has_qr": False},
    "phone_request": {"frame_index": 4, "label": "Телефон запрос", "has_big_price": False, "has_qr": False},
    "email_payment": {"frame_index": 5, "label": "Email оплата", "has_big_price": True, "has_qr": False},
    "sms_payment": {"frame_index": 6, "label": "SMS оплата", "has_big_price": True, "has_qr": False},
    "qr": {"frame_index": 7, "label": "QR", "has_big_price": False, "has_qr": True},
}

LANG_TIMEZONES = {
    "uk": "Europe/London",
    "es": "Europe/Madrid",
    "it": "Europe/Rome",
    "fr": "Europe/Paris",
    "pr": "Europe/Lisbon",
}

QR_LOGO_URL = "https://i.ibb.co/pvwMgd8k/Rectangle-355.png"


def _get_font(font_name: str, size: int) -> ImageFont.FreeTypeFont:
    path = os.path.join(CFG.FONTS_DIR, font_name)
    if os.path.exists(path):
        return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def _format_price_eur(price: float) -> str:
    amount = Decimal(str(price)).quantize(Decimal("0.01"), rounding=ROUND_DOWN)
    return f"{amount:.2f}".replace(".", ",") + " €"


def _split_price(price: float) -> tuple[str, str]:
    amount = Decimal(str(price)).quantize(Decimal("0.01"), rounding=ROUND_DOWN)
    euros = int(amount // 1)
    cents = int((amount - euros) * 100)
    return str(euros), f"{cents:02d}€"


def _text_width_with_spacing(font: ImageFont.ImageFont, text: str, letter_spacing: int) -> float:
    if not text:
        return 0
    widths = [font.getbbox(ch)[2] for ch in text]
    return sum(widths) + letter_spacing * (len(text) - 1)


def _truncate_title(text: str, font: ImageFont.ImageFont, letter_spacing: int) -> str:
    max_width = int(666 * CFG.SCALE_FACTOR)
    max_width_with_ellipsis = int(735 * CFG.SCALE_FACTOR)
    if _text_width_with_spacing(font, text, letter_spacing) <= max_width:
        return text
    ellipsis = "..."
    trimmed = text
    while trimmed and _text_width_with_spacing(font, trimmed + ellipsis, letter_spacing) > max_width_with_ellipsis:
        trimmed = trimmed[:-1]
    return trimmed + ellipsis


def _draw_centered_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, center_x: float, y: float,
                        fill: str, letter_spacing: int = 0):
    total_width = _text_width_with_spacing(font, text, letter_spacing)
    start_x = center_x - total_width / 2
    draw_text_with_letter_spacing(draw, text, font, start_x, y, fill, letter_spacing=letter_spacing)


def _rounded_rect_image(photo_b64: str, size: tuple[int, int], radius: int) -> Optional[Image.Image]:
    if not photo_b64:
        return None
    img = Image.open(io.BytesIO(base64.b64decode(photo_b64))).convert("RGBA")
    img = ImageOps.fit(img, size, Image.Resampling.LANCZOS)
    mask = Image.new("L", size, 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle([(0, 0), size], radius=radius, fill=255)
    rounded = Image.new("RGBA", size, (255, 255, 255, 0))
    rounded.paste(img, (0, 0), mask)
    return rounded


def _circle_image(photo_b64: str, size: tuple[int, int]) -> Optional[Image.Image]:
    if not photo_b64:
        return None
    img = Image.open(io.BytesIO(base64.b64decode(photo_b64))).convert("RGBA")
    img = ImageOps.fit(img, size, Image.Resampling.LANCZOS)
    mask = Image.new("L", size, 0)
    draw = ImageDraw.Draw(mask)
    draw.ellipse([(0, 0), size], fill=255)
    rounded = Image.new("RGBA", size, (255, 255, 255, 0))
    rounded.paste(img, (0, 0), mask)
    return rounded


def _generate_wallapop_qr(url: str) -> Image.Image:
    headers = {"Authorization": f"Bearer {CFG.QR_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "qrCategory": "url",
        "text": url,
        "size": 800,
        "colorDark": "#000000",
        "backgroundColor": "#FFFFFF",
        "transparentBkg": False,
        "eye_outer": "eyeOuter2",
        "eye_inner": "eyeInner2",
        "qrData": "pattern4",
        "logo": QR_LOGO_URL,
    }

    response = requests.post(CFG.QR_ENDPOINT, json=payload, headers=headers)
    if response.status_code != 200:
        raise QRGenerationError(f"Ошибка QR API: {response.text}")
    data = response.json().get("data")
    if not data:
        raise QRGenerationError("Нет данных QR в ответе от API")
    qr_bytes = base64.b64decode(data)
    return Image.open(io.BytesIO(qr_bytes)).convert("RGBA")


def create_wallapop_image(
    variant: str,
    lang: str,
    title: str,
    price: float,
    photo_b64: Optional[str] = None,
    seller_name: str = "",
    seller_photo_b64: Optional[str] = None,
    url: Optional[str] = None,
) -> bytes:
    if variant not in WALLAPOP_VARIANTS:
        raise PDFGenerationError("Unknown wallapop variant")
    if lang not in LANG_TIMEZONES:
        raise PDFGenerationError("lang must be: uk/es/it/fr/pr")

    frame_index = WALLAPOP_VARIANTS[variant]["frame_index"]
    frame_name = f"wallapop{frame_index}_{lang}"
    service_name = f"wallapop_{variant}_{lang}"

    template_json, frame_img_cached, frame_node, use_cache = load_template_with_cache(
        service_name, "Page 3", frame_name
    )

    if not frame_node:
        raise FigmaNodeNotFoundError(f"Фрейм {frame_name} не найден")

    frame_img = get_frame_image(frame_node, frame_img_cached, use_cache)
    width = int(frame_node["absoluteBoundingBox"]["width"] * CFG.SCALE_FACTOR)
    height = int(frame_node["absoluteBoundingBox"]["height"] * CFG.SCALE_FACTOR)
    frame_img = frame_img.resize((width, height), Image.Resampling.LANCZOS)

    result = Image.new("RGBA", (width, height), (255, 255, 255, 0))
    result.paste(frame_img, (0, 0))
    draw = ImageDraw.Draw(result)

    def _node(name: str):
        node = find_node(template_json, "Page 3", name)
        if not node:
            raise FigmaNodeNotFoundError(f"Не найден узел: {name}")
        return node

    def _node_box(node):
        box = node["absoluteBoundingBox"]
        x = int((box["x"] - frame_node["absoluteBoundingBox"]["x"]) * CFG.SCALE_FACTOR)
        y = int((box["y"] - frame_node["absoluteBoundingBox"]["y"]) * CFG.SCALE_FACTOR)
        w = int(box["width"] * CFG.SCALE_FACTOR)
        h = int(box["height"] * CFG.SCALE_FACTOR)
        return x, y, w, h

    nodes = {
        "title": _node(f"nazvwal{frame_index}_{lang}"),
        "price": _node(f"pricewal{frame_index}_{lang}"),
        "name": _node(f"namewal{frame_index}_{lang}"),
        "time": _node(f"timewal{frame_index}_{lang}"),
        "photo": _node(f"picwal{frame_index}_{lang}"),
        "avatar": _node(f"avapicwal{frame_index}_{lang}"),
    }

    if WALLAPOP_VARIANTS[variant]["has_big_price"]:
        nodes["big_price"] = _node(f"bigpricewal{frame_index}_{lang}")

    if WALLAPOP_VARIANTS[variant]["has_qr"]:
        nodes["qr"] = _node(f"qrwal{frame_index}_{lang}")

    title_font = _get_font("Megabyte-Regular.ttf", int(46 * CFG.SCALE_FACTOR))
    price_font = _get_font("Megabyte-Medium.ttf", int(64 * CFG.SCALE_FACTOR))
    name_font = _get_font("Megabyte-Bold.ttf", int(48 * CFG.SCALE_FACTOR))
    time_font = _get_font("SFProText-Semibold.ttf", int(53 * CFG.SCALE_FACTOR))
    big_price_font = _get_font("Montserrat-SemiBold.ttf", int(230 * CFG.SCALE_FACTOR))
    big_price_small_font = _get_font("Montserrat-SemiBold.ttf", int(137 * CFG.SCALE_FACTOR))

    title_spacing = int(46 * CFG.SCALE_FACTOR * 0.01)
    price_spacing = int(64 * CFG.SCALE_FACTOR * -0.02)
    time_spacing = int(53 * CFG.SCALE_FACTOR * -0.02)

    title = _truncate_title(title, title_font, title_spacing)

    title_x, title_y, _, _ = _node_box(nodes["title"])
    draw_text_with_letter_spacing(draw, title, title_font, title_x, title_y, "#000000", letter_spacing=title_spacing)

    price_text = _format_price_eur(price)
    price_x, price_y, _, _ = _node_box(nodes["price"])
    draw_text_with_letter_spacing(draw, price_text, price_font, price_x, price_y, "#000000", letter_spacing=price_spacing)

    name_x, name_y, _, _ = _node_box(nodes["name"])
    draw.text((name_x, name_y), seller_name, font=name_font, fill="#5C7A89")

    tz = timezone(LANG_TIMEZONES[lang])
    now = datetime.datetime.now(tz)
    time_text = f"{now.hour:02d}:{now.minute:02d}"
    time_x, time_y, time_w, _ = _node_box(nodes["time"])
    _draw_centered_text(
        draw,
        time_text,
        time_font,
        time_x + time_w / 2,
        time_y,
        "#000000",
        letter_spacing=time_spacing,
    )

    photo_x, photo_y, _, _ = _node_box(nodes["photo"])
    photo_size = (int(427 * CFG.SCALE_FACTOR), int(525 * CFG.SCALE_FACTOR))
    photo_img = _rounded_rect_image(photo_b64, photo_size, int(14 * CFG.SCALE_FACTOR))
    if photo_img:
        result.paste(photo_img, (photo_x, photo_y), photo_img)

    avatar_x, avatar_y, _, _ = _node_box(nodes["avatar"])
    avatar_size = (int(146 * CFG.SCALE_FACTOR), int(146 * CFG.SCALE_FACTOR))
    avatar_img = _circle_image(seller_photo_b64, avatar_size)
    if avatar_img:
        result.paste(avatar_img, (avatar_x, avatar_y), avatar_img)

    if WALLAPOP_VARIANTS[variant]["has_big_price"]:
        big_price_node = nodes["big_price"]
        bp_x, bp_y, bp_w, _ = _node_box(big_price_node)
        euros, cents = _split_price(price)
        big_width = _text_width_with_spacing(big_price_font, euros, 0)
        small_width = _text_width_with_spacing(big_price_small_font, cents, 0)
        total_width = big_width + small_width
        start_x = bp_x + (bp_w - total_width) / 2
        draw.text((start_x, bp_y), euros, font=big_price_font, fill="#172E36")
        offset_y = bp_y - int(230 * CFG.SCALE_FACTOR * 0.35)
        draw.text((start_x + big_width, offset_y), cents, font=big_price_small_font, fill="#172E36")

    if WALLAPOP_VARIANTS[variant]["has_qr"]:
        if not url:
            raise PDFGenerationError("URL is required for QR variant")
        qr_node = nodes["qr"]
        qr_x, qr_y, qr_w, qr_h = _node_box(qr_node)
        qr_img = _generate_wallapop_qr(url)
        target_size = min(qr_w, qr_h, int(738 * CFG.SCALE_FACTOR))
        qr_img = qr_img.resize((target_size, target_size), Image.Resampling.LANCZOS)
        mask = create_rounded_mask((target_size, target_size), int(16 * CFG.SCALE_FACTOR))
        qr_img.putalpha(mask)
        paste_x = qr_x + (qr_w - target_size) // 2
        paste_y = qr_y + (qr_h - target_size) // 2
        result.paste(qr_img, (paste_x, paste_y), qr_img)

    output = io.BytesIO()
    result.save(output, format="PNG")
    return output.getvalue()


def create_wallapop_email_request(lang: str, title: str, price: float, photo: str = None,
                                  seller_name: str = "", seller_photo: str = None) -> bytes:
    return create_wallapop_image(
        "email_request", lang, title, price, photo_b64=photo, seller_name=seller_name, seller_photo_b64=seller_photo
    )


def create_wallapop_phone_request(lang: str, title: str, price: float, photo: str = None,
                                  seller_name: str = "", seller_photo: str = None) -> bytes:
    return create_wallapop_image(
        "phone_request", lang, title, price, photo_b64=photo, seller_name=seller_name, seller_photo_b64=seller_photo
    )


def create_wallapop_email_payment(lang: str, title: str, price: float, photo: str = None,
                                  seller_name: str = "", seller_photo: str = None) -> bytes:
    return create_wallapop_image(
        "email_payment", lang, title, price, photo_b64=photo, seller_name=seller_name, seller_photo_b64=seller_photo
    )


def create_wallapop_sms_payment(lang: str, title: str, price: float, photo: str = None,
                                seller_name: str = "", seller_photo: str = None) -> bytes:
    return create_wallapop_image(
        "sms_payment", lang, title, price, photo_b64=photo, seller_name=seller_name, seller_photo_b64=seller_photo
    )


def create_wallapop_qr(lang: str, title: str, price: float, photo: str = None,
                       seller_name: str = "", seller_photo: str = None, url: str = "") -> bytes:
    return create_wallapop_image(
        "qr", lang, title, price, photo_b64=photo, seller_name=seller_name, seller_photo_b64=seller_photo, url=url
    )
