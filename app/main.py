# app/main.py

import logging
import multiprocessing
import uvicorn

from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
)

from app.config import CFG
from app.handlers.menu import start, menu_cb
from app.handlers.qr import qr_conv, qr_menu_cb, qr_back_cb   # <--- добавлено
from app.handlers.admin_api_keys import api_keys_conv          # <--- новый обработчик


def start_api():
    """Run FastAPI (app.api:app) with uvicorn."""
    uvicorn.run("app.api:app", host="0.0.0.0", port=8000, reload=False, log_level="info")


def start_bot():
    """Start Telegram bot with required handlers."""
    logging.basicConfig(level=logging.INFO)
    app = Application.builder().token(CFG.TELEGRAM_BOT_TOKEN).build()

    # === Главное меню ===
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(menu_cb, pattern=r"^MENU$"))

    # === QR генератор ===
    app.add_handler(qr_conv)  # ConversationHandler
    app.add_handler(CallbackQueryHandler(qr_menu_cb, pattern=r"^QR:MENU$"))
    app.add_handler(CallbackQueryHandler(qr_back_cb, pattern=r"^QR:BACK$"))

    # === Админ-панель API ключей ===
    app.add_handler(api_keys_conv)

    # === Запуск ===
    app.run_polling()


if __name__ == "__main__":
    p1 = multiprocessing.Process(target=start_api)
    p2 = multiprocessing.Process(target=start_bot)

    p1.start()
    p2.start()

    p1.join()
    p2.join()
