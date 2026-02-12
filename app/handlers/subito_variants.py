# app/handlers/subito_variants.py
"""
Telegram handler для Subito (subito6–10, uk / nl).

subito6  — mail запрос
subito7  — телефон запрос
subito8  — mail оплата
subito9  — sms оплата
subito10 — qr
"""
import base64
import logging
from io import BytesIO

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, InputFile
from telegram.ext import (
    ConversationHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes
)

from app.services.subito_variants import (
    create_subito_new_email_request,
    create_subito_new_phone_request,
    create_subito_new_email_payment,
    create_subito_new_sms_payment,
    create_subito_new_qr,
)

logger = logging.getLogger(__name__)

# ── States ────────────────────────────────────────────────────────────────────
(
    SUBITO_TYPE,
    SUBITO_LANG,
    SUBITO_TITLE,
    SUBITO_PRICE,
    SUBITO_PHOTO,
    SUBITO_URL,
) = range(6)

# ── Метаданные вариантов ──────────────────────────────────────────────────────
_TYPES = {
    "email_request": "📧 Mail запрос",
    "phone_request": "📞 Тел. запрос",
    "email_payment": "💳 Mail оплата",
    "sms_payment":   "💬 SMS оплата",
    "qr":            "🔵 QR",
}
_NEEDS_URL = {"qr"}


# ── Клавиатуры ────────────────────────────────────────────────────────────────

def _type_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(_TYPES["email_request"], callback_data="SN_TYPE:email_request")],
        [InlineKeyboardButton(_TYPES["phone_request"], callback_data="SN_TYPE:phone_request")],
        [InlineKeyboardButton(_TYPES["email_payment"], callback_data="SN_TYPE:email_payment")],
        [InlineKeyboardButton(_TYPES["sms_payment"],   callback_data="SN_TYPE:sms_payment")],
        [InlineKeyboardButton(_TYPES["qr"],            callback_data="SN_TYPE:qr")],
        [InlineKeyboardButton("🏠 Главное меню",       callback_data="MENU")],
    ])


def _lang_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🇬🇧 UK", callback_data="SN_LANG:uk"),
         InlineKeyboardButton("🇳🇱 NL", callback_data="SN_LANG:nl")],
    ])


def _skip_kb(action: str):
    return InlineKeyboardMarkup([[InlineKeyboardButton("⏭️ Пропустить", callback_data=f"SN_SKIP:{action}")]])


# ── Вход ─────────────────────────────────────────────────────────────────────

async def subito_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await update.callback_query.edit_message_text(
        "🇮🇹 <b>Subito — выбери тип:</b>",
        reply_markup=_type_kb(),
        parse_mode="HTML",
    )
    return SUBITO_TYPE


# ── Выбор типа ────────────────────────────────────────────────────────────────

async def subito_type_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    variant = q.data.split(":")[1]
    context.user_data["sn_variant"] = variant
    await q.answer()
    await q.edit_message_text(
        f"🇮🇹 <b>Subito — {_TYPES[variant]}</b>\n\n🌍 Выбери локаль:",
        reply_markup=_lang_kb(),
        parse_mode="HTML",
    )
    return SUBITO_LANG


# ── Выбор языка ───────────────────────────────────────────────────────────────

async def subito_lang_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    lang = q.data.split(":")[1]
    context.user_data["sn_lang"] = lang
    await q.answer()
    await q.edit_message_text(
        f"🌍 Локаль: <b>{lang.upper()}</b>\n\n📝 Введи <b>название товара</b>:",
        parse_mode="HTML",
    )
    return SUBITO_TITLE


# ── Название ─────────────────────────────────────────────────────────────────

async def subito_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["sn_title"] = update.message.text
    await update.message.reply_text("💵 Введи <b>цену</b> (например: 99.99):", parse_mode="HTML")
    return SUBITO_PRICE


# ── Цена ─────────────────────────────────────────────────────────────────────

async def subito_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        price = float(update.message.text.replace(",", "."))
        context.user_data["sn_price"] = price
        await update.message.reply_text(
            "📸 Отправь <b>фото товара</b> или пропусти:",
            reply_markup=_skip_kb("photo"),
            parse_mode="HTML",
        )
        return SUBITO_PHOTO
    except ValueError:
        await update.message.reply_text("❌ Неверный формат цены. Введи ещё раз (например: 99.99):")
        return SUBITO_PRICE


# ── Фото ─────────────────────────────────────────────────────────────────────

async def subito_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    photo_file = await update.message.photo[-1].get_file()
    photo_bytes = await photo_file.download_as_bytearray()
    context.user_data["sn_photo"] = base64.b64encode(photo_bytes).decode("utf-8")
    return await _after_photo(update, context, via_query=False)


async def subito_skip_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["sn_photo"] = None
    await update.callback_query.answer()
    return await _after_photo(update, context, via_query=True)


async def _after_photo(update, context, via_query: bool):
    variant = context.user_data.get("sn_variant", "email_request")
    if variant in _NEEDS_URL:
        text = "🔗 Введи <b>URL</b> (например: https://subito.it/item/123):"
        if via_query:
            await update.callback_query.edit_message_text(text, parse_mode="HTML")
        else:
            await update.message.reply_text(text, parse_mode="HTML")
        return SUBITO_URL
    else:
        if via_query:
            await update.callback_query.message.reply_text("⏳ Генерирую...")
            await _generate(update, context, via_query=True)
        else:
            await update.message.reply_text("⏳ Генерирую...")
            await _generate(update, context, via_query=False)
        return ConversationHandler.END


# ── URL (только для qr) ───────────────────────────────────────────────────────

async def subito_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["sn_url"] = update.message.text
    await update.message.reply_text("⏳ Генерирую...")
    await _generate(update, context, via_query=False)
    return ConversationHandler.END


# ── Генерация ────────────────────────────────────────────────────────────────

async def _generate(update: Update, context: ContextTypes.DEFAULT_TYPE, via_query: bool):
    variant = context.user_data.get("sn_variant", "email_request")
    lang    = context.user_data.get("sn_lang", "uk")
    title   = context.user_data.get("sn_title", "")
    price   = context.user_data.get("sn_price", 0.0)
    photo   = context.user_data.get("sn_photo")
    url     = context.user_data.get("sn_url", "")

    try:
        if variant == "email_request":
            data = create_subito_new_email_request(lang, title, price, photo)
        elif variant == "phone_request":
            data = create_subito_new_phone_request(lang, title, price, photo)
        elif variant == "email_payment":
            data = create_subito_new_email_payment(lang, title, price, photo)
        elif variant == "sms_payment":
            data = create_subito_new_sms_payment(lang, title, price, photo)
        elif variant == "qr":
            data = create_subito_new_qr(lang, title, price, photo, url)
        else:
            raise ValueError(f"Unknown variant: {variant}")

        caption = (
            f"✅ <b>Subito — {_TYPES[variant]} [{lang.upper()}]</b>\n\n"
            f"📝 {title}\n💵 {price:.2f} €"
        )
        doc = InputFile(BytesIO(data), filename="subito.png")

        if via_query:
            await update.callback_query.message.reply_document(
                document=doc, caption=caption, parse_mode="HTML"
            )
        else:
            await update.message.reply_document(
                document=doc, caption=caption, parse_mode="HTML"
            )

    except Exception as e:
        logger.error(f"Subito generation error: {e}")
        err = f"❌ Ошибка генерации:\n<code>{e}</code>"
        if via_query:
            await update.callback_query.message.reply_text(err, parse_mode="HTML")
        else:
            await update.message.reply_text(err, parse_mode="HTML")


# ── Cancel ────────────────────────────────────────────────────────────────────

async def subito_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from app.handlers.menu import start
    await update.callback_query.answer()
    await start(update, context)
    return ConversationHandler.END


# ── ConversationHandler ───────────────────────────────────────────────────────

subito_variants_conv = ConversationHandler(
    entry_points=[CallbackQueryHandler(subito_start, pattern=r"^QR:SUBITO$")],
    states={
        SUBITO_TYPE: [
            CallbackQueryHandler(subito_type_selected, pattern=r"^SN_TYPE:")
        ],
        SUBITO_LANG: [
            CallbackQueryHandler(subito_lang_selected, pattern=r"^SN_LANG:")
        ],
        SUBITO_TITLE: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, subito_title)
        ],
        SUBITO_PRICE: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, subito_price)
        ],
        SUBITO_PHOTO: [
            MessageHandler(filters.PHOTO, subito_photo),
            CallbackQueryHandler(subito_skip_photo, pattern=r"^SN_SKIP:photo$"),
        ],
        SUBITO_URL: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, subito_url)
        ],
    },
    fallbacks=[CallbackQueryHandler(subito_cancel, pattern=r"^MENU$")],
    name="subito_variants",
    per_message=False,
    allow_reentry=True,
)
