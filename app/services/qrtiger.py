import os
import uuid
import requests

from app.config import CFG


class QRGenerationError(RuntimeError):
    pass


def generate_qr(url: str, temp_dir: str) -> str:
    """Generate QR via Rust backend and save as PNG.

    Backend endpoint: POST {QR_BACKEND_URL}/qr -> image/png
    """
    os.makedirs(temp_dir, exist_ok=True)
    path = os.path.join(temp_dir, f"qr_{uuid.uuid4()}.png")

    payload = {
        "text": url,
        "size": CFG.QR_RESIZE[0],
        "margin": 2,
        "colorDark": "#4B6179",
        "colorLight": "#FFFFFF",
        "logoUrl": CFG.LOGO_URL,
        "cornerRadius": int(CFG.CORNER_RADIUS * CFG.SCALE_FACTOR),
    }

    try:
        resp = requests.post(
            f"{CFG.QR_BACKEND_URL.rstrip('/')}/qr",
            json=payload,
            timeout=20,
        )
    except Exception as e:
        raise QRGenerationError(f"QR backend request failed: {e}")

    if resp.status_code != 200:
        raise QRGenerationError(
            f"QR backend error {resp.status_code}: {resp.text[:500]}"
        )

    # Save PNG bytes
    with open(path, "wb") as f:
        f.write(resp.content)

    return path
