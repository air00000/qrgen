import os
import base64
import uuid
import requests
import datetime
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
from fastapi import HTTPException

from app.config import CFG

# Обработка фото: обрезка до 1:1 и скругление углов
def process_photo(photo_data: str):
    photo_bytes = base64.b64decode(photo_data)
    img = Image.open(BytesIO(photo_bytes)).convert("RGBA")
    width, height = img.size
    size = min(width, height)
    left = (width - size) // 2
    top = (height - size) // 2
    img = img.crop((left, top, left + size, top + size))
    mask = create_rounded_mask((size, size), int(CFG.CORNER_RADIUS * CFG.SCALE_FACTOR))
    img.putalpha(mask)
    processed_path = os.path.join(CFG.TEMP_DIR, f"processed_photo_{uuid.uuid4()}.png")
    img.save(processed_path, "PNG")
    return processed_path

# Генерация QR-кода через QR TIGER
def generate_qr(url):

    qr_path = os.path.join(CFG.TEMP_DIR, f"qr_{uuid.uuid4()}.png")
    headers = {
        "Authorization": f"Bearer {CFG.QR_API_KEY}",
        "Content-Type": "application/json"
    }

    logo_payload = None
    if os.path.exists(CFG.LOCAL_LOGO_PATH):
        with open(CFG.LOCAL_LOGO_PATH, "rb") as lf:
            base64.b64encode(lf.read()).decode("utf-8")
            logo_payload = "https://i.ibb.co.com/BR56TLT/logo.png"

    payload = {
        "qrCategory": "url",
        "text": url,
        "size": CFG.QR_SIZE,
        "colorDark": "#FF6E69",
        "backgroundColor": "#FFFFFF",
        "transparentBkg": False,
        "eye_outer": "eyeOuter2",
        "eye_inner": "eyeInner2",
        "qrData": "pattern4",
        "logo": logo_payload
    }

    response = requests.post(CFG.QR_ENDPOINT, json=payload, headers=headers)
    if response.status_code != 200:
        raise HTTPException(status_code=500, detail=f"Ошибка API QR: {response.text}")

    data = response.json().get("data")
    if not data:
        raise HTTPException(status_code=500, detail="Нет данных QR в ответе от QR API")

    qr_bytes = base64.b64decode(data)
    with open(qr_path, "wb") as f:
        f.write(qr_bytes)

    qr_img = Image.open(qr_path).convert("RGBA")
    qr_img = qr_img.resize(CFG.QR_RESIZE, Image.Resampling.BICUBIC)
    mask = create_rounded_mask(CFG.QR_RESIZE, int(CFG.CORNER_RADIUS * CFG.SCALE_FACTOR))
    qr_img.putalpha(mask)
    qr_img.save(qr_path, format="PNG")
    return qr_path

def create_rounded_mask(size, radius):
    mask = Image.new('L', size, 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle([(0, 0), size], radius=radius, fill=255)
    return mask


# Поиск узла по имени на странице
def find_node(file_json, page_name, node_name):
    for page in file_json['document']['children']:
        if page['name'] == page_name:
            def search_node(node, target_name):
                if 'name' in node and node['name'] == target_name:
                    return node
                if 'children' in node:
                    for child in node['children']:
                        result = search_node(child, target_name)
                        if result:
                            return result
                return None
            return search_node(page, node_name)
    return None

# Время по Риму
def get_rome_time():
    now = datetime.datetime.now(CFG.TZ)
    hour = now.hour
    minute = now.minute
    return f"{hour}:{minute:02d}"

def get_figma_headers():
    return {'X-FIGMA-TOKEN': CFG.FIGMA_PAT}

# Отрисовка текста с межбуквенным интервалом
def draw_text_with_letter_spacing(draw, text, font, x, y, fill, letter_spacing=0, align="left"):
    total_width = sum([font.getbbox(ch)[2] for ch in text]) + letter_spacing * (len(text) - 1)
    start_x = x - total_width if align == "right" else x
    cur_x = start_x
    for ch in text:
        draw.text((cur_x, y), ch, font=font, fill=fill)
        cur_x += font.getbbox(ch)[2] + letter_spacing

def get_template_json():
    response = requests.get(f'{CFG.FIGMA_API_URL}/files/{CFG.TEMPLATE_FILE_KEY}', headers=get_figma_headers())
    if response.status_code == 200:
        return response.json()
    else:
        raise HTTPException(status_code=500, detail=f"Ошибка получения шаблона: {response.text}")


def export_frame_as_png(file_key, node_id):
    url = f'{CFG.FIGMA_API_URL}/images/{file_key}?ids={node_id}&format=png&scale={CFG.SCALE_FACTOR}'
    response = requests.get(url, headers=get_figma_headers())
    if response.status_code == 200:
        png_url = response.json()['images'][node_id]
        png_response = requests.get(png_url)
        return png_response.content
    else:
        raise HTTPException(status_code=500, detail=f"Ошибка экспорта PNG: {response.text}")


# Создание изображения
def create_image(nazvanie: str, price: float, photo: str, url: str, name: str = "", address: str = ""):
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
    missing_nodes = [label for label, node in nodes.items() if not node]
    if missing_nodes:
        raise HTTPException(status_code=500, detail=f"Не найдены узлы: {', '.join(missing_nodes)}")

    template_png_content = export_frame_as_png(CFG.TEMPLATE_FILE_KEY, frame_node["id"])
    template_img = Image.open(BytesIO(template_png_content)).convert("RGBA")
    frame_width = frame_node["absoluteBoundingBox"]["width"] * CFG.SCALE_FACTOR
    frame_height = frame_node["absoluteBoundingBox"]["height"] * CFG.SCALE_FACTOR
    template_img = template_img.resize((int(frame_width), int(frame_height)), Image.Resampling.LANCZOS)

    result_img = Image.new("RGBA", (int(frame_width), int(frame_height)), (255, 255, 255, 0))
    result_img.paste(template_img, (0, 0))
    draw = ImageDraw.Draw(result_img)

    nazv_font = ImageFont.truetype(CFG.aktiv_path, int(96 * CFG.SCALE_FACTOR)) if os.path.exists(CFG.aktiv_path) else ImageFont.load_default()
    small_font = ImageFont.truetype(CFG.aktiv_path, int(64 * CFG.SCALE_FACTOR)) if os.path.exists(CFG.aktiv_path) else ImageFont.load_default()
    time_font = ImageFont.truetype(CFG.sfpro_path, int(112 * CFG.SCALE_FACTOR)) if os.path.exists(CFG.sfpro_path) else ImageFont.load_default()

    time_text = get_rome_time()
    formatted_price = f"€{price:.2f}"

    processed_photo_path = None
    if photo and nodes["foto"]:
        processed_photo_path = process_photo(photo)
        foto_img = Image.open(processed_photo_path).convert("RGBA")
        foto_width = int(nodes["foto"]["absoluteBoundingBox"]["width"] * CFG.SCALE_FACTOR)
        foto_height = int(nodes["foto"]["absoluteBoundingBox"]["height"] * CFG.SCALE_FACTOR)
        foto_x = int((nodes["foto"]["absoluteBoundingBox"]["x"] - frame_node["absoluteBoundingBox"]["x"]) * CFG.SCALE_FACTOR)
        foto_y = int((nodes["foto"]["absoluteBoundingBox"]["y"] - frame_node["absoluteBoundingBox"]["y"]) * CFG.SCALE_FACTOR)
        foto_img = foto_img.resize((foto_width, foto_height), Image.Resampling.LANCZOS)
        result_img.paste(foto_img, (foto_x, foto_y), foto_img)

    qr_path = None
    try:
        qr_path = generate_qr(url)
    except Exception:
        qr_path = None

    if qr_path and nodes["qr"]:
        qr_img = Image.open(qr_path).convert("RGBA")
        qr_width = int(nodes["qr"]["absoluteBoundingBox"]["width"] * CFG.SCALE_FACTOR)
        qr_height = int(nodes["qr"]["absoluteBoundingBox"]["height"] * CFG.SCALE_FACTOR)
        qr_x = int((nodes["qr"]["absoluteBoundingBox"]["x"] - frame_node["absoluteBoundingBox"]["x"]) * CFG.SCALE_FACTOR)
        qr_y = int((nodes["qr"]["absoluteBoundingBox"]["y"] - frame_node["absoluteBoundingBox"]["y"]) * CFG.SCALE_FACTOR)
        qr_img = qr_img.resize((qr_width, qr_height), Image.Resampling.LANCZOS)
        result_img.paste(qr_img, (qr_x, qr_y), qr_img)

    nazvanie_x = (nodes["nazvanie"]["absoluteBoundingBox"]["x"] - frame_node["absoluteBoundingBox"]["x"]) * CFG.SCALE_FACTOR
    nazvanie_y = (nodes["nazvanie"]["absoluteBoundingBox"]["y"] - frame_node["absoluteBoundingBox"]["y"]) * CFG.SCALE_FACTOR + CFG.TEXT_OFFSET * CFG.SCALE_FACTOR
    draw.text((nazvanie_x, nazvanie_y), nazvanie, font=nazv_font, fill="#1F262D")

    price_x = (nodes["price"]["absoluteBoundingBox"]["x"] - frame_node["absoluteBoundingBox"]["x"]) * CFG.SCALE_FACTOR
    price_y = (nodes["price"]["absoluteBoundingBox"]["y"] - frame_node["absoluteBoundingBox"]["y"]) * CFG.SCALE_FACTOR + CFG.TEXT_OFFSET * CFG.SCALE_FACTOR
    draw.text((price_x, price_y), formatted_price, font=nazv_font, fill="#838386")

    total_bbox = nodes["total"]["absoluteBoundingBox"]
    total_right_x = (total_bbox["x"] - frame_node["absoluteBoundingBox"]["x"] + total_bbox["width"]) * CFG.SCALE_FACTOR
    total_y = (total_bbox["y"] - frame_node["absoluteBoundingBox"]["y"]) * CFG.SCALE_FACTOR + CFG.TEXT_OFFSET * CFG.SCALE_FACTOR
    draw_text_with_letter_spacing(draw, formatted_price, nazv_font, total_right_x, total_y, fill="#838386", align="right")

    small_size = 64 * CFG.SCALE_FACTOR
    line_height = small_size * 1.219
    imya_x = (nodes["imya"]["absoluteBoundingBox"]["x"] - frame_node["absoluteBoundingBox"]["x"]) * CFG.SCALE_FACTOR
    imya_y = (nodes["imya"]["absoluteBoundingBox"]["y"] - frame_node["absoluteBoundingBox"]["y"]) * CFG.SCALE_FACTOR + CFG.TEXT_OFFSET * CFG.SCALE_FACTOR
    if name:
        for ln in str(name).split("\n"):
            draw.text((imya_x, imya_y), ln, font=small_font, fill="#838386")
            imya_y += line_height

    adress_x = (nodes["adress"]["absoluteBoundingBox"]["x"] - frame_node["absoluteBoundingBox"]["x"]) * CFG.SCALE_FACTOR
    adress_y = (nodes["adress"]["absoluteBoundingBox"]["y"] - frame_node["absoluteBoundingBox"]["y"]) * CFG.SCALE_FACTOR + CFG.TEXT_OFFSET * CFG.SCALE_FACTOR
    if address:
        for ln in str(address).split("\n"):
            draw.text((adress_x, adress_y), ln, font=small_font, fill="#838386")
            adress_y += line_height

    time_bbox = nodes["time"]["absoluteBoundingBox"]
    time_right_x = (time_bbox["x"] - frame_node["absoluteBoundingBox"]["x"] + time_bbox["width"]) * CFG.SCALE_FACTOR
    time_y = (time_bbox["y"] - frame_node["absoluteBoundingBox"]["y"]) * CFG.SCALE_FACTOR + CFG.TEXT_OFFSET * CFG.SCALE_FACTOR
    letter_spacing = 112 * CFG.SCALE_FACTOR * 0.02
    draw_text_with_letter_spacing(draw, time_text, time_font, time_right_x, time_y, fill="#FFFFFF", letter_spacing=letter_spacing, align="right")

    result_img = result_img.resize((CFG.TARGET_WIDTH, CFG.TARGET_HEIGHT), Image.Resampling.LANCZOS)
    result_img = result_img.convert("RGB")

    buffer = BytesIO()
    result_img.save(buffer, format="PNG", optimize=True, quality=85)
    image_bytes = buffer.getvalue()

    if len(image_bytes) > 10 * 1024 * 1024:
        buffer = BytesIO()
        result_img.save(buffer, format="PNG", optimize=True, quality=50)
        image_bytes = buffer.getvalue()

    for path in [processed_photo_path, qr_path]:
        if path and os.path.exists(path):
            try:
                os.remove(path)
            except Exception:
                pass

    return image_bytes
