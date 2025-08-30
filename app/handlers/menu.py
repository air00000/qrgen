from telegram import Update
from telegram.ext import ContextTypes
from keyboards.qr import main_menu_kb
from utils.state_stack import clear_stack

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    clear_stack(context.user_data)
    text = "Привет! Выбери действие:"
    if update.message:
        await update.message.reply_text(text, reply_markup=main_menu_kb())
    else:
        await update.callback_query.message.edit_text(text, reply_markup=main_menu_kb())

async def menu_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await start(update, context)
