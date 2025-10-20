import base64
import os
import uuid

import requests
from PIL import Image, ImageDraw

from app.config import CFG


def _rounded_mask(size, radius):
    m = Image.new("L", size, 0)
    d = ImageDraw.Draw(m)
    d.rounded_rectangle([(0, 0), size], radius=radius, fill=255)
    return m


def generate_qr(
    url: str,
    temp_dir: str,
    *,
    color_dark: str | None = None,
    background_color: str | None = None,
    pattern: str | None = None,
    eye_outer: str | None = None,
    eye_inner: str | None = None,
    logo_url: str | None = None,
):
    os.makedirs(temp_dir, exist_ok=True)
    path = os.path.join(temp_dir, f"qr_{uuid.uuid4()}.png")
    headers = {"Authorization": f"Bearer {CFG.QR_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "qrCategory": "url",
        "text": url,
        "size": CFG.QR_SIZE,
        "colorDark": color_dark or CFG.QR_COLOR_DARK,
        "backgroundColor": background_color or CFG.QR_BACKGROUND_COLOR,
        "transparentBkg": False,
        "eye_outer": eye_outer or CFG.QR_EYE_OUTER,
        "eye_inner": eye_inner or CFG.QR_EYE_INNER,
        "qrData": pattern or CFG.QR_PATTERN,
        "logo": CFG.LOGO_URL if logo_url is None else logo_url,
    }
    resp = requests.post(CFG.QR_ENDPOINT, json=payload, headers=headers)
    resp.raise_for_status()
    data = resp.json().get("data")
    if not data:
        raise RuntimeError("Пустой ответ от QR API")
    with open(path, "wb") as f:
        f.write(base64.b64decode(data))

    # resize + rounded corners
    img = Image.open(path).convert("RGBA").resize(CFG.QR_RESIZE, Image.Resampling.BICUBIC)
    mask = _rounded_mask(CFG.QR_RESIZE, CFG.CORNER_RADIUS * CFG.SCALE_FACTOR)
    img.putalpha(mask)
    img.save(path, "PNG")
    return path
