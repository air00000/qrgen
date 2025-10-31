# app/services/qr_local.py
import os
from typing import Optional, Tuple
from PIL import Image, ImageDraw
import qrcode
from qrcode.constants import ERROR_CORRECT_H

# Стили: круглые модули; глаза подключим, если доступны в версии пакета
try:
    from qrcode.image.styledpil import StyledPilImage
    from qrcode.image.styles.moduledrawers import RoundedModuleDrawer
    from qrcode.image.styles.colormasks import SolidFillColorMask
    try:
        from qrcode.image.styles.eyedrawers import RoundedEyeDrawer
        _HAS_EYES = True
    except Exception:
        RoundedEyeDrawer = None
        _HAS_EYES = False
    _HAS_STYLE = True
except Exception:
    from qrcode.image.pil import PilImage
    _HAS_STYLE = False
    _HAS_EYES = False

from app.config import CFG


def _hex_to_rgb(hex_color: str) -> Tuple[int, int, int]:
    h = hex_color.lstrip("#")
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))


def _rounded_mask(size: Tuple[int, int], radius: int) -> Image.Image:
    w, h = size
    m = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(m)
    d.rounded_rectangle((0, 0, w, h), radius=radius, fill=255)
    return m


def _load_logo(logo_path: Optional[str]) -> Optional[Image.Image]:
    if logo_path and os.path.exists(logo_path):
        try:
            return Image.open(logo_path).convert("RGBA")
        except Exception:
            return None
    return None


def generate_qr(
    url: str,
    temp_dir: str,
    *,
    target_size: Tuple[int, int] = None,
    color_dark: str = "#4B6179",
    color_bg: str = "#FFFFFF",
    corner_radius: Optional[int] = None,
    logo_path: Optional[str] = None,      # локальный путь к логотипу (опц.)
    logo_scale: float = 0.22,             # доля стороны QR под логотип
    center_badge_bg: Optional[str] = None,  # например "#F0A05B" — круг под логотипом
    center_badge_padding: float = 1.12       # круг немного больше логотипа
) -> str:
    """
    Полностью локальная генерация QR:
      - скруглённые модули и (если поддерживается) скруглённые «глаза»
      - сверхчётко: supersampling ×3 + LANCZOS до нужного размера
      - опциональный круглый бейдж + логотип по центру
      - скруглённые углы всей картинки
    Возвращает путь к PNG.
    """
    if target_size is None:
        target_size = CFG.QR_RESIZE
    if corner_radius is None:
        corner_radius = int(CFG.CORNER_RADIUS * CFG.SCALE_FACTOR)

    tw, th = target_size
    fg = _hex_to_rgb(color_dark)
    bg = _hex_to_rgb(color_bg)

    # 1) Базовый QR (делаем после add_data, чтобы узнать modules_count)
    border = 2
    qr = qrcode.QRCode(
        version=None,
        error_correction=ERROR_CORRECT_H,
        box_size=10,  # временно, пересчитаем
        border=border,
    )
    qr.add_data(url)
    qr.make(fit=True)

    # 2) Рендер с супермасштабом → меньше артефактов при сжатии
    SS = 5  # коэффициент oversample (3–4 обычно достаточно)
    # подберём box_size так, чтобы итог ~кратно рос под SS
    modules = qr.modules_count
    box_size = max(8, min(24, (min(tw, th) * SS) // (modules + 2 * border)))
    qr.box_size = box_size

    if _HAS_STYLE:
        kwargs = dict(
            image_factory=StyledPilImage,
            module_drawer=RoundedModuleDrawer(),
            color_mask=SolidFillColorMask(front_color=fg, back_color=bg),
        )
        if _HAS_EYES:
            kwargs["eye_drawer"] = RoundedEyeDrawer()
        img: Image.Image = qr.make_image(**kwargs).convert("RGBA")
    else:
        # фолбэк: обычные квадраты, но тоже с oversample → будет чётче
        img: Image.Image = qr.make_image(
            image_factory=PilImage,
            fill_color=fg,
            back_color=bg,
        ).convert("RGBA")

    # 3) Приводим к целевому размеру (после supersampling) — LANCZOS даёт лучший результат
    img = img.resize((tw, th), Image.Resampling.LANCZOS)

    # 4) Центральный круг + логотип (локальные файлы)
    logo = _load_logo(logo_path)
    if logo:
        lw = int(tw * logo_scale)
        lh = int(th * logo_scale)
        logo = logo.resize((lw, lh), Image.Resampling.LANCZOS)

        if center_badge_bg:
            pad = int(max(lw, lh) * center_badge_padding)
            badge = Image.new("RGBA", (pad, pad), (0, 0, 0, 0))
            bd = ImageDraw.Draw(badge)
            bd.ellipse((0, 0, pad - 1, pad - 1), fill=_hex_to_rgb(center_badge_bg) + (255,))
            bx = (tw - pad) // 2
            by = (th - pad) // 2
            img.alpha_composite(badge, (bx, by))

        x = (tw - lw) // 2
        y = (th - lh) // 2
        img.alpha_composite(logo, (x, y))

    # 5) Скругляем углы всей картинки
    img.putalpha(_rounded_mask((tw, th), corner_radius))

    # 6) Сохраняем
    os.makedirs(temp_dir, exist_ok=True)
    out_path = os.path.join(temp_dir, "qr_code.png")
    img.save(out_path, "PNG")
    return out_path
