import base64, requests
from PIL import Image, ImageDraw
import os, uuid
from app.config import CFG

def _rounded_mask(size, radius):
    m = Image.new("L", size, 0)
    d = ImageDraw.Draw(m)
    d.rounded_rectangle([(0,0), size], radius=radius, fill=255)
    return m

def generate_qr(url, temp_dir):
    path = os.path.join(temp_dir, f"qr_{uuid.uuid4()}.png")
    headers = {"Authorization": f"Bearer {CFG.QR_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "qrCategory": "url",
        "text": url,
        "size": CFG.QR_SIZE,
        "colorDark": "#4B6179",
        "backgroundColor": "#FFFFFF",
        "transparentBkg": False,
        "eye_outer": "eyeOuter2",
        "eye_inner": "eyeInner2",
        "qrData": "pattern4",
        "logo": CFG.LOGO_URL,
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
