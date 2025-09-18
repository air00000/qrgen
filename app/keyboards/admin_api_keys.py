# app/keyboards/admin_api_keys.py

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

def get_admin_api_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🆕 Сгенерировать", callback_data="api_generate")],
        [InlineKeyboardButton("📄 Просмотреть", callback_data="api_list")],
        [InlineKeyboardButton("🔙 Назад", callback_data="admin_back")],
    ])

def get_api_keys_keyboard(keys: dict):
    keyboard = []
    for key, name in keys.items():
        keyboard.append([
            InlineKeyboardButton(f"❌ {name}", callback_data=f"api_delete_{key}")
        ])
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="api_back")])
    return InlineKeyboardMarkup(keyboard)
