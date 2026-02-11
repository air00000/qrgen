# app/services/pdf.py
import os
import io
import time
import uuid
import base64
import datetime
import requests
from typing import Optional
from PIL import Image, ImageDraw, ImageFont, ImageOps
from pytz import timezone

from app.services.figma import get_template_json, find_node, export_frame_as_png
from app.services.cache_wrapper import load_template_with_cache, get_frame_image
from app.config import CFG
import logging

logger = logging.getLogger(__name__)

# ===== Константы для Wallapop Email =====
WALLAPOP_EMAIL_FIGMA_PAT = 'figd_dG6hrm0ysjdpJDGcGio2T6uJw45GPTKJGzFPvd3z'
WALLAPOP_EMAIL_FILE_KEY = '76mcmHxmZ5rhQSY02Kw5pn'
WALLAPOP_EMAIL_SCALE = 1
RADIUS_PRODUCT = 14
RADIUS_AVATAR = 100
TIMEZONES = {'uk': 'Europe/London', 'es': 'Europe/Madrid', 'it': 'Europe/Rome', 'fr': 'Europe/Paris'}

# ===== Константы для Wallapop SMS =====
WALLAPOP_SMS_FIGMA_PAT = 'figd_dG6hrm0ysjdpJDGcGio2T6uJw45GPTKJGzFPvd3z'
WALLAPOP_SMS_FILE_KEY = '76mcmHxmZ5rhQSY02Kw5pn'
WALLAPOP_SMS_SCALE = 2
WALLAPOP_SMS_RADIUS = 35
WALLAPOP_SMS_FINAL_WIDTH = 1242
WALLAPOP_SMS_FINAL_HEIGHT = 2696


# ===== Кастомные исключения =====
class PDFGenerationError(Exception):
    """Базовое исключение для ошибок генерации PDF"""
    pass


class FigmaNodeNotFoundError(PDFGenerationError):
    """Исключение когда нода Figma не найдена"""
    pass


class QRGenerationError(PDFGenerationError):
    """Исключение когда QR код не сгенерирован"""
    pass


# ===== Вспомогательные функции в памяти =====
def create_rounded_mask(size, radius):
    mask = Image.new("L", size, 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle([(0, 0), size], radius=radius, fill=255)
    return mask


def process_photo_in_memory(photo_data: str) -> Image.Image:
    """
    Processes photo in memory, returns PIL Image.
    Accepts both Data URI format and plain base64 for backward compatibility.
    
    Args:
        photo_data: Data URI (data:image/png;base64,...) or plain base64 string
    
    Returns:
        PIL Image or None if photo_data is empty/malformed
    """
    from app.utils.helpers import parse_data_uri
    
    # Parse Data URI to extract base64
    base64_data = parse_data_uri(photo_data)
    if not base64_data:
        return None

    try:
        photo_bytes = base64.b64decode(base64_data)
        img = Image.open(io.BytesIO(photo_bytes)).convert("RGBA")
        w, h = img.size
        s = min(w, h)
        l = (w - s) // 2
        t = (h - s) // 2
        img = img.crop((l, t, l + s, t + s))
        mask = create_rounded_mask((s, s), int(CFG.CORNER_RADIUS * CFG.SCALE_FACTOR))
        img.putalpha(mask)
        return img
    except Exception:
        # If decoding fails, return None (treat as missing photo)
        return None


def draw_text_with_letter_spacing(draw, text, font, x, y, fill, letter_spacing=0, align="left"):
    total_width = sum([font.getbbox(ch)[2] for ch in text]) + letter_spacing * (len(text) - 1)
    start_x = x - total_width if align == "right" else x
    cur_x = start_x
    for ch in text:
        draw.text((cur_x, y), ch, font=font, fill=fill)
        cur_x += font.getbbox(ch)[2] + letter_spacing


# ===== QR генерация в памяти =====
def _generate_qr_in_memory(url: str, service: str) -> Image.Image:
    """Генерирует QR код через Rust backend и возвращает PIL Image."""

    if service == "subito":
        color = "#FF6E69"
        # если нужен другой логотип для subito — можно передать отдельный URL
        logo_url = CFG.LOGO_URL
    else:
        color = "#4B6179"
        logo_url = CFG.LOGO_URL

    payload = {
        "country": "it" if service == "subito" else "nl",
        "service": "qr",
        "method": service,
        "url": url,
    }

    try:
        r = requests.post(
            f"{CFG.QR_BACKEND_URL.rstrip('/')}/generate",
            json=payload,
            headers={"X-API-Key": CFG.BACKEND_API_KEY or ""},
            timeout=20,
        )
    except Exception as e:
        raise QRGenerationError(f"QR backend request failed: {e}")

    if r.status_code != 200:
        raise QRGenerationError(f"QR backend error: {r.status_code} {r.text}")

    qr_img = Image.open(io.BytesIO(r.content)).convert("RGBA")
    return qr_img


# ===== Функции для Wallapop Email =====
def get_wallapop_email_figma_json():
    """Получает JSON шаблона для Wallapop Email"""
    # Добавляем небольшую задержку чтобы избежать 429
    time.sleep(0.5)

    r = requests.get(f'https://api.figma.com/v1/files/{WALLAPOP_EMAIL_FILE_KEY}',
                     headers={'X-FIGMA-TOKEN': WALLAPOP_EMAIL_FIGMA_PAT}, timeout=30)
    r.raise_for_status()
    return r.json()


def export_wallapop_email_png(node_id: str) -> bytes:
    """Экспортирует PNG из Figma для Wallapop Email"""
    r = requests.get(f'https://api.figma.com/v1/images/{WALLAPOP_EMAIL_FILE_KEY}',
                     params={'ids': node_id, 'format': 'png', 'scale': WALLAPOP_EMAIL_SCALE},
                     headers={'X-FIGMA-TOKEN': WALLAPOP_EMAIL_FIGMA_PAT}, timeout=30)
    r.raise_for_status()
    url = r.json()['images'][node_id]
    return requests.get(url, timeout=30).content


def find_wallapop_email_node(name: str, data: dict):
    """Находит ноду в шаблоне Wallapop Email"""

    def search(nodes):
        for n in nodes:
            if n.get('name') == name:
                return n
            if 'children' in n:
                found = search(n['children'])
                if found: return found

    page2 = next(p for p in data['document']['children'] if p['name'] == 'Page 2')
    return search(page2['children'])


def truncate_text(draw, text, font, max_width):
    """Обрезает текст если не помещается"""
    if draw.textlength(text, font=font) <= max_width:
        return text
    ellipsis = "..."
    while text and draw.textlength(text + ellipsis, font=font) > max_width:
        text = text[:-1]
    return text + ellipsis


def create_rounded_email(img_b64: str, size: tuple, radius: int) -> Image.Image:
    """
    Creates rounded image for Wallapop Email.
    Accepts both Data URI format and plain base64.
    
    Args:
        img_b64: Data URI or plain base64 string
        size: Target size tuple (width, height)
        radius: Corner radius
    
    Returns:
        PIL Image or None if img_b64 is empty/malformed
    """
    from app.utils.helpers import parse_data_uri
    
    # Parse Data URI to extract base64
    base64_data = parse_data_uri(img_b64)
    if not base64_data:
        return None
    
    try:
        img = Image.open(io.BytesIO(base64.b64decode(base64_data))).convert("RGBA")
        img = ImageOps.fit(img, size, Image.Resampling.LANCZOS)
        mask = Image.new('L', size, 0)
        draw = ImageDraw.Draw(mask)
        draw.rounded_rectangle([(0, 0), size], radius=radius, fill=255)
        rounded = Image.new('RGBA', size, (255, 255, 255, 0))
        rounded.paste(img, (0, 0), mask)
        return rounded
    except Exception:
        # If decoding fails, return None (treat as missing photo)
        return None


def create_image_wallapop_email(lang: str, nazvanie: str, price: float, photo: str = None,
                                seller_name: str = "", seller_photo: str = None) -> bytes:
    """Генерация изображения для Wallapop Email v3"""

    if lang not in ('uk', 'es', 'it', 'fr'):
        raise PDFGenerationError("lang must be: uk/es/it/fr")

    data = get_wallapop_email_figma_json()
    frame = find_wallapop_email_node(f"wallapop3_{lang}", data)
    if not frame:
        raise FigmaNodeNotFoundError(f"Фрейм wallapop3_{lang} не найден")

    # Экспортируем фон
    bg_bytes = export_wallapop_email_png(frame['id'])
    bg = Image.open(io.BytesIO(bg_bytes)).convert("RGBA")

    draw = ImageDraw.Draw(bg)

    # Загружаем шрифты
    try:
        font_title = ImageFont.truetype(os.path.join(CFG.FONTS_DIR, "Megabyte-Regular.ttf"), 46)
        font_price = ImageFont.truetype(os.path.join(CFG.FONTS_DIR, "Megabyte-Medium.ttf"), 64)
        font_time = ImageFont.truetype(os.path.join(CFG.FONTS_DIR, "SFProText-Semibold.ttf"), 53)
        font_seller = ImageFont.truetype(os.path.join(CFG.FONTS_DIR, "Megabyte-Bold.ttf"), 48)
    except Exception as e:
        # Fallback на стандартные шрифты
        font_title = ImageFont.load_default()
        font_price = ImageFont.load_default()
        font_time = ImageFont.load_default()
        font_seller = ImageFont.load_default()

    # Находим все необходимые ноды
    nodes = {}
    node_names = ['nazvwal3', 'pricewal3', 'timewal3', 'picwal3', 'avapicwal3', 'namewal3']

    for suffix in node_names:
        node = find_wallapop_email_node(f"{suffix}_{lang}", data)
        if not node:
            raise FigmaNodeNotFoundError(f"Нода {suffix}_{lang} не найдена")
        nodes[suffix] = node

    frame_x = frame['absoluteBoundingBox']['x']
    frame_y = frame['absoluteBoundingBox']['y']

    def get_pos(node):
        b = node['absoluteBoundingBox']
        return int(b['x'] - frame_x), int(b['y'] - frame_y)

    def get_size(node):
        b = node['absoluteBoundingBox']
        return int(b['width']), int(b['height'])

    # Фото товара
    if photo:
        n = nodes['picwal3']
        x, y = get_pos(n)
        w, h = get_size(n)
        photo_img = create_rounded_email(photo, (w, h), RADIUS_PRODUCT)
        if photo_img:
            bg.paste(photo_img, (x, y), photo_img)

    # Фото продавца
    if seller_photo:
        n = nodes['avapicwal3']
        x, y = get_pos(n)
        w, h = get_size(n)
        ava_img = create_rounded_email(seller_photo, (w, h), RADIUS_AVATAR)
        if ava_img:
            bg.paste(ava_img, (x, y), ava_img)

    # Название товара
    n = nodes['nazvwal3']
    x, y = get_pos(n)
    title = truncate_text(draw, nazvanie, font_title, 735)
    draw.text((x, y), title, font=font_title, fill="#000000", spacing=int(46 * 0.01))

    # Цена
    n = nodes['pricewal3']
    x, y = get_pos(n)
    price_str = f"{price:,.2f} €".replace('.', ',')
    draw.text((x, y), price_str, font=font_price, fill="#000000", spacing=int(64 * -0.02))

    # Время
    n = nodes['timewal3']
    x, y = get_pos(n)
    time_str = datetime.datetime.now(timezone(TIMEZONES[lang])).strftime('%H:%M')
    draw.text((x, y), time_str, font=font_time, fill="#000000", spacing=int(53 * -0.02))

    # Имя продавца
    n = nodes['namewal3']
    x, y = get_pos(n)
    draw.text((x, y), seller_name, font=font_seller, fill="#5C7A89")

    # Сохраняем результат
    buf = io.BytesIO()
    bg.save(buf, format='PNG', optimize=True, compress_level=6)
    return buf.getvalue()


# ===== Функции для Wallapop SMS =====
def get_wallapop_sms_figma_json():
    """Получает JSON шаблона для Wallapop SMS"""
    time.sleep(0.5)
    r = requests.get(f'https://api.figma.com/v1/files/{WALLAPOP_SMS_FILE_KEY}',
                     headers={'X-FIGMA-TOKEN': WALLAPOP_SMS_FIGMA_PAT}, timeout=30)
    r.raise_for_status()
    return r.json()


def export_wallapop_sms_png(node_id: str) -> bytes:
    """Экспортирует PNG из Figma для Wallapop SMS"""
    r = requests.get(f'https://api.figma.com/v1/images/{WALLAPOP_SMS_FILE_KEY}',
                     params={'ids': node_id, 'format': 'png', 'scale': WALLAPOP_SMS_SCALE},
                     headers={'X-FIGMA-TOKEN': WALLAPOP_SMS_FIGMA_PAT}, timeout=30)
    r.raise_for_status()
    url = r.json()['images'][node_id]
    return requests.get(url, timeout=30).content


def find_wallapop_sms_node(name: str, data: dict):
    """Находит ноду в шаблоне Wallapop SMS"""
    def search(nodes):
        for n in nodes:
            if n.get('name') == name:
                return n
            if 'children' in n:
                found = search(n['children'])
                if found: return found
        return None

    page2 = next(p for p in data['document']['children'] if p['name'] == 'Page 2')
    return search(page2['children'])


def create_rounded_sms_photo(b64: str, size: tuple) -> Image.Image:
    """Создает скругленное изображение для Wallapop SMS"""
    if not b64:
        return None
    img = Image.open(io.BytesIO(base64.b64decode(b64))).convert("RGBA")
    img = ImageOps.fit(img, size, Image.Resampling.LANCZOS)
    mask = Image.new('L', size, 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle([0, 0, size[0], size[1]], radius=WALLAPOP_SMS_RADIUS * WALLAPOP_SMS_SCALE, fill=255)
    rounded = Image.new('RGBA', size, (255, 255, 255, 0))
    rounded.paste(img, (0, 0), mask)
    return rounded


def create_image_wallapop_sms(lang: str, nazvanie: str, price: float, photo: str = None) -> bytes:
    """Генерация изображения для Wallapop SMS версии"""

    if lang not in ('uk', 'es', 'it', 'fr'):
        raise PDFGenerationError("lang must be: uk/es/it/fr")

    data = get_wallapop_sms_figma_json()
    frame = find_wallapop_sms_node(f"wallapop1_{lang}", data)
    if not frame:
        raise FigmaNodeNotFoundError(f"Фрейм wallapop1_{lang} не найден")

    # Экспортируем фон
    bg_bytes = export_wallapop_sms_png(frame['id'])
    bg = Image.open(io.BytesIO(bg_bytes)).convert("RGBA")

    box = frame['absoluteBoundingBox']
    frame_x = box['x']
    frame_y = box['y']
    orig_width = int(box['width'] * WALLAPOP_SMS_SCALE)
    orig_height = int(box['height'] * WALLAPOP_SMS_SCALE)
    bg = bg.resize((orig_width, orig_height), Image.Resampling.LANCZOS)

    draw = ImageDraw.Draw(bg)

    # Шрифты
    try:
        font_big = ImageFont.truetype(os.path.join(CFG.FONTS_DIR, "Montserrat-SemiBold.ttf"), int(400 * WALLAPOP_SMS_SCALE))
        font_small = ImageFont.truetype(os.path.join(CFG.FONTS_DIR, "Montserrat-SemiBold.ttf"), int(125 * WALLAPOP_SMS_SCALE))
        font_time = ImageFont.truetype(os.path.join(CFG.FONTS_DIR, "SFProText-Semibold.ttf"), int(108 * WALLAPOP_SMS_SCALE))
    except Exception as e:
        # Fallback fonts
        font_big = ImageFont.load_default()
        font_small = ImageFont.load_default()
        font_time = ImageFont.load_default()

    # Находим все необходимые ноды
    nodes = {}
    node_names = ['nazvwal1', 'pricewal1', 'timewa1', 'photowal1', 'smallpricewal1']

    for suffix in node_names:
        node = find_wallapop_sms_node(f"{suffix}_{lang}", data)
        if not node:
            raise FigmaNodeNotFoundError(f"Нода {suffix}_{lang} не найдена")
        nodes[suffix] = node

    def get_pos(node, y_offset=0):
        abs_box = node['absoluteBoundingBox']
        rx = abs_box['x'] - frame_x
        ry = abs_box['y'] - frame_y
        x = int(rx * WALLAPOP_SMS_SCALE)
        y = int(ry * WALLAPOP_SMS_SCALE) + int(y_offset * WALLAPOP_SMS_SCALE)
        return x, y

    def get_size(node):
        return int(node['absoluteBoundingBox']['width'] * WALLAPOP_SMS_SCALE), int(node['absoluteBoundingBox']['height'] * WALLAPOP_SMS_SCALE)

    # Форматирование цены
    SUPER = str.maketrans('0123456789', '⁰¹²³⁴⁵⁶⁷⁸⁹')

    def format_price(p: float) -> str:
        e = int(p)
        c = int(round((p - e) * 100))
        return f"€{e}.{c:02d}"

    def format_price_big(p: float) -> str:
        e = int(p)
        cents = int(round((p - e) * 100))
        return f"€{e}{str(cents).zfill(2).translate(SUPER)}"

    # Фото
    if photo:
        photo_node = nodes['photowal1']
        px, py = get_pos(photo_node)
        pw, ph = get_size(photo_node)
        photo_img = create_rounded_sms_photo(photo, (pw, ph))
        if photo_img:
            bg.paste(photo_img, (px, py), photo_img)

    # Большая цена
    price_big = format_price_big(price)
    price_node = nodes['pricewal1']
    px, base_y = get_pos(price_node)
    block_w, block_h = get_size(price_node)
    bbox = draw.textbbox((0, 0), price_big, font=font_big)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    cx = px + (block_w - text_w) // 2
    cy = base_y + (block_h - text_h) // 2
    draw.text((cx, cy - 184), price_big, font=font_big, fill="#172E36")

    # Маленькая цена
    price_small = format_price(price)
    small_node = nodes['smallpricewal1']
    sx, sy = get_pos(small_node)
    draw.text((sx, sy), price_small, font=font_small, fill="#676968")

    # Название
    naz_node = nodes['nazvwal1']
    nx, ny = get_pos(naz_node)
    draw.text((nx, ny), nazvanie, font=font_small, fill="#000000")

    # Время
    time_node = nodes['timewa1']
    tx, ty = get_pos(time_node)
    tw, _ = get_size(time_node)

    time_txt = datetime.datetime.now(timezone(TIMEZONES[lang])).strftime('%H:%M')
    bbox = draw.textbbox((0, 0), time_txt, font=font_time)
    text_w = bbox[2] - bbox[0]
    draw.text((tx + tw - text_w, ty), time_txt, font=font_time, fill="#000000")

    # Финальный ресайз
    final = Image.new("RGBA", (WALLAPOP_SMS_FINAL_WIDTH, WALLAPOP_SMS_FINAL_HEIGHT), (255, 255, 255, 0))
    bg_resized = bg.resize((WALLAPOP_SMS_FINAL_WIDTH, WALLAPOP_SMS_FINAL_HEIGHT), Image.Resampling.LANCZOS)
    if bg_resized.size != (WALLAPOP_SMS_FINAL_WIDTH, WALLAPOP_SMS_FINAL_HEIGHT):
        bg_resized = ImageOps.fit(bg_resized, (WALLAPOP_SMS_FINAL_WIDTH, WALLAPOP_SMS_FINAL_HEIGHT), method=Image.Resampling.LANCZOS, centering=(0.5, 0.5))
    final.paste(bg_resized, (0, 0))

    buf = io.BytesIO()
    final.save(buf, format='PNG', optimize=True, compress_level=6)
    buf.seek(0)

    return buf.getvalue()


# ===== Основные функции генерации (существующие) =====
def create_image_marktplaats(nazvanie: str, price: float, photo: str, url: str) -> bytes:
    """
    Generates image for Marktplaats, returns PNG bytes.
    Handles Data URI format for photos and truncates long text.
    """
    from app.utils.helpers import truncate_title, truncate_url
    
    # Truncate text fields
    nazvanie = truncate_title(nazvanie or "")
    url = truncate_url(url or "")
    
    frame_name = "marktplaats2_nl"
    nazvanie_layer = "NAZVANIE_marktplaats2_nl"
    price_layer = "PRICE_marktplaats2_nl"
    time_layer = "TIME_marktplaats2_nl"
    foto_layer = "FOTO_marktplaats2_nl"
    qr_layer = "QR_marktplaats2_nl"

    # Загружаем с кэшем если доступен
    template_json, frame_img_cached, frame_node, use_cache = load_template_with_cache(
        "marktplaats", "Page 2", frame_name
    )
    
    if not frame_node:
        raise FigmaNodeNotFoundError(f"Фрейм {frame_name} не найден")

    nodes = {
        "nazvanie": find_node(template_json, "Page 2", nazvanie_layer),
        "price": find_node(template_json, "Page 2", price_layer),
        "time": find_node(template_json, "Page 2", time_layer),
        "foto": find_node(template_json, "Page 2", foto_layer),
        "qr": find_node(template_json, "Page 2", qr_layer)
    }
    if any(n is None for n in nodes.values()):
        miss = [k for k, v in nodes.items() if v is None]
        raise FigmaNodeNotFoundError(f"Не найдены узлы: {', '.join(miss)}")

    # Фон из кэша или Figma
    frame_img = get_frame_image(frame_node, frame_img_cached, use_cache)
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
    """
    Generates image for Subito, returns PNG bytes.
    Handles Data URI format for photos and truncates long text.
    """
    from app.utils.helpers import truncate_title, truncate_name, truncate_address, truncate_url
    
    # Truncate text fields
    nazvanie = truncate_title(nazvanie or "")
    name = truncate_name(name or "")
    address = truncate_address(address or "")
    url = truncate_url(url or "")
    
    frame_name = "subito1"
    nazvanie_layer = "NAZVANIE_SUB1"
    price_layer = "PRICE_SUB1"
    total_layer = "TOTAL_SUB1"
    adress_layer = "ADRESS_SUB1"
    imya_layer = "IMYA_SUB1"
    time_layer = "TIME_SUB1"
    foto_layer = "PHOTO_SUB1"
    qr_layer = "QR_SUB1"

    # Загружаем с кэшем если доступен
    template_json, frame_img_cached, frame_node, use_cache = load_template_with_cache(
        "subito", "Page 2", frame_name
    )
    
    if not frame_node:
        raise FigmaNodeNotFoundError(f"Фрейм {frame_name} не найден")

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
        raise FigmaNodeNotFoundError(f"Не найдены узлы: {', '.join(miss)}")

    # Фон из кэша или Figma
    frame_img = get_frame_image(frame_node, frame_img_cached, use_cache)
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


def create_image_wallapop(lang: str, nazvanie: str, price: float, photo: str = None) -> bytes:
    """
    Генерация изображения для Wallapop v2, возвращает bytes PNG.
    Использует кеширование Figma макетов.
    """
    if lang not in ('uk', 'es', 'it', 'fr'):
        raise PDFGenerationError("lang must be: uk/es/it/fr")

    frame_name = f"wallapop2_{lang}"
    service_name = f"wallapop2_{lang}"
    
    # Загружаем с кэшем если доступен
    template_json, frame_img_cached, frame_node, use_cache = load_template_with_cache(
        service_name, "Page 2", frame_name
    )
    
    if not frame_node:
        raise FigmaNodeNotFoundError(f"Фрейм {frame_name} не найден")

    nazvanie_layer = f"nazvwal2_{lang}"
    price_layer = f"pricewal2_{lang}"
    time_layer = f"timewa2_{lang}"
    photo_layer = f"photowal2_{lang}"
    small_price_layer = f"smallpricewal2_{lang}"

    nodes = {
        "nazvanie": find_node(template_json, "Page 2", nazvanie_layer),
        "price": find_node(template_json, "Page 2", price_layer),
        "time": find_node(template_json, "Page 2", time_layer),
        "photo": find_node(template_json, "Page 2", photo_layer),
        "small_price": find_node(template_json, "Page 2", small_price_layer)
    }

    if any(n is None for n in nodes.values()):
        miss = [k for k, v in nodes.items() if v is None]
        raise FigmaNodeNotFoundError(f"Не найдены узлы: {', '.join(miss)}")

    # Фон из кэша или Figma
    frame_img = get_frame_image(frame_node, frame_img_cached, use_cache)
    w = int(frame_node["absoluteBoundingBox"]["width"] * CFG.SCALE_FACTOR)
    h = int(frame_node["absoluteBoundingBox"]["height"] * CFG.SCALE_FACTOR)
    frame_img = frame_img.resize((w, h), Image.Resampling.LANCZOS)

    result = Image.new("RGBA", (w, h), (255, 255, 255, 0))
    result.paste(frame_img, (0, 0))
    draw = ImageDraw.Draw(result)

    # Шрифты
    try:
        montserrat_path = os.path.join(CFG.FONTS_DIR, "Montserrat-SemiBold.ttf")
        sfpro_path = os.path.join(CFG.FONTS_DIR, "SFProText-Semibold.ttf")

        font_big = ImageFont.truetype(montserrat_path, int(400 * CFG.SCALE_FACTOR))
        font_small = ImageFont.truetype(montserrat_path, int(125 * CFG.SCALE_FACTOR))
        font_time = ImageFont.truetype(sfpro_path, int(108 * CFG.SCALE_FACTOR))
    except Exception:
        # Fallback fonts
        font_big = ImageFont.load_default()
        font_small = ImageFont.load_default()
        font_time = ImageFont.load_default()

    # Вспомогательные функции
    def get_pos(node, y_offset=0):
        abs_box = node["absoluteBoundingBox"]
        rx = abs_box["x"] - frame_node["absoluteBoundingBox"]["x"]
        ry = abs_box["y"] - frame_node["absoluteBoundingBox"]["y"]
        x = int(rx * CFG.SCALE_FACTOR)
        y = int(ry * CFG.SCALE_FACTOR) + int(y_offset * CFG.SCALE_FACTOR)
        return x, y

    def get_size(node):
        return int(node["absoluteBoundingBox"]["width"] * CFG.SCALE_FACTOR), int(
            node["absoluteBoundingBox"]["height"] * CFG.SCALE_FACTOR)

    # Форматирование цены
    SUPER = str.maketrans('0123456789', '⁰¹²³⁴⁵⁶⁷⁸⁹')

    def format_price(p: float) -> str:
        e = int(p)
        c = int(round((p - e) * 100))
        return f"€{e}.{c:02d}"

    def format_price_big(p: float) -> str:
        e = int(p)
        cents = int(round((p - e) * 100))
        return f"€{e}{str(cents).zfill(2).translate(SUPER)}"

    # Фото
    if photo and nodes["photo"]:
        photo_img = process_photo_in_memory(photo)
        if photo_img:
            pw, ph = get_size(nodes["photo"])
            px, py = get_pos(nodes["photo"])
            photo_img = photo_img.resize((pw, ph), Image.Resampling.LANCZOS)
            result.paste(photo_img, (px, py), photo_img)

    # Большая цена
    price_big = format_price_big(price)
    price_node = nodes["price"]
    px, base_y = get_pos(price_node)
    block_w, block_h = get_size(price_node)
    bbox = draw.textbbox((0, 0), price_big, font=font_big)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    cx = px + (block_w - text_w) // 2
    cy = base_y + (block_h - text_h) + 48 // 2
    draw.text((cx, cy - int(184 * CFG.SCALE_FACTOR)), price_big, font=font_big, fill="#172E36")

    # Маленькая цена
    price_small = format_price(price)
    small_node = nodes["small_price"]
    sx, sy = get_pos(small_node)
    draw.text((sx, sy), price_small, font=font_small, fill="#676968")

    # Название
    naz_node = nodes["nazvanie"]
    nx, ny = get_pos(naz_node)
    draw.text((nx, ny), nazvanie, font=font_small, fill="#000000")

    # Время
    TIMEZONES = {'uk': 'Europe/London', 'es': 'Europe/Madrid', 'it': 'Europe/Rome', 'fr': 'Europe/Paris'}
    time_node = nodes["time"]
    tx, ty = get_pos(time_node)
    tw, _ = get_size(time_node)

    tz = timezone(TIMEZONES[lang])
    time_txt = datetime.datetime.now(tz).strftime('%H:%M')
    bbox = draw.textbbox((0, 0), time_txt, font=font_time)
    text_w = bbox[2] - bbox[0]
    draw.text((tx + tw - text_w, ty), time_txt, font=font_time, fill="#000000")

    # Финальный ресайз
    FINAL_WIDTH, FINAL_HEIGHT = 1242, 2696
    result = result.resize((FINAL_WIDTH, FINAL_HEIGHT), Image.Resampling.LANCZOS).convert("RGB")
    buf = io.BytesIO()
    result.save(buf, format="PNG", optimize=True, compress_level=6)
    return buf.getvalue()


# ===== Обертки для бота =====
def create_pdf(nazvanie, price, photo_b64, url):
    """Обёртка для бота - возвращает bytes вместо пути к файлу"""
    image_data = create_image_marktplaats(nazvanie, float(price), photo_b64, url)
    return image_data, None, None


def create_pdf_subito(nazvanie, price, name, address, photo_b64, url, language=None):
    """Обёртка для бота - возвращает bytes вместо пути к файлу"""
    image_data = create_image_subito(nazvanie, float(price), photo_b64, url, name, address)
    return image_data, None, None


def create_pdf_wallapop(lang: str, nazvanie: str, price: float, photo_b64: str = None):
    """Обёртка для бота - возвращает bytes вместо пути к файлу"""
    image_data = create_image_wallapop(lang, nazvanie, float(price), photo_b64)
    return image_data, None, None


def create_pdf_wallapop_email(lang: str, nazvanie: str, price: float, photo_b64: str = None,
                              seller_name: str = "", seller_photo_b64: str = None):
    """Обёртка для бота - Wallapop Email версия"""
    image_data = create_image_wallapop_email(lang, nazvanie, float(price), photo_b64, seller_name, seller_photo_b64)
    return image_data, None, None


def create_pdf_wallapop_sms(lang: str, nazvanie: str, price: float, photo_b64: str = None):
    """Обёртка для бота - Wallapop SMS версия"""
    image_data = create_image_wallapop_sms(lang, nazvanie, float(price), photo_b64)
    return image_data, None, None