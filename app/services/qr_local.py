# app/services/qr_local.py
from __future__ import annotations

import os, uuid
from typing import Tuple
from PIL import Image, ImageDraw
import qrcode

def _rounded_mask(size: Tuple[int,int], radius: int):
    m = Image.new("L", size, 0)
    d = ImageDraw.Draw(m)
    d.rounded_rectangle([(0,0), size], radius=radius, fill=255)
    return m

def generate_qr(url: str, temp_dir: str,
                box_size: int = 12, border: int = 2,
                dark: str = "#4B6179", light: str = "#FFFFFF",
                resize: Tuple[int,int] | None = None,
                corner_radius: int = 24) -> str:
    """
    Генерирует QR локально, возвращает путь к PNG с прозрачными скруглёнными углами.
    """
    os.makedirs(temp_dir, exist_ok=True)
    path = os.path.join(temp_dir, f"qr_{uuid.uuid4()}.png")

    qr = qrcode.QRCode(
        version=None,  # авто-подбор
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=box_size,
        border=border,
    )
    qr.add_data(url)
    qr.make(fit=True)

    img = qr.make_image(fill_color=dark, back_color=light).convert("RGBA")
    if resize:
        img = img.resize(resize, Image.Resampling.BICUBIC)

    # скруглённые углы
    mask = _rounded_mask(img.size, corner_radius)
    img.putalpha(mask)
    img.save(path, "PNG")
    return path
