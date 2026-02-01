# app/handlers/markt_variants.py
"""
Telegram bot handlers for Markt service variants.
Supports all 5 generation types with UK and NL language options.
"""
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

from app.keyboards.qr import main_menu_kb, menu_back_kb, photo_step_kb, markt_type_kb, markt_lang_kb
from app.utils.state_stack import push_state, pop_state, clear_stack
from app.utils.async_helpers import generate_with_queue
from app.services.markt import (
    create_markt_qr, create_markt_email_request, create_markt_phone_request,
    create_markt_email_payment, create_markt_sms_payment
)

logger = logging.getLogger(__name__)

# States - using high numbers to avoid collision with main qr.py states
MARKT_TYPE, MARKT_LANG, MARKT_NAZVANIE, MARKT_PRICE, MARKT_PHOTO, MARKT_URL = range(100, 106)


# ========== ENTRY POINTS ==========

async def markt_entry_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Entry point - show Markt type selection menu"""
    context.user_data["service"] = "markt"
    clear_stack(context.user_data)
    await update.callback_query.answer()
    return await ask_markt_type(update, context)


async def ask_markt_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show Markt type selection keyboard"""
    push_state(context.user_data, MARKT_TYPE)
    text = "Выбери тип Markt:"
    
    if update.callback_query:
        await update.callback_query.message.edit_text(text, reply_markup=markt_type_kb())
    else:
        await update.message.reply_text(text, reply_markup=markt_type_kb())
    
    return MARKT_TYPE


# ========== TYPE SELECTION HANDLERS ==========

async def markt_entry_qr(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start Markt QR variant"""
    context.user_data["service"] = "markt"
    context.user_data["markt_type"] = "qr"
    await update.callback_query.answer()
    return await ask_markt_lang(update, context)


async def markt_entry_email_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start Markt Email Request variant"""
    context.user_data["service"] = "markt"
    context.user_data["markt_type"] = "email_request"
    await update.callback_query.answer()
    return await ask_markt_lang(update, context)


async def markt_entry_phone_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start Markt Phone Request variant"""
    context.user_data["service"] = "markt"
    context.user_data["markt_type"] = "phone_request"
    await update.callback_query.answer()
    return await ask_markt_lang(update, context)


async def markt_entry_email_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start Markt Email Payment variant"""
    context.user_data["service"] = "markt"
    context.user_data["markt_type"] = "email_payment"
    await update.callback_query.answer()
    return await ask_markt_lang(update, context)


async def markt_entry_sms_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start Markt SMS Payment variant"""
    context.user_data["service"] = "markt"
    context.user_data["markt_type"] = "sms_payment"
    await update.callback_query.answer()
    return await ask_markt_lang(update, context)


# ========== LANGUAGE SELECTION ==========

async def ask_markt_lang(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show language selection keyboard"""
    push_state(context.user_data, MARKT_LANG)
    markt_type = context.user_data.get("markt_type", "qr")
    text = f"Выбери язык для Markt ({markt_type}):"
    
    if update.callback_query:
        await update.callback_query.message.edit_text(text, reply_markup=markt_lang_kb())
    else:
        await update.message.reply_text(text, reply_markup=markt_lang_kb())
    
    return MARKT_LANG


async def on_markt_lang_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle language selection callback"""
    query = update.callback_query
    await query.answer()
    
    # Extract language from callback data (MARKT_LANG_uk or MARKT_LANG_nl)
    lang = query.data.replace("MARKT_LANG_", "")
    context.user_data["lang"] = lang
    
    logger.info(f"Markt language selected: {lang}")
    return await ask_markt_nazvanie(update, context)


# ========== DATA INPUT STEPS ==========

async def ask_markt_nazvanie(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ask for product title"""
    push_state(context.user_data, MARKT_NAZVANIE)
    text = "Введи название товара:"
    
    if update.callback_query:
        await update.callback_query.message.edit_text(text, reply_markup=menu_back_kb())
    else:
        await update.message.reply_text(text, reply_markup=menu_back_kb())
    
    return MARKT_NAZVANIE


async def on_markt_nazvanie(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle product title input"""
    context.user_data["nazvanie"] = update.message.text
    return await ask_markt_price(update, context)


async def ask_markt_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ask for product price"""
    push_state(context.user_data, MARKT_PRICE)
    text = "Введи цену товара (например: 123.45):"
    await update.message.reply_text(text, reply_markup=menu_back_kb())
    return MARKT_PRICE


async def on_markt_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle product price input"""
    try:
        price_text = update.message.text.replace(",", ".")
        price = float(price_text)
        context.user_data["price"] = price
    except ValueError:
        await update.message.reply_text(
            "Неверный формат цены. Введи число (например: 123.45):",
            reply_markup=menu_back_kb()
        )
        return MARKT_PRICE
    
    return await ask_markt_photo(update, context)


async def ask_markt_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ask for product photo"""
    push_state(context.user_data, MARKT_PHOTO)
    text = "Отправь фото товара (или нажми 'Пропустить'):"
    await update.message.reply_text(text, reply_markup=photo_step_kb())
    return MARKT_PHOTO


async def on_markt_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle product photo input"""
    photo = update.message.photo[-1]  # Get highest resolution
    file = await photo.get_file()
    photo_bytes = await file.download_as_bytearray()
    context.user_data["photo_bytes"] = bytes(photo_bytes)
    
    markt_type = context.user_data.get("markt_type", "qr")
    
    # If QR type, need URL next
    if markt_type == "qr":
        return await ask_markt_url(update, context)
    else:
        return await generate_markt_image(update, context)


async def on_markt_skip_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle skip photo button"""
    await update.callback_query.answer()
    context.user_data["photo_bytes"] = None
    
    markt_type = context.user_data.get("markt_type", "qr")
    
    # If QR type, need URL next
    if markt_type == "qr":
        return await ask_markt_url(update, context)
    else:
        return await generate_markt_image(update, context)


async def ask_markt_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ask for URL (only for QR type)"""
    push_state(context.user_data, MARKT_URL)
    text = "Введи ссылку для QR-кода:"
    
    if update.callback_query:
        await update.callback_query.message.reply_text(text, reply_markup=menu_back_kb())
    else:
        await update.message.reply_text(text, reply_markup=menu_back_kb())
    
    return MARKT_URL


async def on_markt_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle URL input"""
    context.user_data["url"] = update.message.text
    return await generate_markt_image(update, context)


# ========== GENERATION ==========

async def generate_markt_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Generate the Markt image"""
    message = update.callback_query.message if update.callback_query else update.message
    
    # Collect data
    lang = context.user_data.get("lang", "uk")
    markt_type = context.user_data.get("markt_type", "qr")
    nazvanie = context.user_data.get("nazvanie", "")
    price = context.user_data.get("price", 0.0)
    photo_bytes = context.user_data.get("photo_bytes")
    url = context.user_data.get("url", "")
    
    # Convert photo to base64
    photo_b64 = base64.b64encode(photo_bytes).decode() if photo_bytes else None
    
    await message.reply_text("⏳ Генерация изображения...")
    
    try:
        executor = context.application.bot_data.get("executor")
        
        # Select generation function based on type
        if markt_type == "qr":
            image_data = await generate_with_queue(
                executor, create_markt_qr, lang, nazvanie, price, photo_b64, url
            )
        elif markt_type == "email_request":
            image_data = await generate_with_queue(
                executor, create_markt_email_request, lang, nazvanie, price, photo_b64
            )
        elif markt_type == "phone_request":
            image_data = await generate_with_queue(
                executor, create_markt_phone_request, lang, nazvanie, price, photo_b64
            )
        elif markt_type == "email_payment":
            image_data = await generate_with_queue(
                executor, create_markt_email_payment, lang, nazvanie, price, photo_b64
            )
        elif markt_type == "sms_payment":
            image_data = await generate_with_queue(
                executor, create_markt_sms_payment, lang, nazvanie, price, photo_b64
            )
        else:
            raise ValueError(f"Unknown Markt type: {markt_type}")
        
        # Send the generated image
        await context.bot.send_document(
            chat_id=message.chat_id,
            document=io.BytesIO(image_data),
            filename=f"markt_{markt_type}_{lang}_{uuid.uuid4()}.png"
        )
        
        await message.reply_text("✅ Готово!", reply_markup=main_menu_kb())
        clear_stack(context.user_data)
        return ConversationHandler.END
        
    except Exception as e:
        logger.exception(f"Error generating Markt image: {e}")
        await message.reply_text(f"❌ Ошибка: {e}", reply_markup=main_menu_kb())
        clear_stack(context.user_data)
        return ConversationHandler.END


# ========== NAVIGATION ==========

async def markt_menu_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Return to main menu"""
    await update.callback_query.answer("Возврат в главное меню")
    clear_stack(context.user_data)
    from app.handlers.menu import start
    await start(update, context)
    return ConversationHandler.END


async def markt_back_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle back button - return to type selection"""
    await update.callback_query.answer()
    pop_state(context.user_data)
    return await ask_markt_type(update, context)


async def markt_generic_back_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle generic back navigation"""
    await update.callback_query.answer()
    prev_state = pop_state(context.user_data)
    
    if prev_state is None:
        return await markt_menu_cb(update, context)
    
    if prev_state == MARKT_TYPE:
        return await ask_markt_type(update, context)
    elif prev_state == MARKT_LANG:
        return await ask_markt_type(update, context)
    elif prev_state == MARKT_NAZVANIE:
        return await ask_markt_lang(update, context)
    elif prev_state == MARKT_PRICE:
        # Go back to nazvanie - need to send message
        push_state(context.user_data, MARKT_NAZVANIE)
        text = "Введи название товара:"
        await update.callback_query.message.edit_text(text, reply_markup=menu_back_kb())
        return MARKT_NAZVANIE
    elif prev_state == MARKT_PHOTO:
        # Go back to price
        push_state(context.user_data, MARKT_PRICE)
        text = "Введи цену товара (например: 123.45):"
        await update.callback_query.message.edit_text(text, reply_markup=menu_back_kb())
        return MARKT_PRICE
    elif prev_state == MARKT_URL:
        # Go back to photo
        return await ask_markt_photo(update, context)
    
    return await ask_markt_type(update, context)


# ========== CONVERSATION HANDLER ==========

markt_conv = ConversationHandler(
    name="markt_flow",
    entry_points=[
        CallbackQueryHandler(markt_entry_menu, pattern=r"^QR:MARKT_MENU$"),
    ],
    states={
        MARKT_TYPE: [
            CallbackQueryHandler(markt_entry_qr, pattern=r"^QR:MARKT_QR$"),
            CallbackQueryHandler(markt_entry_email_request, pattern=r"^QR:MARKT_EMAIL_REQUEST$"),
            CallbackQueryHandler(markt_entry_phone_request, pattern=r"^QR:MARKT_PHONE_REQUEST$"),
            CallbackQueryHandler(markt_entry_email_payment, pattern=r"^QR:MARKT_EMAIL_PAYMENT$"),
            CallbackQueryHandler(markt_entry_sms_payment, pattern=r"^QR:MARKT_SMS_PAYMENT$"),
            CallbackQueryHandler(markt_menu_cb, pattern=r"^MENU$"),
            CallbackQueryHandler(markt_generic_back_cb, pattern=r"^QR:BACK$"),
        ],
        MARKT_LANG: [
            CallbackQueryHandler(on_markt_lang_callback, pattern=r"^MARKT_LANG_"),
            CallbackQueryHandler(markt_menu_cb, pattern=r"^MENU$"),
            CallbackQueryHandler(markt_back_cb, pattern=r"^QR:MARKT_BACK$"),
            CallbackQueryHandler(markt_generic_back_cb, pattern=r"^QR:BACK$"),
        ],
        MARKT_NAZVANIE: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, on_markt_nazvanie),
            CallbackQueryHandler(markt_menu_cb, pattern=r"^MENU$"),
            CallbackQueryHandler(markt_generic_back_cb, pattern=r"^QR:BACK$"),
        ],
        MARKT_PRICE: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, on_markt_price),
            CallbackQueryHandler(markt_menu_cb, pattern=r"^MENU$"),
            CallbackQueryHandler(markt_generic_back_cb, pattern=r"^QR:BACK$"),
        ],
        MARKT_PHOTO: [
            MessageHandler(filters.PHOTO, on_markt_photo),
            CallbackQueryHandler(on_markt_skip_photo, pattern=r"^QR:SKIP_PHOTO$"),
            CallbackQueryHandler(markt_menu_cb, pattern=r"^MENU$"),
            CallbackQueryHandler(markt_generic_back_cb, pattern=r"^QR:BACK$"),
        ],
        MARKT_URL: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, on_markt_url),
            CallbackQueryHandler(markt_menu_cb, pattern=r"^MENU$"),
            CallbackQueryHandler(markt_generic_back_cb, pattern=r"^QR:BACK$"),
        ],
    },
    fallbacks=[
        CommandHandler("start", markt_menu_cb),
        CallbackQueryHandler(markt_menu_cb, pattern=r"^MENU$"),
    ],
    allow_reentry=True,
)
