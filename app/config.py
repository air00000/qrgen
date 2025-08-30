import os
from dotenv import load_dotenv
from pytz import timezone

load_dotenv()

class CFG:
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    FIGMA_PAT = os.getenv("FIGMA_PAT")
    TEMPLATE_FILE_KEY = os.getenv("TEMPLATE_FILE_KEY")
    QR_API_KEY = os.getenv("QR_API_KEY")
    LOGO_URL = os.getenv("LOGO_URL")
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    PHOTO_DIR = os.path.join(BASE_DIR, "assets", "foti")
    TEMP_DIR = os.path.join(PHOTO_DIR, "temp")
    FONTS_DIR = os.path.join(BASE_DIR, "assets", "fonts")
    CONVERSION_FACTOR = 72 / 96
    SCALE_FACTOR = 2
    TEXT_OFFSET = 2.5
    CORNER_RADIUS = 35
    QR_SIZE = 2000
    QR_RESIZE = (1368, 1368)
    FIGMA_API_URL = "https://api.figma.com/v1"
    QR_ENDPOINT = "https://api.qrtiger.com/api/qr/static"
    TZ = timezone(os.getenv("TZ", "Europe/Amsterdam"))
