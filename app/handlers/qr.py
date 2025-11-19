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

from app.keyboards.qr import main_menu_kb, menu_back_kb, photo_step_kb, wallapop_type_kb, wallapop_lang_kb
from app.utils.state_stack import push_state, pop_state, clear_stack
from app.services.pdf import create_pdf, create_pdf_subito, create_pdf_wallapop, create_pdf_wallapop_email, create_pdf_wallapop_sms

logger = logging.getLogger(__name__)

# Состояния
QR_NAZVANIE, QR_PRICE, QR_NAME, QR_ADDRESS, QR_PHOTO, QR_URL, QR_LANG, QR_SELLER_NAME, QR_SELLER_PHOTO, QR_WALLAPOP_TYPE = range(
    10)


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


async def qr_entry_wallapop_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Меню выбора типа Wallapop"""
    context.user_data["service"] = "wallapop"
    clear_stack(context.user_data)
    await update.callback_query.answer()
    return await ask_wallapop_type(update, context)


async def ask_wallapop_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Запрос типа Wallapop"""
    push_state(context.user_data, QR_WALLAPOP_TYPE)
    text = "Выбери тип Wallapop:"

    if update.callback_query:
        await update.callback_query.message.edit_text(text, reply_markup=wallapop_type_kb())
    else:
        await update.message.reply_text(text, reply_markup=wallapop_type_kb())

    return QR_WALLAPOP_TYPE


async def qr_entry_wallapop_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Старт WALLAPOP LINK версии"""
    context.user_data["service"] = "wallapop"
    context.user_data["wallapop_type"] = "link"
    await update.callback_query.answer()
    return await ask_wallapop_lang(update, context, "link")


async def qr_entry_wallapop_email(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Старт WALLAPOP EMAIL версии"""
    context.user_data["service"] = "wallapop_email"
    context.user_data["wallapop_type"] = "email"
    await update.callback_query.answer()
    return await ask_wallapop_lang(update, context, "email")


async def qr_entry_wallapop_sms(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Старт WALLAPOP SMS версии"""
    context.user_data["service"] = "wallapop"
    context.user_data["wallapop_type"] = "sms"
    await update.callback_query.answer()
    return await ask_wallapop_lang(update, context, "sms")


async def ask_wallapop_lang(update: Update, context: ContextTypes.DEFAULT_TYPE, wallapop_type: str):
    """Запрос языка для Wallapop"""
    push_state(context.user_data, QR_LANG)
    text = f"Выбери язык для Wallapop ({'Email' if wallapop_type == 'email' else 'Link' if wallapop_type == 'link' else 'SMS'} версия):"

    reply_markup = wallapop_lang_kb(wallapop_type)

    if update.callback_query:
        await update.callback_query.message.edit_text(text, reply_markup=reply_markup)
    else:
        await update.message.reply_text(text, reply_markup=reply_markup)

    return QR_LANG


async def on_wallapop_lang_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка выбора языка для Wallapop Link"""
    lang = update.callback_query.data.replace("WALLAPOP_LANG_", "")

    if lang not in ['uk', 'es', 'it', 'fr']:
        await update.callback_query.answer("❌ Неправильный язык")
        return QR_LANG

    context.user_data["lang"] = lang
    await update.callback_query.answer(f"Выбран язык: {lang.upper()}")
    return await ask_nazvanie(update, context)


async def on_wallapop_email_lang_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка выбора языка для Wallapop Email"""
    lang = update.callback_query.data.replace("WALLAPOP_EMAIL_LANG_", "")

    if lang not in ['uk', 'es', 'it', 'fr']:
        await update.callback_query.answer("❌ Неправильный язык")
        return QR_LANG

    context.user_data["lang"] = lang
    await update.callback_query.answer(f"Выбран язык: {lang.upper()}")
    return await ask_nazvanie(update, context)


async def on_wallapop_sms_lang_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка выбора языка для Wallapop SMS"""
    lang = update.callback_query.data.replace("WALLAPOP_SMS_LANG_", "")

    if lang not in ['uk', 'es', 'it', 'fr']:
        await update.callback_query.answer("❌ Неправильный язык")
        return QR_LANG

    context.user_data["lang"] = lang
    await update.callback_query.answer(f"Выбран язык: {lang.upper()}")
    return await ask_nazvanie(update, context)


async def ask_nazvanie(update: Update, context: ContextTypes.DEFAULT_TYPE):
    push_state(context.user_data, QR_NAZVANIE)
    service = context.user_data.get("service", "marktplaats")
    wallapop_type = context.user_data.get("wallapop_type", "link")

    if service == "wallapop_email":
        text = "Введи название товара для Wallapop Email:"
    elif service == "wallapop" and wallapop_type == "sms":
        text = "Введи название товара для Wallapop SMS:"
    else:
        text = "Введи название товара:"

    await _edit_or_send(update, context, text)
    return QR_NAZVANIE


async def ask_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    push_state(context.user_data, QR_PRICE)
    await _edit_or_send(update, context, "Введи цену товара (пример: 99.99):")
    return QR_PRICE


async def ask_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    push_state(context.user_data, QR_NAME)
    await _edit_or_send(update, context, "Введи имя продавца (Name):")
    return QR_NAME


async def ask_address(update: Update, context: ContextTypes.DEFAULT_TYPE):
    push_state(context.user_data, QR_ADDRESS)
    await _edit_or_send(update, context, "Введи адрес (Address):")
    return QR_ADDRESS


async def ask_seller_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    push_state(context.user_data, QR_SELLER_NAME)
    await _edit_or_send(update, context, "Введи имя продавца для Wallapop Email:")
    return QR_SELLER_NAME


async def ask_seller_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    push_state(context.user_data, QR_SELLER_PHOTO)
    txt = "Отправь фото продавца (аватар) или нажми «Пропустить»:"
    if update.callback_query:
        await update.callback_query.message.edit_text(txt, reply_markup=photo_step_kb())
    else:
        await update.message.reply_text(txt, reply_markup=photo_step_kb())
    return QR_SELLER_PHOTO


async def ask_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    push_state(context.user_data, QR_PHOTO)
    txt = "Отправь фото товара или нажми «Пропустить»:"
    if update.callback_query:
        await update.callback_query.message.edit_text(txt, reply_markup=photo_step_kb())
    else:
        await update.message.reply_text(txt, reply_markup=photo_step_kb())
    return QR_PHOTO


async def ask_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    push_state(context.user_data, QR_URL)
    await _edit_or_send(update, context, "Введи URL для QR-кода:")
    return QR_URL


async def _edit_or_send(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
    kb = menu_back_kb()
    if getattr(update, "callback_query", None):
        await update.callback_query.message.edit_text(text, reply_markup=kb)
    else:
        await update.message.reply_text(text, reply_markup=kb)


# ---- Хендлеры шагов
async def on_nazvanie(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["nazvanie"] = (update.message.text or "").strip()
    return await ask_price(update, context)


async def on_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["price"] = (update.message.text or "").strip()
    service = context.user_data.get("service", "marktplaats")
    wallapop_type = context.user_data.get("wallapop_type", "link")

    if service == "subito":
        return await ask_name(update, context)
    elif service == "wallapop_email":
        return await ask_seller_name(update, context)
    else:
        return await ask_photo(update, context)


async def on_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["name"] = (update.message.text or "").strip()
    return await ask_address(update, context)


async def on_address(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["address"] = (update.message.text or "").strip()
    return await ask_photo(update, context)


async def on_seller_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["seller_name"] = (update.message.text or "").strip()
    return await ask_seller_photo(update, context)


async def on_seller_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.photo:
        photo_file = await update.message.photo[-1].get_file()
        photo_bytes = await photo_file.download_as_bytearray()
        context.user_data["seller_photo_bytes"] = photo_bytes
        return await ask_photo(update, context)

    await update.message.reply_text("Пожалуйста, отправь фото или нажми «Пропустить».")
    return QR_SELLER_PHOTO


async def on_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.photo:
        photo_file = await update.message.photo[-1].get_file()
        photo_bytes = await photo_file.download_as_bytearray()
        context.user_data["photo_bytes"] = photo_bytes

        service = context.user_data.get("service", "marktplaats")
        wallapop_type = context.user_data.get("wallapop_type", "link")

        if service == "wallapop_email":
            return await generate_wallapop_email(update, context)
        elif service == "wallapop" and wallapop_type == "link":
            return await generate_wallapop(update, context)
        elif service == "wallapop" and wallapop_type == "sms":
            return await generate_wallapop_sms(update, context)
        else:
            return await ask_url(update, context)

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
        photo_b64 = base64.b64encode(photo_bytes).decode('utf-8') if photo_bytes else None

        if service == "subito":
            image_data, _, _ = await asyncio.to_thread(
                create_pdf_subito, nazvanie, price, name, address, photo_b64, url
            )
        else:
            image_data, _, _ = await asyncio.to_thread(
                create_pdf, nazvanie, price, photo_b64, url
            )

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
    """Генерация Wallapop Link версии"""
    lang = context.user_data.get("lang", "")
    nazvanie = context.user_data.get("nazvanie", "")
    price = context.user_data.get("price", "")
    photo_bytes = context.user_data.get("photo_bytes")

    message = update.message if update.message else update.callback_query.message
    await message.reply_text(f"Обрабатываю данные для Wallapop Link {lang.upper()}…", reply_markup=menu_back_kb())

    try:
        photo_b64 = base64.b64encode(photo_bytes).decode('utf-8') if photo_bytes else None

        image_data, _, _ = await asyncio.to_thread(
            create_pdf_wallapop, lang, nazvanie, price, photo_b64
        )

        await context.bot.send_document(
            chat_id=message.chat_id,
            document=io.BytesIO(image_data),
            filename=f"wallapop_link_{lang}_{uuid.uuid4()}.png"
        )

        await message.reply_text("Готово!", reply_markup=main_menu_kb())
        clear_stack(context.user_data)
        return ConversationHandler.END

    except Exception as e:
        logger.exception("Ошибка генерации Wallapop Link")
        await message.reply_text(f"Ошибка: {e}", reply_markup=main_menu_kb())
        clear_stack(context.user_data)
        return ConversationHandler.END


async def generate_wallapop_email(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Генерация Wallapop Email версии"""
    lang = context.user_data.get("lang", "")
    nazvanie = context.user_data.get("nazvanie", "")
    price = context.user_data.get("price", "")
    seller_name = context.user_data.get("seller_name", "")
    photo_bytes = context.user_data.get("photo_bytes")
    seller_photo_bytes = context.user_data.get("seller_photo_bytes")

    message = update.message if update.message else update.callback_query.message
    await message.reply_text(f"Обрабатываю данные для Wallapop Email {lang.upper()}…", reply_markup=menu_back_kb())

    try:
        photo_b64 = base64.b64encode(photo_bytes).decode('utf-8') if photo_bytes else None
        seller_photo_b64 = base64.b64encode(seller_photo_bytes).decode('utf-8') if seller_photo_bytes else None

        image_data, _, _ = await asyncio.to_thread(
            create_pdf_wallapop_email, lang, nazvanie, price, photo_b64, seller_name, seller_photo_b64
        )

        await context.bot.send_document(
            chat_id=message.chat_id,
            document=io.BytesIO(image_data),
            filename=f"wallapop_email_{lang}_{uuid.uuid4()}.png"
        )

        await message.reply_text("Готово!", reply_markup=main_menu_kb())
        clear_stack(context.user_data)
        return ConversationHandler.END

    except Exception as e:
        logger.exception("Ошибка генерации Wallapop Email")
        await message.reply_text(f"Ошибка: {e}", reply_markup=main_menu_kb())
        clear_stack(context.user_data)
        return ConversationHandler.END


async def generate_wallapop_sms(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Генерация Wallapop SMS версии"""
    lang = context.user_data.get("lang", "")
    nazvanie = context.user_data.get("nazvanie", "")
    price = context.user_data.get("price", "")
    photo_bytes = context.user_data.get("photo_bytes")

    message = update.message if update.message else update.callback_query.message
    await message.reply_text(f"Обрабатываю данные для Wallapop SMS {lang.upper()}…", reply_markup=menu_back_kb())

    try:
        photo_b64 = base64.b64encode(photo_bytes).decode('utf-8') if photo_bytes else None

        image_data, _, _ = await asyncio.to_thread(
            create_pdf_wallapop_sms, lang, nazvanie, price, photo_b64
        )

        await context.bot.send_document(
            chat_id=message.chat_id,
            document=io.BytesIO(image_data),
            filename=f"wallapop_sms_{lang}_{uuid.uuid4()}.png"
        )

        await message.reply_text("Готово!", reply_markup=main_menu_kb())
        clear_stack(context.user_data)
        return ConversationHandler.END

    except Exception as e:
        logger.exception("Ошибка генерации Wallapop SMS")
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
    wallapop_type = context.user_data.get("wallapop_type", "link")

    if service == "wallapop_email":
        return await generate_wallapop_email(update, context)
    elif service == "wallapop" and wallapop_type == "link":
        return await generate_wallapop(update, context)
    elif service == "wallapop" and wallapop_type == "sms":
        return await generate_wallapop_sms(update, context)
    else:
        return await ask_url(update, context)


async def on_skip_seller_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    context.user_data["seller_photo_bytes"] = None
    return await ask_photo(update, context)


async def qr_back_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    prev_state = pop_state(context.user_data)

    if prev_state is None:
        return await qr_menu_cb(update, context)

    service = context.user_data.get("service", "marktplaats")
    wallapop_type = context.user_data.get("wallapop_type", "link")

    if prev_state == QR_WALLAPOP_TYPE:
        return await ask_wallapop_type(update, context)
    elif prev_state == QR_LANG:
        # Возврат к выбору типа Wallapop
        return await ask_wallapop_type(update, context)
    elif prev_state == QR_NAZVANIE:
        return await ask_nazvanie(update, context)
    elif prev_state == QR_PRICE:
        return await ask_price(update, context)
    elif prev_state == QR_NAME:
        return await ask_name(update, context)
    elif prev_state == QR_ADDRESS:
        return await ask_address(update, context)
    elif prev_state == QR_SELLER_NAME:
        return await ask_seller_name(update, context)
    elif prev_state == QR_SELLER_PHOTO:
        return await ask_seller_photo(update, context)
    elif prev_state == QR_PHOTO:
        return await ask_photo(update, context)
    elif prev_state == QR_URL:
        return await ask_url(update, context)


async def wallapop_back_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Назад в меню выбора типа Wallapop"""
    await update.callback_query.answer()
    # Очищаем состояние языка и возвращаемся к выбору типа
    pop_state(context.user_data)  # Убираем QR_LANG
    return await ask_wallapop_type(update, context)


# Conversation Handler
qr_conv = ConversationHandler(
    name="qr_flow",
    entry_points=[
        CallbackQueryHandler(qr_entry, pattern=r"^QR:START$"),
        CallbackQueryHandler(qr_entry_subito, pattern=r"^QR:SUBITO$"),
        CallbackQueryHandler(qr_entry_wallapop_menu, pattern=r"^QR:WALLAPOP_MENU$"),
    ],
    states={
        QR_WALLAPOP_TYPE: [
            CallbackQueryHandler(qr_entry_wallapop_link, pattern=r"^QR:WALLAPOP_LINK$"),
            CallbackQueryHandler(qr_entry_wallapop_email, pattern=r"^QR:WALLAPOP_EMAIL$"),
            CallbackQueryHandler(qr_entry_wallapop_sms, pattern=r"^QR:WALLAPOP_SMS$"),
            CallbackQueryHandler(qr_menu_cb, pattern=r"^QR:MENU$"),
            CallbackQueryHandler(qr_back_cb, pattern=r"^QR:BACK$")
        ],
        QR_LANG: [
            CallbackQueryHandler(on_wallapop_lang_callback, pattern=r"^WALLAPOP_LANG_"),
            CallbackQueryHandler(on_wallapop_email_lang_callback, pattern=r"^WALLAPOP_EMAIL_LANG_"),
            CallbackQueryHandler(on_wallapop_sms_lang_callback, pattern=r"^WALLAPOP_SMS_LANG_"),
            CallbackQueryHandler(qr_menu_cb, pattern=r"^QR:MENU$"),
            CallbackQueryHandler(wallapop_back_cb, pattern=r"^QR:WALLAPOP_BACK$"),
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
        QR_SELLER_NAME: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, on_seller_name),
            CallbackQueryHandler(qr_menu_cb, pattern=r"^QR:MENU$"),
            CallbackQueryHandler(qr_back_cb, pattern=r"^QR:BACK$")
        ],
        QR_SELLER_PHOTO: [
            MessageHandler(filters.PHOTO, on_seller_photo),
            CallbackQueryHandler(qr_menu_cb, pattern=r"^QR:MENU$"),
            CallbackQueryHandler(qr_back_cb, pattern=r"^QR:BACK$"),
            CallbackQueryHandler(on_skip_seller_photo, pattern=r"^QR:SKIP_PHOTO$")
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