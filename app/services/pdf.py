import os
import io
import uuid
import base64
import datetime
from typing import Optional
from PIL import Image, ImageDraw, ImageFont
from fastapi import HTTPException
from pytz import timezone

from app.services.figma import get_template_json, find_node, export_frame_as_png

BASE_DIR = os.path.dirname(__file__)
ROOT_DIR = os.path.abspath(os.path.join(BASE_DIR, ".."))

# Директории под твой проект
TEMP_DIR = os.path.join(ROOT_DIR, "foti", "temp")
FONTS_DIR = os.path.join(ROOT_DIR, "assets", "fonts")
FOTI_DIR  = os.path.join(ROOT_DIR, "assets", "foti")

# Локальные логотипы
SUBITO_LOGO_PATH = os.path.join(FOTI_DIR, "subito.png")
MARKT_LOGO_PATH  = os.path.join(FOTI_DIR, "markt.png")

# Шрифты (путь изменён на app/assets/fonts)
aktiv_path            = os.path.join(FONTS_DIR, "aktivgroteskcorp_medium.ttf")
sfpro_path            = os.path.join(FONTS_DIR, "SFProText-Semibold.ttf")
inter_semibold_path   = os.path.join(FONTS_DIR, "Inter_18pt-SemiBold.ttf")
inter_medium_path     = os.path.join(FONTS_DIR, "Inter_18pt-Medium.ttf")

# Общие константы
SCALE_FACTOR   = 2
TEXT_OFFSET    = 2.5
TARGET_WIDTH   = 1304
TARGET_HEIGHT  = 2838
CORNER_RADIUS  = 15
TEMPLATE_FILE_KEY = "76mcmHxmZ5rhQSY02Kw5pn"

os.makedirs(TEMP_DIR, exist_ok=True)

# ===== Вспомогательные =====
def create_rounded_mask(size, radius):
    mask = Image.new("L", size, 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle([(0, 0), size], radius=radius, fill=255)
    return mask

def process_photo(photo_data: str):
    photo_bytes = base64.b64decode(photo_data)
    img = Image.open(io.BytesIO(photo_bytes)).convert("RGBA")
    w, h = img.size
    s = min(w, h)
    l = (w - s) // 2
    t = (h - s) // 2
    img = img.crop((l, t, l + s, t + s))
    mask = create_rounded_mask((s, s), int(CORNER_RADIUS * SCALE_FACTOR))
    img.putalpha(mask)
    path = os.path.join(TEMP_DIR, f"processed_{uuid.uuid4()}.png")
    img.save(path, "PNG")
    return path

def draw_text_with_letter_spacing(draw, text, font, x, y, fill, letter_spacing=0, align="left"):
    total_width = sum([font.getbbox(ch)[2] for ch in text]) + letter_spacing * (len(text) - 1)
    start_x = x - total_width if align == "right" else x
    cur_x = start_x
    for ch in text:
        draw.text((cur_x, y), ch, font=font, fill=fill)
        cur_x += font.getbbox(ch)[2] + letter_spacing

# ===== QR генерация через QR TIGER (без логотипа, логотип клеим сами при необходимости) =====
def _generate_qr(url: str, color_hex: str) -> str:
    import requests
    QR_ENDPOINT = "https://api.qrtiger.com/api/qr/static"
    QR_API_KEY  = "2b0ec610-6e21-11f0-9fbe-73daa5d669a4"
    QR_SIZE     = 2000
    QR_RESIZE   = (1368, 1368)

    qr_path = os.path.join(TEMP_DIR, f"qr_{uuid.uuid4()}.png")

    headers = {"Authorization": f"Bearer {QR_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "qrCategory": "url",
        "text": url,
        "size": QR_SIZE,
        "colorDark": color_hex,
        "backgroundColor": "#FFFFFF",
        "transparentBkg": False,
        "eye_outer": "eyeOuter2",
        "eye_inner": "eyeInner2",
        "qrData": "pattern4",
        "logo": None  # логотип будем клеить локально при необходимости
    }

    r = requests.post(QR_ENDPOINT, json=payload, headers=headers)
    if r.status_code != 200:
        raise HTTPException(status_code=500, detail=f"Ошибка QR API: {r.text}")
    data = r.json().get("data")
    if not data:
        raise HTTPException(status_code=500, detail="Нет данных QR в ответе от API")

    qr_bytes = base64.b64decode(data)
    with open(qr_path, "wb") as f:
        f.write(qr_bytes)

    # Скругление краёв и размер
    qr_img = Image.open(qr_path).convert("RGBA")
    qr_img = qr_img.resize(QR_RESIZE, Image.Resampling.BICUBIC)
    mask = create_rounded_mask(QR_RESIZE, int(CORNER_RADIUS * SCALE_FACTOR))
    qr_img.putalpha(mask)
    qr_img.save(qr_path, format="PNG")
    return qr_path

def _paste_logo_center(qr_img: Image.Image, logo_path: str, scale_ratio: float = 0.25) -> Image.Image:
    """Кладём логотип по центру QR без отступов/теней. scale_ratio ~ часть стороны QR."""
    if not os.path.exists(logo_path):
        return qr_img
    qr_img = qr_img.copy().convert("RGBA")
    W, H = qr_img.size
    side = int(min(W, H) * scale_ratio)

    logo = Image.open(logo_path).convert("RGBA").resize((side, side), Image.Resampling.LANCZOS)
    cx, cy = W // 2, H // 2
    qr_img.alpha_composite(logo, (cx - side // 2, cy - side // 2))
    return qr_img

# ===== Marktplaats (PNG) =====
def create_image_marktplaats(nazvanie: str, price: float, photo: str, url: str):
    template_json = get_template_json()

    # Имена узлов — строго как в макете mr2
    frame_name      = "marktplaats2_nl"
    nazvanie_layer  = "NAZVANIE_marktplaats2_nl"
    price_layer     = "PRICE_marktplaats2_nl"
    time_layer      = "TIME_marktplaats2_nl"
    foto_layer      = "FOTO_marktplaats2_nl"
    qr_layer        = "QR_marktplaats2_nl"

    frame_node = find_node(template_json, "Page 2", frame_name)
    if not frame_node:
        raise HTTPException(status_code=500, detail=f"Фрейм {frame_name} не найден")

    nodes = {
        "nazvanie": find_node(template_json, "Page 2", nazvanie_layer),
        "price":    find_node(template_json, "Page 2", price_layer),
        "time":     find_node(template_json, "Page 2", time_layer),
        "foto":     find_node(template_json, "Page 2", foto_layer),
        "qr":       find_node(template_json, "Page 2", qr_layer)
    }
    if any(n is None for n in nodes.values()):
        miss = [k for k,v in nodes.items() if v is None]
        raise HTTPException(status_code=500, detail=f"Не найдены узлы: {', '.join(miss)}")

    # Фон из Figma
    frame_png = export_frame_as_png(TEMPLATE_FILE_KEY, frame_node["id"])
    frame_img = Image.open(io.BytesIO(frame_png)).convert("RGBA")
    w = int(frame_node["absoluteBoundingBox"]["width"]  * SCALE_FACTOR)
    h = int(frame_node["absoluteBoundingBox"]["height"] * SCALE_FACTOR)
    frame_img = frame_img.resize((w, h), Image.Resampling.LANCZOS)

    result = Image.new("RGBA", (w, h), (255, 255, 255, 0))
    result.paste(frame_img, (0, 0))
    draw = ImageDraw.Draw(result)

    # Шрифты
    nazv_font  = ImageFont.truetype(inter_semibold_path, int(96 * SCALE_FACTOR)) if os.path.exists(inter_semibold_path) else ImageFont.load_default()
    price_font = ImageFont.truetype(inter_medium_path,  int(96 * SCALE_FACTOR)) if os.path.exists(inter_medium_path) else ImageFont.load_default()
    time_font  = ImageFont.truetype(sfpro_path,         int(108 * SCALE_FACTOR)) if os.path.exists(sfpro_path) else ImageFont.load_default()

    # Данные
    ams_tz = timezone("Europe/Amsterdam")
    now = datetime.datetime.now(ams_tz)
    time_text = f"{now.hour:02d}:{now.minute:02d}"
    formatted_price = f"€{price:.2f}"

    # Фото
    if photo and nodes["foto"]:
        processed_photo_path = process_photo(photo)
        foto_img = Image.open(processed_photo_path).convert("RGBA")
        fw = int(nodes["foto"]["absoluteBoundingBox"]["width"]  * SCALE_FACTOR)
        fh = int(nodes["foto"]["absoluteBoundingBox"]["height"] * SCALE_FACTOR)
        fx = int((nodes["foto"]["absoluteBoundingBox"]["x"] - frame_node["absoluteBoundingBox"]["x"]) * SCALE_FACTOR)
        fy = int((nodes["foto"]["absoluteBoundingBox"]["y"] - frame_node["absoluteBoundingBox"]["y"]) * SCALE_FACTOR)
        foto_img = foto_img.resize((fw, fh), Image.Resampling.LANCZOS)
        result.paste(foto_img, (fx, fy), foto_img)

    # QR
    qr_path = _generate_qr_with_logo(url, "marktplaats")
    qr_img = Image.open(qr_path).convert("RGBA")
    # (Если захочешь — раскомментируй для логотипа Marktplaats в центре)
    # qr_img = _paste_logo_center(qr_img, MARKT_LOGO_PATH, scale_ratio=0.22)

    qw = int(nodes["qr"]["absoluteBoundingBox"]["width"]  * SCALE_FACTOR)
    qh = int(nodes["qr"]["absoluteBoundingBox"]["height"] * SCALE_FACTOR)
    qx = int((nodes["qr"]["absoluteBoundingBox"]["x"] - frame_node["absoluteBoundingBox"]["x"]) * SCALE_FACTOR)
    qy = int((nodes["qr"]["absoluteBoundingBox"]["y"] - frame_node["absoluteBoundingBox"]["y"]) * SCALE_FACTOR)
    qr_img = qr_img.resize((qw, qh), Image.Resampling.LANCZOS)
    result.paste(qr_img, (qx, qy), qr_img)

    # Тексты
    nx = (nodes["nazvanie"]["absoluteBoundingBox"]["x"] - frame_node["absoluteBoundingBox"]["x"]) * SCALE_FACTOR
    ny = (nodes["nazvanie"]["absoluteBoundingBox"]["y"] - frame_node["absoluteBoundingBox"]["y"]) * SCALE_FACTOR
    draw.text((nx, ny), nazvanie, font=nazv_font, fill="#1F262D")

    px = (nodes["price"]["absoluteBoundingBox"]["x"] - frame_node["absoluteBoundingBox"]["x"]) * SCALE_FACTOR
    py = (nodes["price"]["absoluteBoundingBox"]["y"] - frame_node["absoluteBoundingBox"]["y"]) * SCALE_FACTOR
    draw.text((px, py), formatted_price, font=price_font, fill="#838383")

    tb = nodes["time"]["absoluteBoundingBox"]
    tx = (tb["x"] - frame_node["absoluteBoundingBox"]["x"] + tb["width"]) * SCALE_FACTOR
    ty = (tb["y"] - frame_node["absoluteBoundingBox"]["y"]) * SCALE_FACTOR
    draw_text_with_letter_spacing(draw, time_text, time_font, tx, ty, fill="#000000", align="right")

    # Итог
    result = result.resize((TARGET_WIDTH, TARGET_HEIGHT), Image.Resampling.LANCZOS).convert("RGB")
    buf = io.BytesIO()
    result.save(buf, format="PNG", optimize=True)
    return buf.getvalue()

# ===== Subito (PNG) =====
def create_image_subito(nazvanie: str, price: float, photo: str, url: str, name: str = '', address: str = ''):
    template_json = get_template_json()

    # Имена узлов — строго как в макете sub1
    frame_name     = "subito1"
    nazvanie_layer = "NAZVANIE_SUB1"
    price_layer    = "PRICE_SUB1"
    total_layer    = "TOTAL_SUB1"
    adress_layer   = "ADRESS_SUB1"
    imya_layer     = "IMYA_SUB1"
    time_layer     = "TIME_SUB1"
    foto_layer     = "PHOTO_SUB1"
    qr_layer       = "QR_SUB1"

    frame_node = find_node(template_json, "Page 2", frame_name)
    if not frame_node:
        raise HTTPException(status_code=500, detail=f"Фрейм {frame_name} не найден")

    nodes = {
        "nazvanie": find_node(template_json, "Page 2", nazvanie_layer),
        "price":    find_node(template_json, "Page 2", price_layer),
        "total":    find_node(template_json, "Page 2", total_layer),
        "adress":   find_node(template_json, "Page 2", adress_layer),
        "imya":     find_node(template_json, "Page 2", imya_layer),
        "time":     find_node(template_json, "Page 2", time_layer),
        "foto":     find_node(template_json, "Page 2", foto_layer),
        "qr":       find_node(template_json, "Page 2", qr_layer)
    }
    if any(n is None for n in nodes.values()):
        miss = [k for k,v in nodes.items() if v is None]
        raise HTTPException(status_code=500, detail=f"Не найдены узлы: {', '.join(miss)}")

    # Фон из Figma
    frame_png = export_frame_as_png(TEMPLATE_FILE_KEY, frame_node["id"])
    frame_img = Image.open(io.BytesIO(frame_png)).convert("RGBA")
    w = int(frame_node["absoluteBoundingBox"]["width"]  * SCALE_FACTOR)
    h = int(frame_node["absoluteBoundingBox"]["height"] * SCALE_FACTOR)
    frame_img = frame_img.resize((w, h), Image.Resampling.LANCZOS)

    result = Image.new("RGBA", (w, h), (255, 255, 255, 0))
    result.paste(frame_img, (0, 0))
    draw = ImageDraw.Draw(result)

    # Шрифты (из app/assets/fonts)
    nazv_font  = ImageFont.truetype(aktiv_path, int(96 * SCALE_FACTOR)) if os.path.exists(aktiv_path) else ImageFont.load_default()
    small_font = ImageFont.truetype(aktiv_path, int(64 * SCALE_FACTOR)) if os.path.exists(aktiv_path) else ImageFont.load_default()
    time_font  = ImageFont.truetype(sfpro_path, int(112 * SCALE_FACTOR)) if os.path.exists(sfpro_path) else ImageFont.load_default()

    # Данные
    rome_tz = timezone("Europe/Rome")
    now = datetime.datetime.now(rome_tz)
    time_text = f"{now.hour}:{now.minute:02d}"
    formatted_price = f"€{price:.2f}"

    # Фото
    if photo and nodes["foto"]:
        processed_photo_path = process_photo(photo)
        foto_img = Image.open(processed_photo_path).convert("RGBA")
        fw = int(nodes["foto"]["absoluteBoundingBox"]["width"]  * SCALE_FACTOR)
        fh = int(nodes["foto"]["absoluteBoundingBox"]["height"] * SCALE_FACTOR)
        fx = int((nodes["foto"]["absoluteBoundingBox"]["x"] - frame_node["absoluteBoundingBox"]["x"]) * SCALE_FACTOR)
        fy = int((nodes["foto"]["absoluteBoundingBox"]["y"] - frame_node["absoluteBoundingBox"]["y"]) * SCALE_FACTOR)
        foto_img = foto_img.resize((fw, fh), Image.Resampling.LANCZOS)
        result.paste(foto_img, (fx, fy), foto_img)

    # QR (красный) + логотип Subito по центру
    qr_path = _generate_qr_with_logo(url, "subito")
    qr_img = Image.open(qr_path).convert("RGBA")
    qr_img = _paste_logo_center(qr_img, SUBITO_LOGO_PATH, scale_ratio=0.25)

    qw = int(nodes["qr"]["absoluteBoundingBox"]["width"]  * SCALE_FACTOR)
    qh = int(nodes["qr"]["absoluteBoundingBox"]["height"] * SCALE_FACTOR)
    qx = int((nodes["qr"]["absoluteBoundingBox"]["x"] - frame_node["absoluteBoundingBox"]["x"]) * SCALE_FACTOR)
    qy = int((nodes["qr"]["absoluteBoundingBox"]["y"] - frame_node["absoluteBoundingBox"]["y"]) * SCALE_FACTOR)
    qr_img = qr_img.resize((qw, qh), Image.Resampling.LANCZOS)
    result.paste(qr_img, (qx, qy), qr_img)

    # Тексты
    # NAZVANIE_SUB1
    nx = (nodes["nazvanie"]["absoluteBoundingBox"]["x"] - frame_node["absoluteBoundingBox"]["x"]) * SCALE_FACTOR
    ny = (nodes["nazvanie"]["absoluteBoundingBox"]["y"] - frame_node["absoluteBoundingBox"]["y"]) * SCALE_FACTOR
    draw.text((nx, ny), nazvanie, font=nazv_font, fill="#1F262D")

    # PRICE_SUB1
    px = (nodes["price"]["absoluteBoundingBox"]["x"] - frame_node["absoluteBoundingBox"]["x"]) * SCALE_FACTOR
    py = (nodes["price"]["absoluteBoundingBox"]["y"] - frame_node["absoluteBoundingBox"]["y"]) * SCALE_FACTOR
    draw.text((px, py), formatted_price, font=nazv_font, fill="#838386")

    # IMYA_SUB1
    if name:
        ix = (nodes["imya"]["absoluteBoundingBox"]["x"] - frame_node["absoluteBoundingBox"]["x"]) * SCALE_FACTOR
        iy = (nodes["imya"]["absoluteBoundingBox"]["y"] - frame_node["absoluteBoundingBox"]["y"]) * SCALE_FACTOR
        draw.text((ix, iy), name, font=small_font, fill="#838386")

    # ADRESS_SUB1
    if address:
        ax = (nodes["adress"]["absoluteBoundingBox"]["x"] - frame_node["absoluteBoundingBox"]["x"]) * SCALE_FACTOR
        ay = (nodes["adress"]["absoluteBoundingBox"]["y"] - frame_node["absoluteBoundingBox"]["y"]) * SCALE_FACTOR
        draw.text((ax, ay), address, font=small_font, fill="#838386")

    # TOTAL_SUB1 (правый край)
    tb_tot = nodes["total"]["absoluteBoundingBox"]
    total_right_x = (tb_tot["x"] - frame_node["absoluteBoundingBox"]["x"] + tb_tot["width"]) * SCALE_FACTOR
    total_y       = (tb_tot["y"] - frame_node["absoluteBoundingBox"]["y"]) * SCALE_FACTOR
    draw_text_with_letter_spacing(draw, formatted_price, nazv_font, total_right_x, total_y, fill="#838386", align="right")

    # TIME_SUB1
    tb = nodes["time"]["absoluteBoundingBox"]
    tx = (tb["x"] - frame_node["absoluteBoundingBox"]["x"] + tb["width"]) * SCALE_FACTOR
    ty = (tb["y"] - frame_node["absoluteBoundingBox"]["y"]) * SCALE_FACTOR
    # лёгкий кернинг (как было раньше)
    letter_spacing = int(112 * SCALE_FACTOR * 0.02)
    draw_text_with_letter_spacing(draw, time_text, time_font, tx, ty, fill="#FFFFFF", letter_spacing=letter_spacing, align="right")

    # Итог
    result = result.resize((TARGET_WIDTH, TARGET_HEIGHT), Image.Resampling.LANCZOS).convert("RGB")
    buf = io.BytesIO()
    result.save(buf, format="PNG", optimize=True)
    return buf.getvalue()

# ===== Обёртки для бота (совместимость со старым кодом) =====
def create_pdf(nazvanie, price, photo_path, url):
    photo_b64 = None
    if photo_path and os.path.exists(photo_path):
        with open(photo_path, "rb") as f:
            photo_b64 = base64.b64encode(f.read()).decode("utf-8")
    data = create_image_marktplaats(nazvanie, float(price), photo_b64, url)
    path = os.path.join(TEMP_DIR, f"MARKTPLAATS_{uuid.uuid4()}.png")
    with open(path, "wb") as f:
        f.write(data)
    return path, None, None

def create_pdf_subito(nazvanie, price, name, address, photo_path, url, language=None):
    photo_b64 = None
    if photo_path and os.path.exists(photo_path):
        with open(photo_path, "rb") as f:
            photo_b64 = base64.b64encode(f.read()).decode("utf-8")
    data = create_image_subito(nazvanie, float(price), photo_b64, url, name, address)
    path = os.path.join(TEMP_DIR, f"SUBITO_{uuid.uuid4()}.png")
    with open(path, "wb") as f:
        f.write(data)
    return path, None, None


def _generate_qr_with_logo(url: str, service: str) -> str:
    """
    Генерирует QR-код через API QRTiger с нужным цветом и логотипом в центре.
    service: 'subito' или 'marktplaats'
    """
    import requests
    QR_ENDPOINT = "https://api.qrtiger.com/api/qr/static"
    QR_API_KEY  = "2b0ec610-6e21-11f0-9fbe-73daa5d669a4"
    QR_SIZE     = 2000
    QR_RESIZE   = (1368, 1368)

    qr_path = os.path.join(TEMP_DIR, f"qr_{service}_{uuid.uuid4()}.png")

    headers = {"Authorization": f"Bearer {QR_API_KEY}", "Content-Type": "application/json"}

    if service == "subito":
        color = "#FF6E69"
        logo_path = SUBITO_LOGO_PATH
    else:
        color = "#4B6179"
        logo_path = MARKT_LOGO_PATH

    payload = {
        "qrCategory": "url",
        "text": url,
        "size": QR_SIZE,
        "colorDark": color,
        "backgroundColor": "#FFFFFF",
        "transparentBkg": False,
        "eye_outer": "eyeOuter2",
        "eye_inner": "eyeInner2",
        "qrData": "pattern4",
        "logo": None
    }

    # Запрашиваем QR через API
    r = requests.post(QR_ENDPOINT, json=payload, headers=headers)
    if r.status_code != 200:
        raise HTTPException(status_code=500, detail=f"Ошибка QR API: {r.text}")

    data = r.json().get("data")
    if not data:
        raise HTTPException(status_code=500, detail="Нет данных QR в ответе от API")

    qr_bytes = base64.b64decode(data)
    with open(qr_path, "wb") as f:
        f.write(qr_bytes)

    qr_img = Image.open(qr_path).convert("RGBA")
    qr_img = qr_img.resize(QR_RESIZE, Image.Resampling.BICUBIC)

    # Скругляем углы QR
    mask = create_rounded_mask(QR_RESIZE, int(CORNER_RADIUS * SCALE_FACTOR))
    qr_img.putalpha(mask)

    # Добавляем логотип в центр
    if os.path.exists(logo_path):
        logo = Image.open(logo_path).convert("RGBA")
        side = int(qr_img.size[0] * 0.25)
        logo = logo.resize((side, side), Image.Resampling.LANCZOS)
        cx, cy = qr_img.size[0] // 2, qr_img.size[1] // 2
        qr_img.alpha_composite(logo, (cx - side // 2, cy - side // 2))

    qr_img.save(qr_path, format="PNG")
    return qr_path
