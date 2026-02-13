# app/handlers/subito_variants.py
"""Subito variants (NEW subito6..subito10).

Variants:
- Email request  -> subito6
- Phone request  -> subito7
- Email payment  -> subito8
- SMS payment    -> subito9
- QR             -> subito10

Supports language tags: uk / nl.
Thin client MUST call Rust backend (/generate); no local PIL generation.

Backend contract:
  service = "subito"
  method  = one of: qr | email_request | phone_request | email_payment | sms_payment
  country = lang (uk|nl)
"""

from __future__ import annotations

import io
import base64
import logging
from typing import Optional

import requests
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    ConversationHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

from app.config import CFG
from app.keyboards.qr import menu_back_kb, photo_step_kb, main_menu_kb
from app.utils.state_stack import push_state, clear_stack
from app.utils.async_helpers import generate_with_queue

logger = logging.getLogger(__name__)

# States (use high numbers to avoid collisions)
SUBITO_TYPE, SUBITO_LANG, SUBITO_TITLE, SUBITO_PRICE, SUBITO_PHOTO, SUBITO_URL = range(200, 206)


# ========== BACKEND CALL ==========

def _backend_generate_subito(
    lang: str,
    method: str,
    title: str,
    price: float,
    photo_b64: Optional[str],
    url: Optional[str],
) -> bytes:
    backend_url = f"{CFG.QR_BACKEND_URL.rstrip('/')}/generate"
    headers = {"X-API-Key": CFG.BACKEND_API_KEY or ""}

    payload = {
        "country": lang,
        "service": "subito",
        "method": method,
        "title": title,
        "price": price,
        "photo": photo_b64,
        "url": url,
    }

    r = requests.post(backend_url, json=payload, headers=headers, timeout=120)
    if not r.ok:
        raise ValueError(r.text)
    return r.content


# ========== KEYBOARDS ==========

def subito_type_kb():
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("📧 Mail запрос", callback_data="SUBITO_TYPE:email_request")],
            [InlineKeyboardButton("📞 Телефон запрос", callback_data="SUBITO_TYPE:phone_request")],
            [InlineKeyboardButton("💳 Mail оплата", callback_data="SUBITO_TYPE:email_payment")],
            [InlineKeyboardButton("📱 SMS оплата", callback_data="SUBITO_TYPE:sms_payment")],
            [InlineKeyboardButton("🔳 QR", callback_data="SUBITO_TYPE:qr")],
            [InlineKeyboardButton("⬅️ Назад", callback_data="QR:MENU")],
        ]
    )


def subito_lang_kb():
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("🇬🇧 UK", callback_data="SUBITO_LANG:uk"),
                InlineKeyboardButton("🇳🇱 NL", callback_data="SUBITO_LANG:nl"),
            ],
            [
                InlineKeyboardButton("⬅️ Назад", callback_data="SUBITO_BACK:TYPE"),
                InlineKeyboardButton("🏠 Главное меню", callback_data="MENU"),
            ],
        ]
    )


# ========== ENTRY ==========

async def subito_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Entry point from QR:SUBITO."""
    clear_stack(context.user_data)
    context.user_data["service"] = "subito"

    await update.callback_query.answer()
    await update.callback_query.edit_message_text(
        "🇮🇹 <b>Subito</b> — выбери тип:",
        reply_markup=subito_type_kb(),
        parse_mode="HTML",
    )
    push_state(context.user_data, SUBITO_TYPE)
    return SUBITO_TYPE


# ========== TYPE ==========

async def subito_type_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    method = q.data.split(":", 1)[1]
    context.user_data["subito_type"] = method

    await q.answer()
    await q.edit_message_text(
        "Выбери язык (теги uk / nl):",
        reply_markup=subito_lang_kb(),
    )
    push_state(context.user_data, SUBITO_LANG)
    return SUBITO_LANG


async def subito_back_to_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    await q.edit_message_text(
        "🇮🇹 <b>Subito</b> — выбери тип:",
        reply_markup=subito_type_kb(),
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
    )
    push_state(context.user_data, SUBITO_TITLE)
    return SUBITO_TITLE


# ========== TITLE / PRICE ==========

async def subito_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["subito_title"] = (update.message.text or "").strip()
    await update.message.reply_text(
        "💵 Введи <b>цену</b> (например: 123.45):",
        parse_mode="HTML",
        reply_markup=menu_back_kb(),
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
        reply_markup=photo_step_kb(),
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
            reply_markup=menu_back_kb(),
        )
        push_state(context.user_data, SUBITO_URL)
        return SUBITO_URL

    # otherwise generate immediately
    return await _subito_generate(update, context)


async def subito_skip_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    context.user_data["subito_photo"] = None

    method = context.user_data.get("subito_type", "qr")
    if method == "qr":
        await q.edit_message_text(
            "🔗 Введи <b>URL</b> для QR:",
            parse_mode="HTML",
            reply_markup=menu_back_kb(),
        )
        push_state(context.user_data, SUBITO_URL)
        return SUBITO_URL

    # generate
    # We don't have a message context here, so send a new message.
    await q.message.reply_text("⏳ Генерирую...")
    return await _subito_generate(q.message, context)


# ========== URL (QR only) ==========

async def subito_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["subito_url"] = (update.message.text or "").strip()
    return await _subito_generate(update.message, context)


# ========== GENERATE ==========

async def _subito_generate(update_or_message, context: ContextTypes.DEFAULT_TYPE):
    """Generate via backend and send PNG."""
    lang = context.user_data.get("subito_lang", "uk")
    method = context.user_data.get("subito_type", "qr")
    title = context.user_data.get("subito_title", "")
    price = float(context.user_data.get("subito_price", 0.0))
    photo_b64 = context.user_data.get("subito_photo")
    url = context.user_data.get("subito_url")

    executor = context.application.bot_data.get("executor")

    try:
        if hasattr(update_or_message, "reply_text"):
            msg = await update_or_message.reply_text("⏳ Генерирую...")
        else:
            msg = None

        png_bytes = await generate_with_queue(
            executor,
            _backend_generate_subito,
            lang,
            method,
            title,
            price,
            photo_b64,
            url,
        )

        bio = io.BytesIO(png_bytes)
        bio.name = f"subito_{method}_{lang}.png"
        bio.seek(0)

        if msg:
            await msg.delete()

        # Send image
        await update_or_message.reply_photo(photo=bio, reply_markup=main_menu_kb())

    except Exception as e:
        logger.exception("Subito generation failed")
        if hasattr(update_or_message, "reply_text"):
            await update_or_message.reply_text(f"❌ Ошибка генерации: {e}")

    return ConversationHandler.END


# ========== CONVERSATION ==========

subito_variants_conv = ConversationHandler(
    entry_points=[CallbackQueryHandler(subito_start, pattern=r"^QR:SUBITO$")],
    states={
        SUBITO_TYPE: [
            CallbackQueryHandler(subito_type_selected, pattern=r"^SUBITO_TYPE:"),
        ],
        SUBITO_LANG: [
            CallbackQueryHandler(subito_lang_selected, pattern=r"^SUBITO_LANG:"),
            CallbackQueryHandler(subito_back_to_type, pattern=r"^SUBITO_BACK:TYPE$"),
        ],
        SUBITO_TITLE: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, subito_title),
        ],
        SUBITO_PRICE: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, subito_price),
        ],
        SUBITO_PHOTO: [
            MessageHandler(filters.PHOTO, subito_photo),
            CallbackQueryHandler(subito_skip_photo, pattern=r"^QR:SKIP_PHOTO$"),
        ],
        SUBITO_URL: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, subito_url),
        ],
    },
    fallbacks=[],
    name="subito_variants_conv",
    persistent=False,
)
