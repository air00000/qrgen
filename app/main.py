# app/main.py
"""
Асинхронный бот с поддержкой параллельной работы множества пользователей
"""

import logging
import multiprocessing
# uvicorn/threading/time are legacy (python API server). Keep commented to avoid confusion.
# import uvicorn
# import threading
# import time
from concurrent.futures import ThreadPoolExecutor

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
from app.handlers.cache_admin import get_cache_handlers
from app.handlers.subito_variants import subito_variants_conv
from app.handlers.markt_variants import markt_conv
from app.utils.notifications import set_bot_instance

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def start_api():
    """Запуск API сервера (LEGACY).

    Сейчас API работает в Rust backend (`qrgen-backend`), поэтому Python-uvicorn
    по умолчанию не запускаем.
    """
    logger.info("🌐 (LEGACY) Python API server disabled; use Rust backend instead")
    # uvicorn.run(
    #     "app.api:app",
    #     host="0.0.0.0",
    #     port=8080,
    #     log_level="info",
    #     access_log=True
    # )


def start_bot():
    """Запуск Telegram бота"""
    
    # Executor для CPU-bound операций
    max_workers = multiprocessing.cpu_count() * 2
    executor = ThreadPoolExecutor(max_workers=max_workers)
    logger.info(f"🚀 ThreadPoolExecutor: {max_workers} воркеров")
    
    # Создаем Application
    app = (
        Application.builder()
        .token(CFG.TELEGRAM_BOT_TOKEN)
        .concurrent_updates(True)
        .pool_timeout(30.0)
        .connection_pool_size(8)
        .build()
    )
    
    # Настройка timezone
    app.job_queue.scheduler.configure(timezone=CFG.TZ)
    
    # Сохраняем executor
    app.bot_data['executor'] = executor
    
    # Устанавливаем bot instance для уведомлений
    set_bot_instance(app.bot)
    if CFG.NOTIFICATIONS_CHAT_ID:
        logger.info(f"📨 Уведомления: ВКЛ → чат {CFG.NOTIFICATIONS_CHAT_ID}")
    else:
        logger.info("📨 Уведомления: ВЫКЛ")
    
    # Регистрация handlers
    # Порядок важен: ConversationHandler'ы регистрируются раньше глобальных CallbackQueryHandler
    app.add_handler(CommandHandler("start", start))
    app.add_handler(subito_variants_conv)       # QR:SUBITO → SN_TYPE/SN_LANG/...
    app.add_handler(markt_conv)                 # QR:MARKT_MENU → MARKT_LANG_/...
    app.add_handler(qr_conv)                    # QR:WALLAPOP_MENU, QR:2DEHANDS, QR:CONTO, ...
    app.add_handler(api_keys_conv)              # KEYS:START → API:*/...
    app.add_handler(CallbackQueryHandler(menu_cb, pattern=r"^MENU$"))
    app.add_handler(CallbackQueryHandler(qr_menu_cb, pattern=r"^QR:MENU$"))
    app.add_handler(CallbackQueryHandler(qr_back_cb, pattern=r"^QR:BACK$"))
    
    for handler in get_cache_handlers():
        app.add_handler(handler)
    
    logger.info("🤖 Бот запущен")
    
    # Запуск polling
    app.run_polling(
        allowed_updates=['message', 'callback_query'],
        drop_pending_updates=True,
    )


def warmup_subito_cache():
    """
    Фоновый прогрев in-memory кэша для всех субито-фреймов.
    Запускается однократно при старте — после этого генерация мгновенная.
    """
    import time
    from app.cache.figma_cache import FigmaCache
    from app.services.figma import find_node
    from app.services.cache_wrapper import _mem_set

    subito_services = [
        ("subito_email_request_uk", "Page 2", "subito6"),
        ("subito_email_request_nl", "Page 2", "subito6"),
        ("subito_sms_request_uk", "Page 2", "subito7"),
        ("subito_sms_request_nl", "Page 2", "subito7"),
        ("subito_email_confirm_uk", "Page 2", "subito8"),
        ("subito_email_confirm_nl", "Page 2", "subito8"),
        ("subito_sms_confirm_uk",   "Page 2", "subito9"),
        ("subito_sms_confirm_nl",   "Page 2", "subito9"),
        ("subito_qr_uk",            "Page 2", "subito10"),
        ("subito_qr_nl",            "Page 2", "subito10"),
    ]

    loaded = 0
    for service_name, page, frame_name in subito_services:
        cache = FigmaCache(service_name)
        if cache.exists():
            try:
                template_json, frame_img = cache.load()
                _mem_set(service_name, template_json, frame_img)
                loaded += 1
            except Exception as e:
                logger.warning(f"⚠️  warmup {service_name}: {e}")

    if loaded:
        logger.info(f"⚡ Прогрев кэша субито: {loaded}/{len(subito_services)} сервисов в памяти")
    else:
        logger.info("ℹ️  Disk-кэш субито не найден — первый запрос пойдёт через Figma API")


def main():
    """Запуск бота и API вместе"""
    
    logger.info("=" * 50)
    logger.info("🚀 QRGen Bot + API")
    logger.info("=" * 50)

    # Прогрев in-memory кэша субито (если disk-кэш заполнен)
    warmup_subito_cache()

    # # Запускаем API в отдельном потоке
    # api_thread = threading.Thread(target=start_api, daemon=True, name="API-Server")
    # api_thread.start()
    #
    # # Даем API время запуститься
    # time.sleep(1)
    #
    # logger.info("✅ API запущен на http://0.0.0.0:8080")
    # logger.info("✅ Swagger UI: http://127.0.0.1:8080/docs")
    #
    # Запускаем бота в основном потоке
    try:
        start_bot()
    except KeyboardInterrupt:
        logger.info("⛔ Остановка...")


if __name__ == "__main__":
    main()
