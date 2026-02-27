from telegram import Update
from telegram.ext import ContextTypes, ApplicationHandlerStop

from app.config import CFG


DENY_TEXT = "⛔️ Доступ запрещён. Обратитесь к администратору."


def is_admin(update: Update) -> bool:
    uid = update.effective_user.id if update.effective_user else None
    return uid in getattr(CFG, "ADMIN_IDS", set())


async def enforce_admin_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Глобальный guard для любых входящих сообщений.

    Пускает только пользователей из CFG.ADMIN_IDS.
    """
    if is_admin(update):
        return

    if update.message:
        await update.message.reply_text(DENY_TEXT)

    raise ApplicationHandlerStop


async def enforce_admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Глобальный guard для callback_query (нажатия кнопок)."""
    if is_admin(update):
        return

    if update.callback_query:
        try:
            await update.callback_query.answer(DENY_TEXT, show_alert=True)
        except Exception:
            await update.callback_query.answer()

    raise ApplicationHandlerStop
