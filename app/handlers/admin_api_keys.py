from telegram import Update
from telegram.error import BadRequest
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CallbackQueryHandler,
    MessageHandler,
    CommandHandler,
    filters,
)

from app.keyboards.admin_api_keys import get_admin_api_menu, get_api_keys_keyboard
from app.keyboards.common import with_menu_back
from app.services.apikey import generate_key, get_all_keys, delete_key
from app.config import CFG
from app.handlers.menu import start as show_main_menu
from app.utils.state_stack import push_state, pop_state, clear_stack

# Состояния
API_MENU, API_WAIT_NAME, API_LIST = range(3)


def _is_admin(update: Update) -> bool:
    uid = update.effective_user.id if update.effective_user else None
    return uid in getattr(CFG, "ADMIN_IDS", set())


async def _edit_or_send(update: Update, text: str, reply_markup=None):
    if update.callback_query:
        try:
            await update.callback_query.message.edit_text(text, reply_markup=reply_markup)
        except BadRequest as e:
            if "Message is not modified" not in str(e):
                raise
    else:
        await update.message.reply_text(text, reply_markup=reply_markup)


# ===== Вход и экраны =====

async def api_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Вход в раздел API-ключей (KEYS:START)."""
    if not _is_admin(update):
        if update.callback_query:
            await update.callback_query.answer()
        await _edit_or_send(update, "Доступ запрещён.")
        return ConversationHandler.END

    clear_stack(context.user_data)
    return await show_api_menu(update, context)


async def show_api_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Главный экран раздела API."""
    push_state(context.user_data, API_MENU)
    await _edit_or_send(update, "🔑 Управление API ключами", reply_markup=get_admin_api_menu())
    return API_MENU


async def ask_key_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Запрос названия для нового ключа."""
    push_state(context.user_data, API_WAIT_NAME)
    context.user_data["awaiting_key_name"] = True
    kb = with_menu_back([], back_data="API:BACK", menu_data="API:MENU")
    await _edit_or_send(update, "Введите название для нового ключа:", reply_markup=kb)
    return API_WAIT_NAME


async def show_key_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показ списка ключей."""
    push_state(context.user_data, API_LIST)
    keys = get_all_keys()
    if not keys:
        # Пусто — оставляем в меню API
        await _edit_or_send(update, "Нет активных API-ключей.", reply_markup=get_admin_api_menu())
        return API_MENU
    await _edit_or_send(update, "🔑 Список ключей:", reply_markup=get_api_keys_keyboard(keys))
    return API_LIST


# ===== Обработчики кнопок и ввода =====

async def on_generate_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return await ask_key_name(update, context)


async def on_list_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return await show_key_list(update, context)


async def on_delete_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Удаление ключа из списка (API:DELETE_<key>)."""
    data = update.callback_query.data
    key = data.replace("API:DELETE_", "", 1)
    delete_key(key)
    # Обновляем список (или меню, если стал пустым)
    return await show_key_list(update, context)


async def on_key_name_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ввод названия для нового ключа (сообщение)."""
    if not context.user_data.get("awaiting_key_name"):
        return API_MENU
    name = (update.message.text or "").strip()
    key = generate_key(name)
    context.user_data["awaiting_key_name"] = False
    # Показываем результат + меню API
    await update.message.reply_text(
        f"✅ Новый API ключ:\n\n<b>{key}</b>\nНазвание: {name}",
        parse_mode="HTML",
        reply_markup=get_admin_api_menu()
    )
    clear_stack(context.user_data)
    return API_MENU


async def api_back_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Кнопка ⬅️ Назад — как в QR: возвращаемся по стеку."""
    await update.callback_query.answer()
    pop_state(context.user_data)  # снять текущий
    prev = pop_state(context.user_data)  # взять предыдущий
    if prev is None or prev == API_MENU:
        return await show_api_menu(update, context)
    if prev == API_LIST:
        return await show_key_list(update, context)
    if prev == API_WAIT_NAME:
        return await ask_key_name(update, context)
    # на всякий — в меню
    return await show_api_menu(update, context)


async def api_menu_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Кнопка 🏠 Главное меню."""
    await update.callback_query.answer("Возврат в главное меню")
    clear_stack(context.user_data)
    await show_main_menu(update, context)
    return ConversationHandler.END


# ===== Конвейер (как qr_conv) =====

api_keys_conv = ConversationHandler(
    name="api_keys_flow",
    entry_points=[
        CallbackQueryHandler(api_entry, pattern=r"^KEYS:START$"),
    ],
    states={
        API_MENU: [
            CallbackQueryHandler(on_generate_cb, pattern=r"^API:GEN$"),
            CallbackQueryHandler(on_list_cb, pattern=r"^API:LIST$"),
            CallbackQueryHandler(api_menu_cb, pattern=r"^API:MENU$"),
        ],
        API_WAIT_NAME: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, on_key_name_input),
            CallbackQueryHandler(api_back_cb, pattern=r"^API:BACK$"),
            CallbackQueryHandler(api_menu_cb, pattern=r"^API:MENU$"),
        ],
        API_LIST: [
            CallbackQueryHandler(on_delete_cb, pattern=r"^API:DELETE_.+"),
            CallbackQueryHandler(api_back_cb, pattern=r"^API:BACK$"),
            CallbackQueryHandler(api_menu_cb, pattern=r"^API:MENU$"),
        ],
    },
    fallbacks=[CommandHandler("start", api_menu_cb)],
    allow_reentry=True,
)
