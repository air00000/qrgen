from __future__ import annotations

import base64
import io
import logging
import uuid
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
from app.keyboards.qr import main_menu_kb
from app.utils.async_helpers import generate_with_queue
from app.utils.state_stack import clear_stack, push_state

logger = logging.getLogger(__name__)

JOFOGAS_TITLE = 400
JOFOGAS_PRICE = 401
JOFOGAS_SURNAME = 402
JOFOGAS_ADDRESS = 404
JOFOGAS_PHOTO = 405


def _backend_generate_jofogas(
    title: str,
    price: float,
    surname: str,
    name: str,
    address: str,
    photo_b64: Optional[str],
) -> bytes:
    backend_url = f"{CFG.QR_BACKEND_URL.rstrip('/')}/generate"
    headers = {"X-API-Key": CFG.BACKEND_API_KEY or ""}

    payload = {
        "country": "hu",
        "service": "jofogas",
        "method": "payment",
        "title": title,
        "price": price,
        "surname": surname,
        "name": name,
        "address": address,
        "photo": photo_b64,
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


def jofogas_photo_kb():
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("⏭️ Пропустить фото", callback_data="JOFOGAS:SKIP_PHOTO")],
            _nav_row("JOFOGAS_BACK:ADDRESS"),
        ]
    )


async def jofogas_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    clear_stack(context.user_data)
    context.user_data["service"] = "jofogas"

    await update.callback_query.answer()
    await update.callback_query.edit_message_text(
        "🇭🇺 <b>Jófogás</b> — введи название товара:",
        reply_markup=InlineKeyboardMarkup([_nav_row("QR:MENU")]),
        parse_mode="HTML",
    )
    push_state(context.user_data, JOFOGAS_TITLE)
    return JOFOGAS_TITLE


async def jofogas_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["jofogas_title"] = (update.message.text or "").strip()
    await update.message.reply_text(
        "💵 Введи <b>базовую цену</b> товара (например: 123450):",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([_nav_row("JOFOGAS_BACK:TITLE")]),
    )
    push_state(context.user_data, JOFOGAS_PRICE)
    return JOFOGAS_PRICE


async def jofogas_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").replace(" ", "").replace(",", "").strip()
    try:
        price = float(text)
    except ValueError:
        await update.message.reply_text("❌ Неверный формат. Введи цену числом (например 123450)")
        return JOFOGAS_PRICE

    context.user_data["jofogas_price"] = price
    await update.message.reply_text(
        "👤 Введи <b>фамилию и имя</b> покупателя через пробел:",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([_nav_row("JOFOGAS_BACK:PRICE")]),
    )
    push_state(context.user_data, JOFOGAS_SURNAME)
    return JOFOGAS_SURNAME


async def jofogas_surname(update: Update, context: ContextTypes.DEFAULT_TYPE):
    full_name = (update.message.text or "").strip().split()
    if len(full_name) < 2:
        await update.message.reply_text(
            "❌ Введи фамилию и имя через пробел (например: Nagy István)"
        )
        return JOFOGAS_SURNAME

    context.user_data["jofogas_surname"] = full_name[0]
    context.user_data["jofogas_name"] = " ".join(full_name[1:])
    await update.message.reply_text(
        "📍 Введи <b>адрес</b> покупателя:",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([_nav_row("JOFOGAS_BACK:SURNAME")]),
    )
    push_state(context.user_data, JOFOGAS_ADDRESS)
    return JOFOGAS_ADDRESS


async def jofogas_address(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["jofogas_address"] = (update.message.text or "").strip()
    await update.message.reply_text(
        "📸 Отправь <b>фото товара</b> или пропусти:",
        parse_mode="HTML",
        reply_markup=jofogas_photo_kb(),
    )
    push_state(context.user_data, JOFOGAS_PHOTO)
    return JOFOGAS_PHOTO


async def jofogas_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    photo_b64 = None
    if update.message and update.message.photo:
        photo_file = await update.message.photo[-1].get_file()
        photo_bytes = await photo_file.download_as_bytearray()
        photo_b64 = base64.b64encode(photo_bytes).decode("utf-8")

    context.user_data["jofogas_photo"] = photo_b64
    return await _jofogas_generate(update.message, context)


async def jofogas_skip_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    context.user_data["jofogas_photo"] = None
    return await _jofogas_generate(q.message, context)


async def _jofogas_generate(message, context: ContextTypes.DEFAULT_TYPE):
    title = context.user_data.get("jofogas_title", "")
    price = float(context.user_data.get("jofogas_price", 0.0))
    surname = context.user_data.get("jofogas_surname", "")
    name = context.user_data.get("jofogas_name", "")
    address = context.user_data.get("jofogas_address", "")
    photo_b64 = context.user_data.get("jofogas_photo")

    executor = context.application.bot_data.get("executor")

    try:
        msg = await message.reply_text("⏳ Генерирую...")

        png_bytes = await generate_with_queue(
            executor,
            _backend_generate_jofogas,
            title,
            price,
            surname,
            name,
            address,
            photo_b64,
        )

        bio = io.BytesIO(png_bytes)
        bio.name = f"jofogas_{uuid.uuid4().hex[:8]}.png"
        bio.seek(0)

        await msg.delete()
        await message.reply_photo(photo=bio, reply_markup=main_menu_kb())

    except Exception as e:
        logger.exception("Jofogas generation failed")
        await message.reply_text(f"❌ Ошибка генерации: {e}")

    return ConversationHandler.END


async def jofogas_menu_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer("Возврат в главное меню")
    clear_stack(context.user_data)
    await show_main_menu(update, context)
    return ConversationHandler.END


# Back handlers
async def jofogas_back_to_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    await q.edit_message_text(
        "🇭🇺 <b>Jófogás</b> — введи название товара:",
        reply_markup=InlineKeyboardMarkup([_nav_row("QR:MENU")]),
        parse_mode="HTML",
    )
    return JOFOGAS_TITLE


async def jofogas_back_to_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    await q.edit_message_text(
        "💵 Введи <b>базовую цену</b> товара (например: 123450):",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([_nav_row("JOFOGAS_BACK:TITLE")]),
    )
    return JOFOGAS_PRICE


async def jofogas_back_to_surname(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    await q.edit_message_text(
        "👤 Введи <b>фамилию и имя</b> покупателя через пробел:",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([_nav_row("JOFOGAS_BACK:PRICE")]),
    )
    return JOFOGAS_SURNAME


async def jofogas_back_to_address(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    await q.edit_message_text(
        "📍 Введи <b>адрес</b> покупателя:",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([_nav_row("JOFOGAS_BACK:SURNAME")]),
    )
    return JOFOGAS_ADDRESS


async def jofogas_back_to_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    await q.edit_message_text(
        "📸 Отправь <b>фото товара</b> или пропусти:",
        parse_mode="HTML",
        reply_markup=jofogas_photo_kb(),
    )
    return JOFOGAS_PHOTO


jofogas_variants_conv = ConversationHandler(
    entry_points=[CallbackQueryHandler(jofogas_start, pattern=r"^QR:JOFOGAS$")],
    states={
        JOFOGAS_TITLE: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, jofogas_title),
            CallbackQueryHandler(jofogas_menu_cb, pattern=r"^(QR:MENU|MENU)$"),
        ],
        JOFOGAS_PRICE: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, jofogas_price),
            CallbackQueryHandler(jofogas_back_to_title, pattern=r"^JOFOGAS_BACK:TITLE$"),
            CallbackQueryHandler(jofogas_menu_cb, pattern=r"^(QR:MENU|MENU)$"),
        ],
        JOFOGAS_SURNAME: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, jofogas_surname),
            CallbackQueryHandler(jofogas_back_to_price, pattern=r"^JOFOGAS_BACK:PRICE$"),
            CallbackQueryHandler(jofogas_menu_cb, pattern=r"^(QR:MENU|MENU)$"),
        ],
        JOFOGAS_ADDRESS: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, jofogas_address),
            CallbackQueryHandler(jofogas_back_to_surname, pattern=r"^JOFOGAS_BACK:SURNAME$"),
            CallbackQueryHandler(jofogas_menu_cb, pattern=r"^(QR:MENU|MENU)$"),
        ],
        JOFOGAS_PHOTO: [
            MessageHandler(filters.PHOTO, jofogas_photo),
            CallbackQueryHandler(jofogas_skip_photo, pattern=r"^JOFOGAS:SKIP_PHOTO$"),
            CallbackQueryHandler(jofogas_back_to_address, pattern=r"^JOFOGAS_BACK:ADDRESS$"),
            CallbackQueryHandler(jofogas_menu_cb, pattern=r"^(QR:MENU|MENU)$"),
        ],
    },
    fallbacks=[CallbackQueryHandler(jofogas_menu_cb, pattern=r"^(QR:MENU|MENU)$")],
    name="jofogas_variants_conv",
    persistent=False,
)
