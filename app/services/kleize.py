# app/services/kleize.py
"""
Сервис для генерации скриншотов Kleinanzeigen
Поддерживает два варианта: kleize (базовый) и kleize_uniq (уникальный)
"""
import base64
import os
import uuid
import requests
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
import logging
import datetime
from pytz import timezone

from app.config import CFG
from app.services.figma import get_headers, find_node, export_frame_as_png, get_template_json
from app.services.qrtiger import generate_qr

logger = logging.getLogger(__name__)

# Константы для Kleize
KLEIZE_SCALE_FACTOR = 2
KLEIZE_TEXT_OFFSET_Y = 2.5
KLEIZE_TARGET_WIDTH = 1304
KLEIZE_TARGET_HEIGHT = 2838
KLEIZE_CORNER_RADIUS_PHOTO = 15
KLEIZE_CORNER_RADIUS_QR = 16
KLEIZE_QR_COLOR = "#0C0C0B"
KLEIZE_QR_SIZE = 2000
KLEIZE_QR_RESIZE = (738, 738)

# Figma конфиг для kleize
KLEIZE_FIGMA_PAT = os.getenv("KLEIZE_FIGMA_PAT", "figd_dG6hrm0ysjdpJDGcGio2T6uJw45GPTKJGzFPvd3z")
KLEIZE_FILE_KEY = os.getenv("KLEIZE_FILE_KEY", "76mcmHxmZ5rhQSY02Kw5pn")

# QR конфиг для kleize
KLEIZE_QR_LOGO_URL = os.getenv("KLEIZE_QR_LOGO_URL", "https://i.ibb.co/mV9pQDLS/Frame-36.png")


def create_rounded_mask(size, radius):
    """Создает маску с закругленными углами"""
    mask = Image.new('L', size, 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle([(0, 0), size], radius=radius, fill=255)
    return mask


def process_photo_kleize(photo_b64: str, temp_dir: str):
    """
    Обрабатывает фото для kleize: кадрирует до квадрата и применяет закругленные углы
    """
    img = Image.open(BytesIO(base64.b64decode(photo_b64))).convert("RGBA")
    
    # Кадрируем до квадрата
    size = min(img.size)
    img = img.crop((
        (img.width - size) // 2,
        (img.height - size) // 2,
        (img.width + size) // 2,
        (img.height + size) // 2
    ))
    
    # Применяем закругленные углы
    mask = create_rounded_mask(img.size, int(KLEIZE_CORNER_RADIUS_PHOTO * KLEIZE_SCALE_FACTOR))
    img.putalpha(mask)
    
    path = os.path.join(temp_dir, f"photo_kleize_{uuid.uuid4()}.png")
    img.save(path)
    return path


def generate_qr_kleize(url: str, temp_dir: str):
    """
    Генерирует QR код специально для kleize с закругленными углами
    """
    payload = {
        "qrCategory": "url",
        "text": url,
        "size": KLEIZE_QR_SIZE,
        "colorDark": KLEIZE_QR_COLOR,
        "backgroundColor": "#FFFFFF",
        "transparentBkg": False,
        "eye_outer": "eyeOuter2",
        "eye_inner": "eyeInner2",
        "qrData": "pattern4",
        "logo": KLEIZE_QR_LOGO_URL
    }
    
    headers = {
        "Authorization": f"Bearer {CFG.QR_API_KEY}",
        "Content-Type": "application/json"
    }
    
    try:
        r = requests.post(CFG.QR_ENDPOINT, json=payload, headers=headers, timeout=30)
        r.raise_for_status()
        qr_b64 = r.json()['data']
        qr_bytes = base64.b64decode(qr_b64)
        
        path = os.path.join(temp_dir, f"qr_kleize_{uuid.uuid4()}.png")
        with open(path, 'wb') as f:
            f.write(qr_bytes)
        
        # Ресайзим и применяем закругленные углы
        qr_img = Image.open(path).convert("RGBA")
        qr_img = qr_img.resize(KLEIZE_QR_RESIZE, Image.Resampling.LANCZOS)
        mask = create_rounded_mask(KLEIZE_QR_RESIZE, int(KLEIZE_CORNER_RADIUS_QR * KLEIZE_SCALE_FACTOR))
        qr_img.putalpha(mask)
        qr_img.save(path)
        
        return path
    except Exception as e:
        logger.error(f"Ошибка генерации QR для kleize: {e}")
        return None


def get_berlin_time():
    """Получает текущее время в Берлине"""
    tz = timezone('Europe/Berlin')
    now = datetime.datetime.now(tz)
    return now.strftime("%H:%M")


def draw_text_with_spacing(draw, text, font, x, y, fill, spacing=0, align="left"):
    """Рисует текст с кастомным межбуквенным интервалом"""
    if not text:
        return
    
    widths = [font.getbbox(ch)[2] - font.getbbox(ch)[0] for ch in text]
    total_w = sum(widths) + spacing * (len(text) - 1)
    
    if align == "center":
        x -= total_w / 2
    elif align == "right":
        x -= total_w
    
    cur_x = x
    for i, ch in enumerate(text):
        draw.text((cur_x, y), ch, font=font, fill=fill)
        cur_x += widths[i] + spacing


def create_image_kleize(nazvanie: str, price: float, mesto: str, photo_b64: str, url: str, variant: str = "kleize"):
    """
    Генерирует изображение для Kleinanzeigen
    
    Args:
        nazvanie: Название товара
        price: Цена товара
        mesto: Местоположение
        photo_b64: Фото в base64 (опционально)
        url: URL для QR кода
        variant: "kleize" или "kleize_uniq"
    
    Returns:
        tuple: (image_bytes, photo_path, qr_path)
    """
    temp_dir = CFG.PHOTO_DIR
    os.makedirs(temp_dir, exist_ok=True)
    
    photo_path = None
    qr_path = None
    
    try:
        # Определяем имя фрейма в зависимости от варианта
        if variant == "kleize_uniq":
            frame_name = "kleinan2"  # kleize2 из референса
            page_name = "Page 2"
        else:
            frame_name = "kleinan2"  # kleize1 из референса
            page_name = "Page 2"
        
        # Получаем JSON из Figma
        headers = {"X-FIGMA-TOKEN": KLEIZE_FIGMA_PAT}
        r = requests.get(f'{CFG.FIGMA_API_URL}/files/{KLEIZE_FILE_KEY}', headers=headers)
        r.raise_for_status()
        template_json = r.json()
        
        # Находим нужный фрейм
        frame_node = find_node(template_json, page_name, frame_name)
        if not frame_node:
            raise Exception(f"Фрейм {frame_name} не найден на странице {page_name}")
        
        # Находим все необходимые узлы
        node_prefix = "nazv_kleinan2" if variant == "kleize" else "nazv_kleinan2"
        
        nodes = {
            'nazvanie': find_node(template_json, page_name, f'{node_prefix}'),
            'price': find_node(template_json, page_name, 'price_kleinan2'),
            'mesto': find_node(template_json, page_name, 'mesto_kleinan2'),
            'time': find_node(template_json, page_name, 'time_kleinan2'),
            'pic': find_node(template_json, page_name, 'pic_kleinan2'),
            'qr': find_node(template_json, page_name, 'qr_kleinan2'),
        }
        
        # Экспортируем базовый шаблон
        url_export = f'{CFG.FIGMA_API_URL}/images/{KLEIZE_FILE_KEY}?ids={frame_node["id"]}&format=png&scale={KLEIZE_SCALE_FACTOR}'
        r = requests.get(url_export, headers=headers)
        r.raise_for_status()
        img_url = r.json()['images'][frame_node['id']]
        base_png = requests.get(img_url).content
        
        base_img = Image.open(BytesIO(base_png)).convert("RGBA")
        w = int(frame_node['absoluteBoundingBox']['width'] * KLEIZE_SCALE_FACTOR)
        h = int(frame_node['absoluteBoundingBox']['height'] * KLEIZE_SCALE_FACTOR)
        base_img = base_img.resize((w, h), Image.Resampling.LANCZOS)
        
        result = Image.new("RGBA", (w, h), (255, 255, 255, 0))
        result.paste(base_img, (0, 0))
        draw = ImageDraw.Draw(result)
        
        # Загружаем шрифты
        rebond_med2 = ImageFont.truetype(
            os.path.join(CFG.FONTS_DIR, "RebondGrotesqueMedium.ttf"),
            int(36 * KLEIZE_SCALE_FACTOR)
        )
        rebond_med = ImageFont.truetype(
            os.path.join(CFG.FONTS_DIR, "RebondGrotesqueMedium.ttf"),
            int(42 * KLEIZE_SCALE_FACTOR)
        )
        rebond_semibold = ImageFont.truetype(
            os.path.join(CFG.FONTS_DIR, "RebondGrotesqueSemibold.ttf"),
            int(48 * KLEIZE_SCALE_FACTOR)
        )
        sfpro_semibold = ImageFont.truetype(
            os.path.join(CFG.FONTS_DIR, "SFProText-Semibold.ttf"),
            int(54 * KLEIZE_SCALE_FACTOR)
        )
        
        # Подготавливаем данные
        time_text = get_berlin_time()
        total_price = price + 6.99
        price_text = f"{total_price:.2f} €".replace(".", ",") + " (inkl Versand. 6.99 €)"
        
        # Вставляем фото, если есть
        if photo_b64 and nodes['pic']:
            photo_path = process_photo_kleize(photo_b64, temp_dir)
            photo_img = Image.open(photo_path).convert("RGBA")
            
            pw = int(nodes['pic']['absoluteBoundingBox']['width'] * KLEIZE_SCALE_FACTOR)
            ph = int(nodes['pic']['absoluteBoundingBox']['height'] * KLEIZE_SCALE_FACTOR)
            px = int((nodes['pic']['absoluteBoundingBox']['x'] - frame_node['absoluteBoundingBox']['x']) * KLEIZE_SCALE_FACTOR)
            py = int((nodes['pic']['absoluteBoundingBox']['y'] - frame_node['absoluteBoundingBox']['y']) * KLEIZE_SCALE_FACTOR)
            
            photo_img = photo_img.resize((pw, ph), Image.Resampling.LANCZOS)
            result.paste(photo_img, (px, py), photo_img)
        
        # Генерируем и вставляем QR код
        qr_path = generate_qr_kleize(url, temp_dir)
        if qr_path and nodes['qr']:
            qr_img = Image.open(qr_path).convert("RGBA")
            
            qw = int(nodes['qr']['absoluteBoundingBox']['width'] * KLEIZE_SCALE_FACTOR)
            qh = int(nodes['qr']['absoluteBoundingBox']['height'] * KLEIZE_SCALE_FACTOR)
            qx = int((nodes['qr']['absoluteBoundingBox']['x'] - frame_node['absoluteBoundingBox']['x']) * KLEIZE_SCALE_FACTOR)
            qy = int((nodes['qr']['absoluteBoundingBox']['y'] - frame_node['absoluteBoundingBox']['y']) * KLEIZE_SCALE_FACTOR)
            
            qr_img = qr_img.resize((qw, qh), Image.Resampling.LANCZOS)
            result.paste(qr_img, (qx, qy), qr_img)
        
        offset = KLEIZE_TEXT_OFFSET_Y * KLEIZE_SCALE_FACTOR
        
        # Рисуем название
        if nodes['nazvanie']:
            nx = (nodes['nazvanie']['absoluteBoundingBox']['x'] - frame_node['absoluteBoundingBox']['x']) * KLEIZE_SCALE_FACTOR
            ny = (nodes['nazvanie']['absoluteBoundingBox']['y'] - frame_node['absoluteBoundingBox']['y']) * KLEIZE_SCALE_FACTOR + offset
            draw_text_with_spacing(draw, nazvanie, rebond_med, nx, ny, fill="#FCFCFC",
                                 spacing=int(0.02 * 42 * KLEIZE_SCALE_FACTOR), align="left")
        
        # Рисуем цену
        if nodes['price']:
            px = (nodes['price']['absoluteBoundingBox']['x'] - frame_node['absoluteBoundingBox']['x']) * KLEIZE_SCALE_FACTOR
            py = (nodes['price']['absoluteBoundingBox']['y'] - frame_node['absoluteBoundingBox']['y']) * KLEIZE_SCALE_FACTOR + offset
            draw_text_with_spacing(draw, price_text, rebond_semibold, px, py, fill="#D3F28D",
                                 spacing=int(-0.02 * 48 * KLEIZE_SCALE_FACTOR), align="left")
        
        # Рисуем местоположение
        if nodes['mesto']:
            mx = (nodes['mesto']['absoluteBoundingBox']['x'] - frame_node['absoluteBoundingBox']['x']) * KLEIZE_SCALE_FACTOR
            my = (nodes['mesto']['absoluteBoundingBox']['y'] - frame_node['absoluteBoundingBox']['y']) * KLEIZE_SCALE_FACTOR + offset
            draw_text_with_spacing(draw, mesto, rebond_med2, mx, my, fill="#77756F",
                                 spacing=int(0.02 * 36 * KLEIZE_SCALE_FACTOR), align="left")
        
        # Рисуем время по центру
        if nodes['time']:
            tx = (nodes['time']['absoluteBoundingBox']['x'] - frame_node['absoluteBoundingBox']['x'] +
                  nodes['time']['absoluteBoundingBox']['width'] / 2) * KLEIZE_SCALE_FACTOR
            ty = (nodes['time']['absoluteBoundingBox']['y'] - frame_node['absoluteBoundingBox']['y']) * KLEIZE_SCALE_FACTOR + offset
            draw_text_with_spacing(draw, time_text, sfpro_semibold, tx, ty, fill="#FFFFFF", align="center")
        
        # Финальное сжатие до целевого размера
        result = result.resize((KLEIZE_TARGET_WIDTH, KLEIZE_TARGET_HEIGHT), Image.Resampling.LANCZOS)
        result = result.convert("RGB")
        
        # Сохраняем в буфер
        buffer = BytesIO()
        result.save(buffer, format="PNG", optimize=True)
        img_bytes = buffer.getvalue()
        
        return img_bytes, photo_path, qr_path
        
    except Exception as e:
        logger.exception(f"Ошибка генерации kleize ({variant})")
        raise e
    finally:
        # Очистка временных файлов будет выполнена вызывающей стороной
        pass
