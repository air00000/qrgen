from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CallbackQueryHandler,
    MessageHandler,
    CommandHandler,
    filters,
)
from app.services.apikey import generate_key, get_all_keys, delete_key
from app.config import CFG

# Состояния
API_MENU, API_CREATE_WAIT_NAME, API_LIST, API_KEY_DETAIL = range(200, 204)
PAGE_SIZE = 10


def _is_admin(update: Update) -> bool:
    uid = update.effective_user.id if update.effective_user else None
    return uid in getattr(CFG, "ADMIN_IDS", set())


# === Вспомогательные функции ===
def _paginate_keys(keys: dict, page: int = 0):
    items = list(keys.items())
    total_pages = max(1, (len(items) + PAGE_SIZE - 1) // PAGE_SIZE)
    page = max(0, min(page, total_pages - 1))
    start, end = page * PAGE_SIZE, page * PAGE_SIZE + PAGE_SIZE
    page_items = items[start:end]
    return page_items, page, total_pages


def _keys_keyboard(keys: dict, page: int = 0):
    items, page, total_pages = _paginate_keys(keys, page)
    rows = [[InlineKeyboardButton(name, callback_data=f"API:DETAIL:{key}")]
            for key, name in items]

    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton("⬅️ Назад", callback_data=f"API:PAGE:{page - 1}"))
    if page < total_pages - 1:
        nav_row.append(InlineKeyboardButton("▶️ Далее", callback_data=f"API:PAGE:{page + 1}"))

    if nav_row:
        rows.append(nav_row)
    rows.append([InlineKeyboardButton("🏠 Главное меню", callback_data="API:MENU")])
    return InlineKeyboardMarkup(rows)


def _admin_menu_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🆕 Создать ключ", callback_data="API:CREATE")],
        [InlineKeyboardButton("📄 Просмотреть ключи", callback_data="API:LIST:0")],
        [InlineKeyboardButton("🏠 Главное меню", callback_data="API:MENU")],
    ])


def _key_detail_kb(key: str):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 Копировать", callback_data=f"API:COPY:{key}")],
        [InlineKeyboardButton("❌ Удалить", callback_data=f"API:DELETE:{key}")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="API:LIST:0")],
    ])


# === Обработчики ===
async def entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Вход в меню управления ключами"""
    if not _is_admin(update):
        await update.callback_query.answer()
        await update.callback_query.message.reply_text("❌ Доступ запрещён.")
        return ConversationHandler.END

    await update.callback_query.answer()
    await update.callback_query.message.edit_text("🔐 Управление API ключами", reply_markup=_admin_menu_kb())
    return API_MENU


async def on_create(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Переход к созданию ключа"""
    await update.callback_query.answer()
    await update.callback_query.message.edit_text("Введите название для нового ключа:")
    return API_CREATE_WAIT_NAME


async def on_name_entered(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Создание нового ключа"""
    name = (update.message.text or "").strip()
    key = generate_key(name)
    await update.message.reply_text(
        f"✅ Ключ создан:\n<b>{key}</b>\nНазвание: {name}",
        parse_mode="HTML",
        reply_markup=_admin_menu_kb()
    )
    return API_MENU


async def on_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать список ключей"""
    page = int(update.callback_query.data.split(":")[-1]) if ":" in update.callback_query.data else 0
    keys = get_all_keys()
    if not keys:
        await update.callback_query.message.edit_text("Пока нет ключей.", reply_markup=_admin_menu_kb())
        return API_MENU
    await update.callback_query.message.edit_text(
        f"📄 Список ключей (стр. {page + 1})",
        reply_markup=_keys_keyboard(keys, page)
    )
    return API_LIST


async def on_detail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показ информации о ключе"""
    key = update.callback_query.data.split(":")[-1]
    keys = get_all_keys()
    if key not in keys:
        await update.callback_query.answer("Ключ не найден.")
        return API_LIST

    name = keys[key]
    text = f"<b>{name}</b>\n<code>{key}</code>"
    await update.callback_query.message.edit_text(text, parse_mode="HTML", reply_markup=_key_detail_kb(key))
    return API_KEY_DETAIL


async def on_copy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    key = update.callback_query.data.split(":")[-1]
    keys = get_all_keys()
    if key not in keys:
        await update.callback_query.answer("Ключ не найден.")
        return API_LIST

    await update.callback_query.answer("Ключ скопирован!")
    await update.callback_query.message.reply_text(f"<code>{key}</code>", parse_mode="HTML")
    return API_KEY_DETAIL


async def on_delete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    key = update.callback_query.data.split(":")[-1]
    delete_key(key)
    await update.callback_query.answer("Ключ удалён.")
    keys = get_all_keys()
    await update.callback_query.message.edit_text("📄 Ключ удалён. Список обновлён.", reply_markup=_keys_keyboard(keys))
    return API_LIST


async def to_main(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Возврат в главное меню админки"""
    await update.callback_query.answer()
    await update.callback_query.message.edit_text("🔐 Управление API ключами", reply_markup=_admin_menu_kb())
    return API_MENU


# === Conversation ===
api_keys_conv = ConversationHandler(
    name="api_keys_panel",
    entry_points=[
        CallbackQueryHandler(entry, pattern=r"^KEYS:START$"),
        CallbackQueryHandler(entry, pattern=r"^API:MENU$"),
    ],
    states={
        API_MENU: [
            CallbackQueryHandler(on_create, pattern=r"^API:CREATE$"),
            CallbackQueryHandler(on_list, pattern=r"^API:LIST:\d+$"),
        ],
        API_CREATE_WAIT_NAME: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, on_name_entered),
        ],
        API_LIST: [
            CallbackQueryHandler(on_detail, pattern=r"^API:DETAIL:.+"),
            CallbackQueryHandler(on_list, pattern=r"^API:PAGE:\d+$"),
            CallbackQueryHandler(to_main, pattern=r"^API:MENU$"),
        ],
        API_KEY_DETAIL: [
            CallbackQueryHandler(on_copy, pattern=r"^API:COPY:.+"),
            CallbackQueryHandler(on_delete, pattern=r"^API:DELETE:.+"),
            CallbackQueryHandler(on_list, pattern=r"^API:LIST:\d+$"),
            CallbackQueryHandler(to_main, pattern=r"^API:MENU$"),
        ],
    },
    fallbacks=[CommandHandler("api", entry)],
    allow_reentry=True,
)
