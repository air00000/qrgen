# app/handlers/admin_api_keys.py

from telegram import Update
from telegram.ext import CallbackContext, CallbackQueryHandler, MessageHandler, filters

from app.keyboards.admin_api_keys import get_admin_api_menu, get_api_keys_keyboard
from app.services.apikey import generate_key, get_all_keys, delete_key
from app.config import CFG


async def admin_api_menu(update: Update, context: CallbackContext):
    if update.effective_user.id not in CFG.ADMIN_IDS:
        if update.message:
            await update.message.reply_text("Доступ запрещен.")
        else:
            await update.callback_query.message.reply_text("Доступ запрещен.")
        return

    text = "🔑 Управление API ключами"
    kb = get_admin_api_menu()

    if update.message:
        await update.message.reply_text(text, reply_markup=kb)
    else:
        await update.callback_query.message.edit_text(text, reply_markup=kb)

async def handle_api_callbacks(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()

    data = query.data

    if data == "api_generate":
        context.user_data["awaiting_key_name"] = True
        await query.message.reply_text("Введите название для нового ключа:")
    elif data == "api_list":
        keys = get_all_keys()
        if not keys:
            await query.message.reply_text("Нет активных API-ключей.")
        else:
            await query.message.reply_text("🔑 Список ключей:", reply_markup=get_api_keys_keyboard(keys))
    elif data == "api_back":
        await query.message.reply_text("Назад", reply_markup=get_admin_api_menu())
    elif data.startswith("api_delete_"):
        key = data.replace("api_delete_", "")
        if delete_key(key):
            await query.message.reply_text("Ключ удалён ✅")
        else:
            await query.message.reply_text("Ошибка удаления ❌")
        keys = get_all_keys()
        await query.message.reply_text("Обновлённый список:", reply_markup=get_api_keys_keyboard(keys))
    elif data == "admin_back":
        await query.message.reply_text("🔙 Главное меню")


async def handle_key_name_input(update: Update, context: CallbackContext):
    if context.user_data.get("awaiting_key_name"):
        name = update.message.text
        key = generate_key(name)
        await update.message.reply_text(f"✅ Новый API ключ:\n\n<b>{key}</b>\nНазвание: {name}", parse_mode='HTML')
        context.user_data["awaiting_key_name"] = False
