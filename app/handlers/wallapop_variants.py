# app/handlers/wallapop_variants.py
"""
Обработчик для Wallapop вариантов (фреймы 3-7) с локализацией
"""
import io
import uuid
import base64
import logging

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    ContextTypes, ConversationHandler, CallbackQueryHandler,
    MessageHandler, CommandHandler, filters
)

from app.keyboards.qr import main_menu_kb, menu_back_kb, photo_step_kb
from app.utils.state_stack import push_state, pop_state, clear_stack
from app.utils.async_helpers import generate_with_queue
from app.services.wallapop_variants import create_wallapop_variant

logger = logging.getLogger(__name__)

# Состояния
(WV_FRAME, WV_LANG, WV_NAZVANIE, WV_PRICE, WV_SELLER_NAME, 
 WV_SELLER_PHOTO, WV_PHOTO, WV_URL) = range(8)

# Константы
SUPPORTED_FRAMES = [3, 4, 5, 6, 7]
SUPPORTED_LANGUAGES = ['uk', 'es', 'it', 'fr', 'pr']
QR_FRAMES = [7]

# Языки с эмодзи
LANG_LABELS = {
    'uk': '🇬🇧 UK',
    'es': '🇪🇸 ES',
    'it': '🇮🇹 IT',
    'fr': '🇫🇷 FR',
    'pr': '🇵🇹 PR'
}


def wallapop_variant_frame_kb():
    """Клавиатура выбора фрейма Wallapop (3-7)"""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📱 Фрейм 3", callback_data="WV:FRAME:3"),
            InlineKeyboardButton("📱 Фрейм 4", callback_data="WV:FRAME:4"),
        ],
        [
            InlineKeyboardButton("💰 Фрейм 5", callback_data="WV:FRAME:5"),
            InlineKeyboardButton("💰 Фрейм 6", callback_data="WV:FRAME:6"),
        ],
        [
            InlineKeyboardButton("🔲 Фрейм 7 (QR)", callback_data="WV:FRAME:7"),
        ],
        [
            InlineKeyboardButton("⬅️ Назад", callback_data="WV:BACK"),
            InlineKeyboardButton("🏠 Главное меню", callback_data="MENU")
        ],
    ])


def wallapop_variant_lang_kb():
    """Клавиатура выбора языка для Wallapop вариантов"""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(LANG_LABELS['uk'], callback_data="WV:LANG:uk"),
            InlineKeyboardButton(LANG_LABELS['es'], callback_data="WV:LANG:es"),
        ],
        [
            InlineKeyboardButton(LANG_LABELS['it'], callback_data="WV:LANG:it"),
            InlineKeyboardButton(LANG_LABELS['fr'], callback_data="WV:LANG:fr"),
        ],
        [
            InlineKeyboardButton(LANG_LABELS['pr'], callback_data="WV:LANG:pr"),
        ],
        [
            InlineKeyboardButton("⬅️ Назад", callback_data="WV:FRAME_BACK"),
            InlineKeyboardButton("🏠 Главное меню", callback_data="MENU")
        ]
    ])


def wv_back_kb():
    """Клавиатура с кнопками назад"""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("⬅️ Назад", callback_data="WV:BACK_STEP"),
            InlineKeyboardButton("🏠 Главное меню", callback_data="MENU")
        ],
    ])


async def _edit_or_send(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
    """Редактирование или отправка сообщения"""
    kb = wv_back_kb()
    if getattr(update, "callback_query", None):
        await update.callback_query.message.edit_text(text, reply_markup=kb)
    else:
        await update.message.reply_text(text, reply_markup=kb)


async def wv_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Вход в меню Wallapop вариантов"""
    context.user_data["service"] = "wallapop_variant"
    clear_stack(context.user_data)
    await update.callback_query.answer()
    return await ask_wv_frame(update, context)


async def ask_wv_frame(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Выбор фрейма Wallapop (3-7)"""
    push_state(context.user_data, WV_FRAME)
    text = (
        "🎨 Wallapop макеты (фреймы 3-7)\n\n"
        "Выбери фрейм:\n"
        "• Фрейм 3-4: Базовые макеты\n"
        "• Фрейм 5-6: С большой ценой\n"
        "• Фрейм 7: С QR кодом"
    )
    
    if update.callback_query:
        await update.callback_query.message.edit_text(
            text, reply_markup=wallapop_variant_frame_kb()
        )
    else:
        await update.message.reply_text(
            text, reply_markup=wallapop_variant_frame_kb()
        )
    
    return WV_FRAME


async def on_wv_frame_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка выбора фрейма"""
    frame = int(update.callback_query.data.replace("WV:FRAME:", ""))
    
    if frame not in SUPPORTED_FRAMES:
        await update.callback_query.answer("❌ Неверный фрейм")
        return WV_FRAME
    
    context.user_data["wv_frame"] = frame
    await update.callback_query.answer(f"Выбран фрейм {frame}")
    return await ask_wv_lang(update, context)


async def ask_wv_lang(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Выбор языка"""
    push_state(context.user_data, WV_LANG)
    frame = context.user_data.get("wv_frame", 3)
    
    text = f"🌍 Выбери язык для фрейма {frame}:"
    
    if update.callback_query:
        await update.callback_query.message.edit_text(
            text, reply_markup=wallapop_variant_lang_kb()
        )
    else:
        await update.message.reply_text(
            text, reply_markup=wallapop_variant_lang_kb()
        )
    
    return WV_LANG


async def on_wv_lang_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка выбора языка"""
    lang = update.callback_query.data.replace("WV:LANG:", "")
    
    if lang not in SUPPORTED_LANGUAGES:
        await update.callback_query.answer("❌ Неверный язык")
        return WV_LANG
    
    context.user_data["wv_lang"] = lang
    await update.callback_query.answer(f"Выбран язык: {lang.upper()}")
    return await ask_wv_nazvanie(update, context)


async def ask_wv_nazvanie(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ввод названия товара"""
    push_state(context.user_data, WV_NAZVANIE)
    
    frame = context.user_data.get("wv_frame", 3)
    lang = context.user_data.get("wv_lang", "uk")
    
    text = f"📦 Введи название товара\n(Фрейм {frame}, {lang.upper()}):"
    await _edit_or_send(update, context, text)
    return WV_NAZVANIE


async def on_wv_nazvanie(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка названия товара"""
    context.user_data["wv_nazvanie"] = (update.message.text or "").strip()
    return await ask_wv_price(update, context)


async def ask_wv_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ввод цены"""
    push_state(context.user_data, WV_PRICE)
    text = "💰 Введи цену товара (пример: 99.99):"
    await _edit_or_send(update, context, text)
    return WV_PRICE


async def on_wv_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка цены"""
    context.user_data["wv_price"] = (update.message.text or "").strip()
    return await ask_wv_seller_name(update, context)


async def ask_wv_seller_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ввод имени продавца"""
    push_state(context.user_data, WV_SELLER_NAME)
    text = "👤 Введи имя продавца:"
    await _edit_or_send(update, context, text)
    return WV_SELLER_NAME


async def on_wv_seller_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка имени продавца"""
    context.user_data["wv_seller_name"] = (update.message.text or "").strip()
    return await ask_wv_seller_photo(update, context)


async def ask_wv_seller_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Запрос аватарки продавца"""
    push_state(context.user_data, WV_SELLER_PHOTO)
    text = "🖼️ Отправь аватарку продавца или нажми «Пропустить»:"
    
    if update.callback_query:
        await update.callback_query.message.edit_text(text, reply_markup=photo_step_kb())
    else:
        await update.message.reply_text(text, reply_markup=photo_step_kb())
    
    return WV_SELLER_PHOTO


async def on_wv_seller_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка аватарки продавца"""
    if update.message.photo:
        photo_file = await update.message.photo[-1].get_file()
        photo_bytes = await photo_file.download_as_bytearray()
        context.user_data["wv_seller_photo_bytes"] = photo_bytes
        logger.info(f"✅ Аватарка получена: {len(photo_bytes)} bytes")
        return await ask_wv_photo(update, context)
    
    await update.message.reply_text("Пожалуйста, отправь фото или нажми «Пропустить».")
    return WV_SELLER_PHOTO


async def on_wv_skip_seller_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Пропуск аватарки"""
    await update.callback_query.answer()
    context.user_data["wv_seller_photo_bytes"] = None
    return await ask_wv_photo(update, context)


async def ask_wv_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Запрос фото товара"""
    push_state(context.user_data, WV_PHOTO)
    text = "📸 Отправь фото товара или нажми «Пропустить»:"
    
    if update.callback_query:
        await update.callback_query.message.edit_text(text, reply_markup=photo_step_kb())
    else:
        await update.message.reply_text(text, reply_markup=photo_step_kb())
    
    return WV_PHOTO


async def on_wv_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка фото товара"""
    if update.message.photo:
        photo_file = await update.message.photo[-1].get_file()
        photo_bytes = await photo_file.download_as_bytearray()
        context.user_data["wv_photo_bytes"] = photo_bytes
        logger.info(f"✅ Фото товара получено: {len(photo_bytes)} bytes")
        
        frame = context.user_data.get("wv_frame", 3)
        if frame in QR_FRAMES:
            return await ask_wv_url(update, context)
        else:
            return await generate_wv_image(update, context)
    
    await update.message.reply_text("Пожалуйста, отправь фото или нажми «Пропустить».")
    return WV_PHOTO


async def on_wv_skip_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Пропуск фото товара"""
    await update.callback_query.answer()
    context.user_data["wv_photo_bytes"] = None
    
    frame = context.user_data.get("wv_frame", 3)
    if frame in QR_FRAMES:
        return await ask_wv_url(update, context)
    else:
        return await generate_wv_image(update, context)


async def ask_wv_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Запрос URL для QR кода (только фрейм 7)"""
    push_state(context.user_data, WV_URL)
    text = "🔗 Введи URL для QR кода:"
    await _edit_or_send(update, context, text)
    return WV_URL


async def on_wv_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка URL для QR"""
    url = (update.message.text or "").strip()
    if not url.startswith("http"):
        url = "https://" + url
    context.user_data["wv_url"] = url
    return await generate_wv_image(update, context)


async def generate_wv_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Генерация изображения Wallapop варианта"""
    frame = context.user_data.get("wv_frame", 3)
    lang = context.user_data.get("wv_lang", "uk")
    nazvanie = context.user_data.get("wv_nazvanie", "")
    price_str = context.user_data.get("wv_price", "0")
    seller_name = context.user_data.get("wv_seller_name", "")
    photo_bytes = context.user_data.get("wv_photo_bytes")
    seller_photo_bytes = context.user_data.get("wv_seller_photo_bytes")
    qr_url = context.user_data.get("wv_url")
    
    message = update.message if update.message else update.callback_query.message
    await message.reply_text(
        f"⏳ Генерирую Wallapop фрейм {frame} ({lang.upper()})...",
        reply_markup=wv_back_kb()
    )
    
    try:
        # Конвертация цены
        try:
            price = float(price_str.replace(",", "."))
        except ValueError:
            price = 0.0
        
        # Конвертация фото в base64
        photo_b64 = base64.b64encode(photo_bytes).decode('utf-8') if photo_bytes else None
        avatar_b64 = base64.b64encode(seller_photo_bytes).decode('utf-8') if seller_photo_bytes else None
        
        logger.info(f"🎨 Wallapop{frame}_{lang}: {nazvanie}, {price}€, seller={seller_name}")
        logger.info(f"   photo={'yes' if photo_b64 else 'no'}, avatar={'yes' if avatar_b64 else 'no'}, qr={'yes' if qr_url else 'no'}")
        
        # Генерация через очередь
        executor = context.application.bot_data.get("executor")
        image_data = await generate_with_queue(
            executor,
            create_wallapop_variant,
            frame, lang, nazvanie, price, seller_name, photo_b64, avatar_b64, qr_url
        )
        
        # Отправка результата
        await context.bot.send_document(
            chat_id=message.chat_id,
            document=io.BytesIO(image_data),
            filename=f"wallapop{frame}_{lang}_{uuid.uuid4()}.png"
        )
        
        await message.reply_text("✅ Готово!", reply_markup=main_menu_kb())
        clear_stack(context.user_data)
        return ConversationHandler.END
        
    except Exception as e:
        logger.exception(f"❌ Ошибка генерации Wallapop{frame}_{lang}")
        await message.reply_text(f"❌ Ошибка: {e}", reply_markup=main_menu_kb())
        clear_stack(context.user_data)
        return ConversationHandler.END


async def wv_menu_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Возврат в главное меню"""
    await update.callback_query.answer("Возврат в главное меню")
    clear_stack(context.user_data)
    from app.handlers.menu import start
    await start(update, context)
    return ConversationHandler.END


async def wv_back_to_frame(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Возврат к выбору фрейма"""
    await update.callback_query.answer()
    pop_state(context.user_data)
    return await ask_wv_frame(update, context)


async def wv_back_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Назад на предыдущий шаг"""
    await update.callback_query.answer()
    prev_state = pop_state(context.user_data)
    
    if prev_state is None:
        return await wv_menu_cb(update, context)
    
    if prev_state == WV_FRAME:
        return await ask_wv_frame(update, context)
    elif prev_state == WV_LANG:
        return await ask_wv_lang(update, context)
    elif prev_state == WV_NAZVANIE:
        return await ask_wv_nazvanie(update, context)
    elif prev_state == WV_PRICE:
        return await ask_wv_price(update, context)
    elif prev_state == WV_SELLER_NAME:
        return await ask_wv_seller_name(update, context)
    elif prev_state == WV_SELLER_PHOTO:
        return await ask_wv_seller_photo(update, context)
    elif prev_state == WV_PHOTO:
        return await ask_wv_photo(update, context)
    elif prev_state == WV_URL:
        return await ask_wv_url(update, context)
    
    return await ask_wv_frame(update, context)


# Conversation Handler
wallapop_variants_conv = ConversationHandler(
    name="wallapop_variants_flow",
    entry_points=[
        CallbackQueryHandler(wv_entry, pattern=r"^QR:WALLAPOP_VARIANTS$"),
    ],
    states={
        WV_FRAME: [
            CallbackQueryHandler(on_wv_frame_select, pattern=r"^WV:FRAME:\d$"),
            CallbackQueryHandler(wv_menu_cb, pattern=r"^MENU$"),
            CallbackQueryHandler(wv_back_to_frame, pattern=r"^WV:BACK$"),
        ],
        WV_LANG: [
            CallbackQueryHandler(on_wv_lang_select, pattern=r"^WV:LANG:[a-z]{2}$"),
            CallbackQueryHandler(wv_menu_cb, pattern=r"^MENU$"),
            CallbackQueryHandler(wv_back_to_frame, pattern=r"^WV:FRAME_BACK$"),
        ],
        WV_NAZVANIE: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, on_wv_nazvanie),
            CallbackQueryHandler(wv_menu_cb, pattern=r"^MENU$"),
            CallbackQueryHandler(wv_back_step, pattern=r"^WV:BACK_STEP$"),
        ],
        WV_PRICE: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, on_wv_price),
            CallbackQueryHandler(wv_menu_cb, pattern=r"^MENU$"),
            CallbackQueryHandler(wv_back_step, pattern=r"^WV:BACK_STEP$"),
        ],
        WV_SELLER_NAME: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, on_wv_seller_name),
            CallbackQueryHandler(wv_menu_cb, pattern=r"^MENU$"),
            CallbackQueryHandler(wv_back_step, pattern=r"^WV:BACK_STEP$"),
        ],
        WV_SELLER_PHOTO: [
            MessageHandler(filters.PHOTO, on_wv_seller_photo),
            CallbackQueryHandler(on_wv_skip_seller_photo, pattern=r"^QR:SKIP_PHOTO$"),
            CallbackQueryHandler(wv_menu_cb, pattern=r"^MENU$"),
            CallbackQueryHandler(wv_back_step, pattern=r"^WV:BACK_STEP$"),
        ],
        WV_PHOTO: [
            MessageHandler(filters.PHOTO, on_wv_photo),
            CallbackQueryHandler(on_wv_skip_photo, pattern=r"^QR:SKIP_PHOTO$"),
            CallbackQueryHandler(wv_menu_cb, pattern=r"^MENU$"),
            CallbackQueryHandler(wv_back_step, pattern=r"^WV:BACK_STEP$"),
        ],
        WV_URL: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, on_wv_url),
            CallbackQueryHandler(wv_menu_cb, pattern=r"^MENU$"),
            CallbackQueryHandler(wv_back_step, pattern=r"^WV:BACK_STEP$"),
        ],
    },
    fallbacks=[
        CommandHandler("start", wv_menu_cb),
        CallbackQueryHandler(wv_menu_cb, pattern=r"^MENU$"),
    ],
    allow_reentry=True,
)
