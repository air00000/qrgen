from telegram import Update
from telegram.ext import ContextTypes, ApplicationHandlerStop

from app.config import CFG


DENY_TEXT = "⛔️ Доступ запрещён. Обратитесь к администратору."


def is_admin(update: Update) -> bool:
    uid = update.effective_user.id if update.effective_user else None
    return uid in getattr(CFG, "ADMIN_IDS", set())


async def enforce_admin_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Legacy hook: no global restrictions for regular users."""
    return


async def enforce_admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Restrict only explicit admin sections."""
    if is_admin(update):
        return

    data = update.callback_query.data if update.callback_query else ""
    if not data.startswith(("KEYS:", "API:", "CACHE:")):
        return

    if update.callback_query:
        try:
            await update.callback_query.answer(DENY_TEXT, show_alert=True)
        except Exception:
            await update.callback_query.answer()

    raise ApplicationHandlerStop
