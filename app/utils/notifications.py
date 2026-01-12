# app/utils/notifications.py
"""
Модуль для отправки уведомлений о генерациях через API
"""
import logging
import asyncio
from typing import Optional
from telegram import Bot
from telegram.error import TelegramError

from app.config import CFG

logger = logging.getLogger(__name__)

# Глобальный bot instance (будет создан при первом использовании)
_bot_instance: Optional[Bot] = None


def _get_bot_instance() -> Optional[Bot]:
    """Получить или создать bot instance"""
    global _bot_instance
    
    if _bot_instance is None and CFG.TELEGRAM_BOT_TOKEN:
        _bot_instance = Bot(token=CFG.TELEGRAM_BOT_TOKEN)
        logger.info("🤖 Bot instance создан для уведомлений")
    
    return _bot_instance


def set_bot_instance(bot: Bot):
    """Установить bot instance для уведомлений (legacy, не обязательно)"""
    global _bot_instance
    _bot_instance = bot
    logger.info(f"✅ Bot instance установлен для уведомлений")


async def send_api_notification(
    service: str,
    key_name: str,
    title: str,
    price: Optional[float] = None,
    has_photo: bool = False,
    url: Optional[str] = None,
    success: bool = True,
    error: Optional[str] = None
):
    """
    Отправить уведомление о генерации через API
    
    Args:
        service: Название сервиса (marktplaats, depop, kleize, etc)
        key_name: Имя API ключа (не используется)
        title: Название товара (не используется)
        price: Цена (не используется)
        has_photo: Есть ли фото (не используется)
        url: URL (не используется)
        success: Успешна ли генерация
        error: Текст ошибки (если есть)
    """
    # Проверки
    if not CFG.NOTIFY_API_GENERATIONS:
        return
    
    if not CFG.NOTIFICATIONS_CHAT_ID:
        logger.warning("⚠️  NOTIFICATIONS_CHAT_ID не настроен, пропускаю уведомление")
        return
    
    # Получаем или создаем bot instance
    bot = _get_bot_instance()
    
    if not bot:
        logger.warning("⚠️  Не удалось создать Bot instance (нет TELEGRAM_BOT_TOKEN?)")
        return
    
    try:
        # Формируем простое уведомление
        if success:
            message = f"✅ {service.upper()}: Успех"
        else:
            error_short = error[:100] if error else "Unknown error"
            message = f"❌ {service.upper()}: Ошибка\n<code>{error_short}</code>"
        
        # Конвертируем chat_id в int (для супергрупп может быть строка)
        try:
            chat_id = int(CFG.NOTIFICATIONS_CHAT_ID)
        except (ValueError, TypeError):
            logger.error(f"❌ Неверный формат NOTIFICATIONS_CHAT_ID: {CFG.NOTIFICATIONS_CHAT_ID}")
            return
        
        # Отправляем уведомление
        await bot.send_message(
            chat_id=chat_id,
            text=message,
            parse_mode="HTML"
        )
        
        logger.info(f"📨 Уведомление отправлено в чат {chat_id}: {service} - {'✅' if success else '❌'}")
        
    except TelegramError as e:
        logger.error(f"❌ Ошибка отправки уведомления в чат {CFG.NOTIFICATIONS_CHAT_ID}: {e}")
        logger.error(f"   Проверь что бот добавлен в группу и имеет права на отправку сообщений")
    except Exception as e:
        logger.error(f"❌ Неожиданная ошибка при отправке уведомления: {e}")


def send_api_notification_sync(*args, **kwargs):
    """
    Синхронная обертка для send_api_notification
    Использовать в не-async контексте (например, в FastAPI endpoints)
    """
    try:
        # Создаем новый event loop для этого процесса если нужно
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        if loop.is_running():
            # Если loop уже запущен - создаем задачу
            asyncio.create_task(send_api_notification(*args, **kwargs))
        else:
            # Если loop не запущен - запускаем синхронно
            loop.run_until_complete(send_api_notification(*args, **kwargs))
    except Exception as e:
        logger.error(f"❌ Ошибка в send_api_notification_sync: {e}")
