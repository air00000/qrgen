# app/services/conto.py
import os
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

UNIQUE_MODE = True  # True = с уникализацией, False = чистое
SCALE_FACTOR = 2
TEXT_OFFSET_Y = 2.5
TARGET_WIDTH = 1304
TARGET_HEIGHT = 2838
MAX_TEXT_WIDTH = 1085


class ContoGenerationError(Exception):
    """Исключение для ошибок генерации Conto"""
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


def get_rome_time():
    """Получение текущего времени в Риме"""
    return datetime.datetime.now(timezone('Europe/Rome')).strftime("%H:%M")


def get_italian_date():
    """Получение даты в итальянском формате"""
    now = datetime.datetime.now(timezone('Europe/Rome'))
    months = {
        1: 'Gen', 2: 'Feb', 3: 'Mar', 4: 'Apr', 5: 'Mag', 6: 'Giu',
        7: 'Lug', 8: 'Ago', 9: 'Set', 10: 'Ott', 11: 'Nov', 12: 'Dic'
    }
    return f"{now.day} {months[now.month]} {now.year}"


def draw_text_with_spacing(draw, text, font, x, y, fill, spacing=0, align="left"):
    """Рисование текста с кастомным spacing между символами"""
    if not text:
        return
    # Вычисляем общую ширину
    widths = [font.getbbox(ch)[2] - font.getbbox(ch)[0] for ch in text]
    total_width = sum(widths) + spacing * (len(text) - 1)

    if align == "center":
        x -= total_width / 2
    elif align == "right":
        x -= total_width

    cur_x = x
    for i, ch in enumerate(text):
        draw.text((cur_x, y), ch, font=font, fill=fill)
        cur_x += widths[i] + spacing


def wrap_text(text, font, max_width, spacing):
    """Перенос текста по словам с учетом максимальной ширины"""
    words = text.split()
    lines = []
    current = []
    for word in words:
        test = ' '.join(current + [word])
        w = sum([font.getbbox(ch)[2] - font.getbbox(ch)[0] for ch in test]) + spacing * (len(test) - 1)
        if w <= max_width:
            current.append(word)
        else:
            if current:
                lines.append(' '.join(current))
            current = [word]
    if current:
        lines.append(' '.join(current))
    return lines


def create_conto_image(nazvanie: str, price: float) -> bytes:
    """
    Генерация изображения для Conto (Subito)
    
    Args:
        nazvanie: Название товара
        price: Цена товара
        
    Returns:
        bytes: PNG изображение
    """
    logger.info(f"🎨 Генерация Conto: {nazvanie}, {price}€")
    
    try:
        # Формируем полный текст
        full_text = f'Pagamento per il prodotto "{nazvanie}" tramite transazione sicura Subito'
        
        # Определяем количество строк для выбора правильного фрейма
        fonts_dir = os.path.join(CFG.BASE_DIR, "assets", "fonts")
        font_title = ImageFont.truetype(os.path.join(fonts_dir, "SFProText-Semibold.ttf"), int(50 * SCALE_FACTOR))
        spacing_title = int(-0.005 * 50 * SCALE_FACTOR)
        
        lines = wrap_text(full_text, font_title, MAX_TEXT_WIDTH * SCALE_FACTOR, spacing_title)
        frame_name = 'conto1_short' if len(lines) <= 2 else 'conto1_long'
        
        logger.info(f"📐 Текст занимает {len(lines)} строк, используем фрейм: {frame_name}")
        
        # Загружаем с кэшем если доступен
        service_name = f"conto_{frame_name}"
        template_json, frame_img_cached, frame_node, use_cache = load_template_with_cache(
            service_name, "Page 2", frame_name,
            figma_pat=FIGMA_PAT, file_key=TEMPLATE_FILE_KEY
        )
        
        if not frame_node:
            raise ContoGenerationError(f"Фрейм {frame_name} не найден")
        
        nodes = {
            'tovar': find_node(template_json, 'Page 2', f"tovar{frame_name}"),
            'price': find_node(template_json, 'Page 2', f"price{frame_name}"),
            'time': find_node(template_json, 'Page 2', f"time{frame_name}"),
            'data': find_node(template_json, 'Page 2', f"data{frame_name}"),
        }
        
        # Получаем изображение из кэша или Figma
        logger.info("📥 Загрузка шаблона...")
        if use_cache and len(template_json.get('document', {}).get('children', [])) > 0:
            # Возвращаем 6 значений когда передаём custom credentials
            base_img = get_frame_image(frame_node, frame_img_cached, use_cache, 
                                       figma_pat=FIGMA_PAT, file_key=TEMPLATE_FILE_KEY)
        else:
            base_img = get_frame_image(frame_node, frame_img_cached, use_cache,
                                       figma_pat=FIGMA_PAT, file_key=TEMPLATE_FILE_KEY)
        
        w = int(frame_node['absoluteBoundingBox']['width'] * SCALE_FACTOR)
        h = int(frame_node['absoluteBoundingBox']['height'] * SCALE_FACTOR)
        base_img = base_img.resize((w, h), Image.Resampling.LANCZOS)
        
        result = Image.new("RGBA", (w, h), (255, 255, 255, 0))
        result.paste(base_img, (0, 0))
        draw = ImageDraw.Draw(result)
        
        # Загрузка шрифтов
        f_title = ImageFont.truetype(os.path.join(fonts_dir, "SFProText-Semibold.ttf"), int(50 * SCALE_FACTOR))
        f_time = ImageFont.truetype(os.path.join(fonts_dir, "SFProText-Semibold.ttf"), int(54 * SCALE_FACTOR))
        f_date = ImageFont.truetype(os.path.join(fonts_dir, "SFProText-Regular.ttf"), int(50 * SCALE_FACTOR))
        f_int = ImageFont.truetype(os.path.join(fonts_dir, "Inter-SemiBold.ttf"), int(100 * SCALE_FACTOR))
        f_dec = ImageFont.truetype(os.path.join(fonts_dir, "Inter-SemiBold.ttf"), int(55 * SCALE_FACTOR))
        
        offset = TEXT_OFFSET_Y * SCALE_FACTOR
        
        # === НАЗВАНИЕ (многострочное) ===
        if nodes['tovar']:
            nx = (nodes['tovar']['absoluteBoundingBox']['x'] - frame_node['absoluteBoundingBox']['x']) * SCALE_FACTOR
            ny = (nodes['tovar']['absoluteBoundingBox']['y'] - frame_node['absoluteBoundingBox']['y']) * SCALE_FACTOR + offset
            line_h = int(62 * SCALE_FACTOR)
            for i, line in enumerate(lines):
                draw_text_with_spacing(draw, line, f_title, nx, ny + i * line_h, "#000000", spacing_title)
        
        # === ЦЕНА — копейки приподняты на 10 пикселей ===
        if nodes['price']:
            price_str = f"-{price:,.2f} €".replace(".", ",").replace(",-", "-")
            integer_part = price_str.split(",")[0]  # "-123"
            decimal_part = "," + price_str.split(",")[1]  # ",45 €"
            
            px = (nodes['price']['absoluteBoundingBox']['x'] - frame_node['absoluteBoundingBox']['x']) * SCALE_FACTOR
            py = (nodes['price']['absoluteBoundingBox']['y'] - frame_node['absoluteBoundingBox']['y']) * SCALE_FACTOR + offset
            
            # Измеряем ширину целой части
            int_width = sum(f_int.getbbox(ch)[2] - f_int.getbbox(ch)[0] for ch in integer_part)
            
            # Рисуем целую часть
            draw_text_with_spacing(draw, integer_part, f_int, px, py, "#000000", spacing=0)
            
            # Копейки — идеальное выравнивание по нижней линии + подъём на 10 пикселей
            _, _, _, descent_big = f_int.getbbox("gjpqy")
            _, _, _, descent_small = f_dec.getbbox("gjpqy")
            
            dec_x = px + int_width
            dec_y = py + (descent_big - descent_small) - (10 * SCALE_FACTOR)  # приподнимаем на 10 пикселей
            
            draw_text_with_spacing(draw, decimal_part, f_dec, dec_x, dec_y, "#000000", spacing=0)
        
        # === ВРЕМЯ ===
        if nodes['time']:
            tx = (nodes['time']['absoluteBoundingBox']['x'] - frame_node['absoluteBoundingBox']['x'] +
                  nodes['time']['absoluteBoundingBox']['width'] / 2) * SCALE_FACTOR
            ty = (nodes['time']['absoluteBoundingBox']['y'] - frame_node['absoluteBoundingBox']['y']) * SCALE_FACTOR + offset
            draw_text_with_spacing(draw, get_rome_time(), f_time, tx, ty, "#000000",
                                   spacing=int(-0.03 * 54 * SCALE_FACTOR), align="center")
        
        # === ДАТА ===
        if nodes['data']:
            dx = (nodes['data']['absoluteBoundingBox']['x'] - frame_node['absoluteBoundingBox']['x']) * SCALE_FACTOR
            dy = (nodes['data']['absoluteBoundingBox']['y'] - frame_node['absoluteBoundingBox']['y']) * SCALE_FACTOR + offset
            draw_text_with_spacing(draw, get_italian_date(), f_date, dx, dy, "#000000",
                                   spacing=int(-0.005 * 50 * SCALE_FACTOR))
        
        # === УНИКАЛИЗАЦИЯ ===
        logger.info(f"📐 Изменение размера до {TARGET_WIDTH}x{TARGET_HEIGHT}...")
        result = result.resize((TARGET_WIDTH, TARGET_HEIGHT), Image.Resampling.LANCZOS)
        result = result.convert("RGB")
        
        if UNIQUE_MODE:
            # Сдвиг оттенка
            hsv = result.convert("HSV")
            h, s, v = hsv.split()
            h = h.point(lambda p: (p + random.randint(-10, 10)) % 256)
            result = Image.merge("HSV", (h, s, v)).convert("RGB")
            
            # Изменение насыщенности цвета
            result = ImageEnhance.Color(result).enhance(1 + random.uniform(-0.15, 0.10))
            
            # Изменение яркости
            result = ImageEnhance.Brightness(result).enhance(1 + random.uniform(0, 0.03))
            
            # Добавление шума
            arr = np.array(result)
            noise = np.random.normal(0, random.uniform(0, 0.025) * 255, arr.shape)
            arr = np.clip(arr + noise, 0, 255).astype(np.uint8)
            result = Image.fromarray(arr)
            
            logger.info("✨ Применена уникализация изображения")
        
        # Сохранение в bytes
        buffer = BytesIO()
        result.save(buffer, format="PNG", optimize=True)
        img_bytes = buffer.getvalue()
        
        logger.info(f"✅ Изображение Conto сгенерировано ({len(img_bytes)} bytes)")
        return img_bytes
        
    except Exception as e:
        logger.exception("❌ Ошибка генерации Conto")
        raise ContoGenerationError(f"Ошибка генерации: {e}")
