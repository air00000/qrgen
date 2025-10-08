# app/services/pdf.py
import os, uuid, datetime
from io import BytesIO
from pathlib import Path

from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from PIL import Image, ImageDraw, ImageFont

from app.config import CFG
from app.services.figma import get_template_json, find_node, export_frame_as_png
from app.services.qr_local import generate_qr

# Регистрируем шрифты
pdfmetrics.registerFont(TTFont('Inter-SemiBold',      os.path.join(CFG.FONTS_DIR, 'Inter_18pt-SemiBold.ttf')))
pdfmetrics.registerFont(TTFont('Inter-Medium',        os.path.join(CFG.FONTS_DIR, 'Inter_18pt-Medium.ttf')))
pdfmetrics.registerFont(TTFont('SFProText-Semibold',  os.path.join(CFG.FONTS_DIR, 'SFProText-Semibold.ttf')))

# Локальный логотип для QR (офлайн)
_ASSETS_DIR = Path(CFG.FONTS_DIR).parent  # app/assets
_LOCAL_LOGO = _ASSETS_DIR / "foti" / "coin.png"
_LOCAL_LOGO_PATH = str(_LOCAL_LOGO) if _LOCAL_LOGO.exists() else None

_INTER_SEMIBOLD = os.path.join(CFG.FONTS_DIR, 'Inter_18pt-SemiBold.ttf')
_INTER_MEDIUM = os.path.join(CFG.FONTS_DIR, 'Inter_18pt-Medium.ttf')
_SFPRO_SEMIBOLD = os.path.join(CFG.FONTS_DIR, 'SFProText-Semibold.ttf')

def _rounded_mask(size, radius):
    m = Image.new("L", size, 0)
    d = ImageDraw.Draw(m)
    d.rounded_rectangle([(0, 0), size], radius=radius, fill=255)
    return m

def _process_photo(image_path, temp_dir):
    img = Image.open(image_path).convert("RGBA")
    w, h = img.size
    sz = min(w, h)
    l = (w - sz) // 2
    t = (h - sz) // 2
    img = img.crop((l, t, l + sz, t + sz))
    mask = _rounded_mask((sz, sz), CFG.CORNER_RADIUS * CFG.SCALE_FACTOR)
    img.putalpha(mask)
    out = os.path.join(temp_dir, f"processed_{uuid.uuid4()}.png")
    img.save(out, "PNG")
    return out

def _nl_time_str():
    return datetime.datetime.now(CFG.TZ).strftime("%H:%M")


def _load_font(path, size):
    if os.path.exists(path):
        return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def _text_width(font: ImageFont.ImageFont, text: str) -> float:
    if hasattr(font, "getlength"):
        return font.getlength(text)
    bbox = font.getbbox(text)
    return bbox[2] - bbox[0]


def _paste_to_node(base: Image.Image, overlay: Image.Image, frame_node: dict, target_node: dict):
    frame_bbox = frame_node['absoluteBoundingBox']
    target_bbox = target_node['absoluteBoundingBox']
    width = int(target_bbox['width'] * CFG.SCALE_FACTOR)
    height = int(target_bbox['height'] * CFG.SCALE_FACTOR)
    x = int((target_bbox['x'] - frame_bbox['x']) * CFG.SCALE_FACTOR)
    y = int((target_bbox['y'] - frame_bbox['y']) * CFG.SCALE_FACTOR)
    overlay = overlay.resize((width, height), Image.Resampling.LANCZOS)
    base.paste(overlay, (x, y), overlay)

def create_pdf(nazvanie, price, photo_path, url, *, temp_dir=None):
    temp_dir = temp_dir or CFG.TEMP_DIR
    os.makedirs(temp_dir, exist_ok=True)

    # 1) Figma JSON + поиск узлов
    template_json = get_template_json()
    frame_name     = 'Marktplaats'
    nazvanie_layer = '1NAZVANIE'
    price_layer    = '1PRICE'
    time_layer     = '1TIME'
    foto_layer     = '1FOTO'
    qr_layer       = '1QR'

    frame_node   = find_node(template_json, 'Page 2', frame_name)
    nazvanie_node= find_node(template_json, 'Page 2', nazvanie_layer)
    price_node   = find_node(template_json, 'Page 2', price_layer)
    time_node    = find_node(template_json, 'Page 2', time_layer)
    foto_node    = find_node(template_json, 'Page 2', foto_layer)
    qr_node      = find_node(template_json, 'Page 2', qr_layer)

    for n, nm in [
        (frame_node, frame_name),
        (nazvanie_node, nazvanie_layer),
        (price_node,    price_layer),
        (time_node,     time_layer),
        (foto_node,     foto_layer),
        (qr_node,       qr_layer),
    ]:
        if not n:
            raise RuntimeError(f"Узел не найден: {nm}")

    # 2) Экспорт кадра из Figma как PNG
    template_png = export_frame_as_png(CFG.TEMPLATE_FILE_KEY, frame_node['id'])
    template_path = os.path.join(temp_dir, 'template.png')
    with open(template_path, "wb") as f:
        f.write(template_png)

    # 3) Подготовка размеров страницы
    time_text = _nl_time_str()
    formatted_price = f"€{price}"

    frame_w = frame_node['absoluteBoundingBox']['width']  * CFG.SCALE_FACTOR
    frame_h = frame_node['absoluteBoundingBox']['height'] * CFG.SCALE_FACTOR
    page_w  = frame_w * CFG.CONVERSION_FACTOR
    page_h  = frame_h * CFG.CONVERSION_FACTOR

    pdf_path = os.path.join(temp_dir, f"MARKTPLAATS_{uuid.uuid4()}.pdf")
    c = canvas.Canvas(pdf_path, pagesize=(page_w, page_h))

    # Фон
    c.drawImage(template_path, 0, 0, width=page_w, height=page_h)

    # 4) Фото (если есть)
    processed_photo_path = None
    if photo_path and foto_node:
        processed_photo_path = _process_photo(photo_path, temp_dir)
        fx = (foto_node['absoluteBoundingBox']['x'] - frame_node['absoluteBoundingBox']['x']) * CFG.SCALE_FACTOR * CFG.CONVERSION_FACTOR
        fy = page_h - ((foto_node['absoluteBoundingBox']['y'] - frame_node['absoluteBoundingBox']['y']) + foto_node['absoluteBoundingBox']['height']) * CFG.SCALE_FACTOR * CFG.CONVERSION_FACTOR
        fw =  foto_node['absoluteBoundingBox']['width']  * CFG.SCALE_FACTOR * CFG.CONVERSION_FACTOR
        fh =  foto_node['absoluteBoundingBox']['height'] * CFG.SCALE_FACTOR * CFG.CONVERSION_FACTOR
        c.drawImage(processed_photo_path, fx, fy, width=fw, height=fh, preserveAspectRatio=True, mask='auto')

    # 5) QR — ПОЛНОСТЬЮ ЛОКАЛЬНО
    qx = (qr_node['absoluteBoundingBox']['x'] - frame_node['absoluteBoundingBox']['x']) * CFG.SCALE_FACTOR * CFG.CONVERSION_FACTOR
    qy = page_h - ((qr_node['absoluteBoundingBox']['y'] - frame_node['absoluteBoundingBox']['y']) + qr_node['absoluteBoundingBox']['height']) * CFG.SCALE_FACTOR * CFG.CONVERSION_FACTOR
    qw =  qr_node['absoluteBoundingBox']['width']  * CFG.SCALE_FACTOR * CFG.CONVERSION_FACTOR
    qh =  qr_node['absoluteBoundingBox']['height'] * CFG.SCALE_FACTOR * CFG.CONVERSION_FACTOR

    qr_path = generate_qr(
        url,
        str(temp_dir),
        target_size=(int(qw), int(qh)),
        color_dark="#4B6179",
        color_bg="#FFFFFF",
        corner_radius=int(CFG.CORNER_RADIUS * CFG.SCALE_FACTOR),
        logo_path=_LOCAL_LOGO_PATH,         # ← локальный файл (если есть)
        center_badge_bg="#F0A05B",          # ← круг под логотипом (как на эталоне). Убери, если не нужен
        center_badge_padding=1.18
    )
    c.drawImage(qr_path, qx, qy, width=qw, height=qh, preserveAspectRatio=True, mask='auto')

    # 6) Тексты
    nx = (nazvanie_node['absoluteBoundingBox']['x'] - frame_node['absoluteBoundingBox']['x']) * CFG.SCALE_FACTOR * CFG.CONVERSION_FACTOR
    ny = page_h - (nazvanie_node['absoluteBoundingBox']['y'] - frame_node['absoluteBoundingBox']['y']) * CFG.SCALE_FACTOR * CFG.CONVERSION_FACTOR \
         - 96 * CFG.SCALE_FACTOR * CFG.CONVERSION_FACTOR + (CFG.TEXT_OFFSET * CFG.SCALE_FACTOR * CFG.CONVERSION_FACTOR)
    c.setFont('Inter-SemiBold', 96 * CFG.SCALE_FACTOR * CFG.CONVERSION_FACTOR)
    c.setFillColor(HexColor('#1F262D'))
    c.drawString(nx, ny, nazvanie)

    px = (price_node['absoluteBoundingBox']['x'] - frame_node['absoluteBoundingBox']['x']) * CFG.SCALE_FACTOR * CFG.CONVERSION_FACTOR
    py = page_h - (price_node['absoluteBoundingBox']['y'] - frame_node['absoluteBoundingBox']['y']) * CFG.SCALE_FACTOR * CFG.CONVERSION_FACTOR \
         - 96 * CFG.SCALE_FACTOR * CFG.CONVERSION_FACTOR + (CFG.TEXT_OFFSET * CFG.SCALE_FACTOR * CFG.CONVERSION_FACTOR)
    c.setFont('Inter-Medium', 96 * CFG.SCALE_FACTOR * CFG.CONVERSION_FACTOR)
    c.setFillColor(HexColor('#838383'))
    c.drawString(px, py, f"{formatted_price}")

    tb = time_node['absoluteBoundingBox']
    tw = tb['width'] * CFG.SCALE_FACTOR * CFG.CONVERSION_FACTOR
    tx = (tb['x'] - frame_node['absoluteBoundingBox']['x']) * CFG.SCALE_FACTOR * CFG.CONVERSION_FACTOR + \
         (tw - c.stringWidth(time_text, 'SFProText-Semibold', 108 * CFG.SCALE_FACTOR * CFG.CONVERSION_FACTOR)) / 2
    ty = page_h - (tb['y'] - frame_node['absoluteBoundingBox']['y']) * CFG.SCALE_FACTOR * CFG.CONVERSION_FACTOR \
         - 108 * CFG.SCALE_FACTOR * CFG.CONVERSION_FACTOR + (CFG.TEXT_OFFSET * CFG.SCALE_FACTOR * CFG.CONVERSION_FACTOR)
    c.setFont('SFProText-Semibold', 108 * CFG.SCALE_FACTOR * CFG.CONVERSION_FACTOR)
    c.setFillColor(HexColor('#000000'))
    c.drawString(tx, ty, time_text)

    c.showPage()
    c.save()

    # подчистка временных файлов
    try:
        if os.path.exists(template_path):
            os.remove(template_path)
    except Exception:
        pass

    return pdf_path, processed_photo_path, qr_path


def create_marktplaats_image(nazvanie, price, photo_path, url, *, temp_dir=None):
    temp_dir = temp_dir or CFG.TEMP_DIR
    os.makedirs(temp_dir, exist_ok=True)

    template_json = get_template_json()
    frame_name = 'Marktplaats'
    layer_map = {
        'nazvanie': '1NAZVANIE',
        'price': '1PRICE',
        'time': '1TIME',
        'foto': '1FOTO',
        'qr': '1QR',
    }

    frame_node = find_node(template_json, 'Page 2', frame_name)
    if not frame_node:
        raise RuntimeError(f"Узел не найден: {frame_name}")

    nodes = {
        key: find_node(template_json, 'Page 2', layer)
        for key, layer in layer_map.items()
    }

    missing = [layer for key, layer in layer_map.items() if nodes.get(key) is None]
    if missing:
        raise RuntimeError(f"Не найдены узлы: {', '.join(missing)}")

    template_png = export_frame_as_png(CFG.TEMPLATE_FILE_KEY, frame_node['id'])
    template_img = Image.open(BytesIO(template_png)).convert("RGBA")

    frame_w = int(frame_node['absoluteBoundingBox']['width'] * CFG.SCALE_FACTOR)
    frame_h = int(frame_node['absoluteBoundingBox']['height'] * CFG.SCALE_FACTOR)
    template_img = template_img.resize((frame_w, frame_h), Image.Resampling.LANCZOS)

    result = Image.new("RGBA", (frame_w, frame_h), (255, 255, 255, 0))
    result.paste(template_img, (0, 0))
    draw = ImageDraw.Draw(result)

    title_font = _load_font(_INTER_SEMIBOLD, int(96 * CFG.SCALE_FACTOR))
    price_font = _load_font(_INTER_MEDIUM, int(96 * CFG.SCALE_FACTOR))
    time_font = _load_font(_SFPRO_SEMIBOLD, int(108 * CFG.SCALE_FACTOR))

    processed_photo_path = None
    if photo_path and nodes['foto']:
        processed_photo_path = _process_photo(photo_path, temp_dir)
        photo_img = Image.open(processed_photo_path).convert("RGBA")
        _paste_to_node(result, photo_img, frame_node, nodes['foto'])

    qr_path = generate_qr(
        url,
        str(temp_dir),
        target_size=(
            int(nodes['qr']['absoluteBoundingBox']['width'] * CFG.SCALE_FACTOR),
            int(nodes['qr']['absoluteBoundingBox']['height'] * CFG.SCALE_FACTOR),
        ),
        color_dark="#4B6179",
        color_bg="#FFFFFF",
        corner_radius=int(CFG.CORNER_RADIUS * CFG.SCALE_FACTOR),
        logo_path=_LOCAL_LOGO_PATH,
        center_badge_bg="#F0A05B",
        center_badge_padding=1.18,
    )

    qr_img = Image.open(qr_path).convert("RGBA")
    _paste_to_node(result, qr_img, frame_node, nodes['qr'])

    frame_bbox = frame_node['absoluteBoundingBox']

    def _offset(key):
        bbox = nodes[key]['absoluteBoundingBox']
        x = (bbox['x'] - frame_bbox['x']) * CFG.SCALE_FACTOR
        y = (bbox['y'] - frame_bbox['y']) * CFG.SCALE_FACTOR + CFG.TEXT_OFFSET * CFG.SCALE_FACTOR
        return x, y

    title_x, title_y = _offset('nazvanie')
    draw.text((title_x, title_y), nazvanie, font=title_font, fill="#1F262D")

    price_text = f"€{price}"
    price_x, price_y = _offset('price')
    draw.text((price_x, price_y), price_text, font=price_font, fill="#838383")

    time_text = _nl_time_str()
    time_bbox = nodes['time']['absoluteBoundingBox']
    time_x = (time_bbox['x'] - frame_bbox['x']) * CFG.SCALE_FACTOR
    time_y = (time_bbox['y'] - frame_bbox['y']) * CFG.SCALE_FACTOR + CFG.TEXT_OFFSET * CFG.SCALE_FACTOR
    time_width = time_bbox['width'] * CFG.SCALE_FACTOR
    draw_x = time_x + (time_width - _text_width(time_font, time_text)) / 2
    draw.text((draw_x, time_y), time_text, font=time_font, fill="#000000")

    result = result.convert("RGB")
    out_path = os.path.join(temp_dir, f"MARKTPLAATS_{uuid.uuid4()}.png")
    result.save(out_path, format="PNG", optimize=True)

    return out_path, processed_photo_path, qr_path
