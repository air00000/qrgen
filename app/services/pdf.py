import os, uuid, datetime
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.colors import HexColor
from PIL import Image, ImageDraw
from pytz import timezone

from app.config import CFG
from app.services.figma import get_template_json, find_node, export_frame_as_png
from app.services.qrtiger import generate_qr

pdfmetrics.registerFont(TTFont('Inter-SemiBold', os.path.join(CFG.FONTS_DIR, 'Inter_18pt-SemiBold.ttf')))
pdfmetrics.registerFont(TTFont('Inter-Medium',   os.path.join(CFG.FONTS_DIR, 'Inter_18pt-Medium.ttf')))
pdfmetrics.registerFont(TTFont('SFProText-Semibold', os.path.join(CFG.FONTS_DIR, 'SFProText-Semibold.ttf')))

def _rounded_mask(size, radius):
    m = Image.new("L", size, 0)
    d = ImageDraw.Draw(m)
    d.rounded_rectangle([(0,0), size], radius=radius, fill=255)
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

def create_pdf(nazvanie, price, photo_path, url):
    os.makedirs(CFG.TEMP_DIR, exist_ok=True)
    template_json = get_template_json()

    frame_name = 'Marktplaats'
    nazvanie_layer = '1NAZVANIE'
    price_layer = '1PRICE'
    time_layer = '1TIME'
    foto_layer = '1FOTO'
    qr_layer = '1QR'

    frame_node = find_node(template_json, 'Page 2', frame_name)
    nazvanie_node = find_node(template_json, 'Page 2', nazvanie_layer)
    price_node = find_node(template_json, 'Page 2', price_layer)
    time_node = find_node(template_json, 'Page 2', time_layer)
    foto_node = find_node(template_json, 'Page 2', foto_layer)
    qr_node = find_node(template_json, 'Page 2', qr_layer)

    for n, nm in [(frame_node, frame_name), (nazvanie_node, nazvanie_layer),
                  (price_node, price_layer), (time_node, time_layer),
                  (foto_node, foto_layer), (qr_node, qr_layer)]:
        if not n:
            raise RuntimeError(f"Узел не найден: {nm}")

    template_png = export_frame_as_png(CFG.TEMPLATE_FILE_KEY, frame_node['id'])
    template_path = os.path.join(CFG.TEMP_DIR, 'template.png')
    with open(template_path, "wb") as f:
        f.write(template_png)

    time_text = _nl_time_str()
    formatted_price = f"€{price}"

    frame_w = frame_node['absoluteBoundingBox']['width'] * CFG.SCALE_FACTOR
    frame_h = frame_node['absoluteBoundingBox']['height'] * CFG.SCALE_FACTOR
    page_w = frame_w * CFG.CONVERSION_FACTOR
    page_h = frame_h * CFG.CONVERSION_FACTOR

    pdf_path = os.path.join(CFG.TEMP_DIR, f"MARKTPLAATS_{uuid.uuid4()}.pdf")
    c = canvas.Canvas(pdf_path, pagesize=(page_w, page_h))

    c.drawImage(template_path, 0, 0, width=page_w, height=page_h)

    processed_photo_path = None
    if photo_path and foto_node:
        processed_photo_path = _process_photo(photo_path, CFG.TEMP_DIR)
        fx = (foto_node['absoluteBoundingBox']['x'] - frame_node['absoluteBoundingBox']['x']) * CFG.SCALE_FACTOR * CFG.CONVERSION_FACTOR
        fy = page_h - ((foto_node['absoluteBoundingBox']['y'] - frame_node['absoluteBoundingBox']['y']) + foto_node['absoluteBoundingBox']['height']) * CFG.SCALE_FACTOR * CFG.CONVERSION_FACTOR
        fw = foto_node['absoluteBoundingBox']['width'] * CFG.SCALE_FACTOR * CFG.CONVERSION_FACTOR
        fh = foto_node['absoluteBoundingBox']['height'] * CFG.SCALE_FACTOR * CFG.CONVERSION_FACTOR
        c.drawImage(processed_photo_path, fx, fy, width=fw, height=fh, preserveAspectRatio=True, mask='auto')

    qr_path = generate_qr(url, CFG.TEMP_DIR)
    qx = (qr_node['absoluteBoundingBox']['x'] - frame_node['absoluteBoundingBox']['x']) * CFG.SCALE_FACTOR * CFG.CONVERSION_FACTOR
    qy = page_h - ((qr_node['absoluteBoundingBox']['y'] - frame_node['absoluteBoundingBox']['y']) + qr_node['absoluteBoundingBox']['height']) * CFG.SCALE_FACTOR * CFG.CONVERSION_FACTOR
    qw = qr_node['absoluteBoundingBox']['width'] * CFG.SCALE_FACTOR * CFG.CONVERSION_FACTOR
    qh = qr_node['absoluteBoundingBox']['height'] * CFG.SCALE_FACTOR * CFG.CONVERSION_FACTOR
    c.drawImage(qr_path, qx, qy, width=qw, height=qh, preserveAspectRatio=True, mask='auto')

    nx = (nazvanie_node['absoluteBoundingBox']['x'] - frame_node['absoluteBoundingBox']['x']) * CFG.SCALE_FACTOR * CFG.CONVERSION_FACTOR
    ny = page_h - (nazvanie_node['absoluteBoundingBox']['y'] - frame_node['absoluteBoundingBox']['y']) * CFG.SCALE_FACTOR * CFG.CONVERSION_FACTOR - 96 * CFG.SCALE_FACTOR * CFG.CONVERSION_FACTOR + (CFG.TEXT_OFFSET * CFG.SCALE_FACTOR * CFG.CONVERSION_FACTOR)
    c.setFont('Inter-SemiBold', 96 * CFG.SCALE_FACTOR * CFG.CONVERSION_FACTOR)
    c.setFillColor(HexColor('#1F262D'))
    c.drawString(nx, ny, nazvanie)

    px = (price_node['absoluteBoundingBox']['x'] - frame_node['absoluteBoundingBox']['x']) * CFG.SCALE_FACTOR * CFG.CONVERSION_FACTOR
    py = page_h - (price_node['absoluteBoundingBox']['y'] - frame_node['absoluteBoundingBox']['y']) * CFG.SCALE_FACTOR * CFG.CONVERSION_FACTOR - 96 * CFG.SCALE_FACTOR * CFG.CONVERSION_FACTOR + (CFG.TEXT_OFFSET * CFG.SCALE_FACTOR * CFG.CONVERSION_FACTOR)
    c.setFont('Inter-Medium', 96 * CFG.SCALE_FACTOR * CFG.CONVERSION_FACTOR)
    c.setFillColor(HexColor('#838383'))
    c.drawString(px, py, formatted_price)

    tb = time_node['absoluteBoundingBox']
    tw = tb['width'] * CFG.SCALE_FACTOR * CFG.CONVERSION_FACTOR
    tx = (tb['x'] - frame_node['absoluteBoundingBox']['x']) * CFG.SCALE_FACTOR * CFG.CONVERSION_FACTOR + (tw - c.stringWidth(time_text, 'SFProText-Semibold', 108 * CFG.SCALE_FACTOR * CFG.CONVERSION_FACTOR)) / 2
    ty = page_h - (tb['y'] - frame_node['absoluteBoundingBox']['y']) * CFG.SCALE_FACTOR * CFG.CONVERSION_FACTOR - 108 * CFG.SCALE_FACTOR * CFG.CONVERSION_FACTOR + (CFG.TEXT_OFFSET * CFG.SCALE_FACTOR * CFG.CONVERSION_FACTOR)
    c.setFont('SFProText-Semibold', 108 * CFG.SCALE_FACTOR * CFG.CONVERSION_FACTOR)
    c.setFillColor(HexColor('#000000'))
    c.drawString(tx, ty, time_text)

    c.showPage()
    c.save()

    try:
        os.remove(template_path)
    except Exception:
        pass

    return pdf_path, processed_photo_path, qr_path
