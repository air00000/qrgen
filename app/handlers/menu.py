# handlers/menu.py
from telegram import Update
from telegram.ext import ContextTypes
from app.keyboards.qr import main_menu_kb, service_select_kb
from app.config import CFG

def _is_admin(update: Update) -> bool:
    uid = update.effective_user.id if update.effective_user else None
    return uid in getattr(CFG, "ADMIN_IDS", set())

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = "Выбери сервис для генерации скриншота:"
    if update.message:
        await update.message.reply_text(text, reply_markup=service_select_kb())
    else:
        # на случай callback
        await update.callback_query.message.edit_text(text, reply_markup=service_select_kb())

async def menu_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка кнопки 'Главное меню'"""
    await update.callback_query.answer()
    return await start(update, context)
