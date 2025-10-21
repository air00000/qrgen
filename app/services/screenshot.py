# app/services/screenshot.py
import os
import uuid
from datetime import datetime
from io import BytesIO
from typing import Optional, Tuple

from PIL import Image, ImageDraw, ImageFont

from app.config import CFG
from app.services.figma import (
    get_template_json,
    find_node,
    export_frame_as_png,
)
from app.services.qr_local import generate_qr


def _rounded_mask(size: Tuple[int, int], radius: int) -> Image.Image:
    mask = Image.new("L", size, 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle([(0, 0), size], radius=radius, fill=255)
    return mask


def _process_photo(image_path: str, temp_dir: str) -> str:
    img = Image.open(image_path).convert("RGBA")
    width, height = img.size
    size = min(width, height)
    left = (width - size) // 2
    top = (height - size) // 2
    img = img.crop((left, top, left + size, top + size))
    mask = _rounded_mask((size, size), CFG.CORNER_RADIUS * CFG.SCALE_FACTOR)
    img.putalpha(mask)
    out_path = os.path.join(temp_dir, f"processed_{uuid.uuid4()}.png")
    img.save(out_path, "PNG")
    return out_path


def _load_font(path: str, size: int) -> ImageFont.FreeTypeFont:
    if os.path.exists(path):
        return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def _text_width(text: str, font: ImageFont.ImageFont, draw: ImageDraw.ImageDraw) -> float:
    if hasattr(font, "getlength"):
        return font.getlength(text)
    if hasattr(draw, "textlength"):
        return draw.textlength(text, font=font)
    bbox = font.getbbox(text)
    return bbox[2] - bbox[0]


def _format_price(value: str) -> str:
    try:
        numeric = float(value.replace(",", "."))
        return f"€{numeric:.2f}"
    except Exception:
        value = value.strip()
        return value if value.startswith("€") else f"€{value}"


def _char_width(font: ImageFont.ImageFont, ch: str) -> float:
    if hasattr(font, "getlength"):
        return font.getlength(ch)
    bbox = font.getbbox(ch)
    return bbox[2] - bbox[0]


def _draw_with_letter_spacing(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.ImageFont,
    x: float,
    y: float,
    *,
    fill: str,
    letter_spacing: float = 0,
    align: str = "left",
):
    if not text:
        return

    total = sum(_char_width(font, ch) for ch in text)
    if len(text) > 1:
        total += letter_spacing * (len(text) - 1)

    if align == "right":
        x -= total

    cursor = x
    for ch in text:
        draw.text((cursor, y), ch, font=font, fill=fill)
        cursor += _char_width(font, ch) + letter_spacing


def _marktplaats_screenshot(
    template_json,
    nazvanie: str,
    price: str,
    photo_path: Optional[str],
    url: str,
) -> Tuple[str, Optional[str], Optional[str]]:
    frame_name = "Marktplaats"
    nazvanie_layer = "1NAZVANIE"
    price_layer = "1PRICE"
    time_layer = "1TIME"
    foto_layer = "1FOTO"
    qr_layer = "1QR"

    frame_node = find_node(template_json, "Page 2", frame_name)
    nazvanie_node = find_node(template_json, "Page 2", nazvanie_layer)
    price_node = find_node(template_json, "Page 2", price_layer)
    time_node = find_node(template_json, "Page 2", time_layer)
    foto_node = find_node(template_json, "Page 2", foto_layer)
    qr_node = find_node(template_json, "Page 2", qr_layer)

    for node, name in [
        (frame_node, frame_name),
        (nazvanie_node, nazvanie_layer),
        (price_node, price_layer),
        (time_node, time_layer),
        (foto_node, foto_layer),
        (qr_node, qr_layer),
    ]:
        if not node:
            raise RuntimeError(f"Узел не найден: {name}")

    template_png = export_frame_as_png(CFG.TEMPLATE_FILE_KEY, frame_node["id"])
    template_img = Image.open(BytesIO(template_png)).convert("RGBA")

    frame_width = int(frame_node["absoluteBoundingBox"]["width"] * CFG.SCALE_FACTOR)
    frame_height = int(frame_node["absoluteBoundingBox"]["height"] * CFG.SCALE_FACTOR)
    template_img = template_img.resize((frame_width, frame_height), Image.Resampling.LANCZOS)

    result_img = Image.new("RGBA", (frame_width, frame_height), (255, 255, 255, 0))
    result_img.paste(template_img, (0, 0))
    draw = ImageDraw.Draw(result_img)

    processed_photo_path = None
    if photo_path:
        processed_photo_path = _process_photo(photo_path, CFG.TEMP_DIR)
        foto_img = Image.open(processed_photo_path).convert("RGBA")
        fw = int(foto_node["absoluteBoundingBox"]["width"] * CFG.SCALE_FACTOR)
        fh = int(foto_node["absoluteBoundingBox"]["height"] * CFG.SCALE_FACTOR)
        fx = int(
            (foto_node["absoluteBoundingBox"]["x"] - frame_node["absoluteBoundingBox"]["x"]) * CFG.SCALE_FACTOR
        )
        fy = int(
            (foto_node["absoluteBoundingBox"]["y"] - frame_node["absoluteBoundingBox"]["y"]) * CFG.SCALE_FACTOR
        )
        foto_img = foto_img.resize((fw, fh), Image.Resampling.LANCZOS)
        result_img.paste(foto_img, (fx, fy), foto_img)

    qw = int(qr_node["absoluteBoundingBox"]["width"] * CFG.SCALE_FACTOR)
    qh = int(qr_node["absoluteBoundingBox"]["height"] * CFG.SCALE_FACTOR)
    qx = int(
        (qr_node["absoluteBoundingBox"]["x"] - frame_node["absoluteBoundingBox"]["x"]) * CFG.SCALE_FACTOR
    )
    qy = int(
        (qr_node["absoluteBoundingBox"]["y"] - frame_node["absoluteBoundingBox"]["y"]) * CFG.SCALE_FACTOR
    )
    qr_path = generate_qr(
        url,
        str(CFG.TEMP_DIR),
        target_size=(qw, qh),
        color_dark="#4B6179",
        color_bg="#FFFFFF",
        corner_radius=int(CFG.CORNER_RADIUS * CFG.SCALE_FACTOR),
        logo_path=None,
    )
    qr_img = Image.open(qr_path).convert("RGBA")
    qr_img = qr_img.resize((qw, qh), Image.Resampling.LANCZOS)
    result_img.paste(qr_img, (qx, qy), qr_img)

    nazv_font = _load_font(os.path.join(CFG.FONTS_DIR, "Inter_18pt-SemiBold.ttf"), int(96 * CFG.SCALE_FACTOR))
    price_font = _load_font(os.path.join(CFG.FONTS_DIR, "Inter_18pt-Medium.ttf"), int(96 * CFG.SCALE_FACTOR))
    time_font = _load_font(os.path.join(CFG.FONTS_DIR, "SFProText-Semibold.ttf"), int(108 * CFG.SCALE_FACTOR))

    nx = (
        (nazvanie_node["absoluteBoundingBox"]["x"] - frame_node["absoluteBoundingBox"]["x"]) * CFG.SCALE_FACTOR
    )
    ny = (
        (nazvanie_node["absoluteBoundingBox"]["y"] - frame_node["absoluteBoundingBox"]["y"]) * CFG.SCALE_FACTOR
        + CFG.TEXT_OFFSET * CFG.SCALE_FACTOR
    )
    draw.text((nx, ny), nazvanie, font=nazv_font, fill="#1F262D")

    price_value = _format_price(price)
    px = (price_node["absoluteBoundingBox"]["x"] - frame_node["absoluteBoundingBox"]["x"]) * CFG.SCALE_FACTOR
    py = (
        (price_node["absoluteBoundingBox"]["y"] - frame_node["absoluteBoundingBox"]["y"]) * CFG.SCALE_FACTOR
        + CFG.TEXT_OFFSET * CFG.SCALE_FACTOR
    )
    draw.text((px, py), price_value, font=price_font, fill="#838383")

    time_text = datetime.now(CFG.TZ).strftime("%H:%M")
    time_box = time_node["absoluteBoundingBox"]
    tx = (time_box["x"] - frame_node["absoluteBoundingBox"]["x"]) * CFG.SCALE_FACTOR
    ty = (
        (time_box["y"] - frame_node["absoluteBoundingBox"]["y"]) * CFG.SCALE_FACTOR
        + CFG.TEXT_OFFSET * CFG.SCALE_FACTOR
    )
    time_width = time_box["width"] * CFG.SCALE_FACTOR
    text_width = _text_width(time_text, time_font, draw)
    draw.text((tx + time_width - text_width, ty), time_text, font=time_font, fill="#000000")

    target_size = CFG.SCREENSHOT_SIZE
    if target_size and (frame_width, frame_height) != target_size:
        result_img = result_img.resize(target_size, Image.Resampling.LANCZOS)

    result_rgb = result_img.convert("RGB")
    out_path = os.path.join(CFG.TEMP_DIR, f"MARKTPLAATS_{uuid.uuid4()}.png")
    result_rgb.save(out_path, "PNG", optimize=True)

    return out_path, processed_photo_path, qr_path


def _subito_screenshot(
    template_json,
    nazvanie: str,
    price: str,
    photo_path: Optional[str],
    url: str,
    *,
    name: str = "",
    address: str = "",
) -> Tuple[str, Optional[str], Optional[str]]:
    frame_name = "subito1"
    nazvanie_layer = "NAZVANIE_SUB1"
    price_layer = "PRICE_SUB1"
    total_layer = "TOTAL_SUB1"
    address_layer = "ADRESS_SUB1"
    name_layer = "IMYA_SUB1"
    time_layer = "TIME_SUB1"
    foto_layer = "PHOTO_SUB1"
    qr_layer = "QR_SUB1"

    frame_node = find_node(template_json, "Page 2", frame_name)
    nazvanie_node = find_node(template_json, "Page 2", nazvanie_layer)
    price_node = find_node(template_json, "Page 2", price_layer)
    total_node = find_node(template_json, "Page 2", total_layer)
    address_node = find_node(template_json, "Page 2", address_layer)
    name_node = find_node(template_json, "Page 2", name_layer)
    time_node = find_node(template_json, "Page 2", time_layer)
    foto_node = find_node(template_json, "Page 2", foto_layer)
    qr_node = find_node(template_json, "Page 2", qr_layer)

    for node, label in [
        (frame_node, frame_name),
        (nazvanie_node, nazvanie_layer),
        (price_node, price_layer),
        (total_node, total_layer),
        (address_node, address_layer),
        (name_node, name_layer),
        (time_node, time_layer),
        (foto_node, foto_layer),
        (qr_node, qr_layer),
    ]:
        if not node:
            raise RuntimeError(f"Узел не найден: {label}")

    template_png = export_frame_as_png(CFG.TEMPLATE_FILE_KEY, frame_node["id"])
    template_img = Image.open(BytesIO(template_png)).convert("RGBA")

    frame_width = int(frame_node["absoluteBoundingBox"]["width"] * CFG.SCALE_FACTOR)
    frame_height = int(frame_node["absoluteBoundingBox"]["height"] * CFG.SCALE_FACTOR)
    template_img = template_img.resize((frame_width, frame_height), Image.Resampling.LANCZOS)

    result_img = Image.new("RGBA", (frame_width, frame_height), (255, 255, 255, 0))
    result_img.paste(template_img, (0, 0))
    draw = ImageDraw.Draw(result_img)

    processed_photo_path = None
    if photo_path:
        processed_photo_path = _process_photo(photo_path, CFG.TEMP_DIR)
        foto_img = Image.open(processed_photo_path).convert("RGBA")
        fw = int(foto_node["absoluteBoundingBox"]["width"] * CFG.SCALE_FACTOR)
        fh = int(foto_node["absoluteBoundingBox"]["height"] * CFG.SCALE_FACTOR)
        fx = int(
            (foto_node["absoluteBoundingBox"]["x"] - frame_node["absoluteBoundingBox"]["x"]) * CFG.SCALE_FACTOR
        )
        fy = int(
            (foto_node["absoluteBoundingBox"]["y"] - frame_node["absoluteBoundingBox"]["y"]) * CFG.SCALE_FACTOR
        )
        foto_img = foto_img.resize((fw, fh), Image.Resampling.LANCZOS)
        result_img.paste(foto_img, (fx, fy), foto_img)

    qw = int(qr_node["absoluteBoundingBox"]["width"] * CFG.SCALE_FACTOR)
    qh = int(qr_node["absoluteBoundingBox"]["height"] * CFG.SCALE_FACTOR)
    qx = int(
        (qr_node["absoluteBoundingBox"]["x"] - frame_node["absoluteBoundingBox"]["x"]) * CFG.SCALE_FACTOR
    )
    qy = int(
        (qr_node["absoluteBoundingBox"]["y"] - frame_node["absoluteBoundingBox"]["y"]) * CFG.SCALE_FACTOR
    )

    logo_path = CFG.SUBITO_QR_LOGO if os.path.exists(CFG.SUBITO_QR_LOGO) else None
    qr_path = generate_qr(
        url,
        str(CFG.TEMP_DIR),
        target_size=(qw, qh),
        color_dark=CFG.SUBITO_QR_COLOR,
        color_bg="#FFFFFF",
        corner_radius=int(CFG.CORNER_RADIUS * CFG.SCALE_FACTOR),
        logo_path=logo_path,
    )
    qr_img = Image.open(qr_path).convert("RGBA")
    qr_img = qr_img.resize((qw, qh), Image.Resampling.LANCZOS)
    result_img.paste(qr_img, (qx, qy), qr_img)

    aktiv_path = os.path.join(CFG.FONTS_DIR, "AktivGroteskCorp-Medium.ttf")
    nazv_font = _load_font(aktiv_path, int(96 * CFG.SCALE_FACTOR))
    small_font = _load_font(aktiv_path, int(64 * CFG.SCALE_FACTOR))
    time_font = _load_font(os.path.join(CFG.FONTS_DIR, "SFProText-Semibold.ttf"), int(112 * CFG.SCALE_FACTOR))

    nx = (
        (nazvanie_node["absoluteBoundingBox"]["x"] - frame_node["absoluteBoundingBox"]["x"]) * CFG.SCALE_FACTOR
    )
    ny = (
        (nazvanie_node["absoluteBoundingBox"]["y"] - frame_node["absoluteBoundingBox"]["y"]) * CFG.SCALE_FACTOR
        + CFG.TEXT_OFFSET * CFG.SCALE_FACTOR
    )
    draw.text((nx, ny), nazvanie, font=nazv_font, fill="#1F262D")

    price_value = _format_price(price)
    px = (price_node["absoluteBoundingBox"]["x"] - frame_node["absoluteBoundingBox"]["x"]) * CFG.SCALE_FACTOR
    py = (
        (price_node["absoluteBoundingBox"]["y"] - frame_node["absoluteBoundingBox"]["y"]) * CFG.SCALE_FACTOR
        + CFG.TEXT_OFFSET * CFG.SCALE_FACTOR
    )
    draw.text((px, py), price_value, font=nazv_font, fill="#838386")

    total_box = total_node["absoluteBoundingBox"]
    total_right = (
        (total_box["x"] - frame_node["absoluteBoundingBox"]["x"] + total_box["width"]) * CFG.SCALE_FACTOR
    )
    total_y = (
        (total_box["y"] - frame_node["absoluteBoundingBox"]["y"]) * CFG.SCALE_FACTOR
        + CFG.TEXT_OFFSET * CFG.SCALE_FACTOR
    )
    _draw_with_letter_spacing(
        draw,
        price_value,
        nazv_font,
        total_right,
        total_y,
        fill="#838386",
        align="right",
    )

    small_size = getattr(small_font, "size", int(64 * CFG.SCALE_FACTOR))
    line_height = int(small_size * 1.219)

    name_x = (name_node["absoluteBoundingBox"]["x"] - frame_node["absoluteBoundingBox"]["x"]) * CFG.SCALE_FACTOR
    name_y = (
        (name_node["absoluteBoundingBox"]["y"] - frame_node["absoluteBoundingBox"]["y"]) * CFG.SCALE_FACTOR
        + CFG.TEXT_OFFSET * CFG.SCALE_FACTOR
    )
    if name:
        for idx, line in enumerate(str(name).splitlines()):
            draw.text((name_x, name_y + idx * line_height), line.strip(), font=small_font, fill="#838386")

    address_x = (address_node["absoluteBoundingBox"]["x"] - frame_node["absoluteBoundingBox"]["x"]) * CFG.SCALE_FACTOR
    address_y = (
        (address_node["absoluteBoundingBox"]["y"] - frame_node["absoluteBoundingBox"]["y"]) * CFG.SCALE_FACTOR
        + CFG.TEXT_OFFSET * CFG.SCALE_FACTOR
    )
    if address:
        for idx, line in enumerate(str(address).splitlines()):
            draw.text((address_x, address_y + idx * line_height), line.strip(), font=small_font, fill="#838386")

    time_text = datetime.now(CFG.SUBITO_TZ).strftime("%H:%M")
    time_box = time_node["absoluteBoundingBox"]
    time_right = (
        (time_box["x"] - frame_node["absoluteBoundingBox"]["x"] + time_box["width"]) * CFG.SCALE_FACTOR
    )
    time_y = (
        (time_box["y"] - frame_node["absoluteBoundingBox"]["y"]) * CFG.SCALE_FACTOR
        + CFG.TEXT_OFFSET * CFG.SCALE_FACTOR
    )
    letter_spacing = int(112 * CFG.SCALE_FACTOR * 0.02)
    _draw_with_letter_spacing(
        draw,
        time_text,
        time_font,
        time_right,
        time_y,
        fill="#FFFFFF",
        letter_spacing=letter_spacing,
        align="right",
    )

    target_size = CFG.SCREENSHOT_SIZE
    if target_size and (frame_width, frame_height) != target_size:
        result_img = result_img.resize(target_size, Image.Resampling.LANCZOS)

    result_rgb = result_img.convert("RGB")
    out_path = os.path.join(CFG.TEMP_DIR, f"SUBITO_{uuid.uuid4()}.png")
    result_rgb.save(out_path, "PNG", optimize=True)

    return out_path, processed_photo_path, qr_path


def create_screenshot(
    template: str,
    nazvanie: str,
    price: str,
    photo_path: Optional[str],
    url: str,
    *,
    name: str = "",
    address: str = "",
) -> Tuple[str, Optional[str], Optional[str]]:
    os.makedirs(CFG.TEMP_DIR, exist_ok=True)

    template_key = (template or "").lower()
    template_json = get_template_json()

    if template_key == "marktplaats":
        return _marktplaats_screenshot(template_json, nazvanie, price, photo_path, url)
    if template_key == "subito":
        return _subito_screenshot(
            template_json,
            nazvanie,
            price,
            photo_path,
            url,
            name=name,
            address=address,
        )

    raise ValueError(f"Неизвестный шаблон: {template}")

