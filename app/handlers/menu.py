# handlers/menu.py
from telegram import Update
from telegram.ext import ContextTypes
from app.keyboards.qr import main_menu_kb
from app.config import CFG

def _is_admin(update: Update) -> bool:
    uid = update.effective_user.id if update.effective_user else None
    return uid in getattr(CFG, "ADMIN_IDS", set())

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Главное меню"""
    text = "Привет! Выбери действие:"
    kb = main_menu_kb(is_admin=_is_admin(update))
    if update.message:
        await update.message.reply_text(text, reply_markup=kb)
    else:
        await update.callback_query.message.edit_text(text, reply_markup=kb)

async def menu_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка кнопки 'Главное меню'"""
    await update.callback_query.answer()
    return await start(update, context)
