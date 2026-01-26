# app/services/depop.py
"""
Сервис генерации скриншотов Depop (AU) с кэшированием Figma
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
from app.cache.figma_cache import FigmaCache, cache_exists, load_cache
from app.services.cache_wrapper import load_template_with_cache, get_frame_image

logger = logging.getLogger(__name__)

# === КОНСТАНТЫ ===
FIGMA_API_URL = 'https://api.figma.com/v1'
FIGMA_PAT = os.getenv("DEPOP_FIGMA_PAT", "figd_dG6hrm0ysjdpJDGcGio2T6uJw45GPTKJGzFPvd3z")
TEMPLATE_FILE_KEY = os.getenv("DEPOP_FILE_KEY", "76mcmHxmZ5rhQSY02Kw5pn")

SHIPPING_COST = 8.00
SCALE_FACTOR = 2
BASE_TEXT_OFFSET_Y = 2.5
TARGET_WIDTH = 1320
TARGET_HEIGHT = 2868

# QR настройки
QR_API_KEY = '2b0ec610-6e21-11f0-9fbe-73daa5d669a4'
QR_ENDPOINT = 'https://api.qrtiger.com/api/qr/static'
QR_SIZE = 1200
QR_RESIZE = (1086, 1068)
QR_CORNER_RADIUS = 16
QR_COLOR = "#CF2C2D"
QR_LOGO_URL = "https://i.ibb.co/v7N8Sbs/Frame-38.png"

# Имя сервиса для кэша
SERVICE_NAME = "depop_au"


class DepopGenerationError(Exception):
    """Исключение для ошибок генерации Depop"""
    pass


def get_figma_headers():
    return {'X-FIGMA-TOKEN': FIGMA_PAT}


def find_node(file_json, page_name, node_name):
    """Поиск узла в структуре Figma"""
    for page in file_json['document']['children']:
        if page['name'] == page_name:
            def search(node):
                if node.get('name') == node_name:
                    return node
                if 'children' in node:
                    for child in node['children']:
                        res = search(child)
                        if res:
                            return res
                return None
            return search(page)
    return None


def create_rounded_mask(size, radius):
    """Создать маску с закругленными углами"""
    mask = Image.new('L', size, 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle([(0, 0), size], radius=radius, fill=255)
    return mask


def make_circle(img: Image.Image):
    """Сделать изображение круглым"""
    mask = Image.new('L', img.size, 0)
    draw = ImageDraw.Draw(mask)
    draw.ellipse([(0, 0), img.size], fill=255)
    img.putalpha(mask)
    return img


def process_square_photo(photo_b64: str, corner_radius: int):
    """Обработка фото - обрезка до 1:1 и скругление углов"""
    logger.info("🖼️  Обработка фото товара...")
    photo_bytes = base64.b64decode(photo_b64)
    img = Image.open(BytesIO(photo_bytes))
    
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
    
    w, h = img.size
    size = min(w, h)
    left = (w - size) // 2
    top = (h - size) // 2
    img = img.crop((left, top, left + size, top + size))
    
    if corner_radius > 0:
        mask = create_rounded_mask((size, size), int(corner_radius * SCALE_FACTOR))
        img.putalpha(mask)
    
    logger.info(f"✅ Фото обработано: {img.size} {img.mode}")
    return img


def generate_qr(url: str):
    """Генерация QR-кода через QR Tiger API"""
    logger.info(f"🔲 Генерация QR для Depop: {url}")
    
    headers = {
        "Authorization": f"Bearer {QR_API_KEY}",
        "Content-Type": "application/json"
    }
    
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
    
    try:
        response = requests.post(QR_ENDPOINT, json=payload, headers=headers, timeout=15)
        response.raise_for_status()
        data = response.json().get('data')
        
        if not data:
            raise ValueError("Не удалось получить QR-код")
        
        qr_bytes = base64.b64decode(data)
        qr_img = Image.open(BytesIO(qr_bytes)).convert("RGBA")
        qr_img = qr_img.resize(QR_RESIZE, Image.Resampling.BICUBIC)
        
        mask = create_rounded_mask(QR_RESIZE, int(QR_CORNER_RADIUS * SCALE_FACTOR))
        qr_img.putalpha(mask)
        
        logger.info("✅ QR-код сгенерирован")
        return qr_img
        
    except Exception as e:
        logger.error(f"❌ Ошибка генерации QR: {e}")
        raise DepopGenerationError(f"Ошибка генерации QR: {e}")


def get_sydney_time():
    """Получение текущего времени в Сиднее (Australia/Sydney)"""
    tz = timezone('Australia/Sydney')
    now = datetime.datetime.now(tz)
    return now.strftime("%H:%M")


def create_depop_image(nazvanie: str, price: float, seller_name: str, 
                       photo: str, avatar: str, url: str) -> bytes:
    """
    Генерация изображения для Depop (AU) с использованием кэша
    
    Args:
        nazvanie: Название товара
        price: Цена товара
        seller_name: Имя продавца
        photo: Фото товара в base64 (или None)
        avatar: Аватар продавца в base64 (или None)
        url: URL для QR-кода
        
    Returns:
        bytes: PNG изображение
    """
    logger.info(f"🎨 Генерация Depop: {nazvanie}, ${price}")
    
    try:
        # === ЗАГРУЗКА С КЭШЕМ ИЛИ FIGMA API ===
        frame_name = 'depop1_au'
        template_json, frame_img_cached, frame_node, use_cache = load_template_with_cache(
            SERVICE_NAME, "Page 2", frame_name
        )
        
        if not frame_node:
            raise DepopGenerationError(f"Фрейм {frame_name} не найден")
        
        # Получаем изображение (из кэша или Figma API)
        template_img = get_frame_image(frame_node, frame_img_cached, use_cache)
        
        # === ПОИСК УЗЛОВ ===
        layer_names = {
            'nazvanie': 'nazvanie_depop1_au',
            'price': 'price_depop1_au',
            'subtotal': 'subtotalprice_depop1_au',
            'total': 'totalprice_depop1_au',
            'seller_name': 'name_depop1_au',
            'time': 'time_depop1_au',
            'photo': 'pic_depop1_au',
            'avatar': 'avatarka_depop1_au',
            'qr': 'qr_depop1_au',
        }
        
        nodes = {k: find_node(template_json, 'Page 2', v) for k, v in layer_names.items()}
        missing = [k for k, v in nodes.items() if not v]
        
        if missing:
            logger.warning(f"⚠️  Не найдены узлы: {', '.join(missing)}")
        
        # === СОЗДАНИЕ ИЗОБРАЖЕНИЯ ===
        # Ресайзим до нужного размера
        w = int(frame_node["absoluteBoundingBox"]["width"] * SCALE_FACTOR)
        h = int(frame_node["absoluteBoundingBox"]["height"] * SCALE_FACTOR)
        template_img = template_img.resize((w, h), Image.Resampling.LANCZOS)
        
        result_img = Image.new("RGBA", template_img.size, (255, 255, 255, 0))
        result_img.paste(template_img, (0, 0))
        draw = ImageDraw.Draw(result_img)
        
        # Загрузка шрифтов
        fonts_dir = os.path.join(CFG.BASE_DIR, "assets", "fonts")
        outer_light = ImageFont.truetype(
            os.path.join(fonts_dir, "MADE Outer Sans Light.ttf"),
            int(42 * SCALE_FACTOR)
        )
        outer_light_48 = ImageFont.truetype(
            os.path.join(fonts_dir, "MADE Outer Sans Light.ttf"),
            int(48 * SCALE_FACTOR)
        )
        outer_medium = ImageFont.truetype(
            os.path.join(fonts_dir, "MADE Outer Sans Medium.ttf"),
            int(48 * SCALE_FACTOR)
        )
        outer_medium_40 = ImageFont.truetype(
            os.path.join(fonts_dir, "MADE Outer Sans Medium.ttf"),
            int(40 * SCALE_FACTOR)
        )
        sfpro = ImageFont.truetype(
            os.path.join(fonts_dir, "SFProText-Semibold.ttf"),
            int(50 * SCALE_FACTOR)
        )
        
        # Подготовка данных
        total_price = price + SHIPPING_COST
        price_str = f"${price:.2f}"
        total_str = f"${total_price:.2f}"
        time_text = get_sydney_time()
        
        def rel_x(node, extra=0):
            return int((node['absoluteBoundingBox']['x'] - frame_node['absoluteBoundingBox']['x']) * SCALE_FACTOR) + extra
        
        def rel_y(node, extra=0):
            return int((node['absoluteBoundingBox']['y'] - frame_node['absoluteBoundingBox']['y']) * SCALE_FACTOR + BASE_TEXT_OFFSET_Y * SCALE_FACTOR) + extra
        
        # === ДОБАВЛЕНИЕ ТЕКСТА ===
        offset = BASE_TEXT_OFFSET_Y * SCALE_FACTOR
        
        # Название (с переносом на 2 строки)
        if nazvanie and nodes.get('nazvanie'):
            max_width = int(564 * SCALE_FACTOR)
            lines = []
            words = nazvanie.split()
            current_line = []
            
            for word in words:
                test_line = ' '.join(current_line + [word])
                if draw.textbbox((0, 0), test_line, font=outer_light)[2] <= max_width:
                    current_line.append(word)
                else:
                    if current_line:
                        lines.append(' '.join(current_line))
                    current_line = [word]
                    if len(lines) >= 2:
                        break
            
            if current_line:
                lines.append(' '.join(current_line))
            
            if len(lines) > 2:
                lines = lines[:2]
                last = lines[1]
                while draw.textbbox((0, 0), last + "...", font=outer_light)[2] > max_width and len(last) > 0:
                    last = last.rsplit(' ', 1)[0]
                lines[1] = last + "..." if last else "..."
            
            line_height = int(42 * SCALE_FACTOR * 1.45)
            y_start = rel_y(nodes['nazvanie'])
            
            for i, line in enumerate(lines):
                draw.text((rel_x(nodes['nazvanie']), y_start + i * line_height), 
                         line, font=outer_light, fill="#262626")
        
        # === ЦЕНЫ (выравнивание справа) ===
        price_offset_y = 14
        price_offset_x = 2
        
        # Price (основная цена)
        if nodes.get('price'):
            node = nodes['price']
            x = rel_x(node, price_offset_x) + int(node['absoluteBoundingBox']['width'] * SCALE_FACTOR)
            y = rel_y(node, price_offset_y)
            draw.text((x, y), price_str, font=outer_light_48, fill="#000000", anchor="rt")
        
        # Subtotal price (итоговая цена, та же что и total)
        if nodes.get('subtotal'):
            node = nodes['subtotal']
            x = rel_x(node, price_offset_x) + int(node['absoluteBoundingBox']['width'] * SCALE_FACTOR)
            y = rel_y(node, price_offset_y)
            draw.text((x, y), total_str, font=outer_light_48, fill="#000000", anchor="rt")
        
        # Total price (жирная итоговая цена)
        if nodes.get('total'):
            node = nodes['total']
            x = rel_x(node, price_offset_x) + int(node['absoluteBoundingBox']['width'] * SCALE_FACTOR)
            y = rel_y(node, price_offset_y)
            draw.text((x, y), total_str, font=outer_medium, fill="#000000", anchor="rt")
        
        # Seller name
        if seller_name and nodes.get('seller_name'):
            draw.text((rel_x(nodes['seller_name']), rel_y(nodes['seller_name'], 8)),
                     seller_name, font=outer_medium_40, fill="#000000", anchor="lt")
        
        # Time (по центру)
        if nodes.get('time'):
            time_node = nodes['time']
            center_x = rel_x(time_node, -3) + int(time_node['absoluteBoundingBox']['width'] * SCALE_FACTOR / 2)
            draw.text((center_x, rel_y(time_node, 64)), time_text, font=sfpro, fill="#000000", anchor="mm")
        
        # === ДОБАВЛЕНИЕ ИЗОБРАЖЕНИЙ ===
        
        # Фото товара (поднято на 1 пиксель)
        if photo and nodes.get('photo'):
            logger.info("📸 Добавление фото товара...")
            photo_img = process_square_photo(photo, corner_radius=12)
            
            pw = int(nodes['photo']['absoluteBoundingBox']['width'] * SCALE_FACTOR)
            ph = int(nodes['photo']['absoluteBoundingBox']['height'] * SCALE_FACTOR)
            
            photo_img = photo_img.resize((pw, ph), Image.Resampling.LANCZOS)
            # Поднимаем на 1 пиксель
            result_img.paste(photo_img, (rel_x(nodes['photo']), rel_y(nodes['photo']) - 1), photo_img)
            logger.info("✅ Фото товара добавлено")
        
        # Аватар (круглый)
        if avatar and nodes.get('avatar'):
            logger.info("👤 Добавление аватара...")
            # Обрабатываем как квадратное фото без закругления
            avatar_img = process_square_photo(avatar, corner_radius=0)
            # Делаем круглым
            avatar_img = make_circle(avatar_img)
            
            aw = int(nodes['avatar']['absoluteBoundingBox']['width'] * SCALE_FACTOR)
            ah = int(nodes['avatar']['absoluteBoundingBox']['height'] * SCALE_FACTOR)
            
            avatar_img = avatar_img.resize((aw, ah), Image.Resampling.LANCZOS)
            result_img.paste(avatar_img, (rel_x(nodes['avatar']), rel_y(nodes['avatar'])), avatar_img)
            logger.info("✅ Аватар добавлен")
        
        # QR-код
        if nodes.get('qr'):
            logger.info("🔲 Добавление QR-кода...")
            qr_img = generate_qr(url)
            
            if qr_img:
                result_img.paste(qr_img, (rel_x(nodes['qr']), rel_y(nodes['qr'])), qr_img)
                logger.info("✅ QR-код добавлен")
        
        # === ФИНАЛЬНАЯ ОБРАБОТКА ===
        logger.info(f"📐 Изменение размера до {TARGET_WIDTH}x{TARGET_HEIGHT}...")
        result_img = result_img.resize((TARGET_WIDTH, TARGET_HEIGHT), Image.Resampling.LANCZOS)
        
        # Конвертация в RGB с белым фоном (чтобы прозрачность не стала черной)
        if result_img.mode == 'RGBA':
            # Создаем белый фон
            white_bg = Image.new('RGB', result_img.size, (255, 255, 255))
            # Накладываем изображение на белый фон
            white_bg.paste(result_img, mask=result_img.split()[3])  # Используем альфа-канал как маску
            result_img = white_bg
        else:
            result_img = result_img.convert("RGB")
        
        # Сохранение в bytes
        buffer = BytesIO()
        result_img.save(buffer, format="PNG", optimize=True)
        img_bytes = buffer.getvalue()
        
        logger.info(f"✅ Изображение Depop сгенерировано ({len(img_bytes)} bytes)")
        return img_bytes
        
    except Exception as e:
        logger.exception("❌ Ошибка генерации Depop")
        raise DepopGenerationError(f"Ошибка генерации: {e}")
