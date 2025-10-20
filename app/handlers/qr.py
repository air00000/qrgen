import os
import uuid
import logging

import asyncio

from telegram import InputFile, Update
from telegram.ext import (
    ContextTypes, ConversationHandler, CallbackQueryHandler,
    MessageHandler, CommandHandler, filters
)
from app.keyboards.qr import main_menu_kb, menu_back_kb, photo_step_kb, template_step_kb
from app.utils.state_stack import push_state, pop_state, clear_stack
from app.utils.io import ensure_dirs, cleanup_paths
from app.services.render import generate_listing_image

logger = logging.getLogger(__name__)

QR_TEMPLATE, QR_NAZVANIE, QR_PRICE, QR_NAME, QR_ADDRESS, QR_PHOTO, QR_URL = range(7)

async def qr_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ensure_dirs()
    clear_stack(context.user_data)
    await update.callback_query.answer()
    await ask_template(update, context)
    return QR_TEMPLATE


async def ask_template(update: Update, context: ContextTypes.DEFAULT_TYPE):
    push_state(context.user_data, QR_TEMPLATE)
    context.user_data.pop("template", None)
    context.user_data.pop("name", None)
    context.user_data.pop("address", None)
    old_photo = context.user_data.pop("photo_path", None)
    cleanup_paths(old_photo)
    text = "Выбери шаблон объявления:"
    kb = template_step_kb()
    if update.callback_query:
        await update.callback_query.message.edit_text(text, reply_markup=kb)
    else:
        await update.message.reply_text(text, reply_markup=kb)

async def on_template(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    data = update.callback_query.data or ""
    if data.endswith("MARKTPLAATS"):
        context.user_data["template"] = "marktplaats"
    elif data.endswith("SUBITO"):
        context.user_data["template"] = "subito"
    else:
        context.user_data["template"] = "marktplaats"
    return await ask_nazvanie(update, context) or QR_NAZVANIE

async def ask_nazvanie(update: Update, context: ContextTypes.DEFAULT_TYPE):
    push_state(context.user_data, QR_NAZVANIE)
    msg = "Введи название товара:"
    await _send(update, context, msg)

async def ask_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    push_state(context.user_data, QR_PRICE)
    await _edit_or_send(update, context, "Введи цену товара (пример: 99.99):")

async def ask_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    push_state(context.user_data, QR_NAME)
    text = "Введи имя продавца (можно '-' чтобы пропустить):"
    await _edit_or_send(update, context, text)

async def ask_address(update: Update, context: ContextTypes.DEFAULT_TYPE):
    push_state(context.user_data, QR_ADDRESS)
    text = "Введи адрес или город (можно '-' чтобы пропустить):"
    await _edit_or_send(update, context, text)

async def ask_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    push_state(context.user_data, QR_PHOTO)
    txt = "Отправь фото товара или нажми «Пропустить»:"
    if update.callback_query:
        await update.callback_query.message.edit_text(txt, reply_markup=photo_step_kb())
    else:
        await update.message.reply_text(txt, reply_markup=photo_step_kb())


async def ask_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    push_state(context.user_data, QR_URL)
    await _edit_or_send(update, context, "Введи URL для QR-кода:")

async def _send(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
    kb = menu_back_kb()
    if update.callback_query:
        await update.callback_query.message.edit_text(text, reply_markup=kb)
    else:
        await update.message.reply_text(text, reply_markup=kb)

async def _edit_or_send(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
    kb = menu_back_kb()
    if update.callback_query:
        await update.callback_query.message.edit_text(text, reply_markup=kb)
    else:
        await update.message.reply_text(text, reply_markup=kb)

async def on_nazvanie(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["nazvanie"] = update.message.text.strip()
    return await ask_price(update, context) or QR_PRICE

async def on_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["price"] = update.message.text.strip()
    template = context.user_data.get("template", "marktplaats")
    if template == "subito":
        return await ask_name(update, context) or QR_NAME
    return await ask_photo(update, context) or QR_PHOTO

async def on_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").strip()
    if text.lower() in {"", "-", "нет", "no"}:
        context.user_data["name"] = ""
    else:
        context.user_data["name"] = text
    return await ask_address(update, context) or QR_ADDRESS

async def on_address(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").strip()
    if text.lower() in {"", "-", "нет", "no"}:
        context.user_data["address"] = ""
    else:
        context.user_data["address"] = text
    return await ask_photo(update, context) or QR_PHOTO

async def on_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.photo:
        photo_file = await update.message.photo[-1].get_file()
        tmp = os.path.join(
            context.application.bot_data.get("temp_dir", "."),
            f"temp_{uuid.uuid4()}.jpg"
        )
        await photo_file.download_to_drive(tmp)
        context.user_data["photo_path"] = tmp
        return await ask_url(update, context) or QR_URL

    await update.message.reply_text("Пожалуйста, отправь фото или нажми «Пропустить».")
    return QR_PHOTO


async def on_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    nazvanie = context.user_data["nazvanie"]
    price = context.user_data["price"]
    photo_path = context.user_data.get("photo_path")
    template = context.user_data.get("template", "marktplaats")
    name = context.user_data.get("name", "")
    address = context.user_data.get("address", "")
    url = update.message.text.strip()
    if not url.startswith("http"):
        url = "https://" + url

    await update.message.reply_text("Обрабатываю данные…", reply_markup=menu_back_kb())

    result = None
    try:
        result = await asyncio.to_thread(
            generate_listing_image,
            template,
            nazvanie,
            price,
            photo_path,
            url,
            name=name,
            address=address,
        )
        with open(result.path, "rb") as f:
            telegram_file = InputFile(f, filename=os.path.basename(result.path))
            await context.bot.send_photo(chat_id=update.message.chat_id, photo=telegram_file)
        await update.message.reply_text("PNG готов!", reply_markup=main_menu_kb())
        clear_stack(context.user_data)
        return ConversationHandler.END
    except Exception as e:
        logger.exception("Ошибка генерации")
        await update.message.reply_text(f"Ошибка: {e}", reply_markup=main_menu_kb())
        clear_stack(context.user_data)
        return ConversationHandler.END
    finally:
        cleanup_paths(photo_path)
        if result:
            cleanup_paths(result.path, result.processed_photo_path, result.qr_path)


# Кнопки меню/назад
async def qr_menu_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer("Возврат в главное меню")
    clear_stack(context.user_data)
    from app.handlers.menu import start
    await start(update, context)
    return ConversationHandler.END

async def on_skip_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    context.user_data["photo_path"] = None
    return await ask_url(update, context) or QR_URL


async def qr_back_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    last = pop_state(context.user_data)  # текущий
    prev = pop_state(context.user_data)  # предыдущий
    if prev is None:
        # нет истории — в меню
        return await qr_menu_cb(update, context)
    # Вернемся к нужному вопросу:
    if prev == QR_TEMPLATE:
        await ask_template(update, context)
        return QR_TEMPLATE
    if prev == QR_NAZVANIE:
        await ask_nazvanie(update, context)
        return QR_NAZVANIE
    if prev == QR_PRICE:
        await ask_price(update, context)
        return QR_PRICE
    if prev == QR_NAME:
        await ask_name(update, context)
        return QR_NAME
    if prev == QR_ADDRESS:
        await ask_address(update, context)
        return QR_ADDRESS
    if prev == QR_PHOTO:
        await ask_photo(update, context)
        return QR_PHOTO
    if prev == QR_URL:
        await ask_url(update, context)
        return QR_URL

qr_conv = ConversationHandler(
    name="qr_flow",
    entry_points=[CallbackQueryHandler(qr_entry, pattern=r"^QR:START$")],
    states={
        QR_TEMPLATE: [
            CallbackQueryHandler(on_template, pattern=r"^QR:TEMPLATE:(?:MARKTPLAATS|SUBITO)$"),
            CallbackQueryHandler(qr_menu_cb, pattern=r"^QR:MENU$"),
            CallbackQueryHandler(qr_back_cb, pattern=r"^QR:BACK$"),
        ],
        QR_NAZVANIE: [MessageHandler(filters.TEXT & ~filters.COMMAND, on_nazvanie),
                       CallbackQueryHandler(qr_menu_cb, pattern=r"^QR:MENU$"),
                       CallbackQueryHandler(qr_back_cb, pattern=r"^QR:BACK$")],
        QR_PRICE:    [MessageHandler(filters.TEXT & ~filters.COMMAND, on_price),
                       CallbackQueryHandler(qr_menu_cb, pattern=r"^QR:MENU$"),
                       CallbackQueryHandler(qr_back_cb, pattern=r"^QR:BACK$")],
        QR_NAME:     [MessageHandler(filters.TEXT & ~filters.COMMAND, on_name),
                       CallbackQueryHandler(qr_menu_cb, pattern=r"^QR:MENU$"),
                       CallbackQueryHandler(qr_back_cb, pattern=r"^QR:BACK$")],
        QR_ADDRESS:  [MessageHandler(filters.TEXT & ~filters.COMMAND, on_address),
                       CallbackQueryHandler(qr_menu_cb, pattern=r"^QR:MENU$"),
                       CallbackQueryHandler(qr_back_cb, pattern=r"^QR:BACK$")],
        QR_PHOTO: [
            MessageHandler(filters.PHOTO, on_photo),
            CallbackQueryHandler(qr_menu_cb, pattern=r"^QR:MENU$"),
            CallbackQueryHandler(qr_back_cb, pattern=r"^QR:BACK$"),
            CallbackQueryHandler(on_skip_photo, pattern=r"^QR:SKIP_PHOTO$"),
        ],

        QR_URL:      [MessageHandler(filters.TEXT & ~filters.COMMAND, on_url),
                       CallbackQueryHandler(qr_menu_cb, pattern=r"^QR:MENU$"),
                       CallbackQueryHandler(qr_back_cb, pattern=r"^QR:BACK$")],
    },
    fallbacks=[CommandHandler("start", qr_menu_cb)],
    allow_reentry=True,
)
