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
            InlineKeyboardButton("🛒 Markt",        callback_data="QR:MARKT_MENU"),
            InlineKeyboardButton("🇮🇹 Subito",      callback_data="QR:SUBITO"),
        ],
        [
            InlineKeyboardButton("🇪🇺 Wallapop",    callback_data="QR:WALLAPOP_MENU"),
            InlineKeyboardButton("🇳🇱 2dehands",    callback_data="QR:2DEHANDS"),
        ],
        [
            InlineKeyboardButton("🇫🇷 2ememain",    callback_data="QR:2EMEMAIN"),
            InlineKeyboardButton("💰 Conto (Subito)", callback_data="QR:CONTO"),
        ],
        [
            InlineKeyboardButton("🔧 Kleize",        callback_data="QR:KLEIZE"),
            InlineKeyboardButton("🛍️ Depop",         callback_data="QR:DEPOP_MENU"),
        ],
    ]
    if is_admin:
        rows.append([InlineKeyboardButton("🔑 Управление API ключами", callback_data="KEYS:START")])
    rows.append([InlineKeyboardButton("🏠 Главное меню", callback_data="MENU")])
    return InlineKeyboardMarkup(rows)


def markt_type_kb():
    """Клавиатура выбора типа Markt"""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔳 QR", callback_data="QR:MARKT_QR"),
        ],
        [
            InlineKeyboardButton("📧 Email запрос", callback_data="QR:MARKT_EMAIL_REQUEST"),
            InlineKeyboardButton("📞 Телефон запрос", callback_data="QR:MARKT_PHONE_REQUEST"),
        ],
        [
            InlineKeyboardButton("💳 Email оплата", callback_data="QR:MARKT_EMAIL_PAYMENT"),
            InlineKeyboardButton("📱 SMS оплата", callback_data="QR:MARKT_SMS_PAYMENT"),
        ],
        [
            InlineKeyboardButton("⬅️ Назад", callback_data="QR:BACK"),
            InlineKeyboardButton("🏠 Главное меню", callback_data="MENU")
        ],
    ])


def markt_lang_kb():
    """Клавиатура выбора языка для Markt"""
    callback_prefix = "MARKT_LANG_"
    
    keyboard = [
        [
            InlineKeyboardButton("🇬🇧 UK", callback_data=f"{callback_prefix}uk"),
            InlineKeyboardButton("🇳🇱 NL", callback_data=f"{callback_prefix}nl"),
        ],
        [
            InlineKeyboardButton("⬅️ Назад", callback_data="QR:MARKT_BACK"),
            InlineKeyboardButton("🏠 Главное меню", callback_data="MENU")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


def wallapop_type_kb():
    """Клавиатура выбора типа Wallapop"""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📧 Mail запрос", callback_data="QR:WALLAPOP_EMAIL_REQUEST"),
            InlineKeyboardButton("📞 Телефон запрос", callback_data="QR:WALLAPOP_PHONE_REQUEST"),
        ],
        [
            InlineKeyboardButton("💳 Mail оплата", callback_data="QR:WALLAPOP_EMAIL_PAYMENT"),
            InlineKeyboardButton("📱 SMS оплата", callback_data="QR:WALLAPOP_SMS_PAYMENT"),
        ],
        [
            InlineKeyboardButton("🔳 QR", callback_data="QR:WALLAPOP_QR"),
        ],
        [
            InlineKeyboardButton("⬅️ Назад", callback_data="QR:BACK"),
            InlineKeyboardButton("🏠 Главное меню", callback_data="MENU")
        ],
    ])


def wallapop_lang_kb(wallapop_type: str = "link"):
    """Клавиатура выбора языка для Wallapop"""
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
            InlineKeyboardButton("🇵🇹 PT", callback_data=f"{callback_prefix}pr"),
        ],
        [
            InlineKeyboardButton("⬅️ Назад", callback_data="QR:WALLAPOP_BACK"),
            InlineKeyboardButton("🏠 Главное меню", callback_data="MENU")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


def depop_type_kb():
    """Клавиатура выбора типа Depop"""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔗 QR код", callback_data="QR:DEPOP_QR"),
        ],
        [
            InlineKeyboardButton("📧 Email запрос", callback_data="QR:DEPOP_EMAIL_REQUEST"),
            InlineKeyboardButton("✅ Email подтв.", callback_data="QR:DEPOP_EMAIL_CONFIRM"),
        ],
        [
            InlineKeyboardButton("📱 SMS запрос", callback_data="QR:DEPOP_SMS_REQUEST"),
            InlineKeyboardButton("✅ SMS подтв.", callback_data="QR:DEPOP_SMS_CONFIRM"),
        ],
        [
            InlineKeyboardButton("⬅️ Назад", callback_data="QR:BACK"),
            InlineKeyboardButton("🏠 Главное меню", callback_data="MENU")
        ],
    ])
