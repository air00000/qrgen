import os
import uuid
import datetime
from io import BytesIO
from typing import Optional, Tuple

from PIL import Image, ImageDraw, ImageFont

from app.config import CFG
from app.services.figma import export_frame_as_png, find_node, get_template_json
from app.services.qr_local import generate_qr
from app.utils.io import cleanup_paths


TITLE_FONT_PATH = os.path.join(CFG.FONTS_DIR, "Inter_18pt-SemiBold.ttf")
SMALL_FONT_PATH = os.path.join(CFG.FONTS_DIR, "Inter_18pt-Medium.ttf")
TIME_FONT_PATH = os.path.join(CFG.FONTS_DIR, "SFProText-Semibold.ttf")

TARGET_SIZE = (1304, 2838)
FRAME_NAME = "subito1"
PAGE_NAME = "Page 2"

LAYER_NAMES = {
    "nazvanie": "NAZVANIE_SUB1",
    "price": "PRICE_SUB1",
    "total": "TOTAL_SUB1",
    "adress": "ADRESS_SUB1",
    "imya": "IMYA_SUB1",
    "time": "TIME_SUB1",
    "foto": "PHOTO_SUB1",
    "qr": "QR_SUB1",
}


def _load_font(path: str, size: int) -> ImageFont.FreeTypeFont:
    if os.path.exists(path):
        return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def _rounded_mask(size: Tuple[int, int], radius: int) -> Image.Image:
    mask = Image.new("L", size, 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle([(0, 0), size], radius=radius, fill=255)
    return mask


def _process_photo(photo_path: str, temp_dir: str) -> str:
    img = Image.open(photo_path).convert("RGBA")
    width, height = img.size
    size = min(width, height)
    left = (width - size) // 2
    top = (height - size) // 2
    img = img.crop((left, top, left + size, top + size))
    radius = int(CFG.CORNER_RADIUS * CFG.SCALE_FACTOR)
    img.putalpha(_rounded_mask((size, size), radius))
    out_path = os.path.join(temp_dir, f"subito_photo_{uuid.uuid4()}.png")
    img.save(out_path, "PNG")
    return out_path


def _rome_time() -> str:
    now = datetime.datetime.now(CFG.SUBITO_TZ)
    return f"{now.hour}:{now.minute:02d}"


def _draw_with_letter_spacing(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.ImageFont,
    x: float,
    y: float,
    *,
    align: str = "left",
    fill: str = "#1F262D",
    letter_spacing: float = 0.0,
):
    if not text:
        return
    advance = [
        font.getlength(ch) if hasattr(font, "getlength") else font.getsize(ch)[0]
        for ch in text
    ]
    total_width = sum(advance) + letter_spacing * (len(text) - 1)
    start_x = x if align == "left" else x - total_width
    cursor = start_x
    for idx, ch in enumerate(text):
        draw.text((cursor, y), ch, font=font, fill=fill)
        cursor += advance[idx] + (letter_spacing if idx < len(text) - 1 else 0)


def _paste_node_image(
    base: Image.Image,
    overlay: Image.Image,
    frame_node: dict,
    target_node: dict,
):
    fx = frame_node["absoluteBoundingBox"]["x"]
    fy = frame_node["absoluteBoundingBox"]["y"]
    bbox = target_node["absoluteBoundingBox"]
    width = int(bbox["width"] * CFG.SCALE_FACTOR)
    height = int(bbox["height"] * CFG.SCALE_FACTOR)
    x = int((bbox["x"] - fx) * CFG.SCALE_FACTOR)
    y = int((bbox["y"] - fy) * CFG.SCALE_FACTOR)
    overlay = overlay.resize((width, height), Image.Resampling.LANCZOS)
    base.paste(overlay, (x, y), overlay)


def create_subito_image(
    nazvanie: str,
    price: float,
    url: str,
    *,
    name: str = "",
    address: str = "",
    photo_path: Optional[str] = None,
    temp_dir: Optional[str] = None,
):
    temp_dir = temp_dir or CFG.TEMP_DIR
    os.makedirs(temp_dir, exist_ok=True)

    template_json = get_template_json()
    frame_node = find_node(template_json, PAGE_NAME, FRAME_NAME)
    if not frame_node:
        raise RuntimeError(f"Фрейм {FRAME_NAME} не найден")

    nodes = {
        key: find_node(template_json, PAGE_NAME, layer)
        for key, layer in LAYER_NAMES.items()
    }
    missing = [layer for key, layer in LAYER_NAMES.items() if nodes.get(key) is None]
    if missing:
        raise RuntimeError(f"Не найдены узлы: {', '.join(missing)}")

    template_bytes = export_frame_as_png(CFG.TEMPLATE_FILE_KEY, frame_node["id"])
    template_img = Image.open(BytesIO(template_bytes)).convert("RGBA")

    frame_w = int(frame_node["absoluteBoundingBox"]["width"] * CFG.SCALE_FACTOR)
    frame_h = int(frame_node["absoluteBoundingBox"]["height"] * CFG.SCALE_FACTOR)
    template_img = template_img.resize((frame_w, frame_h), Image.Resampling.LANCZOS)

    result = Image.new("RGBA", (frame_w, frame_h), (255, 255, 255, 0))
    result.paste(template_img, (0, 0))
    draw = ImageDraw.Draw(result)

    nazv_font = _load_font(TITLE_FONT_PATH, int(96 * CFG.SCALE_FACTOR))
    price_font = _load_font(TITLE_FONT_PATH, int(96 * CFG.SCALE_FACTOR))
    small_font_size = int(64 * CFG.SCALE_FACTOR)
    small_font = _load_font(SMALL_FONT_PATH, small_font_size)
    time_font = _load_font(TIME_FONT_PATH, int(112 * CFG.SCALE_FACTOR))
    small_line_height = int(small_font_size * 1.22)

    processed_photo = None
    if photo_path and nodes["foto"]:
        processed_photo = _process_photo(photo_path, temp_dir)
        foto_img = Image.open(processed_photo).convert("RGBA")
        _paste_node_image(result, foto_img, frame_node, nodes["foto"])

    qr_path = generate_qr(
        url,
        temp_dir,
        target_size=(
            int(nodes["qr"]["absoluteBoundingBox"]["width"] * CFG.SCALE_FACTOR),
            int(nodes["qr"]["absoluteBoundingBox"]["height"] * CFG.SCALE_FACTOR),
        ),
        color_dark="#FF6E69",
        color_bg="#FFFFFF",
        corner_radius=int(CFG.CORNER_RADIUS * CFG.SCALE_FACTOR),
        logo_path=None,
        center_badge_bg=None,
    )

    qr_img = Image.open(qr_path).convert("RGBA")
    _paste_node_image(result, qr_img, frame_node, nodes["qr"])

    frame_fx = frame_node["absoluteBoundingBox"]["x"]
    frame_fy = frame_node["absoluteBoundingBox"]["y"]

    def _offset(node_key: str) -> Tuple[float, float]:
        node = nodes[node_key]
        bbox = node["absoluteBoundingBox"]
        x = (bbox["x"] - frame_fx) * CFG.SCALE_FACTOR
        y = (bbox["y"] - frame_fy) * CFG.SCALE_FACTOR + CFG.TEXT_OFFSET * CFG.SCALE_FACTOR
        return x, y

    price_text = f"€{price:.2f}"
    time_text = _rome_time()

    nx, ny = _offset("nazvanie")
    draw.text((nx, ny), nazvanie, font=nazv_font, fill="#1F262D")

    px, py = _offset("price")
    draw.text((px, py), price_text, font=price_font, fill="#838386")

    total_bbox = nodes["total"]["absoluteBoundingBox"]
    total_right = (
        (total_bbox["x"] - frame_fx + total_bbox["width"]) * CFG.SCALE_FACTOR
    )
    total_y = (total_bbox["y"] - frame_fy) * CFG.SCALE_FACTOR + CFG.TEXT_OFFSET * CFG.SCALE_FACTOR
    _draw_with_letter_spacing(
        draw,
        price_text,
        price_font,
        total_right,
        total_y,
        fill="#838386",
        align="right",
    )

    name_x, name_y = _offset("imya")
    if name:
        for idx, line in enumerate(str(name).split("\n")):
            draw.text((name_x, name_y + idx * small_line_height), line, font=small_font, fill="#838386")

    addr_x, addr_y = _offset("adress")
    if address:
        for idx, line in enumerate(str(address).split("\n")):
            draw.text((addr_x, addr_y + idx * small_line_height), line, font=small_font, fill="#838386")

    time_bbox = nodes["time"]["absoluteBoundingBox"]
    time_right = (
        (time_bbox["x"] - frame_fx + time_bbox["width"]) * CFG.SCALE_FACTOR
    )
    time_y = (time_bbox["y"] - frame_fy) * CFG.SCALE_FACTOR + CFG.TEXT_OFFSET * CFG.SCALE_FACTOR
    _draw_with_letter_spacing(
        draw,
        time_text,
        time_font,
        time_right,
        time_y,
        fill="#FFFFFF",
        align="right",
        letter_spacing=time_font.size * 0.02,
    )

    result = result.resize(TARGET_SIZE, Image.Resampling.LANCZOS)
    result = result.convert("RGB")

    out_path = os.path.join(temp_dir, f"SUBITO_{uuid.uuid4()}.png")
    result.save(out_path, format="PNG", optimize=True)

    return out_path, processed_photo, qr_path


def create_subito_pdf(
    nazvanie: str,
    price: float,
    url: str,
    *,
    name: str = "",
    address: str = "",
    photo_path: Optional[str] = None,
    temp_dir: Optional[str] = None,
):
    temp_dir = temp_dir or CFG.TEMP_DIR
    os.makedirs(temp_dir, exist_ok=True)

    image_path = processed_photo = qr_path = None
    try:
        image_path, processed_photo, qr_path = create_subito_image(
            nazvanie,
            price,
            url,
            name=name,
            address=address,
            photo_path=photo_path,
            temp_dir=temp_dir,
        )

        pdf_path = os.path.join(temp_dir, f"SUBITO_{uuid.uuid4()}.pdf")
        with Image.open(image_path) as img:
            img.convert("RGB").save(pdf_path, format="PDF", resolution=96.0)

        return pdf_path, image_path, processed_photo, qr_path
    except Exception:
        cleanup_paths(image_path, processed_photo, qr_path)
        raise
