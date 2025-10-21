from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from app.keyboards.common import with_menu_back

def main_menu_kb(is_admin: bool = False):
    rows = [[InlineKeyboardButton("🧾 Создать QR / PDF", callback_data="QR:START")]]
    if is_admin:
        rows.append([InlineKeyboardButton("🔐 API ключи", callback_data="KEYS:START")])
    return InlineKeyboardMarkup(rows)


def template_choice_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🟦 Marktplaats", callback_data="QR:TPL:MARKT")],
        [InlineKeyboardButton("🟥 Subito", callback_data="QR:TPL:SUBITO")],
        [
            InlineKeyboardButton("⬅️ Назад", callback_data="QR:BACK"),
            InlineKeyboardButton("🏠 Главное меню", callback_data="QR:MENU"),
        ],
    ])


def photo_step_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⏭ Пропустить", callback_data="QR:SKIP_PHOTO")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="QR:BACK"),
         InlineKeyboardButton("🏠 Главное меню", callback_data="QR:MENU")]
    ])


def next_step_kb():
    return InlineKeyboardMarkup([[InlineKeyboardButton("Далее ▶️", callback_data="QR:NEXT")]])

def menu_back_kb():
    return with_menu_back([], back_data="QR:BACK", menu_data="QR:MENU")

