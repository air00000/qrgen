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

def service_select_kb(is_admin: bool = False):
    """Клавиатура выбора типа скриншота (+ админ-кнопка при наличии прав)."""
    rows = [
        [
            InlineKeyboardButton("📦 Marktplaats", callback_data="QR:START"),
            InlineKeyboardButton("🇮🇹 Subito", callback_data="QR:SUBITO"),
        ],
    ]
    if is_admin:
        rows.append([InlineKeyboardButton("🔐 API ключи", callback_data="API:MENU")])
    rows.append([InlineKeyboardButton("❌ Отмена", callback_data="QR:MENU")])
    return InlineKeyboardMarkup(rows)
