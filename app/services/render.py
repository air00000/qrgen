import os
import uuid
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from io import BytesIO
from typing import Optional

from PIL import Image, ImageDraw, ImageFont
from pytz import timezone
import datetime

from app.config import CFG
from app.services.figma import get_template_json, find_node, export_frame_as_png
from app.services.qrtiger import generate_qr
from app.utils.io import ensure_dirs


@dataclass
class ImageResult:
    path: str
    processed_photo_path: Optional[str]
    qr_path: Optional[str]


def _rounded_mask(size, radius):
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


def _save_png(image: Image.Image, path: str) -> None:
    buffer = BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    data = buffer.getvalue()
    if len(data) > 10 * 1024 * 1024:
        buffer = BytesIO()
        image.save(buffer, format="PNG", optimize=True, compress_level=9)
        data = buffer.getvalue()
    with open(path, "wb") as f:
        f.write(data)


def _load_font(filename: str, size: int) -> ImageFont.FreeTypeFont:
    font_path = os.path.join(CFG.FONTS_DIR, filename)
    if os.path.exists(font_path):
        return ImageFont.truetype(font_path, size)
    return ImageFont.load_default()


def _format_price(price: str | float | Decimal) -> str:
    try:
        value = Decimal(str(price)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError):
        raise ValueError("Некорректная цена")
    return f"€{value}"


def _measure_text(font: ImageFont.FreeTypeFont, text: str) -> int:
    if not text:
        return 0
    bbox = font.getbbox(text)
    return bbox[2] - bbox[0]


def _draw_text_with_letter_spacing(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont,
                                   x: float, y: float, fill: str, letter_spacing: float = 0.0,
                                   align: str = "left") -> None:
    if not text:
        return
    widths = []
    for ch in text:
        bbox = font.getbbox(ch)
        widths.append(bbox[2] - bbox[0])
    total_width = sum(widths) + letter_spacing * max(len(text) - 1, 0)
    if align == "right":
        cur_x = x - total_width
    elif align == "center":
        cur_x = x - total_width / 2
    else:
        cur_x = x
    for idx, ch in enumerate(text):
        draw.text((cur_x, y), ch, font=font, fill=fill)
        cur_x += widths[idx] + letter_spacing


def _nl_time_str() -> str:
    return datetime.datetime.now(CFG.TZ).strftime("%H:%M")


def _rome_time_str() -> str:
    tz = getattr(CFG, "SUBITO_TZ", timezone("Europe/Rome"))
    return datetime.datetime.now(tz).strftime("%H:%M")


def create_marktplaats_image(nazvanie: str, price: str | float,
                             photo_path: Optional[str], url: str) -> ImageResult:
    ensure_dirs()
    template_json = get_template_json()
    frame_name = "Marktplaats"
    nodes = {
        "frame": find_node(template_json, "Page 2", frame_name),
        "nazvanie": find_node(template_json, "Page 2", "1NAZVANIE"),
        "price": find_node(template_json, "Page 2", "1PRICE"),
        "time": find_node(template_json, "Page 2", "1TIME"),
        "foto": find_node(template_json, "Page 2", "1FOTO"),
        "qr": find_node(template_json, "Page 2", "1QR"),
    }
    missing = [key for key, node in nodes.items() if node is None]
    if missing:
        raise RuntimeError(f"Не найдены узлы: {', '.join(missing)}")

    frame_node = nodes["frame"]
    frame_box = frame_node["absoluteBoundingBox"]
    frame_width = int(frame_box["width"] * CFG.SCALE_FACTOR)
    frame_height = int(frame_box["height"] * CFG.SCALE_FACTOR)

    template_png = export_frame_as_png(CFG.TEMPLATE_FILE_KEY, frame_node["id"])
    base_img = Image.open(BytesIO(template_png)).convert("RGBA")
    base_img = base_img.resize((frame_width, frame_height), Image.Resampling.LANCZOS)

    result_img = Image.new("RGBA", (frame_width, frame_height))
    result_img.paste(base_img, (0, 0))
    draw = ImageDraw.Draw(result_img)

    processed_photo_path = None
    if photo_path and nodes["foto"]:
        processed_photo_path = _process_photo(photo_path, CFG.TEMP_DIR)
        foto_node = nodes["foto"]["absoluteBoundingBox"]
        foto_width = int(foto_node["width"] * CFG.SCALE_FACTOR)
        foto_height = int(foto_node["height"] * CFG.SCALE_FACTOR)
        foto_x = int((foto_node["x"] - frame_box["x"]) * CFG.SCALE_FACTOR)
        foto_y = int((foto_node["y"] - frame_box["y"]) * CFG.SCALE_FACTOR)
        foto_img = Image.open(processed_photo_path).convert("RGBA").resize(
            (foto_width, foto_height), Image.Resampling.LANCZOS
        )
        result_img.paste(foto_img, (foto_x, foto_y), foto_img)

    qr_path = generate_qr(url, str(CFG.TEMP_DIR))
    if nodes["qr"]:
        qr_node = nodes["qr"]["absoluteBoundingBox"]
        qr_width = int(qr_node["width"] * CFG.SCALE_FACTOR)
        qr_height = int(qr_node["height"] * CFG.SCALE_FACTOR)
        qr_x = int((qr_node["x"] - frame_box["x"]) * CFG.SCALE_FACTOR)
        qr_y = int((qr_node["y"] - frame_box["y"]) * CFG.SCALE_FACTOR)
        qr_img = Image.open(qr_path).convert("RGBA").resize((qr_width, qr_height), Image.Resampling.LANCZOS)
        result_img.paste(qr_img, (qr_x, qr_y), qr_img)

    title_font = _load_font("Inter_18pt-SemiBold.ttf", int(96 * CFG.SCALE_FACTOR))
    price_font = _load_font("Inter_18pt-Medium.ttf", int(96 * CFG.SCALE_FACTOR))
    time_font = _load_font("SFProText-Semibold.ttf", int(108 * CFG.SCALE_FACTOR))

    offset = CFG.TEXT_OFFSET * CFG.SCALE_FACTOR
    formatted_price = _format_price(price)

    nazvanie_node = nodes["nazvanie"]["absoluteBoundingBox"]
    nazvanie_x = (nazvanie_node["x"] - frame_box["x"]) * CFG.SCALE_FACTOR
    nazvanie_y = (nazvanie_node["y"] - frame_box["y"]) * CFG.SCALE_FACTOR + offset
    draw.text((nazvanie_x, nazvanie_y), nazvanie, font=title_font, fill="#1F262D")

    price_node = nodes["price"]["absoluteBoundingBox"]
    price_x = (price_node["x"] - frame_box["x"]) * CFG.SCALE_FACTOR
    price_y = (price_node["y"] - frame_box["y"]) * CFG.SCALE_FACTOR + offset
    draw.text((price_x, price_y), formatted_price, font=price_font, fill="#838383")

    time_node = nodes["time"]["absoluteBoundingBox"]
    time_x = (time_node["x"] - frame_box["x"]) * CFG.SCALE_FACTOR
    time_y = (time_node["y"] - frame_box["y"]) * CFG.SCALE_FACTOR + offset
    time_width = time_node["width"] * CFG.SCALE_FACTOR
    time_text = _nl_time_str()
    text_width = _measure_text(time_font, time_text)
    draw.text((time_x + (time_width - text_width) / 2, time_y), time_text, font=time_font, fill="#000000")

    result_img = result_img.convert("RGB")
    image_path = os.path.join(CFG.TEMP_DIR, f"MARKTPLAATS_{uuid.uuid4()}.png")
    _save_png(result_img, image_path)
    return ImageResult(path=image_path, processed_photo_path=processed_photo_path, qr_path=qr_path)


def create_subito_image(nazvanie: str, price: str | float, photo_path: Optional[str], url: str,
                        name: str = "", address: str = "") -> ImageResult:
    ensure_dirs()
    template_json = get_template_json()
    frame_name = "subito1"
    nodes = {
        "frame": find_node(template_json, "Page 2", frame_name),
        "nazvanie": find_node(template_json, "Page 2", "NAZVANIE_SUB1"),
        "price": find_node(template_json, "Page 2", "PRICE_SUB1"),
        "total": find_node(template_json, "Page 2", "TOTAL_SUB1"),
        "adress": find_node(template_json, "Page 2", "ADRESS_SUB1"),
        "imya": find_node(template_json, "Page 2", "IMYA_SUB1"),
        "time": find_node(template_json, "Page 2", "TIME_SUB1"),
        "foto": find_node(template_json, "Page 2", "PHOTO_SUB1"),
        "qr": find_node(template_json, "Page 2", "QR_SUB1"),
    }
    missing = [key for key, node in nodes.items() if node is None]
    if missing:
        raise RuntimeError(f"Не найдены узлы: {', '.join(missing)}")

    frame_node = nodes["frame"]
    frame_box = frame_node["absoluteBoundingBox"]
    frame_width = int(frame_box["width"] * CFG.SCALE_FACTOR)
    frame_height = int(frame_box["height"] * CFG.SCALE_FACTOR)

    template_png = export_frame_as_png(CFG.TEMPLATE_FILE_KEY, frame_node["id"])
    base_img = Image.open(BytesIO(template_png)).convert("RGBA")
    base_img = base_img.resize((frame_width, frame_height), Image.Resampling.LANCZOS)

    result_img = Image.new("RGBA", (frame_width, frame_height))
    result_img.paste(base_img, (0, 0))
    draw = ImageDraw.Draw(result_img)

    processed_photo_path = None
    if photo_path and nodes["foto"]:
        processed_photo_path = _process_photo(photo_path, CFG.TEMP_DIR)
        foto_node = nodes["foto"]["absoluteBoundingBox"]
        foto_width = int(foto_node["width"] * CFG.SCALE_FACTOR)
        foto_height = int(foto_node["height"] * CFG.SCALE_FACTOR)
        foto_x = int((foto_node["x"] - frame_box["x"]) * CFG.SCALE_FACTOR)
        foto_y = int((foto_node["y"] - frame_box["y"]) * CFG.SCALE_FACTOR)
        foto_img = Image.open(processed_photo_path).convert("RGBA").resize(
            (foto_width, foto_height), Image.Resampling.LANCZOS
        )
        result_img.paste(foto_img, (foto_x, foto_y), foto_img)

    qr_path = generate_qr(url, str(CFG.TEMP_DIR), color_dark="#FF6E69")
    if nodes["qr"]:
        qr_node = nodes["qr"]["absoluteBoundingBox"]
        qr_width = int(qr_node["width"] * CFG.SCALE_FACTOR)
        qr_height = int(qr_node["height"] * CFG.SCALE_FACTOR)
        qr_x = int((qr_node["x"] - frame_box["x"]) * CFG.SCALE_FACTOR)
        qr_y = int((qr_node["y"] - frame_box["y"]) * CFG.SCALE_FACTOR)
        qr_img = Image.open(qr_path).convert("RGBA").resize((qr_width, qr_height), Image.Resampling.LANCZOS)
        result_img.paste(qr_img, (qr_x, qr_y), qr_img)

    title_font = _load_font("Inter_18pt-SemiBold.ttf", int(96 * CFG.SCALE_FACTOR))
    small_font = _load_font("Inter_18pt-Medium.ttf", int(64 * CFG.SCALE_FACTOR))
    time_font = _load_font("SFProText-Semibold.ttf", int(112 * CFG.SCALE_FACTOR))

    offset = CFG.TEXT_OFFSET * CFG.SCALE_FACTOR
    formatted_price = _format_price(price)
    time_text = _rome_time_str()

    nazvanie_node = nodes["nazvanie"]["absoluteBoundingBox"]
    nazvanie_x = (nazvanie_node["x"] - frame_box["x"]) * CFG.SCALE_FACTOR
    nazvanie_y = (nazvanie_node["y"] - frame_box["y"]) * CFG.SCALE_FACTOR + offset
    draw.text((nazvanie_x, nazvanie_y), nazvanie, font=title_font, fill="#1F262D")

    price_node = nodes["price"]["absoluteBoundingBox"]
    price_x = (price_node["x"] - frame_box["x"]) * CFG.SCALE_FACTOR
    price_y = (price_node["y"] - frame_box["y"]) * CFG.SCALE_FACTOR + offset
    draw.text((price_x, price_y), formatted_price, font=title_font, fill="#838386")

    total_node = nodes["total"]["absoluteBoundingBox"]
    total_right_x = (total_node["x"] - frame_box["x"] + total_node["width"]) * CFG.SCALE_FACTOR
    total_y = (total_node["y"] - frame_box["y"]) * CFG.SCALE_FACTOR + offset
    _draw_text_with_letter_spacing(draw, formatted_price, title_font, total_right_x, total_y, fill="#838386", align="right")

    if name:
        imya_node = nodes["imya"]["absoluteBoundingBox"]
        imya_x = (imya_node["x"] - frame_box["x"]) * CFG.SCALE_FACTOR
        imya_y = (imya_node["y"] - frame_box["y"]) * CFG.SCALE_FACTOR + offset
        line_height = 64 * CFG.SCALE_FACTOR * 1.219
        cur_y = imya_y
        for line in str(name).split("\n"):
            draw.text((imya_x, cur_y), line, font=small_font, fill="#838386")
            cur_y += line_height

    if address:
        adress_node = nodes["adress"]["absoluteBoundingBox"]
        adress_x = (adress_node["x"] - frame_box["x"]) * CFG.SCALE_FACTOR
        adress_y = (adress_node["y"] - frame_box["y"]) * CFG.SCALE_FACTOR + offset
        line_height = 64 * CFG.SCALE_FACTOR * 1.219
        cur_y = adress_y
        for line in str(address).split("\n"):
            draw.text((adress_x, cur_y), line, font=small_font, fill="#838386")
            cur_y += line_height

    time_node = nodes["time"]["absoluteBoundingBox"]
    time_right_x = (time_node["x"] - frame_box["x"] + time_node["width"]) * CFG.SCALE_FACTOR
    time_y = (time_node["y"] - frame_box["y"]) * CFG.SCALE_FACTOR + offset
    letter_spacing = 112 * CFG.SCALE_FACTOR * 0.02
    _draw_text_with_letter_spacing(draw, time_text, time_font, time_right_x, time_y, fill="#FFFFFF",
                                   letter_spacing=letter_spacing, align="right")

    target_size = (CFG.OUTPUT_WIDTH, CFG.OUTPUT_HEIGHT) if hasattr(CFG, "OUTPUT_WIDTH") else None
    if target_size:
        result_img = result_img.resize(target_size, Image.Resampling.LANCZOS)

    result_img = result_img.convert("RGB")
    image_path = os.path.join(CFG.TEMP_DIR, f"SUBITO_{uuid.uuid4()}.png")
    _save_png(result_img, image_path)
    return ImageResult(path=image_path, processed_photo_path=processed_photo_path, qr_path=qr_path)


def generate_listing_image(template: str, nazvanie: str, price: str | float,
                           photo_path: Optional[str], url: str,
                           name: str = "", address: str = "") -> ImageResult:
    template = (template or "").lower()
    if template == "subito":
        return create_subito_image(nazvanie, price, photo_path, url, name=name, address=address)
    return create_marktplaats_image(nazvanie, price, photo_path, url)
