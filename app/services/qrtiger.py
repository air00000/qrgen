# app/services/qrtiger.py
import os
from io import BytesIO
from typing import Optional, Tuple
import requests
from PIL import Image, ImageDraw
import qrcode
from qrcode.constants import ERROR_CORRECT_H

from app.config import CFG

def _rounded_mask(size: Tuple[int, int], radius: int) -> Image.Image:
    w, h = size
    m = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(m)
    d.rounded_rectangle((0, 0, w, h), radius=radius, fill=255)
    return m

def _download_logo(url: str) -> Optional[Image.Image]:
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        img = Image.open(BytesIO(r.content)).convert("RGBA")
        return img
    except Exception:
        return None

def generate_qr(
    url: str,
    temp_dir: str,
    *,
    target_size: Tuple[int, int] = None,
    color_dark: str = "#4B6179",
    color_bg: str = "#FFFFFF",
    corner_radius: int = None,
    logo_url: Optional[str] = None,
    logo_scale: float = 0.22,  # доля стороны под логотип
) -> str:
    if target_size is None:
        target_size = CFG.QR_RESIZE
    if corner_radius is None:
        corner_radius = CFG.CORNER_RADIUS * CFG.SCALE_FACTOR
    if logo_url is None:
        logo_url = CFG.LOGO_URL

    # 1) QR с высокой коррекцией, затем ресайз
    qr = qrcode.QRCode(version=None, error_correction=ERROR_CORRECT_H, box_size=10, border=2)
    qr.add_data(url); qr.make(fit=True)
    img = qr.make_image(fill_color=color_dark, back_color=color_bg).convert("RGBA")
    img = img.resize(target_size, Image.Resampling.BICUBIC)

    # 2) опциональный логотип по центру
    if logo_url:
        logo = _download_logo(logo_url)
        if logo:
            lw = int(target_size[0] * logo_scale)
            lh = int(target_size[1] * logo_scale)
            logo = logo.resize((lw, lh), Image.Resampling.LANCZOS)
            x = (target_size[0] - lw) // 2
            y = (target_size[1] - lh) // 2
            img.alpha_composite(logo, (x, y))

    # 3) скругление углов всей картинки
    img.putalpha(_rounded_mask(target_size, corner_radius))

    # 4) сохранить во временный PNG
    os.makedirs(temp_dir, exist_ok=True)
    out_path = os.path.join(temp_dir, "qr_code.png")
    img.save(out_path, "PNG")
    return out_path
