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
from app.handlers.menu import start as show_main_menu
from app.handlers.subscription_access import ensure_generation_access, should_apply_watermark
from app.services.watermark import apply_enclave_watermark
from app.keyboards.qr import main_menu_kb
from app.utils.async_helpers import generate_with_queue
from app.utils.state_stack import clear_stack, push_state

logger = logging.getLogger(__name__)

GUMTREE_TYPE, GUMTREE_LANG, GUMTREE_TITLE, GUMTREE_PRICE, GUMTREE_PHOTO, GUMTREE_URL = range(300, 306)


def _backend_generate_gumtree(
    country: str,
    method: str,
    title: str,
    price: float,
    photo_b64: Optional[str],
    url: Optional[str],
) -> bytes:
    backend_url = f"{CFG.QR_BACKEND_URL.rstrip('/')}/generate"
    headers = {"X-API-Key": CFG.BACKEND_API_KEY or ""}

    payload = {
        "country": country,
        "service": "gumtree",
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


def gumtree_type_kb():
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("📧 Mail запрос", callback_data="GUMTREE_TYPE:email_request")],
            [InlineKeyboardButton("📞 Phone запрос", callback_data="GUMTREE_TYPE:phone_request")],
            [InlineKeyboardButton("💳 Mail оплата", callback_data="GUMTREE_TYPE:email_payment")],
            [InlineKeyboardButton("📱 SMS оплата", callback_data="GUMTREE_TYPE:sms_payment")],
            [InlineKeyboardButton("🔳 QR", callback_data="GUMTREE_TYPE:qr")],
            _nav_row("QR:MENU"),
        ]
    )


def gumtree_lang_kb():
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("🇬🇧 UK", callback_data="GUMTREE_LANG:uk"),
                InlineKeyboardButton("🇦🇺 AU", callback_data="GUMTREE_LANG:au"),
            ],
            _nav_row("GUMTREE_BACK:TYPE"),
        ]
    )


def gumtree_price_kb():
    return InlineKeyboardMarkup([_nav_row("GUMTREE_BACK:TITLE")])


def gumtree_photo_kb():
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("⏭️ Пропустить фото", callback_data="GUMTREE:SKIP_PHOTO")],
            _nav_row("GUMTREE_BACK:PRICE"),
        ]
    )


def gumtree_url_kb():
    return InlineKeyboardMarkup([_nav_row("GUMTREE_BACK:PHOTO")])


async def gumtree_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    clear_stack(context.user_data)
    context.user_data["service"] = "gumtree"

    await update.callback_query.answer()
    await update.callback_query.edit_message_text(
        "🌳 <b>Gumtree</b> — выбери тип:",
        reply_markup=gumtree_type_kb(),
        parse_mode="HTML",
    )
    push_state(context.user_data, GUMTREE_TYPE)
    return GUMTREE_TYPE


async def gumtree_type_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    method = q.data.split(":", 1)[1]
    context.user_data["gumtree_type"] = method

    await q.answer()
    await q.edit_message_text(
        "🌍 Выбери гео:",
        parse_mode="HTML",
        reply_markup=gumtree_lang_kb(),
    )
    push_state(context.user_data, GUMTREE_LANG)
    return GUMTREE_LANG


async def gumtree_lang_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    country = q.data.split(":", 1)[1]
    context.user_data["gumtree_country"] = country

    await q.answer()
    await q.edit_message_text(
        "📝 Введи <b>название товара</b>:",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([_nav_row("GUMTREE_BACK:LANG")]),
    )
    push_state(context.user_data, GUMTREE_TITLE)
    return GUMTREE_TITLE


async def gumtree_back_to_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    await q.edit_message_text(
        "🌳 <b>Gumtree</b> — выбери тип:",
        parse_mode="HTML",
        reply_markup=gumtree_type_kb(),
    )
    return GUMTREE_TYPE


async def gumtree_back_to_lang(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    await q.edit_message_text("🌍 Выбери гео:", parse_mode="HTML", reply_markup=gumtree_lang_kb())
    return GUMTREE_LANG


async def gumtree_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["gumtree_title"] = (update.message.text or "").strip()
    await update.message.reply_text(
        "💵 Введи <b>цену</b> (например: 123.45):",
        parse_mode="HTML",
        reply_markup=gumtree_price_kb(),
    )
    push_state(context.user_data, GUMTREE_PRICE)
    return GUMTREE_PRICE


async def gumtree_back_to_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    await q.edit_message_text(
        "📝 Введи <b>название товара</b>:",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([_nav_row("GUMTREE_BACK:LANG")]),
    )
    return GUMTREE_TITLE


async def gumtree_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        price = float((update.message.text or "").replace(",", ".").strip())
    except ValueError:
        await update.message.reply_text("❌ Неверный формат. Введи цену (например 123.45)")
        return GUMTREE_PRICE

    context.user_data["gumtree_price"] = price

    await update.message.reply_text(
        "📸 Отправь <b>фото товара</b> или пропусти:",
        parse_mode="HTML",
        reply_markup=gumtree_photo_kb(),
    )
    push_state(context.user_data, GUMTREE_PHOTO)
    return GUMTREE_PHOTO


async def gumtree_back_to_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    await q.edit_message_text(
        "💵 Введи <b>цену</b> (например: 123.45):",
        parse_mode="HTML",
        reply_markup=gumtree_price_kb(),
    )
    return GUMTREE_PRICE


async def gumtree_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    photo_b64 = None
    if update.message and update.message.photo:
        photo_file = await update.message.photo[-1].get_file()
        photo_bytes = await photo_file.download_as_bytearray()
        photo_b64 = base64.b64encode(photo_bytes).decode("utf-8")

    context.user_data["gumtree_photo"] = photo_b64

    method = context.user_data.get("gumtree_type", "qr")
    if method == "qr":
        await update.message.reply_text(
            "🔗 Введи <b>URL</b> для QR:",
            parse_mode="HTML",
            reply_markup=gumtree_url_kb(),
        )
        push_state(context.user_data, GUMTREE_URL)
        return GUMTREE_URL

    return await _gumtree_generate(update.message, context)


async def gumtree_skip_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    context.user_data["gumtree_photo"] = None

    method = context.user_data.get("gumtree_type", "qr")
    if method == "qr":
        await q.edit_message_text(
            "🔗 Введи <b>URL</b> для QR:",
            parse_mode="HTML",
            reply_markup=gumtree_url_kb(),
        )
        push_state(context.user_data, GUMTREE_URL)
        return GUMTREE_URL

    await q.message.reply_text("⏳ Генерирую...")
    return await _gumtree_generate(q.message, context)


async def gumtree_back_to_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    await q.edit_message_text(
        "📸 Отправь <b>фото товара</b> или пропусти:",
        parse_mode="HTML",
        reply_markup=gumtree_photo_kb(),
    )
    return GUMTREE_PHOTO


async def gumtree_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["gumtree_url"] = (update.message.text or "").strip()
    return await _gumtree_generate(update.message, context)


async def gumtree_menu_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer("Возврат в главное меню")
    clear_stack(context.user_data)
    await show_main_menu(update, context)
    return ConversationHandler.END


async def _gumtree_generate(message, context: ContextTypes.DEFAULT_TYPE):
    method = context.user_data.get("gumtree_type", "qr")
    country = context.user_data.get("gumtree_country", "uk")
    title = context.user_data.get("gumtree_title", "")
    price = float(context.user_data.get("gumtree_price", 0.0))
    photo_b64 = context.user_data.get("gumtree_photo")
    url = context.user_data.get("gumtree_url")

    executor = context.application.bot_data.get("executor")

    try:
        if not await ensure_generation_access(message, context):
            return ConversationHandler.END

        msg = await message.reply_text("⏳ Генерирую...")

        png_bytes = await generate_with_queue(
            executor,
            _backend_generate_gumtree,
            country,
            method,
            title,
            price,
            photo_b64,
            url,
        )
        if should_apply_watermark(message):
            png_bytes = apply_enclave_watermark(png_bytes)

        bio = io.BytesIO(png_bytes)
        bio.name = f"gumtree_{method}_{country}.png"
        bio.seek(0)

        await msg.delete()
        await message.reply_photo(photo=bio, reply_markup=main_menu_kb())

    except Exception as e:
        logger.exception("Gumtree generation failed")
        await message.reply_text(f"❌ Ошибка генерации: {e}")

    return ConversationHandler.END


gumtree_variants_conv = ConversationHandler(
    entry_points=[CallbackQueryHandler(gumtree_start, pattern=r"^QR:GUMTREE$")],
    states={
        GUMTREE_TYPE: [
            CallbackQueryHandler(gumtree_type_selected, pattern=r"^GUMTREE_TYPE:"),
            CallbackQueryHandler(gumtree_menu_cb, pattern=r"^(QR:MENU|MENU)$"),
        ],
        GUMTREE_LANG: [
            CallbackQueryHandler(gumtree_lang_selected, pattern=r"^GUMTREE_LANG:"),
            CallbackQueryHandler(gumtree_back_to_type, pattern=r"^GUMTREE_BACK:TYPE$"),
            CallbackQueryHandler(gumtree_menu_cb, pattern=r"^(QR:MENU|MENU)$"),
        ],
        GUMTREE_TITLE: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, gumtree_title),
            CallbackQueryHandler(gumtree_back_to_lang, pattern=r"^GUMTREE_BACK:LANG$"),
            CallbackQueryHandler(gumtree_menu_cb, pattern=r"^(QR:MENU|MENU)$"),
        ],
        GUMTREE_PRICE: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, gumtree_price),
            CallbackQueryHandler(gumtree_back_to_title, pattern=r"^GUMTREE_BACK:TITLE$"),
            CallbackQueryHandler(gumtree_menu_cb, pattern=r"^(QR:MENU|MENU)$"),
        ],
        GUMTREE_PHOTO: [
            MessageHandler(filters.PHOTO, gumtree_photo),
            CallbackQueryHandler(gumtree_skip_photo, pattern=r"^GUMTREE:SKIP_PHOTO$"),
            CallbackQueryHandler(gumtree_back_to_price, pattern=r"^GUMTREE_BACK:PRICE$"),
            CallbackQueryHandler(gumtree_menu_cb, pattern=r"^(QR:MENU|MENU)$"),
        ],
        GUMTREE_URL: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, gumtree_url),
            CallbackQueryHandler(gumtree_back_to_photo, pattern=r"^GUMTREE_BACK:PHOTO$"),
            CallbackQueryHandler(gumtree_menu_cb, pattern=r"^(QR:MENU|MENU)$"),
        ],
    },
    fallbacks=[CallbackQueryHandler(gumtree_menu_cb, pattern=r"^(QR:MENU|MENU)$")],
    name="gumtree_variants_conv",
    persistent=False,
)
