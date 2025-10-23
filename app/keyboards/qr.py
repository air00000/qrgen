from telegram import InlineKeyboardMarkup, InlineKeyboardButton

def main_menu_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔁 Сгенерировать ещё", callback_data="QR:MENU")],
    ])

def menu_back_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅️ Назад в меню", callback_data="QR:MENU")],
    ])

def photo_step_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⏭ Пропустить фото", callback_data="QR:SKIP_PHOTO")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="QR:BACK")],
    ])

def service_select_kb():
    """Клавиатура выбора типа скриншота"""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📦 Marktplaats", callback_data="QR:START"),
            InlineKeyboardButton("🇮🇹 Subito", callback_data="QR:SUBITO"),
        ],
        [InlineKeyboardButton("❌ Отмена", callback_data="QR:MENU")],
    ])
