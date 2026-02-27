import io
from PIL import Image, ImageDraw

from app.config import CFG


def apply_enclave_watermark(image_bytes: bytes) -> bytes:
    if not CFG.WATERMARK_ENABLED:
        return image_bytes

    with Image.open(io.BytesIO(image_bytes)).convert("RGBA") as base:
        overlay = Image.new("RGBA", base.size, (255, 255, 255, 0))
        draw = ImageDraw.Draw(overlay)

        w, h = base.size
        pad = max(12, int(min(w, h) * 0.02))
        box_w = int(w * 0.22)
        box_h = int(h * 0.07)
        x0 = w - box_w - pad
        y0 = h - box_h - pad
        x1 = w - pad
        y1 = h - pad

        opacity = max(0, min(255, CFG.WATERMARK_OPACITY))
        draw.rounded_rectangle((x0, y0, x1, y1), radius=12, fill=(0, 0, 0, int(opacity * 0.6)))

        # Programmatic Enclave mark (hexagon + E), no external assets
        cx = x0 + box_h // 2
        cy = y0 + box_h // 2
        r = box_h // 3
        hex_pts = [
            (cx - r, cy), (cx - r // 2, cy - r), (cx + r // 2, cy - r),
            (cx + r, cy), (cx + r // 2, cy + r), (cx - r // 2, cy + r),
        ]
        draw.polygon(hex_pts, outline=(0, 255, 180, opacity), fill=(0, 255, 180, int(opacity * 0.22)))
        draw.line((cx - r // 2, cy - r // 2, cx + r // 3, cy - r // 2), fill=(255, 255, 255, opacity), width=2)
        draw.line((cx - r // 2, cy, cx + r // 4, cy), fill=(255, 255, 255, opacity), width=2)
        draw.line((cx - r // 2, cy + r // 2, cx + r // 3, cy + r // 2), fill=(255, 255, 255, opacity), width=2)

        text_x = cx + r + 12
        text_y = y0 + box_h // 3
        draw.text((text_x, text_y), CFG.WATERMARK_TEXT, fill=(255, 255, 255, opacity))

        out = Image.alpha_composite(base, overlay).convert("RGB")
        bio = io.BytesIO()
        out.save(bio, format="PNG")
        return bio.getvalue()
