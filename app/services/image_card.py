# app/services/image_card.py
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
import requests, os
from services.qrtiger import generate_qr
from config import CFG

def _download(url) -> Image.Image:
    r = requests.get(url, timeout=15)
    r.raise_for_status()
    img = Image.open(BytesIO(r.content)).convert("RGBA")
    return img

def _rounded(img: Image.Image, radius: int) -> Image.Image:
    w, h = img.size
    mask = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(mask)
    d.rounded_rectangle((0,0,w,h), radius=radius, fill=255)
    img.putalpha(mask)
    return img

def render_card_png(title: str, price: str, photo_url: str|None, landing_url: str) -> bytes:
    # Канва
    W, H = 1600, 900
    bg = Image.new("RGBA", (W, H), (255,255,255,255))
    draw = ImageDraw.Draw(bg)

    # Фото (слева)
    if photo_url:
        img = _download(photo_url)
        # Кроп под квадрат
        sz = min(img.width, img.height)
        l = (img.width - sz)//2; t = (img.height - sz)//2
        img = img.crop((l,t,l+sz,t+sz)).resize((720,720))
        img = _rounded(img, radius=48)
        bg.alpha_composite(img, (60, 90))

    # QR (справа)
    qr_path = generate_qr(landing_url, CFG.TEMP_DIR)
    qr = Image.open(qr_path).convert("RGBA").resize((540,540))
    bg.alpha_composite(qr, (980, 330))

    # Тексты
    title_font = ImageFont.truetype(os.path.join(CFG.FONTS_DIR, "Inter_18pt-SemiBold.ttf"), 60)
    price_font = ImageFont.truetype(os.path.join(CFG.FONTS_DIR, "Inter_18pt-Medium.ttf"), 56)
    draw.text((900, 120), title, fill=(31,38,45,255), font=title_font)
    draw.text((900, 210), price, fill=(131,131,131,255), font=price_font)

    out = BytesIO()
    bg.save(out, "PNG")
    return out.getvalue()
