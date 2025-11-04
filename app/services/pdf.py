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
from app.config import CFG


# ===== Вспомогательные функции в памяти =====
def create_rounded_mask(size, radius):
    mask = Image.new("L", size, 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle([(0, 0), size], radius=radius, fill=255)
    return mask


def process_photo_in_memory(photo_data: str) -> Image.Image:
    """Обрабатывает фото в памяти, возвращает PIL Image"""
    if not photo_data:
        return None

    photo_bytes = base64.b64decode(photo_data)
    img = Image.open(io.BytesIO(photo_bytes)).convert("RGBA")
    w, h = img.size
    s = min(w, h)
    l = (w - s) // 2
    t = (h - s) // 2
    img = img.crop((l, t, l + s, t + s))
    mask = create_rounded_mask((s, s), int(CFG.CORNER_RADIUS * CFG.SCALE_FACTOR))
    img.putalpha(mask)
    return img


def draw_text_with_letter_spacing(draw, text, font, x, y, fill, letter_spacing=0, align="left"):
    total_width = sum([font.getbbox(ch)[2] for ch in text]) + letter_spacing * (len(text) - 1)
    start_x = x - total_width if align == "right" else x
    cur_x = start_x
    for ch in text:
        draw.text((cur_x, y), ch, font=font, fill=fill)
        cur_x += font.getbbox(ch)[2] + letter_spacing


# ===== QR генерация в памяти =====
def _generate_qr_in_memory(url: str, service: str) -> Image.Image:
    """Генерирует QR код в памяти, возвращает PIL Image"""
    import requests

    if service == "subito":
        color = "#FF6E69"
        logo_path = os.path.join(CFG.PHOTO_DIR, "subito.png")
    else:
        color = "#4B6179"
        logo_path = os.path.join(CFG.PHOTO_DIR, "markt.png")

    headers = {"Authorization": f"Bearer {CFG.QR_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "qrCategory": "url",
        "text": url,
        "size": CFG.QR_SIZE,
        "colorDark": color,
        "backgroundColor": "#FFFFFF",
        "transparentBkg": False,
        "eye_outer": "eyeOuter2",
        "eye_inner": "eyeInner2",
        "qrData": "pattern4",
        "logo": None
    }

    r = requests.post(CFG.QR_ENDPOINT, json=payload, headers=headers)
    if r.status_code != 200:
        raise HTTPException(status_code=500, detail=f"Ошибка QR API: {r.text}")

    data = r.json().get("data")
    if not data:
        raise HTTPException(status_code=500, detail="Нет данных QR в ответе от API")

    qr_bytes = base64.b64decode(data)
    qr_img = Image.open(io.BytesIO(qr_bytes)).convert("RGBA")
    qr_img = qr_img.resize(CFG.QR_RESIZE, Image.Resampling.BICUBIC)

    # Скругление краёв
    mask = create_rounded_mask(CFG.QR_RESIZE, int(CFG.CORNER_RADIUS * CFG.SCALE_FACTOR))
    qr_img.putalpha(mask)

    # Добавление логотипа если нужно
    if logo_path and os.path.exists(logo_path):
        logo = Image.open(logo_path).convert("RGBA")
        side = int(qr_img.size[0] * 0.25)
        logo = logo.resize((side, side), Image.Resampling.LANCZOS)
        cx, cy = qr_img.size[0] // 2, qr_img.size[1] // 2
        qr_img.alpha_composite(logo, (cx - side // 2, cy - side // 2))

    return qr_img


# ===== Основные функции генерации =====
def create_image_marktplaats(nazvanie: str, price: float, photo: str, url: str) -> bytes:
    """Генерирует изображение для Marktplaats, возвращает bytes PNG"""
    template_json = get_template_json()

    frame_name = "marktplaats2_nl"
    nazvanie_layer = "NAZVANIE_marktplaats2_nl"
    price_layer = "PRICE_marktplaats2_nl"
    time_layer = "TIME_marktplaats2_nl"
    foto_layer = "FOTO_marktplaats2_nl"
    qr_layer = "QR_marktplaats2_nl"

    frame_node = find_node(template_json, "Page 2", frame_name)
    if not frame_node:
        raise HTTPException(status_code=500, detail=f"Фрейм {frame_name} не найден")

    nodes = {
        "nazvanie": find_node(template_json, "Page 2", nazvanie_layer),
        "price": find_node(template_json, "Page 2", price_layer),
        "time": find_node(template_json, "Page 2", time_layer),
        "foto": find_node(template_json, "Page 2", foto_layer),
        "qr": find_node(template_json, "Page 2", qr_layer)
    }
    if any(n is None for n in nodes.values()):
        miss = [k for k, v in nodes.items() if v is None]
        raise HTTPException(status_code=500, detail=f"Не найдены узлы: {', '.join(miss)}")

    # Фон из Figma
    frame_png = export_frame_as_png(CFG.TEMPLATE_FILE_KEY, frame_node["id"])
    frame_img = Image.open(io.BytesIO(frame_png)).convert("RGBA")
    w = int(frame_node["absoluteBoundingBox"]["width"] * CFG.SCALE_FACTOR)
    h = int(frame_node["absoluteBoundingBox"]["height"] * CFG.SCALE_FACTOR)
    frame_img = frame_img.resize((w, h), Image.Resampling.LANCZOS)

    result = Image.new("RGBA", (w, h), (255, 255, 255, 0))
    result.paste(frame_img, (0, 0))
    draw = ImageDraw.Draw(result)

    # Шрифты
    inter_semibold_path = os.path.join(CFG.FONTS_DIR, "Inter_18pt-SemiBold.ttf")
    inter_medium_path = os.path.join(CFG.FONTS_DIR, "Inter_18pt-Medium.ttf")
    sfpro_path = os.path.join(CFG.FONTS_DIR, "SFProText-Semibold.ttf")

    nazv_font = ImageFont.truetype(inter_semibold_path, int(96 * CFG.SCALE_FACTOR)) if os.path.exists(
        inter_semibold_path) else ImageFont.load_default()
    price_font = ImageFont.truetype(inter_medium_path, int(96 * CFG.SCALE_FACTOR)) if os.path.exists(
        inter_medium_path) else ImageFont.load_default()
    time_font = ImageFont.truetype(sfpro_path, int(108 * CFG.SCALE_FACTOR)) if os.path.exists(
        sfpro_path) else ImageFont.load_default()

    # Данные
    ams_tz = timezone("Europe/Amsterdam")
    now = datetime.datetime.now(ams_tz)
    time_text = f"{now.hour:02d}:{now.minute:02d}"
    formatted_price = f"€{price:.2f}"

    # Фото в памяти
    if photo and nodes["foto"]:
        foto_img = process_photo_in_memory(photo)
        if foto_img:
            fw = int(nodes["foto"]["absoluteBoundingBox"]["width"] * CFG.SCALE_FACTOR)
            fh = int(nodes["foto"]["absoluteBoundingBox"]["height"] * CFG.SCALE_FACTOR)
            fx = int(
                (nodes["foto"]["absoluteBoundingBox"]["x"] - frame_node["absoluteBoundingBox"]["x"]) * CFG.SCALE_FACTOR)
            fy = int(
                (nodes["foto"]["absoluteBoundingBox"]["y"] - frame_node["absoluteBoundingBox"]["y"]) * CFG.SCALE_FACTOR)
            foto_img = foto_img.resize((fw, fh), Image.Resampling.LANCZOS)
            result.paste(foto_img, (fx, fy), foto_img)

    # QR в памяти
    qr_img = _generate_qr_in_memory(url, "marktplaats")
    qw = int(nodes["qr"]["absoluteBoundingBox"]["width"] * CFG.SCALE_FACTOR)
    qh = int(nodes["qr"]["absoluteBoundingBox"]["height"] * CFG.SCALE_FACTOR)
    qx = int((nodes["qr"]["absoluteBoundingBox"]["x"] - frame_node["absoluteBoundingBox"]["x"]) * CFG.SCALE_FACTOR)
    qy = int((nodes["qr"]["absoluteBoundingBox"]["y"] - frame_node["absoluteBoundingBox"]["y"]) * CFG.SCALE_FACTOR)
    qr_img = qr_img.resize((qw, qh), Image.Resampling.LANCZOS)
    result.paste(qr_img, (qx, qy), qr_img)

    # Тексты
    nx = (nodes["nazvanie"]["absoluteBoundingBox"]["x"] - frame_node["absoluteBoundingBox"]["x"]) * CFG.SCALE_FACTOR
    ny = (nodes["nazvanie"]["absoluteBoundingBox"]["y"] - frame_node["absoluteBoundingBox"]["y"]) * CFG.SCALE_FACTOR
    draw.text((nx, ny), nazvanie, font=nazv_font, fill="#1F262D")

    px = (nodes["price"]["absoluteBoundingBox"]["x"] - frame_node["absoluteBoundingBox"]["x"]) * CFG.SCALE_FACTOR
    py = (nodes["price"]["absoluteBoundingBox"]["y"] - frame_node["absoluteBoundingBox"]["y"]) * CFG.SCALE_FACTOR
    draw.text((px, py), formatted_price, font=price_font, fill="#838383")

    tb = nodes["time"]["absoluteBoundingBox"]
    tx = (tb["x"] - frame_node["absoluteBoundingBox"]["x"] + tb["width"]) * CFG.SCALE_FACTOR
    ty = (tb["y"] - frame_node["absoluteBoundingBox"]["y"]) * CFG.SCALE_FACTOR
    draw_text_with_letter_spacing(draw, time_text, time_font, tx, ty, fill="#000000", align="right")

    # Итог
    result = result.resize((1304, 2838), Image.Resampling.LANCZOS).convert("RGB")
    buf = io.BytesIO()
    result.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def create_image_subito(nazvanie: str, price: float, photo: str, url: str, name: str = '', address: str = '') -> bytes:
    """Генерирует изображение для Subito, возвращает bytes PNG"""
    template_json = get_template_json()

    frame_name = "subito1"
    nazvanie_layer = "NAZVANIE_SUB1"
    price_layer = "PRICE_SUB1"
    total_layer = "TOTAL_SUB1"
    adress_layer = "ADRESS_SUB1"
    imya_layer = "IMYA_SUB1"
    time_layer = "TIME_SUB1"
    foto_layer = "PHOTO_SUB1"
    qr_layer = "QR_SUB1"

    frame_node = find_node(template_json, "Page 2", frame_name)
    if not frame_node:
        raise HTTPException(status_code=500, detail=f"Фрейм {frame_name} не найден")

    nodes = {
        "nazvanie": find_node(template_json, "Page 2", nazvanie_layer),
        "price": find_node(template_json, "Page 2", price_layer),
        "total": find_node(template_json, "Page 2", total_layer),
        "adress": find_node(template_json, "Page 2", adress_layer),
        "imya": find_node(template_json, "Page 2", imya_layer),
        "time": find_node(template_json, "Page 2", time_layer),
        "foto": find_node(template_json, "Page 2", foto_layer),
        "qr": find_node(template_json, "Page 2", qr_layer)
    }
    if any(n is None for n in nodes.values()):
        miss = [k for k, v in nodes.items() if v is None]
        raise HTTPException(status_code=500, detail=f"Не найдены узлы: {', '.join(miss)}")

    # Фон из Figma
    frame_png = export_frame_as_png(CFG.TEMPLATE_FILE_KEY, frame_node["id"])
    frame_img = Image.open(io.BytesIO(frame_png)).convert("RGBA")
    w = int(frame_node["absoluteBoundingBox"]["width"] * CFG.SCALE_FACTOR)
    h = int(frame_node["absoluteBoundingBox"]["height"] * CFG.SCALE_FACTOR)
    frame_img = frame_img.resize((w, h), Image.Resampling.LANCZOS)

    result = Image.new("RGBA", (w, h), (255, 255, 255, 0))
    result.paste(frame_img, (0, 0))
    draw = ImageDraw.Draw(result)

    # Шрифты
    aktiv_path = os.path.join(CFG.FONTS_DIR, "aktivgroteskcorp_medium.ttf")
    sfpro_path = os.path.join(CFG.FONTS_DIR, "SFProText-Semibold.ttf")

    nazv_font = ImageFont.truetype(aktiv_path, int(96 * CFG.SCALE_FACTOR)) if os.path.exists(
        aktiv_path) else ImageFont.load_default()
    small_font = ImageFont.truetype(aktiv_path, int(64 * CFG.SCALE_FACTOR)) if os.path.exists(
        aktiv_path) else ImageFont.load_default()
    time_font = ImageFont.truetype(sfpro_path, int(112 * CFG.SCALE_FACTOR)) if os.path.exists(
        sfpro_path) else ImageFont.load_default()

    # Данные
    rome_tz = timezone("Europe/Rome")
    now = datetime.datetime.now(rome_tz)
    time_text = f"{now.hour}:{now.minute:02d}"
    formatted_price = f"€{price:.2f}"

    # Фото в памяти
    if photo and nodes["foto"]:
        foto_img = process_photo_in_memory(photo)
        if foto_img:
            fw = int(nodes["foto"]["absoluteBoundingBox"]["width"] * CFG.SCALE_FACTOR)
            fh = int(nodes["foto"]["absoluteBoundingBox"]["height"] * CFG.SCALE_FACTOR)
            fx = int(
                (nodes["foto"]["absoluteBoundingBox"]["x"] - frame_node["absoluteBoundingBox"]["x"]) * CFG.SCALE_FACTOR)
            fy = int(
                (nodes["foto"]["absoluteBoundingBox"]["y"] - frame_node["absoluteBoundingBox"]["y"]) * CFG.SCALE_FACTOR)
            foto_img = foto_img.resize((fw, fh), Image.Resampling.LANCZOS)
            result.paste(foto_img, (fx, fy), foto_img)

    # QR в памяти
    qr_img = _generate_qr_in_memory(url, "subito")
    qw = int(nodes["qr"]["absoluteBoundingBox"]["width"] * CFG.SCALE_FACTOR)
    qh = int(nodes["qr"]["absoluteBoundingBox"]["height"] * CFG.SCALE_FACTOR)
    qx = int((nodes["qr"]["absoluteBoundingBox"]["x"] - frame_node["absoluteBoundingBox"]["x"]) * CFG.SCALE_FACTOR)
    qy = int((nodes["qr"]["absoluteBoundingBox"]["y"] - frame_node["absoluteBoundingBox"]["y"]) * CFG.SCALE_FACTOR)
    qr_img = qr_img.resize((qw, qh), Image.Resampling.LANCZOS)
    result.paste(qr_img, (qx, qy), qr_img)

    # Тексты
    nx = (nodes["nazvanie"]["absoluteBoundingBox"]["x"] - frame_node["absoluteBoundingBox"]["x"]) * CFG.SCALE_FACTOR
    ny = (nodes["nazvanie"]["absoluteBoundingBox"]["y"] - frame_node["absoluteBoundingBox"]["y"]) * CFG.SCALE_FACTOR
    draw.text((nx, ny), nazvanie, font=nazv_font, fill="#1F262D")

    px = (nodes["price"]["absoluteBoundingBox"]["x"] - frame_node["absoluteBoundingBox"]["x"]) * CFG.SCALE_FACTOR
    py = (nodes["price"]["absoluteBoundingBox"]["y"] - frame_node["absoluteBoundingBox"]["y"]) * CFG.SCALE_FACTOR
    draw.text((px, py), formatted_price, font=nazv_font, fill="#838386")

    if name:
        ix = (nodes["imya"]["absoluteBoundingBox"]["x"] - frame_node["absoluteBoundingBox"]["x"]) * CFG.SCALE_FACTOR
        iy = (nodes["imya"]["absoluteBoundingBox"]["y"] - frame_node["absoluteBoundingBox"]["y"]) * CFG.SCALE_FACTOR
        draw.text((ix, iy), name, font=small_font, fill="#838386")

    if address:
        ax = (nodes["adress"]["absoluteBoundingBox"]["x"] - frame_node["absoluteBoundingBox"]["x"]) * CFG.SCALE_FACTOR
        ay = (nodes["adress"]["absoluteBoundingBox"]["y"] - frame_node["absoluteBoundingBox"]["y"]) * CFG.SCALE_FACTOR
        draw.text((ax, ay), address, font=small_font, fill="#838386")

    tb_tot = nodes["total"]["absoluteBoundingBox"]
    total_right_x = (tb_tot["x"] - frame_node["absoluteBoundingBox"]["x"] + tb_tot["width"]) * CFG.SCALE_FACTOR
    total_y = (tb_tot["y"] - frame_node["absoluteBoundingBox"]["y"]) * CFG.SCALE_FACTOR
    draw_text_with_letter_spacing(draw, formatted_price, nazv_font, total_right_x, total_y, fill="#838386",
                                  align="right")

    tb = nodes["time"]["absoluteBoundingBox"]
    tx = (tb["x"] - frame_node["absoluteBoundingBox"]["x"] + tb["width"]) * CFG.SCALE_FACTOR
    ty = (tb["y"] - frame_node["absoluteBoundingBox"]["y"]) * CFG.SCALE_FACTOR
    letter_spacing = int(112 * CFG.SCALE_FACTOR * 0.02)
    draw_text_with_letter_spacing(draw, time_text, time_font, tx, ty, fill="#FFFFFF", letter_spacing=letter_spacing,
                                  align="right")

    # Итог
    result = result.resize((1304, 2838), Image.Resampling.LANCZOS).convert("RGB")
    buf = io.BytesIO()
    result.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


# ===== Обёртки для бота (обновлённые) =====
def create_pdf(nazvanie, price, photo_path, url):
    """Обёртка для бота - возвращает bytes вместо пути к файлу"""
    photo_b64 = None
    if photo_path and os.path.exists(photo_path):
        with open(photo_path, "rb") as f:
            photo_b64 = base64.b64encode(f.read()).decode("utf-8")

    image_data = create_image_marktplaats(nazvanie, float(price), photo_b64, url)
    return image_data, None, None


def create_pdf_subito(nazvanie, price, name, address, photo_path, url, language=None):
    """Обёртка для бота - возвращает bytes вместо пути к файлу"""
    photo_b64 = None
    if photo_path and os.path.exists(photo_path):
        with open(photo_path, "rb") as f:
            photo_b64 = base64.b64encode(f.read()).decode("utf-8")

    image_data = create_image_subito(nazvanie, float(price), photo_b64, url, name, address)
    return image_data, None, None