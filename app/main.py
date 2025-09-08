# app/main.py
import logging
from telegram.ext import Application, CommandHandler, CallbackQueryHandler
from config import CFG
from handlers.menu import start, menu_cb
from handlers.qr import qr_conv, qr_back_cb, qr_menu_cb, qr_entry
from handlers.subscription import (
    subscription_entry, sub_create_cb, sub_check_cb
)
from services.db import init_db

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

def main():
    init_db()  # создадим таблицы
    app = Application.builder().token(CFG.TELEGRAM_BOT_TOKEN).build()

    # меню
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(menu_cb, pattern=r"^MENU$"))

    # подписка
    app.add_handler(CommandHandler("subscribe", subscription_entry))
    app.add_handler(CallbackQueryHandler(sub_create_cb, pattern=r"^SUB:CREATE$"))
    app.add_handler(CallbackQueryHandler(sub_check_cb, pattern=r"^SUB:CHECK:\d+$"))

    # генерация QR — entry point оставляем, но проверим подписку внутри (см. ниже)
    app.add_handler(qr_conv)
    app.add_handler(CallbackQueryHandler(qr_menu_cb, pattern=r"^QR:MENU$"))
    app.add_handler(CallbackQueryHandler(qr_back_cb, pattern=r"^QR:BACK$"))

    app.run_polling()

if __name__ == "__main__":
    main()
