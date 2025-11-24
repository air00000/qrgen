# app/services/twodehands.py
import os
import io
import base64
import datetime
import requests
from typing import Optional
from PIL import Image, ImageDraw, ImageFont
from pytz import timezone

from app.services.figma import get_template_json, find_node, export_frame_as_png
from app.config import CFG

# Константы для 2dehands
TWODEHANDS_FIGMA_PAT = 'figd_dG6hrm0ysjdpJDGcGio2T6uJw45GPTKJGzFPvd3z'
TWODEHANDS_FILE_KEY = '76mcmHxmZ5rhQSY02Kw5pn'
TWODEHANDS_SCALE_FACTOR = 2
TWODEHANDS_TEXT_OFFSET = 2.5
TARGET_WIDTH = 1304
TARGET_HEIGHT = 2838
QR_SIZE = 2000
QR_RESIZE = (1020, 1020)
CORNER_RADIUS_PHOTO = 15
CORNER_RADIUS_QR = 16
QR_COLOR = "#11223E"
QR_LOGO_URL = "https://i.ibb.co/6crPXzDJ/2dehlogo.png"


class TwoDehandsGenerationError(Exception):
    """Базовое исключение для ошибок генерации 2dehands"""
    pass


def create_rounded_mask(size, radius):
    """Создание маски с закругленными углами"""
    mask = Image.new('L', size, 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle([(0, 0), size], radius=radius, fill=255)
    return mask


def process_photo_2dehands(photo_data: str) -> Image.Image:
    """Обработка фото: обрезка до 1:1 и скругление углов"""
    if not photo_data:
        return None
    
    photo_bytes = base64.b64decode(photo_data)
    img = Image.open(io.BytesIO(photo_bytes)).convert("RGBA")
    width, height = img.size
    size = min(width, height)
    left = (width - size) // 2
    top = (height - size) // 2
    img = img.crop((left, top, left + size, top + size))
    mask = create_rounded_mask((size, size), int(CORNER_RADIUS_PHOTO * TWODEHANDS_SCALE_FACTOR))
    img.putalpha(mask)
    return img


def generate_qr_2dehands(url: str) -> Image.Image:
    """Генерация QR-кода через QR TIGER для 2dehands"""
    import logging
    logger = logging.getLogger(__name__)
    
    logger.info(f"🔲 Запрос QR для URL: {url}")
    
    headers = {
        "Authorization": f"Bearer {CFG.QR_API_KEY}",
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
    
    logger.info(f"📡 Отправка запроса к QR Tiger API...")
    
    try:
        response = requests.post(CFG.QR_ENDPOINT, json=payload, headers=headers, timeout=30)
        logger.info(f"📥 Получен ответ: {response.status_code}")
    except requests.Timeout:
        logger.error("❌ Timeout при запросе QR API")
        raise TwoDehandsGenerationError("Timeout при генерации QR")
    except Exception as e:
        logger.error(f"❌ Ошибка запроса QR API: {e}")
        raise
    
    if response.status_code != 200:
        logger.error(f"❌ QR API вернул ошибку: {response.status_code} - {response.text}")
        raise TwoDehandsGenerationError(f"Ошибка API QR: {response.text}")
    
    data = response.json().get('data')
    if not data:
        logger.error("❌ Нет данных QR в ответе")
        raise TwoDehandsGenerationError("Нет данных QR в ответе от QR API")
    
    logger.info("🎨 Обработка QR изображения...")
    
    qr_bytes = base64.b64decode(data)
    qr_img = Image.open(io.BytesIO(qr_bytes)).convert("RGBA")
    qr_img = qr_img.resize(QR_RESIZE, Image.Resampling.BICUBIC)
    mask = create_rounded_mask(QR_RESIZE, int(CORNER_RADIUS_QR * TWODEHANDS_SCALE_FACTOR))
    qr_img.putalpha(mask)
    
    logger.info("✅ QR обработан и готов")
    
    return qr_img


def get_local_time(language: str) -> str:
    """Получение времени по часовому поясу"""
    if language == 'nl':
        tz = timezone('Europe/Amsterdam')
    elif language == 'fr':
        tz = timezone('Europe/Paris')
    else:
        tz = timezone('Europe/Amsterdam')
    
    now = datetime.datetime.now(tz)
    hour = now.hour
    minute = now.minute
    return f"{hour:02d}:{minute:02d}"


def draw_text_with_letter_spacing(draw, text, font, x, y, fill, letter_spacing=0, align="left"):
    """Отрисовка текста с межбуквенным интервалом"""
    char_widths = [font.getbbox(ch)[2] for ch in text]
    total_width = sum(char_widths) + letter_spacing * (len(text) - 1)
    
    if align == "right":
        start_x = x - total_width
    elif align == "center":
        start_x = x - total_width / 2
    else:
        start_x = x
    
    cur_x = start_x
    for i, ch in enumerate(text):
        draw.text((cur_x, y), ch, font=font, fill=fill)
        cur_x += char_widths[i] + letter_spacing


def create_2dehands_image(nazvanie: str, price: float, photo: Optional[str], url: str, language: str) -> bytes:
    """Создание изображения для 2dehands"""
    
    import logging
    logger = logging.getLogger(__name__)
    
    logger.info(f"🚀 Начало генерации 2dehands: {nazvanie}, {price}€, язык={language}")
    logger.info(f"📷 Фото: {'есть' if photo else 'нет'}, URL: {url}")
    
    # Получаем JSON шаблона из Figma
    logger.info("📥 Запрос шаблона из Figma...")
    try:
        template_json = get_template_json(TWODEHANDS_FIGMA_PAT, TWODEHANDS_FILE_KEY)
        logger.info("✅ Шаблон получен из Figma")
    except Exception as e:
        logger.error(f"❌ Ошибка получения шаблона Figma: {e}")
        raise
    
    # Определяем имена фреймов и слоев в зависимости от языка
    frame_name = '2dehands1' if language == 'nl' else '2ememain1'
    nazvanie_layer = f'nazv_{frame_name}'
    price_layer = f'price_{frame_name}'
    time_layer = f'time_{frame_name}'
    foto_layer = f'pic_{frame_name}'
    qr_layer = f'qr_{frame_name}'
    
    logger.info(f"🔍 Поиск фрейма: {frame_name}")
    
    # Находим узлы в Figma
    frame_node = find_node(template_json, 'Page 2', frame_name)
    if not frame_node:
        logger.error(f"❌ Фрейм {frame_name} не найден")
        raise TwoDehandsGenerationError(f"Фрейм {frame_name} не найден")
    
    logger.info(f"✅ Фрейм найден, поиск слоёв...")
    
    nodes = {
        'nazvanie': find_node(template_json, 'Page 2', nazvanie_layer),
        'price': find_node(template_json, 'Page 2', price_layer),
        'time': find_node(template_json, 'Page 2', time_layer),
        'foto': find_node(template_json, 'Page 2', foto_layer),
        'qr': find_node(template_json, 'Page 2', qr_layer)
    }
    
    missing_nodes = [label for label, node in nodes.items() if not node]
    if missing_nodes:
        logger.error(f"❌ Не найдены узлы: {', '.join(missing_nodes)}")
        raise TwoDehandsGenerationError(f"Не найдены узлы: {', '.join(missing_nodes)}")
    
    logger.info("✅ Все узлы найдены")
    
    # Экспортируем фрейм как PNG
    logger.info("🖼️  Экспорт фрейма из Figma...")
    try:
        template_png_content = export_frame_as_png(TWODEHANDS_FIGMA_PAT, TWODEHANDS_FILE_KEY, frame_node['id'], TWODEHANDS_SCALE_FACTOR)
        logger.info(f"✅ Фрейм экспортирован, размер: {len(template_png_content)} байт")
    except Exception as e:
        logger.error(f"❌ Ошибка экспорта фрейма: {e}")
        raise
    template_img = Image.open(io.BytesIO(template_png_content)).convert("RGBA")
    frame_width = frame_node['absoluteBoundingBox']['width'] * TWODEHANDS_SCALE_FACTOR
    frame_height = frame_node['absoluteBoundingBox']['height'] * TWODEHANDS_SCALE_FACTOR
    template_img = template_img.resize((int(frame_width), int(frame_height)), Image.Resampling.LANCZOS)
    
    # Создаем изображение
    result_img = Image.new("RGBA", (int(frame_width), int(frame_height)), (255, 255, 255, 0))
    result_img.paste(template_img, (0, 0))
    draw = ImageDraw.Draw(result_img)
    
    logger.info("🔤 Загрузка шрифтов...")
    
    # Загрузка шрифтов
    sfpro_regular_path = os.path.join(CFG.FONTS_DIR, 'SFProText-Regular.ttf')
    sfpro_semibold_path = os.path.join(CFG.FONTS_DIR, 'SFProText-Semibold.ttf')
    
    nazv_font_size = int(42 * TWODEHANDS_SCALE_FACTOR)
    price_font_size = int(48 * TWODEHANDS_SCALE_FACTOR)
    time_font_size = int(54 * TWODEHANDS_SCALE_FACTOR)
    
    nazv_font = ImageFont.truetype(sfpro_regular_path, nazv_font_size) if os.path.exists(sfpro_regular_path) else ImageFont.load_default()
    price_font = ImageFont.truetype(sfpro_semibold_path, price_font_size) if os.path.exists(sfpro_semibold_path) else ImageFont.load_default()
    time_font = ImageFont.truetype(sfpro_semibold_path, time_font_size) if os.path.exists(sfpro_semibold_path) else ImageFont.load_default()
    
    logger.info("✅ Шрифты загружены")
    
    # Letter spacing
    nazv_letter_spacing = int(-0.04 * (nazv_font_size / 2))
    price_letter_spacing = int(-0.03 * (price_font_size / 2))
    time_letter_spacing = 0
    
    # Подготавливаем данные
    time_text = get_local_time(language)
    formatted_price = f'€ {price:.2f}'.replace('.', ',')
    
    logger.info(f"📝 Время: {time_text}, Цена: {formatted_price}")
    
    # Накладываем фото
    if photo and nodes['foto']:
        logger.info("📷 Обработка фото...")
        foto_img = process_photo_2dehands(photo)
        if foto_img:
            foto_width = int(nodes['foto']['absoluteBoundingBox']['width'] * TWODEHANDS_SCALE_FACTOR)
            foto_height = int(nodes['foto']['absoluteBoundingBox']['height'] * TWODEHANDS_SCALE_FACTOR)
            foto_x = int((nodes['foto']['absoluteBoundingBox']['x'] - frame_node['absoluteBoundingBox']['x']) * TWODEHANDS_SCALE_FACTOR)
            foto_y = int((nodes['foto']['absoluteBoundingBox']['y'] - frame_node['absoluteBoundingBox']['y']) * TWODEHANDS_SCALE_FACTOR)
            foto_img = foto_img.resize((foto_width, foto_height), Image.Resampling.LANCZOS)
            result_img.paste(foto_img, (foto_x, foto_y), foto_img)
            logger.info("✅ Фото добавлено")
    else:
        logger.info("ℹ️  Фото пропущено")
    
    # Накладываем QR
    logger.info("🔲 Генерация QR-кода...")
    try:
        qr_img = generate_qr_2dehands(url)
        logger.info("✅ QR-код сгенерирован")
        if qr_img and nodes['qr']:
            qr_width = int(nodes['qr']['absoluteBoundingBox']['width'] * TWODEHANDS_SCALE_FACTOR)
            qr_height = int(nodes['qr']['absoluteBoundingBox']['height'] * TWODEHANDS_SCALE_FACTOR)
            qr_x = int((nodes['qr']['absoluteBoundingBox']['x'] - frame_node['absoluteBoundingBox']['x']) * TWODEHANDS_SCALE_FACTOR)
            qr_y = int((nodes['qr']['absoluteBoundingBox']['y'] - frame_node['absoluteBoundingBox']['y']) * TWODEHANDS_SCALE_FACTOR)
            qr_img = qr_img.resize((qr_width, qr_height), Image.Resampling.LANCZOS)
            result_img.paste(qr_img, (qr_x, qr_y), qr_img)
            logger.info("✅ QR-код добавлен на изображение")
    except Exception as e:
        # Если QR не сгенерировался, продолжаем без него
        logger.warning(f"⚠️  Ошибка генерации QR (продолжаем без него): {e}")
    
    logger.info("✍️  Добавление текста...")
    
    # NAZVANIE (left align)
    nazvanie_x = (nodes['nazvanie']['absoluteBoundingBox']['x'] - frame_node['absoluteBoundingBox']['x']) * TWODEHANDS_SCALE_FACTOR
    nazvanie_y = (nodes['nazvanie']['absoluteBoundingBox']['y'] - frame_node['absoluteBoundingBox']['y']) * TWODEHANDS_SCALE_FACTOR + TWODEHANDS_TEXT_OFFSET * TWODEHANDS_SCALE_FACTOR
    draw_text_with_letter_spacing(draw, nazvanie, nazv_font, nazvanie_x, nazvanie_y, fill="#001836", letter_spacing=nazv_letter_spacing, align="left")
    
    # PRICE (left align)
    price_x = (nodes['price']['absoluteBoundingBox']['x'] - frame_node['absoluteBoundingBox']['x']) * TWODEHANDS_SCALE_FACTOR
    price_y = (nodes['price']['absoluteBoundingBox']['y'] - frame_node['absoluteBoundingBox']['y']) * TWODEHANDS_SCALE_FACTOR + TWODEHANDS_TEXT_OFFSET * TWODEHANDS_SCALE_FACTOR
    draw_text_with_letter_spacing(draw, formatted_price, price_font, price_x, price_y, fill="#001836", letter_spacing=price_letter_spacing, align="left")
    
    # TIME (center align)
    time_bbox = nodes['time']['absoluteBoundingBox']
    time_center_x = (time_bbox['x'] - frame_node['absoluteBoundingBox']['x'] + time_bbox['width'] / 2) * TWODEHANDS_SCALE_FACTOR
    time_y = (time_bbox['y'] - frame_node['absoluteBoundingBox']['y']) * TWODEHANDS_SCALE_FACTOR + TWODEHANDS_TEXT_OFFSET * TWODEHANDS_SCALE_FACTOR
    draw_text_with_letter_spacing(draw, time_text, time_font, time_center_x, time_y, fill="#FFFFFF", letter_spacing=time_letter_spacing, align="center")
    
    logger.info("✅ Текст добавлен")
    logger.info("🔄 Финальная обработка изображения...")
    
    # Сжимаем изображение до целевых размеров
    result_img = result_img.resize((TARGET_WIDTH, TARGET_HEIGHT), Image.Resampling.LANCZOS)
    
    # Конвертируем в RGB для отправки в Telegram
    result_img = result_img.convert("RGB")
    
    logger.info("💾 Сохранение в байты...")
    
    # Сохраняем изображение в байты с оптимизацией
    buffer = io.BytesIO()
    result_img.save(buffer, format="PNG", optimize=True, quality=85)
    image_bytes = buffer.getvalue()
    
    logger.info(f"✅ Изображение сохранено: {len(image_bytes)/1024:.1f} КБ")
    
    # Проверяем размер файла
    if len(image_bytes) > 10 * 1024 * 1024:  # 10 МБ
        logger.info("🔄 Изображение слишком большое, пересжимаем...")
        buffer = io.BytesIO()
        result_img.save(buffer, format="PNG", optimize=True, quality=50)
        image_bytes = buffer.getvalue()
        logger.info(f"✅ Пересжато до: {len(image_bytes)/1024:.1f} КБ")
    
    logger.info("🎉 Генерация завершена успешно!")
    return image_bytes
