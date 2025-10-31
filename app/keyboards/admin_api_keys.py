from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from app.keyboards.common import with_menu_back

def get_admin_api_menu():
    """Главное меню управления API ключами"""
    rows = [
        [InlineKeyboardButton("🆕 Сгенерировать ключ", callback_data="API:GEN")],
        [InlineKeyboardButton("📋 Список ключей", callback_data="API:LIST")],
        [InlineKeyboardButton("✏️ Редактировать ключ", callback_data="API:EDIT_MENU")],
        [InlineKeyboardButton("🗑️ Удалить ключ", callback_data="API:DELETE_MENU")],
    ]
    return with_menu_back(rows, back_data="API:BACK", menu_data="API:MENU")

def get_api_keys_list_keyboard(keys: dict, action_prefix: str = "API:VIEW_"):
    """Клавиатура со списком ключей"""
    rows = []
    for key, name in keys.items():
        display_key = f"{key[:8]}...{key[-6:]}" if len(key) > 16 else key
        rows.append([
            InlineKeyboardButton(f"🔑 {name} ({display_key})", callback_data=f"{action_prefix}{key}")
        ])
    return with_menu_back(rows, back_data="API:BACK", menu_data="API:MENU")

def get_key_actions_keyboard(key: str):
    """Клавиатура действий с конкретным ключом"""
    rows = [
        [InlineKeyboardButton("✏️ Изменить название", callback_data=f"API:EDIT_NAME_{key}")],
        [InlineKeyboardButton("🗑️ Удалить ключ", callback_data=f"API:DELETE_{key}")],
    ]
    return with_menu_back(rows, back_data="API:BACK", menu_data="API:MENU")

def get_delete_confirm_keyboard(key: str):
    """Клавиатура подтверждения удаления"""
    rows = [
        [InlineKeyboardButton("✅ Да, удалить", callback_data=f"API:DELETE_CONFIRM_{key}")],
        [InlineKeyboardButton("❌ Отмена", callback_data=f"API:VIEW_{key}")],
    ]
    return InlineKeyboardMarkup(rows)
