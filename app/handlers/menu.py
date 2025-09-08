from keyboards.qr import main_menu_kb
from telegram import InlineKeyboardMarkup, InlineKeyboardButton

def main_menu_full_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🧾 Создать QR / PDF", callback_data="QR:START")],
        [InlineKeyboardButton("💳 Подписка", callback_data="SUB:CREATE")]
    ])

async def start(update, context):
    from utils.state_stack import clear_stack
    clear_stack(context.user_data)
    text = "Привет! Выбери действие:"
    kb = main_menu_full_kb()
    if update.message:
        await update.message.reply_text(text, reply_markup=kb)
    else:
        await update.callback_query.message.edit_text(text, reply_markup=kb)
