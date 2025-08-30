from telegram import InlineKeyboardButton, InlineKeyboardMarkup

def with_menu_back(rows, back_data: str, menu_data: str):

    rows = list(rows)
    rows.append([
        InlineKeyboardButton("⬅️ Назад", callback_data=back_data),
        InlineKeyboardButton("🏠 Главное меню", callback_data=menu_data),
    ])
    return InlineKeyboardMarkup(rows)
