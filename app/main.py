import logging
from telegram.ext import Application, CommandHandler, CallbackQueryHandler
from config import CFG
from handlers.menu import start, menu_cb
from handlers.qr import qr_conv, qr_back_cb, qr_menu_cb

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

def main():
    app = Application.builder().token(CFG.TELEGRAM_BOT_TOKEN).build()
    app.job_queue.scheduler.configure(timezone=CFG.TZ)

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(menu_cb, pattern=r"^MENU$"))

    app.add_handler(qr_conv)

    app.add_handler(CallbackQueryHandler(qr_menu_cb, pattern=r"^QR:MENU$"))
    app.add_handler(CallbackQueryHandler(qr_back_cb, pattern=r"^QR:BACK$"))

    app.run_polling()

if __name__ == "__main__":
    main()
