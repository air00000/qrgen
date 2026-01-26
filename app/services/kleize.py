# app/services/kleize.py
"""
Сервис для генерации скриншотов Kleinanzeigen (Kleize)
Версия 2.0 с фиксом для фото
"""
import base64
import os
import uuid
import requests
from PIL import Image, ImageDraw, ImageFont, ImageEnhance
from io import BytesIO
import logging
import datetime
from pytz import timezone
import numpy as np
import random

from app.config import CFG
from app.services.cache_wrapper import load_template_with_cache, get_frame_image
from app.services.figma import find_node

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# === КОНСТАНТЫ ===
FIGMA_API_URL = 'https://api.figma.com/v1'
FIGMA_PAT = 'figd_dG6hrm0ysjdpJDGcGio2T6uJw45GPTKJGzFPvd3z'
TEMPLATE_FILE_KEY = '76mcmHxmZ5rhQSY02Kw5pn'

SCALE_FACTOR = 2
TEXT_OFFSET_Y = 2.5
TARGET_WIDTH = 1304
TARGET_HEIGHT = 2838

# QR настройки
QR_API_KEY = '2b0ec610-6e21-11f0-9fbe-73daa5d669a4'
QR_ENDPOINT = 'https://api.qrtiger.com/api/qr/static'
QR_COLOR = "#0C0C0B"
QR_LOGO_URL = "https://i.ibb.co/mV9pQDLS/Frame-36.png"
QR_SIZE = 2000
QR_RESIZE = (738, 738)
CORNER_RADIUS_PHOTO = 15
CORNER_RADIUS_QR = 16

# === КОСТЫЛЬ ДЛЯ ФОТО (если Figma не работает) ===
USE_FIXED_COORDS = True  # Включен костыль с фиксированными координатами
FIXED_PHOTO_X = 90
FIXED_PHOTO_Y = 542.0
FIXED_PHOTO_WIDTH = 240.0
FIXED_PHOTO_HEIGHT = 240.0


class KleizeGenerationError(Exception):
    """Исключение для ошибок генерации Kleize"""
    pass


def get_figma_headers():
    return {'X-FIGMA-TOKEN': FIGMA_PAT}


def find_node(file_json, page_name, node_name):
    for page in file_json['document']['children']:
        if page['name'] == page_name:
            def search(node):
                if node.get('name') == node_name:
                    return node
                if 'children' in node:
                    for child in node['children']:
                        found = search(child)
                        if found:
                            return found
                return None
            return search(page)
    return None


def get_template_json():
    r = requests.get(f'{FIGMA_API_URL}/files/{TEMPLATE_FILE_KEY}', headers=get_figma_headers(), timeout=30)
    r.raise_for_status()
    return r.json()


def export_frame_as_png(file_key, node_id):
    url = f'{FIGMA_API_URL}/images/{file_key}?ids={node_id}&format=png&scale={SCALE_FACTOR}'
    r = requests.get(url, headers=get_figma_headers(), timeout=30)
    r.raise_for_status()
    img_url = r.json()['images'][node_id]
    return requests.get(img_url, timeout=60).content


def create_rounded_mask(size, radius):
    mask = Image.new('L', size, 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle([(0, 0), size], radius=radius, fill=255)
    return mask


def process_photo(photo_b64: str):
    """Обработка фото - обрезка до 1:1 и скругление углов"""
    logger.info("🖼️  Декодирование и обработка фото...")
    img = Image.open(BytesIO(base64.b64decode(photo_b64)))
    
    # Если есть прозрачность - наложить на белый фон
    if img.mode in ('RGBA', 'LA', 'P'):
        # Конвертируем в RGBA если нужно
        if img.mode != 'RGBA':
            img = img.convert('RGBA')
        
        # Создаем белый фон
        white_bg = Image.new('RGBA', img.size, (255, 255, 255, 255))
        # Накладываем изображение на белый фон
        white_bg.paste(img, (0, 0), img)
        img = white_bg
    else:
        img = img.convert("RGBA")
    
    size = min(img.size)
    img = img.crop(((img.width - size) // 2, (img.height - size) // 2,
                    (img.width + size) // 2, (img.height + size) // 2))
    mask = create_rounded_mask(img.size, int(CORNER_RADIUS_PHOTO * SCALE_FACTOR))
    img.putalpha(mask)
    logger.info(f"✅ Фото обработано: {img.size} {img.mode}")
    return img


def generate_qr(url: str):
    """Генерация QR-кода через QR Tiger API"""
    logger.info(f"🔲 Генерация QR для Kleize: {url}")
    
    payload = {
        "qrCategory": "url",
        "text": url,
        "size": QR_SIZE,
        "colorDark": QR_COLOR,
        "backgroundColor": "#FFFFFF",
        "transparentBkg": False,
        "eye_outer": "eyeOuter2",
        "eye_inner": "eyeInner2",
        "qrData": "pattern4",
        "logo": QR_LOGO_URL
    }
    headers = {"Authorization": f"Bearer {QR_API_KEY}", "Content-Type": "application/json"}
    
    try:
        r = requests.post(QR_ENDPOINT, json=payload, headers=headers, timeout=15)
        r.raise_for_status()
        qr_b64 = r.json()['data']
        qr_bytes = base64.b64decode(qr_b64)
        
        qr_img = Image.open(BytesIO(qr_bytes)).convert("RGBA")
        qr_img = qr_img.resize(QR_RESIZE, Image.Resampling.LANCZOS)
        mask = create_rounded_mask(QR_RESIZE, int(CORNER_RADIUS_QR * SCALE_FACTOR))
        qr_img.putalpha(mask)
        
        logger.info("✅ QR-код сгенерирован")
        return qr_img
        
    except Exception as e:
        logger.error(f"❌ Ошибка генерации QR: {e}")
        raise KleizeGenerationError(f"Ошибка генерации QR: {e}")


def get_berlin_time():
    """Получение текущего времени в Берлине"""
    tz = timezone('Europe/Berlin')
    now = datetime.datetime.now(tz)
    return now.strftime("%H:%M")


def draw_text_with_spacing(draw, text, font, x, y, fill, spacing=0, align="left"):
    """Рисование текста с кастомным spacing между символами"""
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


def create_kleize_image(nazvanie: str, price: float, photo: str, url: str) -> bytes:
    """
    Генерация изображения для Kleize (Kleinanzeigen)
    
    Args:
        nazvanie: Название товара
        price: Цена товара
        photo: Фото товара в base64 (или None)
        url: URL для QR-кода
        
    Returns:
        bytes: PNG изображение
    """
    logger.info(f"🎨 Генерация Kleize: {nazvanie}, {price}€")
    
    try:
        # Загружаем с кэшем если доступен
        logger.info("📥 Загрузка шаблона...")
        template_json, frame_img_cached, frame_node, use_cache = load_template_with_cache(
            "kleize", "Page 2", "kleinan2",
            figma_pat=FIGMA_PAT, file_key=TEMPLATE_FILE_KEY
        )
        
        if not frame_node:
            raise KleizeGenerationError("Фрейм kleinan2 не найден")
        
        logger.info("=== Поиск узлов в Figma ===")
        nodes = {
            'nazvanie': find_node(template_json, 'Page 2', 'nazv_kleinan2'),
            'price': find_node(template_json, 'Page 2', 'price_kleinan2'),
            'time': find_node(template_json, 'Page 2', 'time_kleinan2'),
            'pic': find_node(template_json, 'Page 2', 'pic_kleinan2'),
            'qr': find_node(template_json, 'Page 2', 'qr_kleinan2'),
        }
        
        # Логируем найденные узлы
        for key, node in nodes.items():
            if node and 'absoluteBoundingBox' in node:
                abs_box = node['absoluteBoundingBox']
                rel_x = abs_box['x'] - frame_node['absoluteBoundingBox']['x']
                rel_y = abs_box['y'] - frame_node['absoluteBoundingBox']['y']
                logger.info(f"✅ {key}: x={rel_x:.1f}, y={rel_y:.1f}, w={abs_box['width']}, h={abs_box['height']}")
            else:
                logger.warning(f"❌ {key}: НЕ НАЙДЕН!")
        
        logger.info("=== Конец поиска узлов ===\n")
        
        # Получаем изображение из кэша или Figma
        logger.info("📥 Загрузка изображения шаблона...")
        base_img = get_frame_image(frame_node, frame_img_cached, use_cache,
                                   figma_pat=FIGMA_PAT, file_key=TEMPLATE_FILE_KEY)
        w = int(frame_node['absoluteBoundingBox']['width'] * SCALE_FACTOR)
        h = int(frame_node['absoluteBoundingBox']['height'] * SCALE_FACTOR)
        base_img = base_img.resize((w, h), Image.Resampling.LANCZOS)
        
        result = Image.new("RGBA", (w, h), (255, 255, 255, 0))
        result.paste(base_img, (0, 0))
        draw = ImageDraw.Draw(result)
        
        # Загрузка шрифтов
        fonts_dir = os.path.join(CFG.BASE_DIR, "assets", "fonts")
        rebond_med = ImageFont.truetype(os.path.join(fonts_dir, "RebondGrotesqueMedium.ttf"), int(42 * SCALE_FACTOR))
        rebond_semibold = ImageFont.truetype(os.path.join(fonts_dir, "RebondGrotesqueSemibold.ttf"), int(48 * SCALE_FACTOR))
        sfpro_semibold = ImageFont.truetype(os.path.join(fonts_dir, "SFProText-Semibold.ttf"), int(54 * SCALE_FACTOR))
        
        # Подготовка данных
        time_text = get_berlin_time()
        total_price = price + 6.99
        price_text = f"{total_price:.2f} €".replace(".", ",") + " (inkl Versand. 6.99 €)"
        
        # === ДОБАВЛЕНИЕ ФОТО (с поддержкой костыля) ===
        logger.info(f"📸 Проверка фото: photo={'есть' if photo else 'НЕТ'}, USE_FIXED_COORDS={USE_FIXED_COORDS}")
        
        if photo:
            logger.info("🖼️  Начинаем обработку фото...")
            photo_img = process_photo(photo)
            logger.info(f"✅ Фото обработано: {photo_img.size}, mode={photo_img.mode}")
            
            if USE_FIXED_COORDS:
                # Режим костыля - используем захардкоженные координаты
                pw = int(FIXED_PHOTO_WIDTH * SCALE_FACTOR)
                ph = int(FIXED_PHOTO_HEIGHT * SCALE_FACTOR)
                px = int(FIXED_PHOTO_X * SCALE_FACTOR)
                py = int(FIXED_PHOTO_Y * SCALE_FACTOR)
                photo_img = photo_img.resize((pw, ph), Image.Resampling.LANCZOS)
                logger.info(f"🔧 КОСТЫЛЬ: Вставка фото по фиксированным координатам x={px}, y={py}, size={pw}x{ph}")
                result.paste(photo_img, (px, py), photo_img)
                logger.info("✅ Фото вставлено через КОСТЫЛЬ")
            elif nodes.get('pic') and 'absoluteBoundingBox' in nodes['pic']:
                # Обычный режим - через Figma узел
                logger.info(f"📍 Узел pic найден! Координаты из Figma...")
                pw = int(nodes['pic']['absoluteBoundingBox']['width'] * SCALE_FACTOR)
                ph = int(nodes['pic']['absoluteBoundingBox']['height'] * SCALE_FACTOR)
                px = int((nodes['pic']['absoluteBoundingBox']['x'] - frame_node['absoluteBoundingBox']['x']) * SCALE_FACTOR)
                py = int((nodes['pic']['absoluteBoundingBox']['y'] - frame_node['absoluteBoundingBox']['y']) * SCALE_FACTOR)
                logger.info(f"📐 Размер до resize: {photo_img.size}, целевой размер: {pw}x{ph}")
                photo_img = photo_img.resize((pw, ph), Image.Resampling.LANCZOS)
                logger.info(f"📐 Размер после resize: {photo_img.size}")
                logger.info(f"📐 Вставка фото через Figma узел: x={px}, y={py}, size={pw}x{ph}")
                logger.info(f"📐 Размер result до вставки: {result.size}, mode={result.mode}")
                result.paste(photo_img, (px, py), photo_img)
                logger.info("✅✅✅ ФОТО УСПЕШНО ВСТАВЛЕНО!")
            else:
                logger.error(f"❌ Узел pic не найден или нет absoluteBoundingBox!")
                logger.error(f"   nodes.get('pic') = {nodes.get('pic') is not None}")
                if nodes.get('pic'):
                    logger.error(f"   'absoluteBoundingBox' in nodes['pic'] = {'absoluteBoundingBox' in nodes['pic']}")
                logger.error("   Включи USE_FIXED_COORDS=True для костыля")
        else:
            logger.info("ℹ️  Фото пропущено пользователем")
        
        # === ДОБАВЛЕНИЕ QR-кода ===
        if nodes['qr'] and 'absoluteBoundingBox' in nodes['qr']:
            logger.info("🔲 Генерация QR...")
            qr_img = generate_qr(url)
            if qr_img:
                qw = int(nodes['qr']['absoluteBoundingBox']['width'] * SCALE_FACTOR)
                qh = int(nodes['qr']['absoluteBoundingBox']['height'] * SCALE_FACTOR)
                qx = int((nodes['qr']['absoluteBoundingBox']['x'] - frame_node['absoluteBoundingBox']['x']) * SCALE_FACTOR)
                qy = int((nodes['qr']['absoluteBoundingBox']['y'] - frame_node['absoluteBoundingBox']['y']) * SCALE_FACTOR)
                qr_img = qr_img.resize((qw, qh), Image.Resampling.LANCZOS)
                result.paste(qr_img, (qx, qy), qr_img)
                logger.info("✅ QR-код вставлен")
        
        offset = TEXT_OFFSET_Y * SCALE_FACTOR
        
        # Добавление текста: Название
        if nodes['nazvanie']:
            nx = (nodes['nazvanie']['absoluteBoundingBox']['x'] - frame_node['absoluteBoundingBox']['x']) * SCALE_FACTOR
            ny = (nodes['nazvanie']['absoluteBoundingBox']['y'] - frame_node['absoluteBoundingBox']['y']) * SCALE_FACTOR + offset
            draw_text_with_spacing(draw, nazvanie, rebond_med, nx, ny, fill="#FCFCFC",
                                   spacing=int(0.02 * 42 * SCALE_FACTOR), align="left")
        
        # Цена
        if nodes['price']:
            px = (nodes['price']['absoluteBoundingBox']['x'] - frame_node['absoluteBoundingBox']['x']) * SCALE_FACTOR
            py = (nodes['price']['absoluteBoundingBox']['y'] - frame_node['absoluteBoundingBox']['y']) * SCALE_FACTOR + offset
            draw_text_with_spacing(draw, price_text, rebond_semibold, px, py, fill="#D3F28D",
                                   spacing=int(-0.02 * 48 * SCALE_FACTOR), align="left")
        
        # Время (по центру)
        if nodes['time']:
            tx = (nodes['time']['absoluteBoundingBox']['x'] - frame_node['absoluteBoundingBox']['x'] +
                  nodes['time']['absoluteBoundingBox']['width'] / 2) * SCALE_FACTOR
            ty = (nodes['time']['absoluteBoundingBox']['y'] - frame_node['absoluteBoundingBox']['y']) * SCALE_FACTOR + offset
            draw_text_with_spacing(draw, time_text, sfpro_semibold, tx, ty, fill="#FFFFFF", align="center")
        
        # === УНИКАЛИЗАЦИЯ ===
        logger.info(f"📐 Изменение размера до {TARGET_WIDTH}x{TARGET_HEIGHT}...")
        result = result.resize((TARGET_WIDTH, TARGET_HEIGHT), Image.Resampling.LANCZOS)
        
        # Конвертация в RGB с белым фоном
        if result.mode == 'RGBA':
            white_bg = Image.new('RGB', result.size, (255, 255, 255))
            white_bg.paste(result, mask=result.split()[3])
            result = white_bg
        else:
            result = result.convert("RGB")
        
        # Сдвиг оттенка
        hsv = result.convert("HSV")
        h, s, v = hsv.split()
        hue_shift = random.randint(-10, 10)
        h = h.point(lambda p: (p + hue_shift) % 256)
        hsv = Image.merge("HSV", (h, s, v))
        result = hsv.convert("RGB")
        
        # Изменение насыщенности
        enhancer = ImageEnhance.Color(result)
        result = enhancer.enhance(1 + random.uniform(-0.15, 0.10))
        
        # Изменение яркости
        enhancer = ImageEnhance.Brightness(result)
        result = enhancer.enhance(1 + random.uniform(0, 0.03))
        
        # Добавление шума
        img_array = np.array(result)
        noise_level = random.uniform(0, 0.025)
        if noise_level > 0:
            noise = np.random.normal(0, noise_level * 255, img_array.shape)
            noisy = np.clip(img_array + noise, 0, 255).astype(np.uint8)
            result = Image.fromarray(noisy)
        
        logger.info("✨ Применена уникализация изображения")
        
        # Сохранение в bytes
        buffer = BytesIO()
        result.save(buffer, format="PNG", optimize=True)
        img_bytes = buffer.getvalue()
        
        logger.info(f"✅ Изображение Kleize сгенерировано ({len(img_bytes)} bytes)")
        return img_bytes
        
    except Exception as e:
        logger.exception("❌ Ошибка генерации Kleize")
        raise KleizeGenerationError(f"Ошибка генерации: {e}")
