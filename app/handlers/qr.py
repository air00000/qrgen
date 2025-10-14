import os, uuid, datetime, base64, logging

import asyncio
from pathlib import Path

from telegram import Update
from telegram.ext import (
    ContextTypes, ConversationHandler, CallbackQueryHandler,
    MessageHandler, CommandHandler, filters
)
from app.keyboards.qr import main_menu_kb, menu_back_kb, photo_step_kb
from app.keyboards.common import with_menu_back
from app.utils.state_stack import push_state, pop_state, clear_stack
from app.utils.io import ensure_dirs, cleanup_paths
from app.services.pdf import create_marktplaats_image

logger = logging.getLogger(__name__)

QR_NAZVANIE, QR_PRICE, QR_PHOTO, QR_URL = range(4)

async def qr_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ensure_dirs()
    clear_stack(context.user_data)
    await update.callback_query.answer()
    await ask_nazvanie(update, context)
    return QR_NAZVANIE

async def ask_nazvanie(update: Update, context: ContextTypes.DEFAULT_TYPE):
    push_state(context.user_data, QR_NAZVANIE)
    msg = "Введи название товара:"
    await _send(update, context, msg)

async def ask_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    push_state(context.user_data, QR_PRICE)
    await _edit_or_send(update, context, "Введи цену товара (пример: 99.99):")

async def ask_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    push_state(context.user_data, QR_PHOTO)
    txt = "Отправь фото товара или нажми «Пропустить»:"
    if update.callback_query:
        await update.callback_query.message.edit_text(txt, reply_markup=photo_step_kb("QR"))
    else:
        await update.message.reply_text(txt, reply_markup=photo_step_kb("QR"))


async def ask_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    push_state(context.user_data, QR_URL)
    await _edit_or_send(update, context, "Введи URL для QR-кода:")

async def _send(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
    kb = menu_back_kb("QR")
    if update.callback_query:
        await update.callback_query.message.edit_text(text, reply_markup=kb)
    else:
        await update.message.reply_text(text, reply_markup=kb)

async def _edit_or_send(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
    kb = menu_back_kb("QR")
    if update.callback_query:
        await update.callback_query.message.edit_text(text, reply_markup=kb)
    else:
        await update.message.reply_text(text, reply_markup=kb)

async def on_nazvanie(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["nazvanie"] = update.message.text.strip()
    return await ask_price(update, context) or QR_PRICE

async def on_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["price"] = update.message.text.strip()
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
    url = update.message.text.strip()
    if not url.startswith("http"):
        url = "https://" + url

    await update.message.reply_text("Обрабатываю данные…", reply_markup=menu_back_kb("QR"))

    image_path = processed_photo_path = qr_path = None
    try:
        image_path, processed_photo_path, qr_path = await asyncio.to_thread(
            create_marktplaats_image, nazvanie, price, photo_path, url
        )
        with open(image_path, "rb") as f:
            await context.bot.send_document(
                chat_id=update.message.chat_id,
                document=f,
                filename=os.path.basename(image_path),
            )
        await update.message.reply_text("PNG готов!", reply_markup=main_menu_kb())
        clear_stack(context.user_data)
        Path(image_path).unlink()
        return ConversationHandler.END
    except Exception as e:
        logger.exception("Ошибка генерации")
        await update.message.reply_text(f"Ошибка: {e}", reply_markup=main_menu_kb())
        clear_stack(context.user_data)
        return ConversationHandler.END
    finally:
        cleanup_paths(photo_path, processed_photo_path, qr_path)
        # template удаляется внутри сервиса


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
    if prev == QR_NAZVANIE:
        await ask_nazvanie(update, context)
        return QR_NAZVANIE
    if prev == QR_PRICE:
        await ask_price(update, context)
        return QR_PRICE
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
        QR_NAZVANIE: [MessageHandler(filters.TEXT & ~filters.COMMAND, on_nazvanie),
                       CallbackQueryHandler(qr_menu_cb, pattern=r"^QR:MENU$"),
                       CallbackQueryHandler(qr_back_cb, pattern=r"^QR:BACK$")],
        QR_PRICE:    [MessageHandler(filters.TEXT & ~filters.COMMAND, on_price),
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
