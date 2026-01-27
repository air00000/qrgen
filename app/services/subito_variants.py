# app/services/subito_variants.py
"""
Различные варианты генерации для Subito:
- subito2: Email запрос
- subito3: Email подтверждение  
- subito4: SMS запрос
- subito5: SMS подтверждение
"""

import os
import io
import datetime
from pytz import timezone
from PIL import Image, ImageDraw, ImageFont

from app.config import CFG
from app.services.pdf import (
    get_template_json, find_node, export_frame_as_png, 
    process_photo_in_memory, draw_text_with_letter_spacing,
    _generate_qr_in_memory, FigmaNodeNotFoundError, PDFGenerationError
)
from app.services.cache_wrapper import load_template_with_cache, get_frame_image


def create_image_subito_email_request(nazvanie: str, price: float, photo: str, name: str = '', address: str = '') -> bytes:
    """
    Generates image for Subito Email Request (subito2), returns PNG bytes.
    Handles Data URI format for photos and truncates long text.
    """
    from app.utils.helpers import truncate_title, truncate_name, truncate_address
    
    # Truncate text fields
    nazvanie = truncate_title(nazvanie or "")
    name = truncate_name(name or "")
    address = truncate_address(address or "")
    
    frame_name = "subito2"
    nazvanie_layer = "NAZVANIE_SUB2"
    price_layer = "PRICE_SUB2"
    total_layer = "TOTAL_SUB2"
    adress_layer = "ADRESS_SUB2"
    imya_layer = "IMYA_SUB2"
    time_layer = "TIME_SUB2"
    foto_layer = "PHOTO_SUB2"

    # Загружаем с кэшем если доступен
    template_json, frame_img_cached, frame_node, use_cache = load_template_with_cache(
        "subito_email_request", "Page 2", frame_name
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
    }
    if any(n is None for n in nodes.values()):
        miss = [k for k, v in nodes.items() if v is None]
        raise FigmaNodeNotFoundError(f"Не найдены узлы: {', '.join(miss)}")

    # Фон из Figma или кэша
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

    # Итог - уменьшаем в 2 раза
    result = result.resize((1304, 2838), Image.Resampling.LANCZOS).convert("RGB")
    buf = io.BytesIO()
    result.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def create_image_subito_email_confirm(nazvanie: str, price: float, photo: str, name: str = '', address: str = '') -> bytes:
    """
    Generates image for Subito Email Confirm (subito3), returns PNG bytes.
    Handles Data URI format for photos and truncates long text.
    """
    from app.utils.helpers import truncate_title, truncate_name, truncate_address
    
    # Truncate text fields
    nazvanie = truncate_title(nazvanie or "")
    name = truncate_name(name or "")
    address = truncate_address(address or "")
    
    frame_name = "subito3"
    # Загружаем с кэшем если доступен
    template_json, frame_img_cached, frame_node, use_cache = load_template_with_cache(
        "subito_email_confirm", "Page 2", frame_name
    )

    if not frame_node:
        raise FigmaNodeNotFoundError(f"Фрейм {frame_name} не найден")

    nazvanie_layer = "NAZVANIE_SUB3"
    price_layer = "PRICE_SUB3"
    total_layer = "TOTAL_SUB3"
    adress_layer = "ADRESS_SUB3"
    imya_layer = "IMYA_SUB3"
    time_layer = "TIME_SUB3"
    foto_layer = "PHOTO_SUB3"

    nodes = {
        "nazvanie": find_node(template_json, "Page 2", nazvanie_layer),
        "price": find_node(template_json, "Page 2", price_layer),
        "total": find_node(template_json, "Page 2", total_layer),
        "adress": find_node(template_json, "Page 2", adress_layer),
        "imya": find_node(template_json, "Page 2", imya_layer),
        "time": find_node(template_json, "Page 2", time_layer),
        "foto": find_node(template_json, "Page 2", foto_layer),
    }
    
    if any(n is None for n in nodes.values()):
        miss = [k for k, v in nodes.items() if v is None]
        raise FigmaNodeNotFoundError(f"Не найдены узлы: {', '.join(miss)}")

    # Фон из Figma или кэша
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

    # Итог - уменьшаем в 2 раза
    result = result.resize((1304, 2838), Image.Resampling.LANCZOS).convert("RGB")
    buf = io.BytesIO()
    result.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def create_image_subito_sms_request(nazvanie: str, price: float, photo: str, name: str = '', address: str = '') -> bytes:
    """
    Generates image for Subito SMS Request (subito4), returns PNG bytes.
    Handles Data URI format for photos and truncates long text.
    """
    from app.utils.helpers import truncate_title, truncate_name, truncate_address
    
    # Truncate text fields
    nazvanie = truncate_title(nazvanie or "")
    name = truncate_name(name or "")
    address = truncate_address(address or "")
    
    frame_name = "subito4"
    # Загружаем с кэшем если доступен
    template_json, frame_img_cached, frame_node, use_cache = load_template_with_cache(
        "subito_sms_request", "Page 2", frame_name
    )

    if not frame_node:
        raise FigmaNodeNotFoundError(f"Фрейм {frame_name} не найден")

    nazvanie_layer = "NAZVANIE_SUB4"
    price_layer = "PRICE_SUB4"
    total_layer = "TOTAL_SUB4"
    adress_layer = "ADRESS_SUB4"
    imya_layer = "IMYA_SUB4"
    time_layer = "TIME_SUB4"
    foto_layer = "PHOTO_SUB4"

    nodes = {
        "nazvanie": find_node(template_json, "Page 2", nazvanie_layer),
        "price": find_node(template_json, "Page 2", price_layer),
        "total": find_node(template_json, "Page 2", total_layer),
        "adress": find_node(template_json, "Page 2", adress_layer),
        "imya": find_node(template_json, "Page 2", imya_layer),
        "time": find_node(template_json, "Page 2", time_layer),
        "foto": find_node(template_json, "Page 2", foto_layer),
    }
    
    if any(n is None for n in nodes.values()):
        miss = [k for k, v in nodes.items() if v is None]
        raise FigmaNodeNotFoundError(f"Не найдены узлы: {', '.join(miss)}")

    # Фон из Figma или кэша
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

    # Итог - уменьшаем в 2 раза
    result = result.resize((1304, 2838), Image.Resampling.LANCZOS).convert("RGB")
    buf = io.BytesIO()
    result.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def create_image_subito_sms_confirm(nazvanie: str, price: float, photo: str, name: str = '', address: str = '') -> bytes:
    """
    Generates image for Subito SMS Confirm (subito5), returns PNG bytes.
    Handles Data URI format for photos and truncates long text.
    """
    from app.utils.helpers import truncate_title, truncate_name, truncate_address
    
    # Truncate text fields
    nazvanie = truncate_title(nazvanie or "")
    name = truncate_name(name or "")
    address = truncate_address(address or "")
    
    frame_name = "subito5"
    # Загружаем с кэшем если доступен
    template_json, frame_img_cached, frame_node, use_cache = load_template_with_cache(
        "subito_sms_confirm", "Page 2", frame_name
    )

    if not frame_node:
        raise FigmaNodeNotFoundError(f"Фрейм {frame_name} не найден")

    nazvanie_layer = "NAZVANIE_SUB5"
    price_layer = "PRICE_SUB5"
    total_layer = "TOTAL_SUB5"
    adress_layer = "ADRESS_SUB5"
    imya_layer = "IMYA_SUB5"
    time_layer = "TIME_SUB5"
    foto_layer = "PHOTO_SUB5"

    nodes = {
        "nazvanie": find_node(template_json, "Page 2", nazvanie_layer),
        "price": find_node(template_json, "Page 2", price_layer),
        "total": find_node(template_json, "Page 2", total_layer),
        "adress": find_node(template_json, "Page 2", adress_layer),
        "imya": find_node(template_json, "Page 2", imya_layer),
        "time": find_node(template_json, "Page 2", time_layer),
        "foto": find_node(template_json, "Page 2", foto_layer),
    }
    
    if any(n is None for n in nodes.values()):
        miss = [k for k, v in nodes.items() if v is None]
        raise FigmaNodeNotFoundError(f"Не найдены узлы: {', '.join(miss)}")

    # Фон из Figma или кэша
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

    # Итог - уменьшаем в 2 раза
    result = result.resize((1304, 2838), Image.Resampling.LANCZOS).convert("RGB")
    buf = io.BytesIO()
    result.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


# Класс ошибки для совместимости
class SubitoVariantError(Exception):
    """Ошибка генерации Subito вариантов"""
    pass
