from telegram import Update
from telegram.ext import ContextTypes

from app.config import CFG
from app.services.subscriptions import has_active_subscription
from app.keyboards.subscription import subscription_menu_kb


async def ensure_generation_access(update_or_message, context: ContextTypes.DEFAULT_TYPE) -> bool:
    user = getattr(update_or_message, "effective_user", None)
    if not user and getattr(update_or_message, "chat", None):
        user = update_or_message.from_user

    uid = user.id if user else None
    if uid in CFG.ADMIN_IDS:
        return True
    if uid and has_active_subscription(uid):
        return True

    target = getattr(update_or_message, "message", None)
    cb = getattr(update_or_message, "callback_query", None)
    if target is None and cb is not None:
        target = cb.message
    if target is None and hasattr(update_or_message, "reply_text"):
        target = update_or_message

    if target:
        await target.reply_text(
            "⛔️ Нет активной подписки. Оформи доступ, чтобы генерировать скрины.",
            reply_markup=subscription_menu_kb(),
        )
    return False
