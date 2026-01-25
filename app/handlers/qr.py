# app/handlers/qr.py
import os
import io
import uuid
import base64
import logging
import asyncio
from app.utils.async_helpers import (
    with_rate_limit,
    generate_with_queue,
    usage_stats
)


from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    ContextTypes, ConversationHandler, CallbackQueryHandler,
    MessageHandler, CommandHandler, filters
)

from app.keyboards.qr import main_menu_kb, menu_back_kb, photo_step_kb, wallapop_type_kb, wallapop_lang_kb, depop_type_kb
from app.utils.state_stack import push_state, pop_state, clear_stack
from app.services.pdf import create_pdf, create_pdf_subito
from app.services.wallapop_variants import WALLAPOP_VARIANTS

logger = logging.getLogger(__name__)

# Состояния
QR_NAZVANIE, QR_PRICE, QR_NAME, QR_ADDRESS, QR_PHOTO, QR_URL, QR_LANG, QR_SELLER_NAME, QR_SELLER_PHOTO, QR_WALLAPOP_TYPE, QR_DEPOP_TYPE = range(
    11)


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


async def qr_entry_2dehands(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Старт 2DEHANDS (нидерландский)"""
    context.user_data["service"] = "2dehands"
    context.user_data["lang"] = "nl"  # Нидерландский
    clear_stack(context.user_data)
    await update.callback_query.answer()
    return await ask_nazvanie(update, context)


async def qr_entry_2ememain(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Старт 2EMEMAIN (французский)"""
    context.user_data["service"] = "2ememain"
    context.user_data["lang"] = "fr"  # Французский
    clear_stack(context.user_data)
    await update.callback_query.answer()
    return await ask_nazvanie(update, context)


async def qr_entry_conto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Старт CONTO (Subito payment)"""
    context.user_data["service"] = "conto"
    clear_stack(context.user_data)
    await update.callback_query.answer()
    return await ask_nazvanie(update, context)


async def qr_entry_kleize(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Старт KLEIZE"""
    context.user_data["service"] = "kleize"
    clear_stack(context.user_data)
    await update.callback_query.answer()
    return await ask_nazvanie(update, context)


async def qr_entry_depop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Старт DEPOP (AU) QR"""
    context.user_data["service"] = "depop"
    context.user_data["depop_type"] = "qr"
    clear_stack(context.user_data)
    await update.callback_query.answer()
    return await ask_nazvanie(update, context)


async def qr_entry_depop_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Меню выбора типа Depop"""
    context.user_data["service"] = "depop"
    clear_stack(context.user_data)
    await update.callback_query.answer()
    return await ask_depop_type(update, context)


async def ask_depop_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Запрос типа Depop"""
    push_state(context.user_data, QR_DEPOP_TYPE)
    text = "Выбери тип Depop:"

    if update.callback_query:
        await update.callback_query.message.edit_text(text, reply_markup=depop_type_kb())
    else:
        await update.message.reply_text(text, reply_markup=depop_type_kb())

    return QR_DEPOP_TYPE


async def qr_entry_depop_qr(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Старт DEPOP QR версии"""
    context.user_data["service"] = "depop"
    context.user_data["depop_type"] = "qr"
    await update.callback_query.answer()
    return await ask_nazvanie(update, context)


async def qr_entry_depop_email_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Старт DEPOP Email Request версии"""
    context.user_data["service"] = "depop_email_request"
    context.user_data["depop_type"] = "email_request"
    await update.callback_query.answer()
    return await ask_nazvanie(update, context)


async def qr_entry_depop_email_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Старт DEPOP Email Confirm версии"""
    context.user_data["service"] = "depop_email_confirm"
    context.user_data["depop_type"] = "email_confirm"
    await update.callback_query.answer()
    return await ask_nazvanie(update, context)


async def qr_entry_depop_sms_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Старт DEPOP SMS Request версии"""
    context.user_data["service"] = "depop_sms_request"
    context.user_data["depop_type"] = "sms_request"
    await update.callback_query.answer()
    return await ask_nazvanie(update, context)


async def qr_entry_depop_sms_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Старт DEPOP SMS Confirm версии"""
    context.user_data["service"] = "depop_sms_confirm"
    context.user_data["depop_type"] = "sms_confirm"
    await update.callback_query.answer()
    return await ask_nazvanie(update, context)


async def depop_back_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Назад в меню выбора типа Depop"""
    await update.callback_query.answer()
    pop_state(context.user_data)
    return await ask_depop_type(update, context)


async def ask_wallapop_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Запрос типа Wallapop"""
    push_state(context.user_data, QR_WALLAPOP_TYPE)
    text = "Выбери тип Wallapop:"

    if update.callback_query:
        await update.callback_query.message.edit_text(text, reply_markup=wallapop_type_kb())
    else:
        await update.message.reply_text(text, reply_markup=wallapop_type_kb())

    return QR_WALLAPOP_TYPE


async def qr_entry_wallapop_email_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Старт WALLAPOP Email Request версии"""
    context.user_data["service"] = "wallapop"
    context.user_data["wallapop_type"] = "email_request"
    await update.callback_query.answer()
    return await ask_wallapop_lang(update, context, "email_request")


async def qr_entry_wallapop_phone_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Старт WALLAPOP Phone Request версии"""
    context.user_data["service"] = "wallapop"
    context.user_data["wallapop_type"] = "phone_request"
    await update.callback_query.answer()
    return await ask_wallapop_lang(update, context, "phone_request")


async def qr_entry_wallapop_email_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Старт WALLAPOP Email Payment версии"""
    context.user_data["service"] = "wallapop"
    context.user_data["wallapop_type"] = "email_payment"
    await update.callback_query.answer()
    return await ask_wallapop_lang(update, context, "email_payment")


async def qr_entry_wallapop_sms_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Старт WALLAPOP SMS Payment версии"""
    context.user_data["service"] = "wallapop"
    context.user_data["wallapop_type"] = "sms_payment"
    await update.callback_query.answer()
    return await ask_wallapop_lang(update, context, "sms_payment")


async def qr_entry_wallapop_qr(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Старт WALLAPOP QR версии"""
    context.user_data["service"] = "wallapop"
    context.user_data["wallapop_type"] = "qr"
    await update.callback_query.answer()
    return await ask_wallapop_lang(update, context, "qr")


async def ask_wallapop_lang(update: Update, context: ContextTypes.DEFAULT_TYPE, wallapop_type: str):
    """Запрос языка для Wallapop"""
    push_state(context.user_data, QR_LANG)
    wallapop_label = WALLAPOP_VARIANTS.get(wallapop_type, {}).get("label", wallapop_type)
    text = f"Выбери язык для Wallapop ({wallapop_label}):"

    reply_markup = wallapop_lang_kb(wallapop_type)

    if update.callback_query:
        await update.callback_query.message.edit_text(text, reply_markup=reply_markup)
    else:
        await update.message.reply_text(text, reply_markup=reply_markup)

    return QR_LANG


async def on_wallapop_lang_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка выбора языка для Wallapop"""
    lang = update.callback_query.data.replace("WALLAPOP_LANG_", "")

    if lang not in ['uk', 'es', 'it', 'fr', 'pr']:
        await update.callback_query.answer("❌ Неправильный язык")
        return QR_LANG

    context.user_data["lang"] = lang
    await update.callback_query.answer(f"Выбран язык: {lang.upper()}")
    return await ask_nazvanie(update, context)


async def ask_nazvanie(update: Update, context: ContextTypes.DEFAULT_TYPE):
    push_state(context.user_data, QR_NAZVANIE)
    service = context.user_data.get("service", "marktplaats")
    wallapop_type = context.user_data.get("wallapop_type", "email_request")

    if service == "wallapop":
        wallapop_label = WALLAPOP_VARIANTS.get(wallapop_type, {}).get("label", wallapop_type)
        text = f"Введи название товара для Wallapop ({wallapop_label}):"
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
    await _edit_or_send(update, context, "Введи имя продавца:")
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

    if service == "conto":
        # Для Conto идем сразу к генерации (нет фото и URL)
        return await on_url(update, context)
    elif service == "subito":
        return await ask_name(update, context)
    elif service == "depop":
        # Для Depop QR нужен seller_name
        return await ask_seller_name(update, context)
    elif service in ["depop_email_request", "depop_email_confirm", "depop_sms_request", "depop_sms_confirm"]:
        # Для Depop вариантов (без QR) - только фото
        return await ask_photo(update, context)
    elif service == "wallapop":
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
    service = context.user_data.get("service", "")
    
    if update.message.photo:
        photo_file = await update.message.photo[-1].get_file()
        photo_bytes = await photo_file.download_as_bytearray()
        context.user_data["seller_photo_bytes"] = photo_bytes
        logger.info(f"✅ Аватар получен: {len(photo_bytes)} bytes")
        
        # Для Depop и Wallapop идем к фото товара
        return await ask_photo(update, context)

    await update.message.reply_text("Пожалуйста, отправь фото или нажми «Пропустить».")
    return QR_SELLER_PHOTO


async def on_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.photo:
        photo_file = await update.message.photo[-1].get_file()
        photo_bytes = await photo_file.download_as_bytearray()
        context.user_data["photo_bytes"] = photo_bytes
        logger.info(f"✅ Фото получено: {len(photo_bytes)} bytes")

        service = context.user_data.get("service", "marktplaats")
        wallapop_type = context.user_data.get("wallapop_type", "email_request")

        if service in ["2dehands", "2ememain"]:
            return await ask_url(update, context)
        elif service == "wallapop":
            if wallapop_type == "qr":
                return await ask_url(update, context)
            return await generate_wallapop_variant(update, context)
        elif service in ["depop_email_request", "depop_email_confirm", "depop_sms_request", "depop_sms_confirm"]:
            return await generate_depop_variant(update, context)
        else:
            return await ask_url(update, context)

    await update.message.reply_text("Пожалуйста, отправь фото или нажми «Пропустить».")
    return QR_PHOTO


@with_rate_limit
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
        logger.info(f"📸 Генерация для {service}: фото={'есть (' + str(len(photo_b64)) + ' символов)' if photo_b64 else 'нет'}, название={nazvanie}, цена={price}")

        if service == "conto":
            # Импортируем функцию для Conto
            from app.services.conto import create_conto_image
            
            try:
                price_float = float(price)
            except ValueError:
                price_float = 0.0
            
            executor = context.application.bot_data.get("executor")
            image_data = await generate_with_queue(executor, 
                create_conto_image, nazvanie, price_float
            )
        elif service == "kleize":
            # Импортируем функцию для Kleize
            from app.services.kleize import create_kleize_image
            
            try:
                price_float = float(price)
            except ValueError:
                price_float = 0.0
            
            executor = context.application.bot_data.get("executor")
            image_data = await generate_with_queue(executor, 
                create_kleize_image, nazvanie, price_float, photo_b64, url
            )
        elif service == "depop":
            # Импортируем функцию для Depop
            from app.services.depop import create_depop_image
            from app.cache.figma_cache import cache_exists
            
            # Проверка кэша
            if not cache_exists("depop_au"):
                await update.message.reply_text(
                    "❌ Кэш Depop не найден!\n\n"
                    "Администратор должен выполнить:\n"
                    "/refresh_cache depop_au"
                )
                return ConversationHandler.END
            
            try:
                price_float = float(price)
            except ValueError:
                price_float = 0.0
            
            # Получаем seller_name и avatar
            seller_name = context.user_data.get("seller_name", "Seller")
            seller_photo_bytes = context.user_data.get("seller_photo_bytes")
            avatar_b64 = base64.b64encode(seller_photo_bytes).decode('utf-8') if seller_photo_bytes else None
            
            logger.info(f"🇦🇺 Depop: seller={seller_name}, avatar={'есть' if avatar_b64 else 'нет'}")
            
            executor = context.application.bot_data.get("executor")
            image_data = await generate_with_queue(executor, 
                create_depop_image, nazvanie, price_float, seller_name, photo_b64, avatar_b64, url
            )
        elif service == "wallapop":
            return await generate_wallapop_variant(update, context, url=url)
        elif service in ["2dehands", "2ememain"]:
            # Импортируем функцию для 2dehands
            from app.services.twodehands import create_2dehands_image
            lang = context.user_data.get("lang", "nl")
            
            try:
                price_float = float(price)
            except ValueError:
                price_float = 0.0
            
            executor = context.application.bot_data.get("executor")
            image_data = await generate_with_queue(executor, 
                create_2dehands_image, nazvanie, price_float, photo_b64, url, lang
            )
        elif service == "subito":
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


async def generate_wallapop_variant(update: Update, context: ContextTypes.DEFAULT_TYPE, url: str = None):
    """Генерация Wallapop вариантов"""
    lang = context.user_data.get("lang", "")
    nazvanie = context.user_data.get("nazvanie", "")
    price = context.user_data.get("price", "")
    seller_name = context.user_data.get("seller_name", "")
    photo_bytes = context.user_data.get("photo_bytes")
    seller_photo_bytes = context.user_data.get("seller_photo_bytes")
    wallapop_type = context.user_data.get("wallapop_type", "email_request")

    message = update.message if update.message else update.callback_query.message
    wallapop_label = WALLAPOP_VARIANTS.get(wallapop_type, {}).get("label", wallapop_type)
    await message.reply_text(f"Обрабатываю данные для Wallapop ({wallapop_label}) {lang.upper()}…", reply_markup=menu_back_kb())

    try:
        from app.services.wallapop_variants import (
            create_wallapop_email_request,
            create_wallapop_phone_request,
            create_wallapop_email_payment,
            create_wallapop_sms_payment,
            create_wallapop_qr,
        )
        try:
            price_float = float(price)
        except ValueError:
            price_float = 0.0

        photo_b64 = base64.b64encode(photo_bytes).decode('utf-8') if photo_bytes else None
        seller_photo_b64 = base64.b64encode(seller_photo_bytes).decode('utf-8') if seller_photo_bytes else None

        executor = context.application.bot_data.get("executor")

        async def _generate_wallapop_image():
            if wallapop_type == "email_request":
                return await generate_with_queue(
                    executor, create_wallapop_email_request, lang, nazvanie, price_float, photo_b64, seller_name, seller_photo_b64
                )
            if wallapop_type == "phone_request":
                return await generate_with_queue(
                    executor, create_wallapop_phone_request, lang, nazvanie, price_float, photo_b64, seller_name, seller_photo_b64
                )
            if wallapop_type == "email_payment":
                return await generate_with_queue(
                    executor, create_wallapop_email_payment, lang, nazvanie, price_float, photo_b64, seller_name, seller_photo_b64
                )
            if wallapop_type == "sms_payment":
                return await generate_with_queue(
                    executor, create_wallapop_sms_payment, lang, nazvanie, price_float, photo_b64, seller_name, seller_photo_b64
                )
            if wallapop_type == "qr":
                return await generate_with_queue(
                    executor, create_wallapop_qr, lang, nazvanie, price_float, photo_b64, seller_name, seller_photo_b64, url
                )
            raise ValueError(f"Неизвестный Wallapop тип: {wallapop_type}")

        try:
            image_data = await _generate_wallapop_image()
        except Exception as e:
            if "Кэш" in str(e) and "wallapop" in str(e):
                logger.warning("Wallapop cache warning detected, retrying with Figma fallback.")
                image_data = await _generate_wallapop_image()
            else:
                raise

        await context.bot.send_document(
            chat_id=message.chat_id,
            document=io.BytesIO(image_data),
            filename=f"wallapop_{wallapop_type}_{lang}_{uuid.uuid4()}.png"
        )

        await message.reply_text("Готово!", reply_markup=main_menu_kb())
        clear_stack(context.user_data)
        return ConversationHandler.END

    except Exception as e:
        logger.exception("Ошибка генерации Wallapop")
        await message.reply_text(f"Ошибка: {e}", reply_markup=main_menu_kb())
        clear_stack(context.user_data)
        return ConversationHandler.END


async def generate_depop_variant(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Генерация Depop вариантов (email request/confirm, sms request/confirm)"""
    service = context.user_data.get("service", "")
    nazvanie = context.user_data.get("nazvanie", "")
    price = context.user_data.get("price", "")
    photo_bytes = context.user_data.get("photo_bytes")

    message = update.message if update.message else update.callback_query.message
    
    service_names = {
        "depop_email_request": "Depop Email Request",
        "depop_email_confirm": "Depop Email Confirm",
        "depop_sms_request": "Depop SMS Request",
        "depop_sms_confirm": "Depop SMS Confirm"
    }
    display_name = service_names.get(service, service)
    
    await message.reply_text(f"Обрабатываю данные для {display_name}…", reply_markup=menu_back_kb())

    try:
        # Импортируем функции для Depop вариантов
        from app.services.depop_variants import (
            create_depop_email_request, create_depop_email_confirm,
            create_depop_sms_request, create_depop_sms_confirm
        )
        from app.cache.figma_cache import cache_exists
        
        # Проверка кэша - имена в формате depop_au_email_request
        cache_name_map = {
            "depop_email_request": "depop_au_email_request",
            "depop_email_confirm": "depop_au_email_confirm",
            "depop_sms_request": "depop_au_sms_request",
            "depop_sms_confirm": "depop_au_sms_confirm"
        }
        cache_name = cache_name_map.get(service, service)
        if not cache_exists(cache_name):
            await message.reply_text(
                f"❌ Кэш {cache_name} не найден!\n\n"
                f"Администратор должен выполнить:\n"
                f"/refresh_cache {cache_name}"
            )
            return ConversationHandler.END
        
        try:
            price_float = float(price)
        except ValueError:
            price_float = 0.0
        
        photo_b64 = base64.b64encode(photo_bytes).decode('utf-8') if photo_bytes else None
        logger.info(f"🛍️ Depop {service}: фото={'есть' if photo_b64 else 'нет'}, название={nazvanie}, цена={price_float}")
        
        # Выбор функции генерации
        executor = context.application.bot_data.get("executor")
        
        if service == "depop_email_request":
            image_data = await generate_with_queue(executor, create_depop_email_request, nazvanie, price_float, photo_b64)
        elif service == "depop_email_confirm":
            image_data = await generate_with_queue(executor, create_depop_email_confirm, nazvanie, price_float, photo_b64)
        elif service == "depop_sms_request":
            image_data = await generate_with_queue(executor, create_depop_sms_request, nazvanie, price_float, photo_b64)
        elif service == "depop_sms_confirm":
            image_data = await generate_with_queue(executor, create_depop_sms_confirm, nazvanie, price_float, photo_b64)
        else:
            raise ValueError(f"Неизвестный сервис: {service}")

        await context.bot.send_document(
            chat_id=message.chat_id,
            document=io.BytesIO(image_data),
            filename=f"{service}_{uuid.uuid4()}.png"
        )

        await message.reply_text("Готово!", reply_markup=main_menu_kb())
        clear_stack(context.user_data)
        return ConversationHandler.END

    except Exception as e:
        logger.exception(f"Ошибка генерации {service}")
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
    wallapop_type = context.user_data.get("wallapop_type", "email_request")

    if service in ["2dehands", "2ememain"]:
        return await ask_url(update, context)
    elif service == "wallapop":
        if wallapop_type == "qr":
            return await ask_url(update, context)
        return await generate_wallapop_variant(update, context)
    elif service in ["depop_email_request", "depop_email_confirm", "depop_sms_request", "depop_sms_confirm"]:
        return await generate_depop_variant(update, context)
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

    if prev_state == QR_WALLAPOP_TYPE:
        return await ask_wallapop_type(update, context)
    elif prev_state == QR_DEPOP_TYPE:
        return await ask_depop_type(update, context)
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
        # QR:SUBITO теперь обрабатывается в subito_variants_conv
        CallbackQueryHandler(qr_entry_wallapop_menu, pattern=r"^QR:WALLAPOP_MENU$"),
        CallbackQueryHandler(qr_entry_2dehands, pattern=r"^QR:2DEHANDS$"),
        CallbackQueryHandler(qr_entry_2ememain, pattern=r"^QR:2EMEMAIN$"),
        CallbackQueryHandler(qr_entry_conto, pattern=r"^QR:CONTO$"),
        CallbackQueryHandler(qr_entry_kleize, pattern=r"^QR:KLEIZE$"),
        CallbackQueryHandler(qr_entry_depop, pattern=r"^QR:DEPOP$"),
        CallbackQueryHandler(qr_entry_depop_menu, pattern=r"^QR:DEPOP_MENU$"),
    ],
    states={
        QR_WALLAPOP_TYPE: [
            CallbackQueryHandler(qr_entry_wallapop_email_request, pattern=r"^QR:WALLAPOP_EMAIL_REQUEST$"),
            CallbackQueryHandler(qr_entry_wallapop_phone_request, pattern=r"^QR:WALLAPOP_PHONE_REQUEST$"),
            CallbackQueryHandler(qr_entry_wallapop_email_payment, pattern=r"^QR:WALLAPOP_EMAIL_PAYMENT$"),
            CallbackQueryHandler(qr_entry_wallapop_sms_payment, pattern=r"^QR:WALLAPOP_SMS_PAYMENT$"),
            CallbackQueryHandler(qr_entry_wallapop_qr, pattern=r"^QR:WALLAPOP_QR$"),
            CallbackQueryHandler(qr_menu_cb, pattern=r"^QR:MENU$"),
            CallbackQueryHandler(qr_back_cb, pattern=r"^QR:BACK$")
        ],
        QR_DEPOP_TYPE: [
            CallbackQueryHandler(qr_entry_depop_qr, pattern=r"^QR:DEPOP_QR$"),
            CallbackQueryHandler(qr_entry_depop_email_request, pattern=r"^QR:DEPOP_EMAIL_REQUEST$"),
            CallbackQueryHandler(qr_entry_depop_email_confirm, pattern=r"^QR:DEPOP_EMAIL_CONFIRM$"),
            CallbackQueryHandler(qr_entry_depop_sms_request, pattern=r"^QR:DEPOP_SMS_REQUEST$"),
            CallbackQueryHandler(qr_entry_depop_sms_confirm, pattern=r"^QR:DEPOP_SMS_CONFIRM$"),
            CallbackQueryHandler(qr_menu_cb, pattern=r"^QR:MENU$"),
            CallbackQueryHandler(qr_back_cb, pattern=r"^QR:BACK$")
        ],
        QR_LANG: [
            CallbackQueryHandler(on_wallapop_lang_callback, pattern=r"^WALLAPOP_LANG_"),
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
