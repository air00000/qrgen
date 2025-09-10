# app/keyboards/keys.py
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from .common import with_menu_back

def keys_menu_kb():
    rows = [
        [InlineKeyboardButton("➕ Добавить ключ", callback_data="KEYS:ADD")],
        [InlineKeyboardButton("🗑 Удалить ключ", callback_data="KEYS:DEL")],
        [InlineKeyboardButton("📃 Список ключей", callback_data="KEYS:LIST")],
    ]
    return with_menu_back(rows, back_data="KEYS:BACK", menu_data="KEYS:MENU")
