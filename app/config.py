# app/config.py
import os
from dotenv import load_dotenv
from pytz import timezone

load_dotenv()


class CFG:
    KEYS_PATH = os.getenv("APIKEYS")
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    FIGMA_PAT = os.getenv("FIGMA_PAT")
    TEMPLATE_FILE_KEY = os.getenv("TEMPLATE_FILE_KEY")
    # QR generation is handled by Rust backend
    QR_BACKEND_URL = os.getenv("QR_BACKEND_URL", os.getenv("BACKEND_URL", "http://127.0.0.1:8080"))
    BACKEND_API_KEY = os.getenv("BACKEND_API_KEY")
    LOGO_URL = os.getenv("LOGO_URL")

    # Legacy (external QR API) - kept for backward compatibility, not used by default
    QR_API_KEY = os.getenv("QR_API_KEY")
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    PHOTO_DIR = os.path.join(BASE_DIR, "assets", "foti")
    FONTS_DIR = os.path.join(BASE_DIR, "assets", "fonts")
    CONVERSION_FACTOR = 72 / 96
    SCALE_FACTOR = 2
    TEXT_OFFSET = 2.5
    CORNER_RADIUS = 15
    QR_SIZE = 2000
    QR_RESIZE = (1368, 1368)
    FIGMA_API_URL = "https://api.figma.com/v1"
    # Legacy external endpoint (QR TIGER) - not used by default
    QR_ENDPOINT = os.getenv("QR_ENDPOINT", "https://api.qrtiger.com/api/qr/static")
    TZ = timezone(os.getenv("TZ", "Europe/Amsterdam"))
    _ADMIN_IDS_RAW = os.getenv("ADMINS", "")

    # Wallapop Email конфигурация
    WALLAPOP_EMAIL_FIGMA_PAT = os.getenv("WALLAPOP_EMAIL_FIGMA_PAT", "figd_dG6hrm0ysjdpJDGcGio2T6uJw45GPTKJGzFPvd3z")
    WALLAPOP_EMAIL_FILE_KEY = os.getenv("WALLAPOP_EMAIL_FILE_KEY", "76mcmHxmZ5rhQSY02Kw5pn")
    WALLAPOP_EMAIL_SCALE = 1

    try:
        ADMIN_IDS = {int(x.strip()) for x in _ADMIN_IDS_RAW.split(",") if x.strip()}
    except ValueError:
        ADMIN_IDS = set()
    
    # Уведомления о генерациях через API
    NOTIFICATIONS_CHAT_ID = os.getenv("NOTIFICATIONS_CHAT_ID")  # ID чата для уведомлений
    NOTIFY_API_GENERATIONS = os.getenv("NOTIFY_API_GENERATIONS", "true").lower() == "true"