from telegram import InlineKeyboardButton, InlineKeyboardMarkup

def with_menu_back(rows, back_data: str = "BACK", menu_data: str = "MENU"):
    """Добавляет кнопки Назад и Главное меню"""
    rows = list(rows)
    rows.append([
        InlineKeyboardButton("⬅️ Назад", callback_data=back_data),
        InlineKeyboardButton("🏠 Главное меню", callback_data=menu_data),
    ])
    return InlineKeyboardMarkup(rows)