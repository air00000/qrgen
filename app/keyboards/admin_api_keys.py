from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from app.keyboards.common import with_menu_back

def get_admin_api_menu():
    """Меню управления API ключами."""
    rows = [
        [InlineKeyboardButton("🆕 Сгенерировать", callback_data="API:GEN")],
        [InlineKeyboardButton("📄 Просмотреть", callback_data="API:LIST")],
    ]
    # Вверху «Главное меню», как и в QR-разделе через отдельную кнопку
    rows.append([InlineKeyboardButton("🏠 Главное меню", callback_data="API:MENU")])
    return InlineKeyboardMarkup(rows)

def get_api_keys_keyboard(keys: dict):
    """Список ключей + пара 'Назад / Главное меню' внизу (как в QR)."""
    rows = []
    for key, name in keys.items():
        rows.append([
            InlineKeyboardButton(f"❌ {name}", callback_data=f"API:DELETE_{key}")
        ])
    # Добавляем «⬅️ Назад» и «🏠 Главное меню» в одном ряду
    return with_menu_back(rows, back_data="API:BACK", menu_data="API:MENU")
