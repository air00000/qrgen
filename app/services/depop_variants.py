# app/services/depop_variants.py
"""
Различные варианты генерации для Depop (AU):
- depop2_au: Email запрос (mail request)
- depop3_au: Email подтверждение (mail confirm)
- depop4_au: SMS запрос (number request)
- depop5_au: SMS подтверждение (sms confirm)
"""

import os
import io
import base64
import datetime
from pytz import timezone
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
import logging

from app.config import CFG
from app.cache.figma_cache import FigmaCache, cache_exists
from app.services.cache_wrapper import load_template_with_cache, get_frame_image

logger = logging.getLogger(__name__)

# === КОНСТАНТЫ ===
SHIPPING_COST = 8.00
SCALE_FACTOR = 2
BASE_TEXT_OFFSET_Y = 2.5
TARGET_WIDTH = 1320
TARGET_HEIGHT = 2868


class DepopVariantError(Exception):
    """Исключение для ошибок генерации Depop вариантов"""
    pass


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


def clear_template_areas(img: Image.Image, frame_node: dict, nodes: dict, scale: int = SCALE_FACTOR, skip_keys: list = None) -> Image.Image:
    """
    Очистка областей текста и фото на шаблоне (заливка белым/серым)
    Это нужно чтобы данные из Figma не накладывались на новые данные
    
    Args:
        skip_keys: список ключей узлов которые НЕ нужно очищать (например ['time'])
    """
    draw = ImageDraw.Draw(img)
    
    frame_x = frame_node['absoluteBoundingBox']['x']
    frame_y = frame_node['absoluteBoundingBox']['y']
    
    skip_keys = skip_keys or []
    cleared_count = 0
    
    for key, node in nodes.items():
        if node is None:
            continue
        
        # Пропускаем указанные ключи
        if key in skip_keys:
            continue
            
        # Вычисляем координаты относительно фрейма
        x = int((node['absoluteBoundingBox']['x'] - frame_x) * scale)
        y = int((node['absoluteBoundingBox']['y'] - frame_y) * scale)
        w = int(node['absoluteBoundingBox']['width'] * scale)
        h = int(node['absoluteBoundingBox']['height'] * scale)
        
        # Добавляем небольшой отступ для полной очистки
        padding = 5
        x = max(0, x - padding)
        y = max(0, y - padding)
        w = w + padding * 2
        h = h + padding * 2
        
        # Заливаем белым цветом
        draw.rectangle([(x, y), (x + w, y + h)], fill=(255, 255, 255, 255))
        cleared_count += 1
        
    logger.info(f"🧹 Очищено {cleared_count} областей на шаблоне (пропущено: {skip_keys})")
    return img


def create_rounded_mask(size, radius):
    """Создать маску с закругленными углами"""
    mask = Image.new('L', size, 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle([(0, 0), size], radius=radius, fill=255)
    return mask


def process_square_photo(photo_b64: str, corner_radius: int):
    """
    Обработка фото - обрезка до 1:1 и скругление углов.
    Поддерживает Data URI и plain base64.
    """
    from app.utils.helpers import parse_data_uri
    
    logger.info("🖼️  Обработка фото товара...")
    
    # Парсим Data URI
    base64_data = parse_data_uri(photo_b64)
    if not base64_data:
        logger.warning("⚠️  Фото пустое или неверный формат")
        return None
    
    try:
        photo_bytes = base64.b64decode(base64_data)
        img = Image.open(BytesIO(photo_bytes))
        
        # Если есть прозрачность - наложить на белый фон
        if img.mode in ('RGBA', 'LA', 'P'):
            if img.mode != 'RGBA':
                img = img.convert('RGBA')
            white_bg = Image.new('RGBA', img.size, (255, 255, 255, 255))
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
    except Exception as e:
        logger.error(f"❌ Ошибка обработки фото: {e}")
        return None


def get_rome_time():
    """Получение текущего времени в Риме (Europe/Rome)"""
    tz = timezone('Europe/Rome')
    now = datetime.datetime.now(tz)
    return now.strftime("%H:%M")


def _create_depop_variant_image(
    frame_name: str,
    service_name: str,
    nazvanie: str, 
    price: float, 
    photo: str = None
) -> bytes:
    """
    Общая функция генерации изображения для Depop вариантов (без QR).
    Поддерживает Data URI для фото и обрезку длинного текста.
    
    Args:
        frame_name: Имя фрейма в Figma (depop2_au, depop3_au, etc.)
        service_name: Имя сервиса для кэша
        nazvanie: Название товара
        price: Цена товара
        photo: Фото товара в Data URI или base64 (или None)
        
    Returns:
        bytes: PNG изображение
    """
    from app.utils.helpers import truncate_title
    
    # Обрезаем длинный текст
    nazvanie = truncate_title(nazvanie or "")
    
    logger.info(f"🎨 Генерация {service_name}: {nazvanie}, ${price}")
    
    try:
        # Загрузка с кэшем
        template_json, frame_img_cached, frame_node, use_cache = load_template_with_cache(
            service_name, "Page 2", frame_name
        )
        
        if not frame_node:
            raise DepopVariantError(f"Фрейм {frame_name} не найден")
        
        # Имена слоёв
        layer_names = {
            'nazvanie': f'nazvanie_{frame_name}',
            'price': f'price_{frame_name}',
            'subtotal': f'subtotalprice_{frame_name}',
            'total': f'totalprice_{frame_name}',
            'time': f'time_{frame_name}',
            'photo': f'pic_{frame_name}',
        }
        
        nodes = {k: find_node(template_json, 'Page 2', v) for k, v in layer_names.items()}
        missing = [k for k, v in nodes.items() if not v]
        
        if missing:
            logger.warning(f"⚠️  Не найдены узлы: {', '.join(missing)}")
        
        # Получаем изображение фрейма
        frame_img = get_frame_image(frame_node, frame_img_cached, use_cache)
        w = int(frame_node["absoluteBoundingBox"]["width"] * SCALE_FACTOR)
        h = int(frame_node["absoluteBoundingBox"]["height"] * SCALE_FACTOR)
        frame_img = frame_img.resize((w, h), Image.Resampling.LANCZOS)
        
        result_img = Image.new("RGBA", (w, h), (255, 255, 255, 0))
        result_img.paste(frame_img, (0, 0))
        
        # Очищаем области текста и фото чтобы данные из Figma не накладывались
        result_img = clear_template_areas(result_img, frame_node, nodes, SCALE_FACTOR, skip_keys=['time'])
        
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
        sfpro = ImageFont.truetype(
            os.path.join(fonts_dir, "SFProText-Semibold.ttf"),
            int(50 * SCALE_FACTOR)
        )
        
        # Подготовка данных
        total_price = price + SHIPPING_COST
        price_str = f"${price:.2f}"
        total_str = f"${total_price:.2f}"
        time_text = get_rome_time()
        
        def rel_x(node, extra=0):
            return int((node['absoluteBoundingBox']['x'] - frame_node['absoluteBoundingBox']['x']) * SCALE_FACTOR) + extra
        
        def rel_y(node, extra=0):
            return int((node['absoluteBoundingBox']['y'] - frame_node['absoluteBoundingBox']['y']) * SCALE_FACTOR + BASE_TEXT_OFFSET_Y * SCALE_FACTOR) + extra
        
        # === ДОБАВЛЕНИЕ ТЕКСТА ===
        
        # Название (с переносом на 2 строки, макс ширина 452px)
        if nazvanie and nodes.get('nazvanie'):
            max_width = int(452 * SCALE_FACTOR)
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
                    last = last.rsplit(' ', 1)[0] if ' ' in last else last[:-1]
                lines[1] = last + "..." if last else "..."
            
            # Line height 147.2%
            line_height = int(42 * SCALE_FACTOR * 1.472)
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
        
        # Subtotal price
        if nodes.get('subtotal'):
            node = nodes['subtotal']
            x = rel_x(node, price_offset_x) + int(node['absoluteBoundingBox']['width'] * SCALE_FACTOR)
            y = rel_y(node, price_offset_y)
            draw.text((x, y), total_str, font=outer_light_48, fill="#000000", anchor="rt")
        
        # Total price (жирная)
        if nodes.get('total'):
            node = nodes['total']
            x = rel_x(node, price_offset_x) + int(node['absoluteBoundingBox']['width'] * SCALE_FACTOR)
            y = rel_y(node, price_offset_y)
            draw.text((x, y), total_str, font=outer_medium, fill="#000000", anchor="rt")
        
        # Time (по центру, letter spacing -3%)
        if nodes.get('time'):
            time_node = nodes['time']
            center_x = rel_x(time_node, -3) + int(time_node['absoluteBoundingBox']['width'] * SCALE_FACTOR / 2)
            draw.text((center_x, rel_y(time_node, 64)), time_text, font=sfpro, fill="#000000", anchor="mm")
        
        # === ДОБАВЛЕНИЕ ФОТО ===
        if photo and nodes.get('photo'):
            logger.info("📸 Добавление фото товара...")
            photo_img = process_square_photo(photo, corner_radius=12)
            
            pw = int(nodes['photo']['absoluteBoundingBox']['width'] * SCALE_FACTOR)
            ph = int(nodes['photo']['absoluteBoundingBox']['height'] * SCALE_FACTOR)
            
            photo_img = photo_img.resize((pw, ph), Image.Resampling.LANCZOS)
            result_img.paste(photo_img, (rel_x(nodes['photo']), rel_y(nodes['photo']) - 5), photo_img)
            logger.info("✅ Фото товара добавлено")
        
        # === ФИНАЛЬНАЯ ОБРАБОТКА ===
        logger.info(f"📐 Изменение размера до {TARGET_WIDTH}x{TARGET_HEIGHT}...")
        result_img = result_img.resize((TARGET_WIDTH, TARGET_HEIGHT), Image.Resampling.LANCZOS)
        
        # Конвертация в RGB с белым фоном
        if result_img.mode == 'RGBA':
            white_bg = Image.new('RGB', result_img.size, (255, 255, 255))
            white_bg.paste(result_img, mask=result_img.split()[3])
            result_img = white_bg
        else:
            result_img = result_img.convert("RGB")
        
        # Сохранение в bytes
        buffer = BytesIO()
        result_img.save(buffer, format="PNG", optimize=True)
        img_bytes = buffer.getvalue()
        
        logger.info(f"✅ Изображение {service_name} сгенерировано ({len(img_bytes)} bytes)")
        return img_bytes
        
    except Exception as e:
        logger.exception(f"❌ Ошибка генерации {service_name}")
        raise DepopVariantError(f"Ошибка генерации: {e}")


def create_depop_email_request(nazvanie: str, price: float, photo: str = None) -> bytes:
    """
    Генерация изображения для Depop Email Request (depop2_au)
    """
    return _create_depop_variant_image(
        frame_name="depop2_au",
        service_name="depop_au_email_request",
        nazvanie=nazvanie,
        price=price,
        photo=photo
    )


def create_depop_email_confirm(nazvanie: str, price: float, photo: str = None) -> bytes:
    """
    Генерация изображения для Depop Email Confirm (depop3_au)
    """
    return _create_depop_variant_image(
        frame_name="depop3_au",
        service_name="depop_au_email_confirm",
        nazvanie=nazvanie,
        price=price,
        photo=photo
    )


def create_depop_sms_request(nazvanie: str, price: float, photo: str = None) -> bytes:
    """
    Генерация изображения для Depop SMS Request (depop4_au)
    """
    return _create_depop_variant_image(
        frame_name="depop4_au",
        service_name="depop_au_sms_request",
        nazvanie=nazvanie,
        price=price,
        photo=photo
    )


def create_depop_sms_confirm(nazvanie: str, price: float, photo: str = None) -> bytes:
    """
    Генерация изображения для Depop SMS Confirm (depop5_au)
    """
    return _create_depop_variant_image(
        frame_name="depop5_au",
        service_name="depop_au_sms_confirm",
        nazvanie=nazvanie,
        price=price,
        photo=photo
    )
