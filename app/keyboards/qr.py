# app/keyboards/qr.py
from telegram import InlineKeyboardMarkup, InlineKeyboardButton


def main_menu_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔁 Сгенерировать ещё", callback_data="QR:MENU")],
    ])


def menu_back_kb():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("⬅️ Назад", callback_data="QR:BACK"),
            InlineKeyboardButton("🏠 Главное меню", callback_data="MENU")
        ],
    ])


def photo_step_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⏭ Пропустить фото", callback_data="QR:SKIP_PHOTO")],
        [
            InlineKeyboardButton("⬅️ Назад", callback_data="QR:BACK"),
            InlineKeyboardButton("🏠 Главное меню", callback_data="MENU")
        ],
    ])


def service_select_kb(is_admin: bool = False):
    """Клавиатура выбора типа скриншота (+ админ-кнопка при наличии прав)."""
    rows = [
        [
            InlineKeyboardButton("📦 Marktplaats", callback_data="QR:START"),
            InlineKeyboardButton("🇮🇹 Subito", callback_data="QR:SUBITO"),
        ],
        [
            InlineKeyboardButton("🇪🇺 Wallapop", callback_data="QR:WALLAPOP_MENU"),
            InlineKeyboardButton("🇩🇪 Kleinanzeigen", callback_data="QR:KLEINANZEIGEN"),
        ],
        [
            InlineKeyboardButton("🇳🇱 2dehands", callback_data="QR:2DEHANDS"),
            InlineKeyboardButton("🇫🇷 2ememain", callback_data="QR:2EMEMAIN"),
        ],
    ]
    if is_admin:
        rows.append([InlineKeyboardButton("🔐 API ключи", callback_data="API:MENU")])
    rows.append([InlineKeyboardButton("🏠 Главное меню", callback_data="MENU")])
    return InlineKeyboardMarkup(rows)


def wallapop_type_kb():
    """Клавиатура выбора типа Wallapop"""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📧 Email версия", callback_data="QR:WALLAPOP_EMAIL"),
            InlineKeyboardButton("🔗 Link версия", callback_data="QR:WALLAPOP_LINK"),
        ],
        [
            InlineKeyboardButton("📱 SMS версия", callback_data="QR:WALLAPOP_SMS"),
        ],
        [
            InlineKeyboardButton("⬅️ Назад", callback_data="QR:BACK"),
            InlineKeyboardButton("🏠 Главное меню", callback_data="MENU")
        ],
    ])


def wallapop_lang_kb(wallapop_type: str = "link"):
    """Клавиатура выбора языка для Wallapop"""
    if wallapop_type == "email":
        callback_prefix = "WALLAPOP_EMAIL_LANG_"
    elif wallapop_type == "sms":
        callback_prefix = "WALLAPOP_SMS_LANG_"
    else:
        callback_prefix = "WALLAPOP_LANG_"

    keyboard = [
        [
            InlineKeyboardButton("🇬🇧 UK", callback_data=f"{callback_prefix}uk"),
            InlineKeyboardButton("🇪🇸 ES", callback_data=f"{callback_prefix}es"),
        ],
        [
            InlineKeyboardButton("🇮🇹 IT", callback_data=f"{callback_prefix}it"),
            InlineKeyboardButton("🇫🇷 FR", callback_data=f"{callback_prefix}fr"),
        ],
        [
            InlineKeyboardButton("⬅️ Назад", callback_data="QR:WALLAPOP_BACK"),
            InlineKeyboardButton("🏠 Главное меню", callback_data="MENU")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)
