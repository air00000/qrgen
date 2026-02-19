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

from app.keyboards.admin_api_keys import (
    get_admin_api_menu,
    get_api_keys_list_keyboard,
    get_key_actions_keyboard,
    get_delete_confirm_keyboard
)
from app.services.apikey import generate_key, get_all_keys, delete_key, update_key_name, get_key_name
from app.config import CFG
from app.handlers.menu import start as show_main_menu
from app.utils.state_stack import push_state, pop_state, clear_stack

# Состояния
API_MENU, API_WAIT_NAME, API_LIST, API_EDIT_MENU, API_DELETE_MENU, API_VIEW_KEY, API_WAIT_NEW_NAME = range(7)


def _is_admin(update: Update) -> bool:
    uid = update.effective_user.id if update.effective_user else None
    return uid in getattr(CFG, "ADMIN_IDS", set())


async def _edit_or_send(update: Update, text: str, reply_markup=None, parse_mode="HTML"):
    if update.callback_query:
        try:
            await update.callback_query.message.edit_text(text, reply_markup=reply_markup, parse_mode=parse_mode)
        except BadRequest as e:
            if "Message is not modified" not in str(e):
                raise
    else:
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode=parse_mode)


# ===== Основные экраны =====

async def api_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Вход в раздел API ключей"""
    if not _is_admin(update):
        await update.callback_query.answer("Доступ запрещён", show_alert=True)
        return ConversationHandler.END

    await update.callback_query.answer()
    clear_stack(context.user_data)
    return await show_api_menu(update, context)


async def show_api_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Главное меню API"""
    push_state(context.user_data, API_MENU)
    await _edit_or_send(update, "🔑 <b>Управление API ключами</b>\n\nВыберите действие:",
                        reply_markup=get_admin_api_menu())
    return API_MENU


async def ask_key_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Запрос названия для нового ключа"""
    push_state(context.user_data, API_WAIT_NAME)
    context.user_data["awaiting_key_name"] = True
    await _edit_or_send(update, "📝 Введите название для нового API ключа:")
    return API_WAIT_NAME


async def show_keys_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать список всех ключей"""
    push_state(context.user_data, API_LIST)
    keys = get_all_keys()
    if not keys:
        await _edit_or_send(update, "📭 Нет активных API ключей.")
        return await show_api_menu(update, context)

    await _edit_or_send(update, f"📋 <b>Список API ключей</b> ({len(keys)}):",
                        reply_markup=get_api_keys_list_keyboard(keys, "API:VIEW_"))
    return API_LIST


async def show_edit_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Меню редактирования"""
    push_state(context.user_data, API_EDIT_MENU)
    keys = get_all_keys()
    if not keys:
        await _edit_or_send(update, "📭 Нет ключей для редактирования.")
        return await show_api_menu(update, context)

    await _edit_or_send(update, "✏️ <b>Выберите ключ для редактирования:</b>",
                        reply_markup=get_api_keys_list_keyboard(keys, "API:EDIT_"))
    return API_EDIT_MENU


async def show_delete_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Меню удаления"""
    push_state(context.user_data, API_DELETE_MENU)
    keys = get_all_keys()
    if not keys:
        await _edit_or_send(update, "📭 Нет ключей для удаления.")
        return await show_api_menu(update, context)

    await _edit_or_send(update, "🗑️ <b>Выберите ключ для удаления:</b>",
                        reply_markup=get_api_keys_list_keyboard(keys, "API:DELETE_"))
    return API_DELETE_MENU


async def show_key_details(update: Update, context: ContextTypes.DEFAULT_TYPE, key: str):
    """Показать детали ключа"""
    push_state(context.user_data, API_VIEW_KEY)
    key_name = get_key_name(key)

    if not key_name:
        await _edit_or_send(update, "❌ Ключ не найден.")
        return await show_api_menu(update, context)

    context.user_data["current_key"] = key

    text = (
        f"🔑 <b>Информация о ключе</b>\n\n"
        f"<b>Название:</b> {key_name}\n"
        f"<b>Ключ:</b> <code>{key}</code>\n"
        f"<b>Статус:</b> ✅ Активен"
    )
    await _edit_or_send(update, text, reply_markup=get_key_actions_keyboard(key))
    return API_VIEW_KEY


# ===== Обработчики действий =====

async def on_generate_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    return await ask_key_name(update, context)


async def on_list_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    return await show_keys_list(update, context)


async def on_edit_menu_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    return await show_edit_menu(update, context)


async def on_delete_menu_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    return await show_delete_menu(update, context)


async def on_view_key_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Просмотр ключа"""
    data = update.callback_query.data
    key = data.replace("API:VIEW_", "", 1)
    await update.callback_query.answer()
    return await show_key_details(update, context, key)


async def on_edit_key_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Редактирование ключа"""
    data = update.callback_query.data
    key = data.replace("API:EDIT_", "", 1)
    await update.callback_query.answer()
    return await show_key_details(update, context, key)


async def on_delete_key_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Удаление ключа"""
    data = update.callback_query.data
    key = data.replace("API:DELETE_", "", 1)

    key_name = get_key_name(key)
    if not key_name:
        await update.callback_query.answer("❌ Ключ не найден")
        return await show_delete_menu(update, context)

    await update.callback_query.answer()

    text = (
        f"🗑️ <b>Подтвердите удаление</b>\n\n"
        f"<b>Ключ:</b> {key_name}\n"
        f"<code>{key}</code>\n\n"
        f"⚠️ Это действие нельзя отменить!"
    )
    await _edit_or_send(update, text, reply_markup=get_delete_confirm_keyboard(key))
    return API_DELETE_MENU


async def on_edit_name_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Изменение названия ключа"""
    data = update.callback_query.data
    key = data.replace("API:EDIT_NAME_", "", 1)

    context.user_data["current_key"] = key
    context.user_data["awaiting_new_name"] = True
    push_state(context.user_data, API_WAIT_NEW_NAME)

    key_name = get_key_name(key)
    await update.callback_query.answer()

    text = f"✏️ Введите новое название для ключа <b>{key_name}</b>:"
    await _edit_or_send(update, text)
    return API_WAIT_NEW_NAME


async def on_delete_confirm_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Подтверждение удаления"""
    data = update.callback_query.data
    key = data.replace("API:DELETE_CONFIRM_", "", 1)

    key_name = get_key_name(key)
    if delete_key(key):
        await update.callback_query.answer("✅ Ключ удалён")
        await _edit_or_send(update, f"✅ Ключ <b>{key_name}</b> успешно удалён.",
                            reply_markup=get_admin_api_menu())
    else:
        await update.callback_query.answer("❌ Ошибка удаления")
        await _edit_or_send(update, "❌ Ошибка при удалении ключа.",
                            reply_markup=get_admin_api_menu())
    return API_MENU


# ===== Обработчики ввода =====

async def on_key_name_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка ввода названия для нового ключа"""
    if not context.user_data.get("awaiting_key_name"):
        return API_MENU

    name = (update.message.text or "").strip()
    if not name:
        await update.message.reply_text("❌ Название не может быть пустым.")
        return API_WAIT_NAME

    key = generate_key(name)
    context.user_data["awaiting_key_name"] = False

    text = (
        f"✅ <b>Новый API ключ создан</b>\n\n"
        f"<b>Название:</b> {name}\n"
        f"<b>Ключ:</b> <code>{key}</code>\n\n"
        f"⚠️ <i>Сохраните этот ключ, он больше не будет показан!</i>"
    )
    await update.message.reply_text(text, parse_mode="HTML", reply_markup=get_admin_api_menu())
    clear_stack(context.user_data)
    return API_MENU


async def on_new_name_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка ввода нового названия"""
    if not context.user_data.get("awaiting_new_name"):
        return API_VIEW_KEY

    new_name = (update.message.text or "").strip()
    key = context.user_data.get("current_key")

    if not new_name:
        await update.message.reply_text("❌ Название не может быть пустым.")
        return API_WAIT_NEW_NAME

    if update_key_name(key, new_name):
        context.user_data["awaiting_new_name"] = False
        await update.message.reply_text(
            f"✅ Название ключа изменено на: <b>{new_name}</b>",
            parse_mode="HTML",
            reply_markup=get_admin_api_menu()
        )
        clear_stack(context.user_data)
        return API_MENU
    else:
        await update.message.reply_text(
            "❌ Ошибка при изменении названия ключа.",
            reply_markup=get_admin_api_menu()
        )
        return API_MENU


# ===== Навигация =====

async def api_menu_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Кнопка Главное меню"""
    await update.callback_query.answer("Возврат в главное меню")
    clear_stack(context.user_data)
    await show_main_menu(update, context)
    return ConversationHandler.END


async def api_back_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Кнопка Назад для API keys flow"""
    await update.callback_query.answer()

    # Извлекаем текущее состояние и получаем предыдущее
    pop_state(context.user_data)
    prev_state = pop_state(context.user_data)

    if prev_state is None or prev_state == API_MENU:
        return await show_api_menu(update, context)
    elif prev_state == API_LIST:
        return await show_keys_list(update, context)
    elif prev_state == API_EDIT_MENU:
        return await show_edit_menu(update, context)
    elif prev_state == API_DELETE_MENU:
        return await show_delete_menu(update, context)
    elif prev_state == API_VIEW_KEY:
        key = context.user_data.get("current_key")
        if key:
            return await show_key_details(update, context, key)
        else:
            return await show_api_menu(update, context)
    elif prev_state == API_WAIT_NAME:
        return await ask_key_name(update, context)
    elif prev_state == API_WAIT_NEW_NAME:
        key = context.user_data.get("current_key")
        if key:
            return await show_key_details(update, context, key)
        return await show_api_menu(update, context)
    else:
        return await show_api_menu(update, context)


# ===== Conversation Handler =====

api_keys_conv = ConversationHandler(
    name="api_keys_flow",
    entry_points=[
        CallbackQueryHandler(api_entry, pattern=r"^KEYS:START$"),
    ],
    states={
        API_MENU: [
            CallbackQueryHandler(on_generate_cb, pattern=r"^API:GEN$"),
            CallbackQueryHandler(on_list_cb, pattern=r"^API:LIST$"),
            CallbackQueryHandler(on_edit_menu_cb, pattern=r"^API:EDIT_MENU$"),
            CallbackQueryHandler(on_delete_menu_cb, pattern=r"^API:DELETE_MENU$"),
            CallbackQueryHandler(api_back_cb, pattern=r"^API:BACK$"),
            CallbackQueryHandler(api_menu_cb, pattern=r"^API:MENU$"),
        ],
        API_WAIT_NAME: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, on_key_name_input),
            CallbackQueryHandler(api_back_cb, pattern=r"^API:BACK$"),
            CallbackQueryHandler(api_menu_cb, pattern=r"^API:MENU$"),
        ],
        API_LIST: [
            CallbackQueryHandler(on_view_key_cb, pattern=r"^API:VIEW_.+"),
            CallbackQueryHandler(api_back_cb, pattern=r"^API:BACK$"),
            CallbackQueryHandler(api_menu_cb, pattern=r"^API:MENU$"),
        ],
        API_EDIT_MENU: [
            CallbackQueryHandler(on_edit_key_cb, pattern=r"^API:EDIT_.+"),
            CallbackQueryHandler(api_back_cb, pattern=r"^API:BACK$"),
            CallbackQueryHandler(api_menu_cb, pattern=r"^API:MENU$"),
        ],
        API_DELETE_MENU: [
            CallbackQueryHandler(on_delete_confirm_cb, pattern=r"^API:DELETE_CONFIRM_.+"),
            CallbackQueryHandler(on_delete_key_cb, pattern=r"^API:DELETE_(?!CONFIRM_).+"),
            CallbackQueryHandler(on_view_key_cb, pattern=r"^API:VIEW_.+"),
            CallbackQueryHandler(api_back_cb, pattern=r"^API:BACK$"),
            CallbackQueryHandler(api_menu_cb, pattern=r"^API:MENU$"),
        ],
        API_VIEW_KEY: [
            CallbackQueryHandler(on_edit_name_cb, pattern=r"^API:EDIT_NAME_.+"),
            CallbackQueryHandler(on_delete_key_cb, pattern=r"^API:DELETE_.+"),
            CallbackQueryHandler(api_back_cb, pattern=r"^API:BACK$"),
            CallbackQueryHandler(api_menu_cb, pattern=r"^API:MENU$"),
        ],
        API_WAIT_NEW_NAME: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, on_new_name_input),
            CallbackQueryHandler(api_back_cb, pattern=r"^API:BACK$"),
            CallbackQueryHandler(api_menu_cb, pattern=r"^API:MENU$"),
        ],
    },
    fallbacks=[CommandHandler("start", show_main_menu)],
    allow_reentry=True,
)