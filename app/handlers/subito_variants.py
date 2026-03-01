# app/handlers/subito_variants.py
"""Subito variants (frames subito6..subito10).

Only Italy is supported for Subito.

Backend contract:
  service = "subito"
  method  = one of: qr | email_request | sms_request | email_confirm | sms_confirm
  country = "it"

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
from app.handlers.menu import start as show_main_menu
from app.handlers.subscription_access import ensure_generation_access, should_apply_watermark
from app.services.watermark import apply_enclave_watermark
from app.utils.async_helpers import generate_with_queue
from app.utils.state_stack import clear_stack, push_state

logger = logging.getLogger(__name__)

# States
SUBITO_TYPE, SUBITO_TITLE, SUBITO_PRICE, SUBITO_PHOTO, SUBITO_URL = range(200, 205)


def _backend_generate_subito(
    method: str,
    title: str,
    price: float,
    photo_b64: Optional[str],
    url: Optional[str],
) -> bytes:
    backend_url = f"{CFG.QR_BACKEND_URL.rstrip('/')}/generate"
    headers = {"X-API-Key": CFG.BACKEND_API_KEY or ""}

    payload = {
        "country": "it",
        "service": "subito",
        "method": method,
        "title": title,
        "price": price,
        "photo": photo_b64,
        "url": url,
    }

    r = requests.post(backend_url, json=payload, headers=headers, timeout=180)
    if not r.ok:
        raise ValueError(r.text)
    return r.content


def _nav_row(back_cb: str):
    return [
        InlineKeyboardButton("⬅️ Назад", callback_data=back_cb),
        InlineKeyboardButton("🏠 Главное меню", callback_data="MENU"),
    ]


def subito_type_kb():
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("📧 Mail запрос", callback_data="SUBITO_TYPE:email_request")],
            [InlineKeyboardButton("📩 SMS запрос", callback_data="SUBITO_TYPE:sms_request")],
            [InlineKeyboardButton("✅ Mail подтверждение", callback_data="SUBITO_TYPE:email_confirm")],
            [InlineKeyboardButton("✅ SMS подтверждение", callback_data="SUBITO_TYPE:sms_confirm")],
            [InlineKeyboardButton("🔳 QR", callback_data="SUBITO_TYPE:qr")],
            _nav_row("QR:MENU"),
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


async def subito_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
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


async def subito_type_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    method = q.data.split(":", 1)[1]
    context.user_data["subito_type"] = method

    await q.answer()
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
    await q.edit_message_text(
        "🇮🇹 <b>Subito</b> — выбери тип:",
        reply_markup=subito_type_kb(),
        parse_mode="HTML",
    )
    return SUBITO_TYPE


async def subito_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["subito_title"] = (update.message.text or "").strip()
    await update.message.reply_text(
        "💵 Введи <b>цену</b> (например: 123.45):",
        parse_mode="HTML",
        reply_markup=subito_price_kb(),
    )
    push_state(context.user_data, SUBITO_PRICE)
    return SUBITO_PRICE


async def subito_back_to_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    await q.edit_message_text(
        "📝 Введи <b>название товара</b>:",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([_nav_row("SUBITO_BACK:TYPE")]),
    )
    return SUBITO_TITLE


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


async def subito_back_to_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    await q.edit_message_text(
        "💵 Введи <b>цену</b> (например: 123.45):",
        parse_mode="HTML",
        reply_markup=subito_price_kb(),
    )
    return SUBITO_PRICE


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

    return await _subito_generate(update.message, context)


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

    await q.message.reply_text("⏳ Генерирую...")
    return await _subito_generate(update, context)


async def subito_back_to_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    await q.edit_message_text(
        "📸 Отправь <b>фото товара</b> или пропусти:",
        parse_mode="HTML",
        reply_markup=subito_photo_kb(),
    )
    return SUBITO_PHOTO


async def subito_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["subito_url"] = (update.message.text or "").strip()
    return await _subito_generate(update.message, context)


async def subito_menu_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer("Возврат в главное меню")
    clear_stack(context.user_data)
    await show_main_menu(update, context)
    return ConversationHandler.END


async def _subito_generate(update_or_message, context: ContextTypes.DEFAULT_TYPE):
    if isinstance(update_or_message, Update):
        message = update_or_message.message or (update_or_message.callback_query.message if update_or_message.callback_query else None)
    else:
        message = update_or_message
    method = context.user_data.get("subito_type", "qr")
    title = context.user_data.get("subito_title", "")
    price = float(context.user_data.get("subito_price", 0.0))
    photo_b64 = context.user_data.get("subito_photo")
    url = context.user_data.get("subito_url")

    executor = context.application.bot_data.get("executor")

    try:
        if not await ensure_generation_access(update_or_message, context):
            return ConversationHandler.END

        msg = await message.reply_text("⏳ Генерирую...")

        png_bytes = await generate_with_queue(
            executor,
            _backend_generate_subito,
            method,
            title,
            price,
            photo_b64,
            url,
        )
        if should_apply_watermark(update_or_message):
            png_bytes = apply_enclave_watermark(png_bytes)

        bio = io.BytesIO(png_bytes)
        bio.name = f"subito_{method}_it.png"
        bio.seek(0)

        await msg.delete()
        await message.reply_photo(photo=bio, reply_markup=main_menu_kb())

    except Exception as e:
        logger.exception("Subito generation failed")
        await message.reply_text(f"❌ Ошибка генерации: {e}")

    return ConversationHandler.END


subito_variants_conv = ConversationHandler(
    entry_points=[CallbackQueryHandler(subito_start, pattern=r"^QR:SUBITO$")],
    states={
        SUBITO_TYPE: [
            CallbackQueryHandler(subito_type_selected, pattern=r"^SUBITO_TYPE:"),
            CallbackQueryHandler(subito_menu_cb, pattern=r"^(QR:MENU|MENU)$"),
        ],
        SUBITO_TITLE: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, subito_title),
            CallbackQueryHandler(subito_back_to_type, pattern=r"^SUBITO_BACK:TYPE$"),
            CallbackQueryHandler(subito_menu_cb, pattern=r"^(QR:MENU|MENU)$"),
        ],
        SUBITO_PRICE: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, subito_price),
            CallbackQueryHandler(subito_back_to_title, pattern=r"^SUBITO_BACK:TITLE$"),
            CallbackQueryHandler(subito_menu_cb, pattern=r"^(QR:MENU|MENU)$"),
        ],
        SUBITO_PHOTO: [
            MessageHandler(filters.PHOTO, subito_photo),
            CallbackQueryHandler(subito_skip_photo, pattern=r"^SUBITO:SKIP_PHOTO$"),
            CallbackQueryHandler(subito_back_to_price, pattern=r"^SUBITO_BACK:PRICE$"),
            CallbackQueryHandler(subito_menu_cb, pattern=r"^(QR:MENU|MENU)$"),
        ],
        SUBITO_URL: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, subito_url),
            CallbackQueryHandler(subito_back_to_photo, pattern=r"^SUBITO_BACK:PHOTO$"),
            CallbackQueryHandler(subito_menu_cb, pattern=r"^(QR:MENU|MENU)$"),
        ],
    },
    fallbacks=[CallbackQueryHandler(subito_menu_cb, pattern=r"^(QR:MENU|MENU)$")],
    name="subito_variants_conv",
    persistent=False,
)
