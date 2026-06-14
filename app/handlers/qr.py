# app/handlers/qr.py
import io
import uuid
import base64
import logging
import asyncio
from app.utils.async_helpers import (
    with_rate_limit,
)


from telegram import Update
from telegram.ext import (
    ContextTypes, ConversationHandler, CallbackQueryHandler,
    MessageHandler, CommandHandler, filters
)

from app.keyboards.qr import main_menu_kb, menu_back_kb, photo_step_kb, wallapop_type_kb, wallapop_lang_kb, depop_type_kb, booking_lang_kb, skip_link_kb
from app.utils.state_stack import push_state, pop_state, clear_stack
from app.services.wallapop_variants import WALLAPOP_VARIANTS
from app.config import CFG
import requests

logger = logging.getLogger(__name__)


def _backend_generate(payload: dict) -> tuple[bytes, str]:
    """Call Rust backend /generate and return (bytes, content_type)."""
    url = f"{CFG.QR_BACKEND_URL.rstrip('/')}/generate"
    headers = {"X-API-Key": CFG.BACKEND_API_KEY or ""}
    r = requests.post(url, json=payload, headers=headers, timeout=60)
    if not r.ok:
        body = (r.text or "")[:2000]
        raise requests.HTTPError(
            f"{r.status_code} {r.reason} for {url}; backend body: {body}",
            response=r,
        )
    return r.content, r.headers.get("content-type", "image/png")


def _service_country_defaults(service: str, lang: str | None = None) -> tuple[str, str, str]:
    """Returns (country, backend_service, backend_method_default)."""
    s = (service or "").lower()
    if s == "marktplaats":
        return ("nl", "markt", "qr")
    if s == "kleize":
        return ("de", "kleinanzeigen", "qr")
    if s in ["2dehands", "2ememain"]:
        # country here is used as language selector in rust twodehands generator.
        return ("nl" if s == "2dehands" else "fr", s, "qr")
    if s == "wallapop":
        return ((lang or "es"), "wallapop", "qr")
    if s == "conto":
        return ("it", "conto", "qr")
    if s.startswith("depop"):
        return ("au", "depop", "qr")
    if s == "booking":
        return ((lang or "en"), "booking", "pdf")
    return ("nl", s, "qr")

# Состояния
QR_NAZVANIE, QR_PRICE, QR_PHOTO, QR_URL, QR_LANG, QR_SELLER_NAME, QR_SELLER_PHOTO, QR_WALLAPOP_TYPE, QR_DEPOP_TYPE, QR_BOOK_LANG, QR_BOOK_LINK1, QR_BOOK_LINK2, QR_BOOK_DETAILS = range(13)


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


async def qr_entry_depop_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Меню выбора типа Depop"""
    context.user_data["service"] = "depop"
    clear_stack(context.user_data)
    await update.callback_query.answer()
    return await ask_depop_type(update, context)


async def qr_entry_booking(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["service"] = "booking"
    context.user_data.pop("booking_field_idx", None)
    clear_stack(context.user_data)
    await update.callback_query.answer()
    return await ask_booking_lang(update, context)


async def ask_booking_lang(update: Update, context: ContextTypes.DEFAULT_TYPE):
    push_state(context.user_data, QR_BOOK_LANG)
    text = "Выбери язык Booking:"
    if update.callback_query:
        await update.callback_query.message.edit_text(text, reply_markup=booking_lang_kb())
    else:
        await update.message.reply_text(text, reply_markup=booking_lang_kb())
    return QR_BOOK_LANG


async def on_booking_lang_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = update.callback_query.data.replace("BOOK_LANG_", "")
    if lang not in ["en", "it", "fr", "es", "pr", "de", "nl"]:
        await update.callback_query.answer("❌ Неправильный язык")
        return QR_BOOK_LANG
    context.user_data["lang"] = lang
    await update.callback_query.answer(f"Выбран язык: {lang.upper()}")
    return await ask_nazvanie(update, context)


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


async def ask_booking_link1(update: Update, context: ContextTypes.DEFAULT_TYPE):
    push_state(context.user_data, QR_BOOK_LINK1)
    txt = "Ссылка для кнопки подтверждения (knopbook1), или Пропустить:"
    if update.callback_query:
        await update.callback_query.message.edit_text(txt, reply_markup=skip_link_kb())
    else:
        await update.message.reply_text(txt, reply_markup=skip_link_kb())
    return QR_BOOK_LINK1


async def ask_booking_link2(update: Update, context: ContextTypes.DEFAULT_TYPE):
    push_state(context.user_data, QR_BOOK_LINK2)
    txt = "Ссылка для кнопки отмены (knopbook2), или Пропустить:"
    if update.callback_query:
        await update.callback_query.message.edit_text(txt, reply_markup=skip_link_kb())
    else:
        await update.message.reply_text(txt, reply_markup=skip_link_kb())
    return QR_BOOK_LINK2


BOOKING_FIELDS = [
    ("name", "Имя гостя (name):"),
    ("hotel_name", "Название отеля (hotel_name):"),
    ("address", "Адрес (address):"),
    ("nights", "Количество ночей (nights), число:"),
    ("checkin_date", "Дата заезда (checkin_date) в формате YYYY-MM-DD:"),
    ("checkout_date", "Дата выезда (checkout_date) в формате YYYY-MM-DD:"),
]


async def ask_booking_details(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get("booking_field_idx") is None:
        push_state(context.user_data, QR_BOOK_DETAILS)
        context.user_data["booking_field_idx"] = 0

    idx = int(context.user_data.get("booking_field_idx", 0))
    if idx >= len(BOOKING_FIELDS):
        return await on_url(update, context)

    key, prompt = BOOKING_FIELDS[idx]
    await _edit_or_send(update, context, f"Booking шаг {idx + 1}/{len(BOOKING_FIELDS)}\n{prompt}")
    return QR_BOOK_DETAILS


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
    elif service == "depop":
        # Для Depop QR нужен seller_name
        return await ask_seller_name(update, context)
    elif service in ["depop_email_request", "depop_email_confirm", "depop_sms_request", "depop_sms_confirm"]:
        # Для Depop вариантов (без QR) - только фото
        return await ask_photo(update, context)
    elif service == "wallapop":
        return await ask_seller_name(update, context)
    elif service == "booking":
        return await ask_booking_link1(update, context)
    else:
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


async def on_booking_link1(update: Update, context: ContextTypes.DEFAULT_TYPE):
    link = (update.message.text or "").strip()
    if link and not link.startswith("http"):
        link = "https://" + link
    context.user_data["knopbook1"] = link
    return await ask_booking_link2(update, context)


async def on_booking_link2(update: Update, context: ContextTypes.DEFAULT_TYPE):
    link = (update.message.text or "").strip()
    if link and not link.startswith("http"):
        link = "https://" + link
    context.user_data["knopbook2"] = link or "https://www.booking.com/"
    return await ask_booking_details(update, context)


async def on_booking_details(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").strip()
    idx = int(context.user_data.get("booking_field_idx", 0))
    if idx >= len(BOOKING_FIELDS):
        return await on_url(update, context)

    key, _prompt = BOOKING_FIELDS[idx]

    if key == "nights":
        try:
            context.user_data[key] = int(text)
        except Exception:
            await update.message.reply_text("Нужно ввести число. Попробуй ещё раз.")
            return QR_BOOK_DETAILS
    else:
        if text not in ("", "-"):
            context.user_data[key] = text
        else:
            context.user_data.pop(key, None)

    context.user_data["booking_field_idx"] = idx + 1
    return await ask_booking_details(update, context)


@with_rate_limit
async def on_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message if update.message else update.callback_query.message

    nazvanie = context.user_data.get("nazvanie", "")
    price = context.user_data.get("price", "")
    name = context.user_data.get("name")
    address = context.user_data.get("address")
    phone = context.user_data.get("phone")
    photo_bytes = context.user_data.get("photo_bytes")

    # URL can come from a text message step OR be prefilled in context (variants flow).
    url = (update.message.text or "").strip() if update.message else (context.user_data.get("url") or "")
    url = (url or "").strip()
    if url and not url.startswith("http"):
        url = "https://" + url

    service = context.user_data.get("service", "marktplaats")
    await message.reply_text(f"Обрабатываю данные для {service}…", reply_markup=menu_back_kb())

    try:
        photo_b64 = base64.b64encode(photo_bytes).decode('utf-8') if photo_bytes else None
        logger.info(f"📸 Генерация для {service}: фото={'есть (' + str(len(photo_b64)) + ' символов)' if photo_b64 else 'нет'}, название={nazvanie}, цена={price}")

        # All generation must happen in Rust backend.
        try:
            price_float = float(price)
        except ValueError:
            price_float = 0.0

        lang = context.user_data.get("lang")
        depop_type = context.user_data.get("depop_type")
        wallapop_type = context.user_data.get("wallapop_type")

        country, backend_service, method_default = _service_country_defaults(service, lang=lang)
        backend_method = method_default

        if backend_service == "wallapop":
            backend_method = wallapop_type or "qr"
        if backend_service == "depop":
            backend_method = depop_type or "qr"

        payload = {
            "country": country,
            "service": backend_service,
            "method": backend_method,
            "title": nazvanie,
            "price": price_float,
            "url": url,
            "photo": photo_b64,
            "name": name,
            "address": address,
            "phone": phone,
            "hotel_name": context.user_data.get("hotel_name"),
            "checkin_date": context.user_data.get("checkin_date"),
            "checkout_date": context.user_data.get("checkout_date"),
            "nights": context.user_data.get("nights"),
            "seller_name": context.user_data.get("seller_name"),
            "seller_photo": base64.b64encode(context.user_data.get("seller_photo_bytes") or b"").decode("utf-8")
            if context.user_data.get("seller_photo_bytes")
            else None,
            "knopbook1": context.user_data.get("knopbook1"),
            "knopbook2": context.user_data.get("knopbook2") or ("https://www.booking.com/" if backend_service == "booking" else None),
        }

        file_data, content_type = await asyncio.to_thread(_backend_generate, payload)
        ext = "pdf" if "pdf" in (content_type or "").lower() else "png"

        await context.bot.send_document(
            chat_id=message.chat_id,
            document=io.BytesIO(file_data),
            filename=f"{service}_{uuid.uuid4()}.{ext}"
        )

        await message.reply_text("Готово!", reply_markup=main_menu_kb())
        clear_stack(context.user_data)
        return ConversationHandler.END

    except Exception as e:
        logger.exception("Ошибка генерации")
        await message.reply_text(f"Ошибка: {e}", reply_markup=main_menu_kb())
        clear_stack(context.user_data)
        return ConversationHandler.END


async def generate_wallapop_variant(update: Update, context: ContextTypes.DEFAULT_TYPE, url: str = None):
    """Wallapop variants must be generated by Rust backend."""
    # Reuse the main generation path by forcing service=wallapop and method from context.
    message = update.message if update.message else update.callback_query.message
    await message.reply_text("Обрабатываю данные для Wallapop…", reply_markup=menu_back_kb())

    try:
        context.user_data["service"] = "wallapop"
        context.user_data["url"] = url or context.user_data.get("url")
        # Delegate to the normal send flow (builds backend payload and sends document)
        return await on_url(update, context)
    except Exception as e:
        logger.exception("Ошибка генерации Wallapop")
        await message.reply_text(f"Ошибка: {e}", reply_markup=main_menu_kb())
        clear_stack(context.user_data)
        return ConversationHandler.END


async def generate_depop_variant(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Depop variants must be generated by Rust backend."""
    message = update.message if update.message else update.callback_query.message
    await message.reply_text("Обрабатываю данные для Depop…", reply_markup=menu_back_kb())

    try:
        # Force service=depop; method comes from depop_type in context.
        context.user_data["service"] = "depop"
        return await on_url(update, context)
    except Exception as e:
        logger.exception("Ошибка генерации Depop")
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


async def on_skip_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    stack = context.user_data.get("state_stack", [])
    current_state = stack[-1] if stack else None
    if current_state == QR_BOOK_LINK1:
        context.user_data["knopbook1"] = ""
        return await ask_booking_link2(update, context)
    context.user_data["knopbook2"] = "https://www.booking.com/"
    return await ask_booking_details(update, context)


async def qr_back_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()

    # Стек хранит историю шагов: [..., PREV, CURRENT].
    # На "Назад" снимаем CURRENT и переходим к PREV.
    pop_state(context.user_data)
    target_state = pop_state(context.user_data)

    if target_state is None:
        return await qr_menu_cb(update, context)

    if target_state == QR_WALLAPOP_TYPE:
        return await ask_wallapop_type(update, context)
    elif target_state == QR_DEPOP_TYPE:
        return await ask_depop_type(update, context)
    elif target_state == QR_BOOK_LANG:
        return await ask_booking_lang(update, context)
    elif target_state == QR_LANG:
        wallapop_type = context.user_data.get("wallapop_type", "email_request")
        return await ask_wallapop_lang(update, context, wallapop_type)
    elif target_state == QR_NAZVANIE:
        return await ask_nazvanie(update, context)
    elif target_state == QR_PRICE:
        return await ask_price(update, context)
    elif target_state == QR_SELLER_NAME:
        return await ask_seller_name(update, context)
    elif target_state == QR_SELLER_PHOTO:
        return await ask_seller_photo(update, context)
    elif target_state == QR_PHOTO:
        return await ask_photo(update, context)
    elif target_state == QR_BOOK_LINK1:
        return await ask_booking_link1(update, context)
    elif target_state == QR_BOOK_LINK2:
        return await ask_booking_link2(update, context)
    elif target_state == QR_BOOK_DETAILS:
        return await ask_booking_details(update, context)
    elif target_state == QR_URL:
        return await ask_url(update, context)

    # Fallback: если стек в неожиданном состоянии
    return await qr_menu_cb(update, context)


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
        CallbackQueryHandler(qr_entry_wallapop_menu, pattern=r"^QR:WALLAPOP_MENU$"),
        CallbackQueryHandler(qr_entry_2dehands, pattern=r"^QR:2DEHANDS$"),
        CallbackQueryHandler(qr_entry_2ememain, pattern=r"^QR:2EMEMAIN$"),
        CallbackQueryHandler(qr_entry_conto, pattern=r"^QR:CONTO$"),
        CallbackQueryHandler(qr_entry_kleize, pattern=r"^QR:KLEIZE$"),
        CallbackQueryHandler(qr_entry_depop_menu, pattern=r"^QR:DEPOP_MENU$"),
        CallbackQueryHandler(qr_entry_booking, pattern=r"^QR:BOOKING$"),
    ],
    states={
        QR_WALLAPOP_TYPE: [
            CallbackQueryHandler(qr_entry_wallapop_email_request, pattern=r"^QR:WALLAPOP_EMAIL_REQUEST$"),
            CallbackQueryHandler(qr_entry_wallapop_phone_request, pattern=r"^QR:WALLAPOP_PHONE_REQUEST$"),
            CallbackQueryHandler(qr_entry_wallapop_email_payment, pattern=r"^QR:WALLAPOP_EMAIL_PAYMENT$"),
            CallbackQueryHandler(qr_entry_wallapop_sms_payment, pattern=r"^QR:WALLAPOP_SMS_PAYMENT$"),
            CallbackQueryHandler(qr_entry_wallapop_qr, pattern=r"^QR:WALLAPOP_QR$"),
            CallbackQueryHandler(qr_menu_cb, pattern=r"^(QR:MENU|MENU)$"),
            CallbackQueryHandler(qr_back_cb, pattern=r"^QR:BACK$")
        ],
        QR_DEPOP_TYPE: [
            CallbackQueryHandler(qr_entry_depop_qr, pattern=r"^QR:DEPOP_QR$"),
            CallbackQueryHandler(qr_entry_depop_email_request, pattern=r"^QR:DEPOP_EMAIL_REQUEST$"),
            CallbackQueryHandler(qr_entry_depop_email_confirm, pattern=r"^QR:DEPOP_EMAIL_CONFIRM$"),
            CallbackQueryHandler(qr_entry_depop_sms_request, pattern=r"^QR:DEPOP_SMS_REQUEST$"),
            CallbackQueryHandler(qr_entry_depop_sms_confirm, pattern=r"^QR:DEPOP_SMS_CONFIRM$"),
            CallbackQueryHandler(qr_menu_cb, pattern=r"^(QR:MENU|MENU)$"),
            CallbackQueryHandler(qr_back_cb, pattern=r"^QR:BACK$")
        ],
        QR_LANG: [
            CallbackQueryHandler(on_wallapop_lang_callback, pattern=r"^WALLAPOP_LANG_"),
            CallbackQueryHandler(qr_menu_cb, pattern=r"^(QR:MENU|MENU)$"),
            CallbackQueryHandler(wallapop_back_cb, pattern=r"^QR:WALLAPOP_BACK$"),
            CallbackQueryHandler(qr_back_cb, pattern=r"^QR:BACK$")
        ],
        QR_BOOK_LANG: [
            CallbackQueryHandler(on_booking_lang_callback, pattern=r"^BOOK_LANG_"),
            CallbackQueryHandler(qr_menu_cb, pattern=r"^(QR:MENU|MENU)$"),
            CallbackQueryHandler(qr_back_cb, pattern=r"^QR:BACK$")
        ],
        QR_NAZVANIE: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, on_nazvanie),
            CallbackQueryHandler(qr_menu_cb, pattern=r"^(QR:MENU|MENU)$"),
            CallbackQueryHandler(qr_back_cb, pattern=r"^QR:BACK$")
        ],
        QR_PRICE: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, on_price),
            CallbackQueryHandler(qr_menu_cb, pattern=r"^(QR:MENU|MENU)$"),
            CallbackQueryHandler(qr_back_cb, pattern=r"^QR:BACK$")
        ],

        QR_SELLER_NAME: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, on_seller_name),
            CallbackQueryHandler(qr_menu_cb, pattern=r"^(QR:MENU|MENU)$"),
            CallbackQueryHandler(qr_back_cb, pattern=r"^QR:BACK$")
        ],
        QR_SELLER_PHOTO: [
            MessageHandler(filters.PHOTO, on_seller_photo),
            CallbackQueryHandler(qr_menu_cb, pattern=r"^(QR:MENU|MENU)$"),
            CallbackQueryHandler(qr_back_cb, pattern=r"^QR:BACK$"),
            CallbackQueryHandler(on_skip_seller_photo, pattern=r"^QR:SKIP_PHOTO$")
        ],
        QR_PHOTO: [
            MessageHandler(filters.PHOTO, on_photo),
            CallbackQueryHandler(qr_menu_cb, pattern=r"^(QR:MENU|MENU)$"),
            CallbackQueryHandler(qr_back_cb, pattern=r"^QR:BACK$"),
            CallbackQueryHandler(on_skip_photo, pattern=r"^QR:SKIP_PHOTO$")
        ],
        QR_BOOK_LINK1: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, on_booking_link1),
            CallbackQueryHandler(on_skip_link, pattern=r"^QR:SKIP_LINK$"),
            CallbackQueryHandler(qr_menu_cb, pattern=r"^(QR:MENU|MENU)$"),
            CallbackQueryHandler(qr_back_cb, pattern=r"^QR:BACK$")
        ],
        QR_BOOK_LINK2: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, on_booking_link2),
            CallbackQueryHandler(on_skip_link, pattern=r"^QR:SKIP_LINK$"),
            CallbackQueryHandler(qr_menu_cb, pattern=r"^(QR:MENU|MENU)$"),
            CallbackQueryHandler(qr_back_cb, pattern=r"^QR:BACK$")
        ],
        QR_BOOK_DETAILS: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, on_booking_details),
            CallbackQueryHandler(qr_menu_cb, pattern=r"^(QR:MENU|MENU)$"),
            CallbackQueryHandler(qr_back_cb, pattern=r"^QR:BACK$")
        ],
        QR_URL: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, on_url),
            CallbackQueryHandler(qr_menu_cb, pattern=r"^(QR:MENU|MENU)$"),
            CallbackQueryHandler(qr_back_cb, pattern=r"^QR:BACK$")
        ],
    },
    fallbacks=[CommandHandler("start", qr_menu_cb)],
    allow_reentry=True,
)
