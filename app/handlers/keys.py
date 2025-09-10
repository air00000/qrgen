# app/handlers/keys.py
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler, CallbackQueryHandler, MessageHandler, filters
from app.keyboards.keys import keys_menu_kb
from app.keyboards.qr import main_menu_kb
from app.services.keystore import list_keys, add_key, remove_key
from app.config import CFG

ADD_WAIT, DEL_WAIT = range(2)

def _is_admin(update: Update) -> bool:
    uid = (update.effective_user.id if update.effective_user else None)
    return uid in getattr(CFG, "ADMIN_IDS", set())

async def keys_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_admin(update):
        if update.callback_query:
            await update.callback_query.answer("Только для админов", show_alert=True)
        else:
            await update.message.reply_text("Только для админов")
        return ConversationHandler.END
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.message.edit_text("Управление API-ключами:", reply_markup=keys_menu_kb())
    else:
        await update.message.reply_text("Управление API-ключами:", reply_markup=keys_menu_kb())

async def keys_menu_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await keys_entry(update, context)

async def back_to_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from app.handlers.menu import start
    await start(update, context)
    return ConversationHandler.END

async def add_key_btn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    # Предложить: сгенерировать автоматически или ввести вручную
    await update.callback_query.message.edit_text(
        "Введи ключ вручную или отправь «генерировать», чтобы сгенерировать автоматически."
    )
    return ADD_WAIT

async def on_add_key(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = (update.message.text or "").strip()
    if txt.lower().startswith("ген"):
        k = add_key(path=getattr(CFG, "KEYS_PATH", "data/api_keys.json"))
        await update.message.reply_text(f"✅ Ключ сгенерирован:\n`{k}`", parse_mode="Markdown", reply_markup=keys_menu_kb())
    else:
        k = add_key(txt, path=getattr(CFG, "KEYS_PATH", "data/api_keys.json"))
        await update.message.reply_text(f"✅ Ключ добавлен:\n`{k}`", parse_mode="Markdown", reply_markup=keys_menu_kb())
    return ConversationHandler.END

async def del_key_btn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await update.callback_query.message.edit_text("Отправь точный ключ, который нужно удалить.")
    return DEL_WAIT

async def on_del_key(update: Update, context: ContextTypes.DEFAULT_TYPE):
    k = (update.message.text or "").strip()
    ok = remove_key(k, path=getattr(CFG, "KEYS_PATH", "data/api_keys.json"))
    if ok:
        await update.message.reply_text("🗑 Ключ удалён.", reply_markup=keys_menu_kb())
    else:
        await update.message.reply_text("Не найден такой ключ.", reply_markup=keys_menu_kb())
    return ConversationHandler.END

async def list_keys_btn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    keys = list_keys(path=getattr(CFG, "KEYS_PATH", "data/api_keys.json"))
    if not keys:
        txt = "Ключей пока нет."
    else:
        txt = "Текущие ключи:\n" + "\n".join(f"• `{k}`" for k in keys)
    await update.callback_query.message.edit_text(txt, parse_mode="Markdown", reply_markup=keys_menu_kb())

keys_conv = ConversationHandler(
    name="keys_flow",
    entry_points=[CallbackQueryHandler(keys_entry, pattern=r"^KEYS:START$")],
    states={
        ADD_WAIT: [MessageHandler(filters.TEXT & ~filters.COMMAND, on_add_key)],
        DEL_WAIT: [MessageHandler(filters.TEXT & ~filters.COMMAND, on_del_key)],
    },
    fallbacks=[CallbackQueryHandler(back_to_menu, pattern=r"^KEYS:MENU$")],
    allow_reentry=True,
)

# маршрутизация кнопок внутри раздела
extra_handlers = [
    CallbackQueryHandler(keys_menu_cb, pattern=r"^KEYS:MENU$"),
    CallbackQueryHandler(back_to_menu, pattern=r"^KEYS:BACK$"),
    CallbackQueryHandler(add_key_btn, pattern=r"^KEYS:ADD$"),
    CallbackQueryHandler(del_key_btn, pattern=r"^KEYS:DEL$"),
    CallbackQueryHandler(list_keys_btn, pattern=r"^KEYS:LIST$"),
]
