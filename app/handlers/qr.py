# app/handlers/qr.py
import os
import io
import uuid
import base64
import logging
import asyncio

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    ContextTypes, ConversationHandler, CallbackQueryHandler,
    MessageHandler, CommandHandler, filters
)

from app.keyboards.qr import main_menu_kb, menu_back_kb, photo_step_kb
from app.utils.state_stack import push_state, pop_state, clear_stack
from app.services.pdf import create_pdf, create_pdf_subito, create_pdf_wallapop

logger = logging.getLogger(__name__)

# Состояния: общий + доп. шаги для subito + wallapop
QR_NAZVANIE, QR_PRICE, QR_NAME, QR_ADDRESS, QR_PHOTO, QR_URL, QR_LANG = range(7)


async def qr_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Старт MARKTPLAATS"""
    context.user_data["service"] = "marktplaats"
    clear_stack(context.user_data)
    await update.callback_query.answer()
    await ask_nazvanie(update, context)
    return QR_NAZVANIE


async def qr_entry_subito(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Старт SUBITO"""
    context.user_data["service"] = "subito"
    clear_stack(context.user_data)
    await update.callback_query.answer()
    await ask_nazvanie(update, context)
    return QR_NAZVANIE


async def qr_entry_wallapop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Старт WALLAPOP"""
    context.user_data["service"] = "wallapop"
    clear_stack(context.user_data)
    await update.callback_query.answer()
    await ask_lang(update, context)
    return QR_LANG


async def ask_lang(update: Update, context: ContextTypes.DEFAULT_TYPE):
    push_state(context.user_data, QR_LANG)
    text = "Выбери язык Wallapop:"

    # Клавиатура с кнопками языков
    keyboard = [
        [
            InlineKeyboardButton("🇬🇧 UK", callback_data="WALLAPOP_LANG_uk"),
            InlineKeyboardButton("🇪🇸 ES", callback_data="WALLAPOP_LANG_es"),
        ],
        [
            InlineKeyboardButton("🇮🇹 IT", callback_data="WALLAPOP_LANG_it"),
            InlineKeyboardButton("🇫🇷 FR", callback_data="WALLAPOP_LANG_fr"),
        ],
        [
            InlineKeyboardButton("⬅️ Назад", callback_data="QR:BACK"),
        ]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    if update.callback_query:
        await update.callback_query.message.edit_text(text, reply_markup=reply_markup)
    else:
        await update.message.reply_text(text, reply_markup=reply_markup)


async def on_lang_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка выбора языка через кнопку"""
    lang = update.callback_query.data.replace("WALLAPOP_LANG_", "")

    if lang not in ['uk', 'es', 'it', 'fr']:
        await update.callback_query.answer("❌ Неправильный язык")
        return QR_LANG

    context.user_data["lang"] = lang
    await update.callback_query.answer(f"Выбран язык: {lang.upper()}")
    return await ask_nazvanie(update, context) or QR_NAZVANIE


async def ask_nazvanie(update: Update, context: ContextTypes.DEFAULT_TYPE):
    push_state(context.user_data, QR_NAZVANIE)
    await _edit_or_send(update, context, "Введи название товара:")


async def ask_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    push_state(context.user_data, QR_PRICE)
    await _edit_or_send(update, context, "Введи цену товара (пример: 99.99):")


async def ask_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    push_state(context.user_data, QR_NAME)
    await _edit_or_send(update, context, "Введи имя продавца (Name):")


async def ask_address(update: Update, context: ContextTypes.DEFAULT_TYPE):
    push_state(context.user_data, QR_ADDRESS)
    await _edit_or_send(update, context, "Введи адрес (Address):")


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


async def _edit_or_send(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
    kb = menu_back_kb()
    if getattr(update, "callback_query", None):
        await update.callback_query.message.edit_text(text, reply_markup=kb)
    else:
        await update.message.reply_text(text, reply_markup=kb)


# ---- Хендлеры шагов
async def on_nazvanie(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["nazvanie"] = (update.message.text or "").strip()
    return await ask_price(update, context) or QR_PRICE


async def on_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["price"] = (update.message.text or "").strip()
    if context.user_data.get("service") == "subito":
        return await ask_name(update, context) or QR_NAME
    return await ask_photo(update, context) or QR_PHOTO


async def on_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["name"] = (update.message.text or "").strip()
    return await ask_address(update, context) or QR_ADDRESS


async def on_address(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["address"] = (update.message.text or "").strip()
    return await ask_photo(update, context) or QR_PHOTO


async def on_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.photo:
        # Обрабатываем фото в памяти без сохранения на диск
        photo_file = await update.message.photo[-1].get_file()
        photo_bytes = await photo_file.download_as_bytearray()
        context.user_data["photo_bytes"] = photo_bytes

        service = context.user_data.get("service", "marktplaats")
        if service == "wallapop":
            # Для Wallapop не нужен URL, сразу генерируем
            return await generate_wallapop(update, context)
        else:
            return await ask_url(update, context) or QR_URL

    await update.message.reply_text("Пожалуйста, отправь фото или нажми «Пропустить».")
    return QR_PHOTO


async def on_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    nazvanie = context.user_data.get("nazvanie", "")
    price = context.user_data.get("price", "")
    name = context.user_data.get("name")
    address = context.user_data.get("address")
    photo_bytes = context.user_data.get("photo_bytes")
    url = (update.message.text or "").strip()
    if not url.startswith("http"):
        url = "https://" + url

    service = context.user_data.get("service", "marktplaats")
    await update.message.reply_text(f"Обрабатываю данные для {service}…", reply_markup=menu_back_kb())

    try:
        # Конвертируем bytes в base64 для передачи в сервис
        photo_b64 = base64.b64encode(photo_bytes).decode('utf-8') if photo_bytes else None

        if service == "subito":
            image_data, _, _ = await asyncio.to_thread(
                create_pdf_subito, nazvanie, price, name, address, photo_b64, url
            )
        else:
            image_data, _, _ = await asyncio.to_thread(
                create_pdf, nazvanie, price, photo_b64, url
            )

        # Отправляем bytes как документ
        await context.bot.send_document(
            chat_id=update.message.chat_id,
            document=io.BytesIO(image_data),
            filename=f"{service}_{uuid.uuid4()}.png"
        )

        await update.message.reply_text("Готово!", reply_markup=main_menu_kb())
        clear_stack(context.user_data)
        return ConversationHandler.END

    except Exception as e:
        logger.exception("Ошибка генерации")
        await update.message.reply_text(f"Ошибка: {e}", reply_markup=main_menu_kb())
        clear_stack(context.user_data)
        return ConversationHandler.END


async def generate_wallapop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Генерация Wallapop без URL"""
    lang = context.user_data.get("lang", "")
    nazvanie = context.user_data.get("nazvanie", "")
    price = context.user_data.get("price", "")
    photo_bytes = context.user_data.get("photo_bytes")

    message = update.message if update.message else update.callback_query.message
    await message.reply_text(f"Обрабатываю данные для Wallapop {lang.upper()}…", reply_markup=menu_back_kb())

    try:
        # Конвертируем bytes в base64 для передачи в сервис
        photo_b64 = base64.b64encode(photo_bytes).decode('utf-8') if photo_bytes else None

        image_data, _, _ = await asyncio.to_thread(
            create_pdf_wallapop, lang, nazvanie, price, photo_b64
        )

        await context.bot.send_document(
            chat_id=message.chat_id,
            document=io.BytesIO(image_data),
            filename=f"wallapop_{lang}_{uuid.uuid4()}.png"
        )

        await message.reply_text("Готово!", reply_markup=main_menu_kb())
        clear_stack(context.user_data)
        return ConversationHandler.END

    except Exception as e:
        logger.exception("Ошибка генерации Wallapop")
        await message.reply_text(f"Ошибка: {e}", reply_markup=main_menu_kb())
        clear_stack(context.user_data)
        return ConversationHandler.END


# ---- Навигация
async def qr_menu_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer("Возврат в главное меню")
    clear_stack(context.user_data)
    from app.handlers.menu import start
    await start(update, context)
    return ConversationHandler.END


async def on_skip_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    context.user_data["photo_bytes"] = None

    service = context.user_data.get("service", "marktplaats")
    if service == "wallapop":
        # Для Wallapop не нужен URL, сразу генерируем
        return await generate_wallapop(update, context)
    else:
        return await ask_url(update, context) or QR_URL


async def qr_back_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    _ = pop_state(context.user_data)
    prev = pop_state(context.user_data)
    if prev is None:
        return await qr_menu_cb(update, context)
    if prev == QR_LANG:
        await ask_lang(update, context);
        return QR_LANG
    if prev == QR_NAZVANIE:
        await ask_nazvanie(update, context);
        return QR_NAZVANIE
    if prev == QR_PRICE:
        await ask_price(update, context);
        return QR_PRICE
    if prev == QR_NAME:
        await ask_name(update, context);
        return QR_NAME
    if prev == QR_ADDRESS:
        await ask_address(update, context);
        return QR_ADDRESS
    if prev == QR_PHOTO:
        await ask_photo(update, context);
        return QR_PHOTO
    if prev == QR_URL:
        await ask_url(update, context);
        return QR_URL


# Conversation Handler
qr_conv = ConversationHandler(
    name="qr_flow",
    entry_points=[
        CallbackQueryHandler(qr_entry, pattern=r"^QR:START$"),
        CallbackQueryHandler(qr_entry_subito, pattern=r"^QR:SUBITO$"),
        CallbackQueryHandler(qr_entry_wallapop, pattern=r"^QR:WALLAPOP$"),
    ],
    states={
        QR_LANG: [
            CallbackQueryHandler(on_lang_callback, pattern=r"^WALLAPOP_LANG_.+$"),
            CallbackQueryHandler(qr_menu_cb, pattern=r"^QR:MENU$"),
            CallbackQueryHandler(qr_back_cb, pattern=r"^QR:BACK$")
        ],
        QR_NAZVANIE: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, on_nazvanie),
            CallbackQueryHandler(qr_menu_cb, pattern=r"^QR:MENU$"),
            CallbackQueryHandler(qr_back_cb, pattern=r"^QR:BACK$")
        ],
        QR_PRICE: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, on_price),
            CallbackQueryHandler(qr_menu_cb, pattern=r"^QR:MENU$"),
            CallbackQueryHandler(qr_back_cb, pattern=r"^QR:BACK$")
        ],
        QR_NAME: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, on_name),
            CallbackQueryHandler(qr_menu_cb, pattern=r"^QR:MENU$"),
            CallbackQueryHandler(qr_back_cb, pattern=r"^QR:BACK$")
        ],
        QR_ADDRESS: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, on_address),
            CallbackQueryHandler(qr_menu_cb, pattern=r"^QR:MENU$"),
            CallbackQueryHandler(qr_back_cb, pattern=r"^QR:BACK$")
        ],
        QR_PHOTO: [
            MessageHandler(filters.PHOTO, on_photo),
            CallbackQueryHandler(qr_menu_cb, pattern=r"^QR:MENU$"),
            CallbackQueryHandler(qr_back_cb, pattern=r"^QR:BACK$"),
            CallbackQueryHandler(on_skip_photo, pattern=r"^QR:SKIP_PHOTO$")
        ],
        QR_URL: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, on_url),
            CallbackQueryHandler(qr_menu_cb, pattern=r"^QR:MENU$"),
            CallbackQueryHandler(qr_back_cb, pattern=r"^QR:BACK$")
        ],
    },
    fallbacks=[CommandHandler("start", qr_menu_cb)],
    allow_reentry=True,
)