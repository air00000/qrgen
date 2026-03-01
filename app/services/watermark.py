import io
from PIL import Image

from app.config import CFG


def _build_logo_overlay(base_w: int, base_h: int) -> Image.Image:
    logo = Image.open(CFG.WATERMARK_IMAGE_PATH).convert("RGBA")

    # Keep watermark visible but not too aggressive: ~35% of shorter side.
    target_size = max(120, int(min(base_w, base_h) * 0.35))
    resample = getattr(getattr(Image, "Resampling", Image), "LANCZOS")
    logo = logo.resize((target_size, target_size), resample)

    # Global alpha multiplier (requested: 0.2 by default).
    alpha_mul = max(0.0, min(1.0, CFG.WATERMARK_IMAGE_OPACITY))
    if alpha_mul < 1.0:
        r, g, b, a = logo.split()
        a = a.point(lambda p: int(p * alpha_mul))
        logo = Image.merge("RGBA", (r, g, b, a))

    return logo


def apply_enclave_watermark(image_bytes: bytes) -> bytes:
    if not CFG.WATERMARK_ENABLED:
        return image_bytes

    with Image.open(io.BytesIO(image_bytes)).convert("RGBA") as base:
        w, h = base.size
        logo = _build_logo_overlay(w, h)

        x = (w - logo.width) // 2
        y = (h - logo.height) // 2

        out = base.copy()
        out.alpha_composite(logo, dest=(x, y))

        bio = io.BytesIO()
        out.convert("RGB").save(bio, format="PNG")
        return bio.getvalue()
