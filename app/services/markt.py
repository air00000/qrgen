# app/services/markt.py
"""
Markt service - generates marketing images for Markt marketplace
Supports 5 generation types:
1. QR (markt1)
2. Email request (markt2)
3. Phone request (markt3)
4. Email payment (markt4)
5. SMS payment (markt5)

Each type supports uk and nl language variants.
"""
import base64
import datetime
import io
import os
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

from PIL import Image, ImageDraw, ImageFont, ImageOps
from pytz import timezone

from app.config import CFG
from app.services.figma import find_node
from app.services.cache_wrapper import load_template_with_cache, get_frame_image
from app.services.pdf import (
    PDFGenerationError,
    FigmaNodeNotFoundError,
    QRGenerationError,
    draw_text_with_letter_spacing,
    create_rounded_mask,
)


class MarktGenerationError(Exception):
    """Custom exception for Markt generation errors"""
    pass


# ========== CONSTANTS ==========

# Frame mapping: method -> frame_index
MARKT_VARIANTS = {
    "qr": {"frame_index": 1, "label": "QR", "has_qr": True},
    "email_request": {"frame_index": 2, "label": "Email запрос", "has_qr": False},
    "phone_request": {"frame_index": 3, "label": "Телефон запрос", "has_qr": False},
    "email_payment": {"frame_index": 4, "label": "Email оплата", "has_qr": False},
    "sms_payment": {"frame_index": 5, "label": "SMS оплата", "has_qr": False},
}

# Supported languages
MARKT_LANGUAGES = ["uk", "nl"]

# Timezone mapping
LANG_TIMEZONES = {
    "uk": "Europe/London",
    "nl": "Europe/Amsterdam",
}

# QR logo URL
QR_LOGO_URL = "https://i.ibb.co/DfXf3X7x/Frame-40.png"

# Fixed fees
DELIVERY_FEE = Decimal("6.25")
SERVICE_FEE = Decimal("0.40")
PROTECTION_RATE = Decimal("0.05")  # 5%


# ========== FONT HELPERS ==========

def _get_font(font_name: str, size: int) -> ImageFont.FreeTypeFont:
    """Load font from assets directory"""
    path = os.path.join(CFG.FONTS_DIR, font_name)
    if os.path.exists(path):
        return ImageFont.truetype(path, size)
    return ImageFont.load_default()


# ========== PRICE FORMATTING ==========

def _format_price_eur(price: float) -> str:
    """Format price as € XX,XX"""
    amount = Decimal(str(price)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return f"€ {amount:.2f}".replace(".", ",")


def _calculate_protection_fee(price: float) -> Decimal:
    """Calculate 5% protection fee, rounded to 2 decimal places"""
    amount = Decimal(str(price))
    fee = (amount * PROTECTION_RATE).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return fee


def _calculate_total_price(price: float) -> Decimal:
    """
    Calculate total price:
    total = product_price + protection_fee (5%) + delivery (6.25) + service (0.40)
    """
    product = Decimal(str(price))
    protection = _calculate_protection_fee(price)
    total = product + protection + DELIVERY_FEE + SERVICE_FEE
    return total.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


# ========== TEXT HELPERS ==========

def _text_width_with_spacing(font: ImageFont.ImageFont, text: str, letter_spacing: int) -> float:
    """Calculate text width including letter spacing"""
    if not text:
        return 0
    widths = [font.getbbox(ch)[2] for ch in text]
    return sum(widths) + letter_spacing * (len(text) - 1)


def _truncate_title_markt(text: str, font: ImageFont.ImageFont, letter_spacing: int, max_width: int) -> str:
    """
    Truncate title to fit max_width (666px scaled).
    If text exceeds width, replace last characters with '...' to fit.
    """
    if _text_width_with_spacing(font, text, letter_spacing) <= max_width:
        return text
    
    ellipsis = "..."
    trimmed = text
    while trimmed and _text_width_with_spacing(font, trimmed + ellipsis, letter_spacing) > max_width:
        trimmed = trimmed[:-1]
    
    return trimmed + ellipsis if trimmed else ellipsis


def _draw_right_aligned_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.ImageFont,
    right_x: float,
    y: float,
    fill: str,
    letter_spacing: int = 0
):
    """Draw text aligned to the right edge"""
    total_width = _text_width_with_spacing(font, text, letter_spacing)
    start_x = right_x - total_width
    draw_text_with_letter_spacing(draw, text, font, start_x, y, fill, letter_spacing=letter_spacing)


def _draw_centered_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.ImageFont,
    center_x: float,
    y: float,
    fill: str,
    letter_spacing: int = 0
):
    """Draw text centered horizontally"""
    total_width = _text_width_with_spacing(font, text, letter_spacing)
    start_x = center_x - total_width / 2
    draw_text_with_letter_spacing(draw, text, font, start_x, y, fill, letter_spacing=letter_spacing)


# ========== IMAGE HELPERS ==========

def _rounded_rect_image(photo_b64: str, size: tuple[int, int], radius: int) -> Optional[Image.Image]:
    """
    Create rounded rectangle image from base64 or Data URI.
    Returns None if photo_b64 is empty or malformed.
    """
    from app.utils.helpers import parse_data_uri
    
    base64_data = parse_data_uri(photo_b64)
    if not base64_data:
        return None
    
    try:
        img = Image.open(io.BytesIO(base64.b64decode(base64_data))).convert("RGBA")
        # Crop to 1:1 aspect ratio
        min_dim = min(img.width, img.height)
        left = (img.width - min_dim) // 2
        top = (img.height - min_dim) // 2
        img = img.crop((left, top, left + min_dim, top + min_dim))
        # Resize to target size
        img = ImageOps.fit(img, size, Image.Resampling.LANCZOS)
        # Apply rounded corners
        mask = Image.new("L", size, 0)
        draw = ImageDraw.Draw(mask)
        draw.rounded_rectangle([(0, 0), size], radius=radius, fill=255)
        rounded = Image.new("RGBA", size, (255, 255, 255, 0))
        rounded.paste(img, (0, 0), mask)
        return rounded
    except Exception:
        return None


def _generate_markt_qr(url: str) -> Image.Image:
    """
    Generate QR code for Markt.
    Initial size: 600x600, then resized to 570x570
    """
    import requests
    
    headers = {"Authorization": f"Bearer {CFG.QR_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "qrCategory": "url",
        "text": url,
        "size": 600,
        "colorDark": "#000000",
        "backgroundColor": "#FFFFFF",
        "transparentBkg": False,
        "eye_outer": "eyeOuter2",
        "eye_inner": "eyeInner2",
        "qrData": "pattern4",
        "logo": QR_LOGO_URL,
    }
    
    try:
        response = requests.post(CFG.QR_ENDPOINT, json=payload, headers=headers, timeout=15)
        if response.status_code != 200:
            raise QRGenerationError(f"QR API error: {response.text}")
        
        data = response.json().get("data")
        if not data:
            raise QRGenerationError("No QR data in API response")
        
        qr_bytes = base64.b64decode(data)
        qr_img = Image.open(io.BytesIO(qr_bytes)).convert("RGBA")
        return qr_img
    except requests.RequestException as e:
        raise QRGenerationError(f"QR generation request failed: {e}")


# ========== MAIN GENERATION FUNCTION ==========

def create_markt_image(
    variant: str,
    lang: str,
    title: str,
    price: float,
    photo_b64: Optional[str] = None,
    url: Optional[str] = None,
) -> bytes:
    """
    Create Markt variant image.
    
    Args:
        variant: One of 'qr', 'email_request', 'phone_request', 'email_payment', 'sms_payment'
        lang: Language code 'uk' or 'nl'
        title: Product title
        price: Product price (float, e.g., 123.45)
        photo_b64: Product photo as base64 or Data URI (optional)
        url: URL for QR code (required for qr variant)
    
    Returns:
        PNG image as bytes
    """
    from app.utils.helpers import truncate_title
    
    # Validate inputs
    if variant not in MARKT_VARIANTS:
        raise MarktGenerationError(f"Unknown variant: {variant}. Must be one of {list(MARKT_VARIANTS.keys())}")
    
    if lang not in MARKT_LANGUAGES:
        raise MarktGenerationError(f"Unknown language: {lang}. Must be one of {MARKT_LANGUAGES}")
    
    if MARKT_VARIANTS[variant]["has_qr"] and not url:
        raise MarktGenerationError("URL is required for QR variant")
    
    # Get frame info
    frame_index = MARKT_VARIANTS[variant]["frame_index"]
    frame_name = f"markt{frame_index}_{lang}"
    service_name = f"markt_{variant}_{lang}"
    
    # Load template with cache
    template_json, frame_img_cached, frame_node, use_cache = load_template_with_cache(
        service_name, "Page 2", frame_name
    )
    
    if not frame_node:
        raise FigmaNodeNotFoundError(f"Frame {frame_name} not found")
    
    # Get frame image
    frame_img = get_frame_image(frame_node, frame_img_cached, use_cache)
    
    # Calculate dimensions
    width = int(frame_node["absoluteBoundingBox"]["width"] * CFG.SCALE_FACTOR)
    height = int(frame_node["absoluteBoundingBox"]["height"] * CFG.SCALE_FACTOR)
    frame_img = frame_img.resize((width, height), Image.Resampling.LANCZOS)
    
    # Create result image
    result = Image.new("RGBA", (width, height), (255, 255, 255, 0))
    result.paste(frame_img, (0, 0))
    draw = ImageDraw.Draw(result)
    
    # Helper to find nodes
    def _node(name: str):
        node = find_node(template_json, "Page 2", name)
        if not node:
            raise FigmaNodeNotFoundError(f"Node not found: {name}")
        return node
    
    def _node_optional(name: str):
        """Find node, return None if not found"""
        return find_node(template_json, "Page 2", name)
    
    def _node_box(node):
        """Get node bounding box relative to frame"""
        box = node["absoluteBoundingBox"]
        x = int((box["x"] - frame_node["absoluteBoundingBox"]["x"]) * CFG.SCALE_FACTOR)
        y = int((box["y"] - frame_node["absoluteBoundingBox"]["y"]) * CFG.SCALE_FACTOR)
        w = int(box["width"] * CFG.SCALE_FACTOR)
        h = int(box["height"] * CFG.SCALE_FACTOR)
        return x, y, w, h
    
    # ========== FONTS ==========
    # Title: SFProText-Regular, size 48, letter-spacing -3%
    title_font = _get_font("SFProText-Regular.ttf", int(48 * CFG.SCALE_FACTOR))
    title_spacing = int(48 * CFG.SCALE_FACTOR * -0.03)
    
    # Price: SFProText-Medium, size 42, letter-spacing 2%
    price_font = _get_font("SFPROTEXT-MEDIUM.TTF", int(42 * CFG.SCALE_FACTOR))
    price_spacing = int(42 * CFG.SCALE_FACTOR * 0.02)
    
    # Askprice/Protect/Total: SFProText-Regular, size 42, letter-spacing 1%
    detail_font = _get_font("SFProText-Regular.ttf", int(42 * CFG.SCALE_FACTOR))
    detail_spacing = int(42 * CFG.SCALE_FACTOR * 0.01)
    
    # Time: SFProText-Semibold, size 53, letter-spacing -2%
    time_font = _get_font("SFProText-Semibold.ttf", int(53 * CFG.SCALE_FACTOR))
    time_spacing = int(53 * CFG.SCALE_FACTOR * -0.02)
    
    # ========== DRAW TITLE ==========
    title_node = _node(f"nazv{frame_name}")
    title_x, title_y, title_w, _ = _node_box(title_node)
    
    # Max width 666px scaled
    max_title_width = int(666 * CFG.SCALE_FACTOR)
    truncated_title = _truncate_title_markt(title, title_font, title_spacing, max_title_width)
    
    # Draw title (left aligned, black)
    draw_text_with_letter_spacing(
        draw, truncated_title, title_font, title_x, title_y, "#000000", letter_spacing=title_spacing
    )
    
    # ========== DRAW PRICE ==========
    price_node = _node(f"price{frame_name}")
    price_x, price_y, price_w, _ = _node_box(price_node)
    
    # Format price: € XX,XX
    price_text = _format_price_eur(price)
    
    # Draw price (right aligned, black)
    _draw_right_aligned_text(
        draw, price_text, price_font, price_x + price_w, price_y, "#000000", letter_spacing=price_spacing
    )
    
    # ========== DRAW ASKPRICE (same as product price) ==========
    askprice_node = _node_optional(f"askprice{frame_name}")
    if askprice_node:
        ask_x, ask_y, ask_w, _ = _node_box(askprice_node)
        # Same format as product price
        _draw_right_aligned_text(
            draw, price_text, detail_font, ask_x + ask_w, ask_y, "#20394C", letter_spacing=detail_spacing
        )
    
    # ========== DRAW PROTECTION FEE (5% of product price) ==========
    protect_node = _node_optional(f"protect{frame_name}")
    if protect_node:
        prot_x, prot_y, prot_w, _ = _node_box(protect_node)
        protection_fee = _calculate_protection_fee(price)
        protect_text = _format_price_eur(float(protection_fee))
        _draw_right_aligned_text(
            draw, protect_text, detail_font, prot_x + prot_w, prot_y, "#20394C", letter_spacing=detail_spacing
        )
    
    # ========== DRAW TOTAL PRICE ==========
    total_node = _node_optional(f"totalprice{frame_name}")
    if total_node:
        total_x, total_y, total_w, _ = _node_box(total_node)
        total_price = _calculate_total_price(price)
        total_text = _format_price_eur(float(total_price))
        _draw_right_aligned_text(
            draw, total_text, detail_font, total_x + total_w, total_y, "#20394C", letter_spacing=detail_spacing
        )
    
    # ========== DRAW PRODUCT IMAGE ==========
    pic_node = _node_optional(f"pic{frame_name}")
    if pic_node and photo_b64:
        pic_x, pic_y, pic_w, pic_h = _node_box(pic_node)
        # Corner radius 11px scaled
        pic_radius = int(11 * CFG.SCALE_FACTOR)
        photo_img = _rounded_rect_image(photo_b64, (pic_w, pic_h), pic_radius)
        if photo_img:
            result.paste(photo_img, (pic_x, pic_y), photo_img)
    
    # ========== DRAW TIME ==========
    time_node = _node_optional(f"time{frame_name}")
    if time_node:
        time_x, time_y, time_w, _ = _node_box(time_node)
        # Get current time in appropriate timezone
        tz = timezone(LANG_TIMEZONES.get(lang, "Europe/Amsterdam"))
        now = datetime.datetime.now(tz)
        time_text = f"{now.hour:02d}:{now.minute:02d}"
        
        # Draw time (centered, white)
        _draw_centered_text(
            draw, time_text, time_font, time_x + time_w / 2, time_y, "#FFFFFF", letter_spacing=time_spacing
        )
    
    # ========== DRAW QR CODE (only for qr variant) ==========
    if MARKT_VARIANTS[variant]["has_qr"] and url:
        qr_node = _node_optional(f"qr{frame_name}")
        if qr_node:
            qr_x, qr_y, qr_w, qr_h = _node_box(qr_node)
            
            # Generate QR code
            qr_img = _generate_markt_qr(url)
            
            # Resize to 570x570 (scaled)
            target_size = int(570 * CFG.SCALE_FACTOR)
            qr_img = qr_img.resize((target_size, target_size), Image.Resampling.LANCZOS)
            
            # Apply rounded corners (16px scaled)
            qr_radius = int(16 * CFG.SCALE_FACTOR)
            mask = create_rounded_mask((target_size, target_size), qr_radius)
            qr_img.putalpha(mask)
            
            # Center QR in the designated area
            paste_x = qr_x + (qr_w - target_size) // 2
            paste_y = qr_y + (qr_h - target_size) // 2
            result.paste(qr_img, (paste_x, paste_y), qr_img)
    
    # ========== OUTPUT ==========
    output = io.BytesIO()
    result.save(output, format="PNG")
    return output.getvalue()


# ========== PUBLIC API FUNCTIONS ==========

def create_markt_qr(lang: str, title: str, price: float, photo: str = None, url: str = "") -> bytes:
    """Generate Markt QR variant"""
    return create_markt_image("qr", lang, title, price, photo_b64=photo, url=url)


def create_markt_email_request(lang: str, title: str, price: float, photo: str = None) -> bytes:
    """Generate Markt Email Request variant"""
    return create_markt_image("email_request", lang, title, price, photo_b64=photo)


def create_markt_phone_request(lang: str, title: str, price: float, photo: str = None) -> bytes:
    """Generate Markt Phone Request variant"""
    return create_markt_image("phone_request", lang, title, price, photo_b64=photo)


def create_markt_email_payment(lang: str, title: str, price: float, photo: str = None) -> bytes:
    """Generate Markt Email Payment variant"""
    return create_markt_image("email_payment", lang, title, price, photo_b64=photo)


def create_markt_sms_payment(lang: str, title: str, price: float, photo: str = None) -> bytes:
    """Generate Markt SMS Payment variant"""
    return create_markt_image("sms_payment", lang, title, price, photo_b64=photo)
