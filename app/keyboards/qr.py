from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from app.keyboards.common import with_menu_back


def main_menu_kb(is_admin: bool = False):
    rows = [
        [InlineKeyboardButton("🧾 Marktplaats PDF", callback_data="QR:START")],
        [InlineKeyboardButton("📸 Subito скрин", callback_data="SUBITO:START")],
    ]
    if is_admin:
        rows.append([InlineKeyboardButton("🔐 API ключи", callback_data="KEYS:START")])
    return InlineKeyboardMarkup(rows)


def photo_step_kb(prefix: str = "QR"):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⏭ Пропустить", callback_data=f"{prefix}:SKIP_PHOTO")],
        [InlineKeyboardButton("⬅️ Назад", callback_data=f"{prefix}:BACK"),
         InlineKeyboardButton("🏠 Главное меню", callback_data=f"{prefix}:MENU")]
    ])


def next_step_kb(prefix: str = "QR"):
    return InlineKeyboardMarkup([[InlineKeyboardButton("Далее ▶️", callback_data=f"{prefix}:NEXT")]])


def menu_back_kb(prefix: str = "QR"):
    return with_menu_back([], back_data=f"{prefix}:BACK", menu_data=f"{prefix}:MENU")