# app/main.py

import logging
import multiprocessing
import uvicorn

from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
)

from app.config import CFG
from app.handlers.menu import start, menu_cb
from app.handlers.qr import qr_conv, qr_back_cb, qr_menu_cb
from app.handlers.admin_api_keys import api_keys_conv

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def start_api():
    uvicorn.run("app.api:app", host="0.0.0.0", port=8000)


def start_bot():
    app = Application.builder().token(CFG.TELEGRAM_BOT_TOKEN).build()
    app.job_queue.scheduler.configure(timezone=CFG.TZ)

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(menu_cb, pattern=r"^MENU$"))

    app.add_handler(qr_conv)
    app.add_handler(CallbackQueryHandler(qr_menu_cb, pattern=r"^QR:MENU$"))
    app.add_handler(CallbackQueryHandler(qr_back_cb, pattern=r"^QR:BACK$"))

    app.add_handler(api_keys_conv)

    app.run_polling()

if __name__ == "__main__":
    p1 = multiprocessing.Process(target=start_api)
    p2 = multiprocessing.Process(target=start_bot)

    p1.start()
    p2.start()

    p1.join()
    p2.join()