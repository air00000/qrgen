from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def subscription_menu_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💳 Подписка на 1 день", callback_data="SUB:BUY:day")],
        [InlineKeyboardButton("📅 Подписка на 1 неделю", callback_data="SUB:BUY:week")],
        [InlineKeyboardButton("📊 Статус подписки", callback_data="SUB:STATUS")],
    ])


def invoice_kb(pay_url: str, payment_id: str):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💸 Оплатить в CryptoBot", url=pay_url)],
        [InlineKeyboardButton("✅ Проверить оплату", callback_data=f"SUB:CHECK:{payment_id}")],
        [InlineKeyboardButton("📊 Статус подписки", callback_data="SUB:STATUS")],
    ])
