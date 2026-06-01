# app/handlers/menu.py
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
from app.config import CFG


def _is_admin(update: Update) -> bool:
    uid = update.effective_user.id if update.effective_user else None
    return uid in getattr(CFG, "ADMIN_IDS", set())


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = "Выбери сервис для генерации скриншота:"

    # Базовая клавиатура
    keyboard = [
        [
            InlineKeyboardButton("🛒 Markt",          callback_data="QR:MARKT_MENU"),
            InlineKeyboardButton("🇮🇹 Subito",        callback_data="QR:SUBITO"),
        ],
        [
            InlineKeyboardButton("🌳 Gumtree",        callback_data="QR:GUMTREE"),
        ],
        [
            InlineKeyboardButton("🇪🇺 Wallapop",      callback_data="QR:WALLAPOP_MENU"),
            InlineKeyboardButton("🇳🇱 2dehands",      callback_data="QR:2DEHANDS"),
        ],
        [
            InlineKeyboardButton("🇫🇷 2ememain",      callback_data="QR:2EMEMAIN"),
            InlineKeyboardButton("💰 Conto (Subito)", callback_data="QR:CONTO"),
        ],
        [
            InlineKeyboardButton("🔧 Kleize",          callback_data="QR:KLEIZE"),
            InlineKeyboardButton("🛍️ Depop",           callback_data="QR:DEPOP_MENU"),
        ],
        [
            InlineKeyboardButton("🇭🇺 Jófogás",         callback_data="QR:JOFOGAS"),
            InlineKeyboardButton("🏨 Booking",         callback_data="QR:BOOKING"),
        ],
    ]

    if _is_admin(update):
        keyboard.append([InlineKeyboardButton("🔑 Управление API ключами", callback_data="KEYS:START")])
        keyboard.append([InlineKeyboardButton("💾 Управление кэшем", callback_data="CACHE:MENU")])

    reply_markup = InlineKeyboardMarkup(keyboard)

    if update.message:
        await update.message.reply_text(text, reply_markup=reply_markup)
    else:
        await update.callback_query.message.edit_text(text, reply_markup=reply_markup)


async def menu_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка кнопки 'Главное меню'"""
    await update.callback_query.answer()
    return await start(update, context)