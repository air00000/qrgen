# app/main.py
"""
Асинхронный бот с поддержкой параллельной работы множества пользователей
"""

import logging
import multiprocessing
import uvicorn
import asyncio
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
from app.utils.notifications import set_bot_instance

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Глобальный executor для CPU-bound операций (генерация изображений)
# Размер пула = количество CPU ядер * 2
MAX_WORKERS = multiprocessing.cpu_count() * 2
executor = ThreadPoolExecutor(max_workers=MAX_WORKERS)
logger.info(f"🚀 ThreadPoolExecutor создан с {MAX_WORKERS} воркерами")


def start_api():
    """Запуск API сервера"""
    uvicorn.run("app.api:app", host="0.0.0.0", port=8000, workers=2)


def start_bot():
    """Запуск Telegram бота с оптимизацией для множества пользователей"""
    
    # Создаем Application с оптимальными настройками
    app = (
        Application.builder()
        .token(CFG.TELEGRAM_BOT_TOKEN)
        .concurrent_updates(True)  # ✅ Параллельная обработка апдейтов
        .pool_timeout(30.0)  # Таймаут для HTTP пула
        .connection_pool_size(8)  # Размер connection pool
        .build()
    )
    
    # Настройка timezone
    app.job_queue.scheduler.configure(timezone=CFG.TZ)
    
    # Сохраняем executor в bot_data для доступа из handlers
    app.bot_data['executor'] = executor
    
    # Устанавливаем bot instance для уведомлений
    set_bot_instance(app.bot)
    if CFG.NOTIFICATIONS_CHAT_ID:
        logger.info(f"📨 Уведомления о API генерациях: ВКЛ → чат {CFG.NOTIFICATIONS_CHAT_ID}")
    else:
        logger.info("📨 Уведомления о API генерациях: ВЫКЛ (не настроен NOTIFICATIONS_CHAT_ID)")
    
    # Регистрация handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(menu_cb, pattern=r"^MENU$"))
    
    app.add_handler(qr_conv)
    app.add_handler(CallbackQueryHandler(qr_menu_cb, pattern=r"^QR:MENU$"))
    app.add_handler(CallbackQueryHandler(qr_back_cb, pattern=r"^QR:BACK$"))
    
    app.add_handler(api_keys_conv)
    
    # Админ-команды для кэша
    for handler in get_cache_handlers():
        app.add_handler(handler)
    
    logger.info("🤖 Бот запущен в асинхронном режиме")
    logger.info(f"✅ concurrent_updates=True (параллельная обработка)")
    logger.info(f"✅ ThreadPoolExecutor: {MAX_WORKERS} воркеров")
    
    # Запуск в режиме polling
    app.run_polling(
        allowed_updates=['message', 'callback_query'],
        drop_pending_updates=True,  # Пропускаем старые апдейты при запуске
    )


if __name__ == "__main__":
    # Запуск API и бота в отдельных процессах
    p1 = multiprocessing.Process(target=start_api, name="API-Server")
    p2 = multiprocessing.Process(target=start_bot, name="Telegram-Bot")
    
    p1.start()
    p2.start()
    
    logger.info("🚀 Все сервисы запущены")
    
    try:
        p1.join()
        p2.join()
    except KeyboardInterrupt:
        logger.info("⛔ Остановка сервисов...")
        p1.terminate()
        p2.terminate()
        p1.join()
        p2.join()
        executor.shutdown(wait=True)
        logger.info("✅ Все сервисы остановлены")
