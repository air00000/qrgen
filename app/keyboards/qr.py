from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from .common import with_menu_back

def main_menu_kb(is_admin: bool = False):
    rows = [[InlineKeyboardButton("🧾 Создать QR / PDF", callback_data="QR:START")]]
    if is_admin:
        rows.append([InlineKeyboardButton("🔐 API ключи", callback_data="KEYS:START")])
    return InlineKeyboardMarkup(rows)

def next_step_kb():
    return InlineKeyboardMarkup([[InlineKeyboardButton("Далее ▶️", callback_data="QR:NEXT")]])

def menu_back_kb():
    return with_menu_back([], back_data="QR:BACK", menu_data="QR:MENU")