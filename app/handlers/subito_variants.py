# app/handlers/subito_variants.py
"""Subito variants.

We support TWO template families:

A) New Subito mockups (subito6..subito10)
   - language tags: uk / nl (NOT in frame name)
   - methods: qr | email_request | phone_request | email_payment | sms_payment
   - country is used as language selector (uk|nl)

B) Legacy Italian Subito mockups (subito1..subito5)
   - country = it
   - methods: qr | email_request | email_confirm | sms_request | sms_confirm
   - (name/address fields are supported for backward compatibility)

Thin client MUST call Rust backend (/generate); no local PIL generation.
"""

from __future__ import annotations

import base64
import io
import logging
from typing import Optional

import requests
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    CallbackQueryHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from app.config import CFG
from app.keyboards.qr import main_menu_kb
from app.utils.async_helpers import generate_with_queue
from app.utils.state_stack import clear_stack, push_state

logger = logging.getLogger(__name__)

# States (use high numbers to avoid collisions)
(
    SUBITO_MODE,
    SUBITO_TYPE,
    SUBITO_LANG,
    SUBITO_TITLE,
    SUBITO_PRICE,
    SUBITO_PHOTO,
    SUBITO_URL,
    SUBITO_NAME,
    SUBITO_ADDRESS,
) = range(200, 209)


# ========== BACKEND CALL ==========

def _backend_generate_subito(
    country: str,
    method: str,
    title: str,
    price: float,
    photo_b64: Optional[str],
    url: Optional[str],
    name: Optional[str],
    address: Optional[str],
) -> bytes:
    backend_url = f"{CFG.QR_BACKEND_URL.rstrip('/')}/generate"
    headers = {"X-API-Key": CFG.BACKEND_API_KEY or ""}

    payload = {
        "country": country,
        "service": "subito",
        "method": method,
        "title": title,
        "price": price,
        "photo": photo_b64,
        "url": url,
        "name": name,
        "address": address,
    }

    r = requests.post(backend_url, json=payload, headers=headers, timeout=180)
    if not r.ok:
        raise ValueError(r.text)
    return r.content


# ========== KEYBOARDS ==========

def _nav_row(back_cb: str):
    return [
        InlineKeyboardButton("⬅️ Назад", callback_data=back_cb),
        InlineKeyboardButton("🏠 Главное меню", callback_data="MENU"),
    ]


def subito_mode_kb():
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🇬🇧/🇳🇱 Subito (uk/nl) — новые", callback_data="SUBITO_MODE:NEW")],
            [InlineKeyboardButton("🇮🇹 Subito (it) — legacy subito1-5", callback_data="SUBITO_MODE:IT")],
            _nav_row("QR:MENU"),
        ]
    )


def subito_type_new_kb():
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("📧 Mail запрос", callback_data="SUBITO_TYPE:email_request")],
            [InlineKeyboardButton("📞 Телефон запрос", callback_data="SUBITO_TYPE:phone_request")],
            [InlineKeyboardButton("💳 Mail оплата", callback_data="SUBITO_TYPE:email_payment")],
            [InlineKeyboardButton("📱 SMS оплата", callback_data="SUBITO_TYPE:sms_payment")],
            [InlineKeyboardButton("🔳 QR", callback_data="SUBITO_TYPE:qr")],
            _nav_row("SUBITO_BACK:MODE"),
        ]
    )


def subito_type_it_kb():
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🔵 QR (legacy)", callback_data="SUBITO_TYPE:qr")],
            [InlineKeyboardButton("📧 Email запрос (legacy)", callback_data="SUBITO_TYPE:email_request")],
            [InlineKeyboardButton("✅ Email подтверждение (legacy)", callback_data="SUBITO_TYPE:email_confirm")],
            [InlineKeyboardButton("📱 SMS запрос (legacy)", callback_data="SUBITO_TYPE:sms_request")],
            [InlineKeyboardButton("✅ SMS подтверждение (legacy)", callback_data="SUBITO_TYPE:sms_confirm")],
            _nav_row("SUBITO_BACK:MODE"),
        ]
    )


def subito_lang_kb():
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("🇬🇧 UK", callback_data="SUBITO_LANG:uk"),
                InlineKeyboardButton("🇳🇱 NL", callback_data="SUBITO_LANG:nl"),
            ],
            _nav_row("SUBITO_BACK:TYPE"),
        ]
    )


def subito_price_kb():
    return InlineKeyboardMarkup([_nav_row("SUBITO_BACK:TITLE")])


def subito_photo_kb():
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("⏭️ Пропустить фото", callback_data="SUBITO:SKIP_PHOTO")],
            _nav_row("SUBITO_BACK:PRICE"),
        ]
    )


def subito_url_kb():
    return InlineKeyboardMarkup([_nav_row("SUBITO_BACK:PHOTO")])


def subito_name_kb():
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("⏭️ Пропустить имя", callback_data="SUBITO:SKIP_NAME")],
            _nav_row("SUBITO_BACK:URL"),
        ]
    )


def subito_address_kb():
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("⏭️ Пропустить адрес", callback_data="SUBITO:SKIP_ADDRESS")],
            _nav_row("SUBITO_BACK:NAME"),
        ]
    )


# NOTE: Python doesn't have a global flag; we set it per user_data.

def _mode(context) -> str:
    return context.user_data.get("subito_mode", "NEW")


def _is_new(context) -> bool:
    return _mode(context) == "NEW"


def _country(context) -> str:
    # NEW => country is lang (uk/nl)
    # IT  => country is it
    if _is_new(context):
        return context.user_data.get("subito_lang", "uk")
    return "it"


# ========== ENTRY ==========

async def subito_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    clear_stack(context.user_data)
    context.user_data["service"] = "subito"

    await update.callback_query.answer()
    await update.callback_query.edit_message_text(
        "<b>Subito</b> — выбери набор макетов:",
        reply_markup=subito_mode_kb(),
        parse_mode="HTML",
    )
    push_state(context.user_data, SUBITO_MODE)
    return SUBITO_MODE


# ========== MODE ==========

async def subito_mode_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    mode = q.data.split(":", 1)[1]
    context.user_data["subito_mode"] = mode
    await q.answer()

    if mode == "IT":
        await q.edit_message_text(
            "🇮🇹 <b>Subito IT (legacy)</b> — выбери тип:",
            reply_markup=subito_type_it_kb(),
            parse_mode="HTML",
        )
        push_state(context.user_data, SUBITO_TYPE)
        return SUBITO_TYPE

    await q.edit_message_text(
        "🇬🇧/🇳🇱 <b>Subito (uk/nl)</b> — выбери тип:",
        reply_markup=subito_type_new_kb(),
        parse_mode="HTML",
    )
    push_state(context.user_data, SUBITO_TYPE)
    return SUBITO_TYPE


async def subito_back_to_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    await q.edit_message_text(
        "<b>Subito</b> — выбери набор макетов:",
        reply_markup=subito_mode_kb(),
        parse_mode="HTML",
    )
    return SUBITO_MODE


# ========== TYPE ==========

async def subito_type_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    method = q.data.split(":", 1)[1]
    context.user_data["subito_type"] = method
    await q.answer()

    if _is_new(context):
        await q.edit_message_text("Выбери язык (uk / nl):", reply_markup=subito_lang_kb())
        push_state(context.user_data, SUBITO_LANG)
        return SUBITO_LANG

    # IT legacy: no lang selection
    await q.edit_message_text(
        "📝 Введи <b>название товара</b>:",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([_nav_row("SUBITO_BACK:TYPE")]),
    )
    push_state(context.user_data, SUBITO_TITLE)
    return SUBITO_TITLE


async def subito_back_to_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if _is_new(context):
        await q.edit_message_text(
            "🇬🇧/🇳🇱 <b>Subito (uk/nl)</b> — выбери тип:",
            reply_markup=subito_type_new_kb(),
            parse_mode="HTML",
        )
    else:
        await q.edit_message_text(
            "🇮🇹 <b>Subito IT (legacy)</b> — выбери тип:",
            reply_markup=subito_type_it_kb(),
            parse_mode="HTML",
        )
    return SUBITO_TYPE


# ========== LANG ==========

async def subito_lang_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    lang = q.data.split(":", 1)[1]
    context.user_data["subito_lang"] = lang

    await q.answer()
    await q.edit_message_text(
        "📝 Введи <b>название товара</b>:",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([_nav_row("SUBITO_BACK:LANG")]),
    )
    push_state(context.user_data, SUBITO_TITLE)
    return SUBITO_TITLE


async def subito_back_to_lang(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    await q.edit_message_text("Выбери язык (uk / nl):", reply_markup=subito_lang_kb())
    return SUBITO_LANG


# ========== BACK (INPUT STEPS) ==========

async def subito_back_to_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    await q.edit_message_text(
        "📝 Введи <b>название товара</b>:" ,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([
            _nav_row("SUBITO_BACK:LANG" if _is_new(context) else "SUBITO_BACK:TYPE")
        ]),
    )
    return SUBITO_TITLE


async def subito_back_to_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    await q.edit_message_text(
        "💵 Введи <b>цену</b> (например: 123.45):",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([_nav_row("SUBITO_BACK:TITLE")]),
    )
    return SUBITO_PRICE


async def subito_back_to_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    await q.edit_message_text(
        "📸 Отправь <b>фото товара</b> или пропусти:",
        parse_mode="HTML",
        reply_markup=subito_photo_kb(),
    )
    return SUBITO_PHOTO


async def subito_back_to_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    await q.edit_message_text(
        "🔗 Введи <b>URL</b> для QR:",
        parse_mode="HTML",
        reply_markup=subito_url_kb(),
    )
    return SUBITO_URL


async def subito_back_to_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    await q.edit_message_text(
        "👤 Введи <b>имя</b> (можно пропустить):",
        parse_mode="HTML",
        reply_markup=subito_name_kb(),
    )
    return SUBITO_NAME


# ========== TITLE / PRICE ==========

async def subito_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["subito_title"] = (update.message.text or "").strip()
    await update.message.reply_text(
        "💵 Введи <b>цену</b> (например: 123.45):",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([_nav_row("SUBITO_BACK:TITLE")]),
    )
    push_state(context.user_data, SUBITO_PRICE)
    return SUBITO_PRICE


async def subito_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        price = float((update.message.text or "").replace(",", ".").strip())
    except ValueError:
        await update.message.reply_text("❌ Неверный формат. Введи цену (например 123.45)")
        return SUBITO_PRICE

    context.user_data["subito_price"] = price

    await update.message.reply_text(
        "📸 Отправь <b>фото товара</b> или пропусти:",
        parse_mode="HTML",
        reply_markup=subito_photo_kb(),
    )
    push_state(context.user_data, SUBITO_PHOTO)
    return SUBITO_PHOTO


# ========== PHOTO ==========

async def subito_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    photo_b64 = None
    if update.message and update.message.photo:
        photo_file = await update.message.photo[-1].get_file()
        photo_bytes = await photo_file.download_as_bytearray()
        photo_b64 = base64.b64encode(photo_bytes).decode("utf-8")

    context.user_data["subito_photo"] = photo_b64

    method = context.user_data.get("subito_type", "qr")

    if method == "qr":
        await update.message.reply_text(
            "🔗 Введи <b>URL</b> для QR:",
            parse_mode="HTML",
            reply_markup=subito_url_kb(),
        )
        push_state(context.user_data, SUBITO_URL)
        return SUBITO_URL

    if _is_new(context):
        return await _subito_generate(update.message, context)

    # IT legacy: ask name/address (optional) even for non-QR variants
    await update.message.reply_text(
        "👤 Введи <b>имя</b> (можно пропустить):",
        parse_mode="HTML",
        reply_markup=subito_name_kb(),
    )
    push_state(context.user_data, SUBITO_NAME)
    return SUBITO_NAME


async def subito_skip_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    context.user_data["subito_photo"] = None

    method = context.user_data.get("subito_type", "qr")
    if method == "qr":
        await q.edit_message_text(
            "🔗 Введи <b>URL</b> для QR:",
            parse_mode="HTML",
            reply_markup=subito_url_kb(),
        )
        push_state(context.user_data, SUBITO_URL)
        return SUBITO_URL

    # non-qr
    if _is_new(context):
        await q.message.reply_text("⏳ Генерирую...")
        return await _subito_generate(q.message, context)

    await q.edit_message_text(
        "👤 Введи <b>имя</b> (можно пропустить):",
        parse_mode="HTML",
        reply_markup=subito_name_kb(),
    )
    push_state(context.user_data, SUBITO_NAME)
    return SUBITO_NAME


# ========== URL (QR only) ==========

async def subito_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["subito_url"] = (update.message.text or "").strip()

    if _is_new(context):
        return await _subito_generate(update.message, context)

    # IT legacy: proceed to name/address
    await update.message.reply_text(
        "👤 Введи <b>имя</b> (можно пропустить):",
        parse_mode="HTML",
        reply_markup=subito_name_kb(),
    )
    push_state(context.user_data, SUBITO_NAME)
    return SUBITO_NAME


# ========== NAME / ADDRESS (IT legacy) ==========

async def subito_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["subito_name"] = (update.message.text or "").strip()
    await update.message.reply_text(
        "📍 Введи <b>адрес</b> (можно пропустить):",
        parse_mode="HTML",
        reply_markup=subito_address_kb(),
    )
    push_state(context.user_data, SUBITO_ADDRESS)
    return SUBITO_ADDRESS


async def subito_skip_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    context.user_data["subito_name"] = ""
    await q.edit_message_text(
        "📍 Введи <b>адрес</b> (можно пропустить):",
        parse_mode="HTML",
        reply_markup=subito_address_kb(),
    )
    push_state(context.user_data, SUBITO_ADDRESS)
    return SUBITO_ADDRESS


async def subito_address(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["subito_address"] = (update.message.text or "").strip()
    return await _subito_generate(update.message, context)


async def subito_skip_address(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    context.user_data["subito_address"] = ""
    await q.message.reply_text("⏳ Генерирую...")
    return await _subito_generate(q.message, context)


# ========== GENERATE ==========

async def _subito_generate(message, context: ContextTypes.DEFAULT_TYPE):
    country = _country(context)
    method = context.user_data.get("subito_type", "qr")
    title = context.user_data.get("subito_title", "")
    price = float(context.user_data.get("subito_price", 0.0))
    photo_b64 = context.user_data.get("subito_photo")
    url = context.user_data.get("subito_url")
    name = context.user_data.get("subito_name")
    address = context.user_data.get("subito_address")

    executor = context.application.bot_data.get("executor")

    try:
        msg = await message.reply_text("⏳ Генерирую...")

        png_bytes = await generate_with_queue(
            executor,
            _backend_generate_subito,
            country,
            method,
            title,
            price,
            photo_b64,
            url,
            name,
            address,
        )

        bio = io.BytesIO(png_bytes)
        bio.name = f"subito_{method}_{country}.png"
        bio.seek(0)

        await msg.delete()
        await message.reply_photo(photo=bio, reply_markup=main_menu_kb())

    except Exception as e:
        logger.exception("Subito generation failed")
        await message.reply_text(f"❌ Ошибка генерации: {e}")

    return ConversationHandler.END


# ========== CONVERSATION ==========

subito_variants_conv = ConversationHandler(
    entry_points=[CallbackQueryHandler(subito_start, pattern=r"^QR:SUBITO$")],
    states={
        SUBITO_MODE: [CallbackQueryHandler(subito_mode_selected, pattern=r"^SUBITO_MODE:")],
        SUBITO_TYPE: [
            CallbackQueryHandler(subito_type_selected, pattern=r"^SUBITO_TYPE:"),
            CallbackQueryHandler(subito_back_to_mode, pattern=r"^SUBITO_BACK:MODE$"),
        ],
        SUBITO_LANG: [
            CallbackQueryHandler(subito_lang_selected, pattern=r"^SUBITO_LANG:"),
            CallbackQueryHandler(subito_back_to_type, pattern=r"^SUBITO_BACK:TYPE$"),
        ],
        SUBITO_TITLE: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, subito_title),
            CallbackQueryHandler(subito_back_to_lang, pattern=r"^SUBITO_BACK:LANG$"),
            CallbackQueryHandler(subito_back_to_type, pattern=r"^SUBITO_BACK:TYPE$"),
        ],
        SUBITO_PRICE: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, subito_price),
            CallbackQueryHandler(subito_back_to_title, pattern=r"^SUBITO_BACK:TITLE$"),
        ],
        SUBITO_PHOTO: [
            MessageHandler(filters.PHOTO, subito_photo),
            CallbackQueryHandler(subito_skip_photo, pattern=r"^SUBITO:SKIP_PHOTO$"),
            CallbackQueryHandler(subito_back_to_price, pattern=r"^SUBITO_BACK:PRICE$"),
        ],
        SUBITO_URL: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, subito_url),
            CallbackQueryHandler(subito_back_to_photo, pattern=r"^SUBITO_BACK:PHOTO$"),
        ],
        SUBITO_NAME: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, subito_name),
            CallbackQueryHandler(subito_skip_name, pattern=r"^SUBITO:SKIP_NAME$"),
            CallbackQueryHandler(subito_back_to_url, pattern=r"^SUBITO_BACK:URL$"),
        ],
        SUBITO_ADDRESS: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, subito_address),
            CallbackQueryHandler(subito_skip_address, pattern=r"^SUBITO:SKIP_ADDRESS$"),
            CallbackQueryHandler(subito_back_to_name, pattern=r"^SUBITO_BACK:NAME$"),
        ],
    },
    fallbacks=[],
    name="subito_variants_conv",
    persistent=False,
)
