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
from app.handlers.admin_api_keys import (
    admin_api_menu,
    handle_api_callbacks,
    handle_key_name_input,
)

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


# Запуск FastAPI (webapi.py)
def start_api():
    uvicorn.run("app.webapi:app", host="0.0.0.0", port=8000)


# Запуск Telegram-бота
def start_bot():
    app = Application.builder().token(CFG.TELEGRAM_BOT_TOKEN).build()
    app.job_queue.scheduler.configure(timezone=CFG.TZ)

    # Основное меню
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(menu_cb, pattern=r"^MENU$"))

    # QR генератор
    app.add_handler(qr_conv)
    app.add_handler(CallbackQueryHandler(qr_menu_cb, pattern=r"^QR:MENU$"))
    app.add_handler(CallbackQueryHandler(qr_back_cb, pattern=r"^QR:BACK$"))

    # API-ключи для админа
    app.add_handler(CallbackQueryHandler(admin_api_menu, pattern=r"^KEYS:START$"))  # ← новая строка!
    app.add_handler(CallbackQueryHandler(handle_api_callbacks, pattern="^api_"))
    app.add_handler(MessageHandler(
        filters.TEXT & filters.User(CFG.ADMIN_IDS) & ~filters.COMMAND,
        handle_key_name_input
    ))
    app.add_handler(CommandHandler("admin", admin_api_menu))

    # Запуск polling
    app.run_polling()


if __name__ == "__main__":
    # Запускаем API и бота параллельно
    p1 = multiprocessing.Process(target=start_api)
    p2 = multiprocessing.Process(target=start_bot)

    p1.start()
    p2.start()

    p1.join()
    p2.join()
