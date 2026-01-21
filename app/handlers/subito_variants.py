# app/handlers/subito_variants.py
"""
Handler для различных вариантов Subito:
- QR (оригинальный) - subito1
- Email запрос - subito2
- Email подтверждение - subito3
- SMS запрос - subito4
- SMS подтверждение - subito5
"""

import logging
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    ConversationHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes
)

from app.services.pdf import create_image_subito
from app.services.subito_variants import (
    create_image_subito_email_request,
    create_image_subito_email_confirm,
    create_image_subito_sms_request,
    create_image_subito_sms_confirm
)

logger = logging.getLogger(__name__)

# States
SUBITO_SELECT_VARIANT, SUBITO_TITLE, SUBITO_PRICE, SUBITO_PHOTO, SUBITO_URL, SUBITO_NAME, SUBITO_ADDRESS = range(7)


async def subito_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Выбор варианта Subito"""
    keyboard = [
        [InlineKeyboardButton("🔵 QR (оригинал)", callback_data="SUBITO_VAR:qr")],
        [InlineKeyboardButton("📧 Email запрос", callback_data="SUBITO_VAR:email_req")],
        [InlineKeyboardButton("✅ Email подтверждение", callback_data="SUBITO_VAR:email_conf")],
        [InlineKeyboardButton("📱 SMS запрос", callback_data="SUBITO_VAR:sms_req")],
        [InlineKeyboardButton("✅ SMS подтверждение", callback_data="SUBITO_VAR:sms_conf")],
        [InlineKeyboardButton("◀️ Назад", callback_data="QR:MENU")]
    ]
    
    await update.callback_query.answer()
    await update.callback_query.edit_message_text(
        "🇮🇹 <b>Subito - Выбери вариант:</b>",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML"
    )
    
    return SUBITO_SELECT_VARIANT


async def subito_variant_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Вариант выбран, запрашиваем название"""
    query = update.callback_query
    variant = query.data.split(":")[1]
    
    # Сохраняем выбранный вариант
    context.user_data['subito_variant'] = variant
    
    # Названия вариантов
    variant_names = {
        'qr': '🔵 QR (оригинал)',
        'email_req': '📧 Email запрос',
        'email_conf': '✅ Email подтверждение',
        'sms_req': '📱 SMS запрос',
        'sms_conf': '✅ SMS подтверждение'
    }
    
    await query.answer()
    await query.edit_message_text(
        f"🇮🇹 <b>Subito - {variant_names[variant]}</b>\n\n"
        f"📝 Введи <b>название товара</b>:",
        parse_mode="HTML"
    )
    
    return SUBITO_TITLE


async def subito_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получили название, запрашиваем цену"""
    context.user_data['subito_title'] = update.message.text
    
    await update.message.reply_text(
        "💵 Введи <b>цену</b> (например: 99.99):",
        parse_mode="HTML"
    )
    
    return SUBITO_PRICE


async def subito_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получили цену, запрашиваем фото"""
    try:
        price = float(update.message.text.replace(',', '.'))
        context.user_data['subito_price'] = price
        
        keyboard = [[InlineKeyboardButton("⏭️ Пропустить", callback_data="SUBITO:SKIP_PHOTO")]]
        
        await update.message.reply_text(
            "📸 Отправь <b>фото товара</b> или пропусти:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )
        
        return SUBITO_PHOTO
        
    except ValueError:
        await update.message.reply_text(
            "❌ Неверный формат цены!\n\n"
            "💵 Введи цену (например: 99.99):"
        )
        return SUBITO_PRICE


async def subito_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получили фото, запрашиваем URL или имя в зависимости от варианта"""
    if update.message.photo:
        # Берем фото лучшего качества
        photo_file = await update.message.photo[-1].get_file()
        photo_bytes = await photo_file.download_as_bytearray()
        
        import base64
        context.user_data['subito_photo'] = base64.b64encode(photo_bytes).decode('utf-8')
    
    variant = context.user_data.get('subito_variant', 'qr')
    
    # Только QR вариант требует URL
    if variant == 'qr':
        await update.message.reply_text(
            "🔗 Введи <b>URL</b> (например: https://subito.it/item/123):",
            parse_mode="HTML"
        )
        return SUBITO_URL
    else:
        # Для email/sms вариантов пропускаем URL и переходим к имени
        keyboard = [[InlineKeyboardButton("⏭️ Пропустить", callback_data="SUBITO:SKIP_NAME")]]
        await update.message.reply_text(
            "👤 Введи <b>имя получателя</b> или пропусти:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )
        return SUBITO_NAME


async def subito_skip_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Пропустили фото"""
    context.user_data['subito_photo'] = None
    
    variant = context.user_data.get('subito_variant', 'qr')
    
    await update.callback_query.answer()
    
    # Только QR вариант требует URL
    if variant == 'qr':
        await update.callback_query.edit_message_text(
            "🔗 Введи <b>URL</b> (например: https://subito.it/item/123):",
            parse_mode="HTML"
        )
        return SUBITO_URL
    else:
        # Для email/sms вариантов пропускаем URL и переходим к имени
        keyboard = [[InlineKeyboardButton("⏭️ Пропустить", callback_data="SUBITO:SKIP_NAME")]]
        await update.callback_query.edit_message_text(
            "👤 Введи <b>имя получателя</b> или пропусти:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )
        return SUBITO_NAME


async def subito_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получили URL, запрашиваем имя получателя"""
    context.user_data['subito_url'] = update.message.text
    
    keyboard = [[InlineKeyboardButton("⏭️ Пропустить", callback_data="SUBITO:SKIP_NAME")]]
    
    await update.message.reply_text(
        "👤 Введи <b>имя получателя</b> или пропусти:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML"
    )
    
    return SUBITO_NAME


async def subito_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получили имя, запрашиваем адрес"""
    context.user_data['subito_name'] = update.message.text
    
    keyboard = [[InlineKeyboardButton("⏭️ Пропустить", callback_data="SUBITO:SKIP_ADDRESS")]]
    
    await update.message.reply_text(
        "🏠 Введи <b>адрес</b> (например: Milano, IT) или пропусти:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML"
    )
    
    return SUBITO_ADDRESS


async def subito_skip_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Пропустили имя"""
    context.user_data['subito_name'] = ''
    
    keyboard = [[InlineKeyboardButton("⏭️ Пропустить", callback_data="SUBITO:SKIP_ADDRESS")]]
    
    await update.callback_query.answer()
    await update.callback_query.edit_message_text(
        "🏠 Введи <b>адрес</b> (например: Milano, IT) или пропусти:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML"
    )
    
    return SUBITO_ADDRESS


async def subito_address(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получили адрес, генерируем изображение"""
    context.user_data['subito_address'] = update.message.text
    
    await generate_subito_image(update, context)
    
    return ConversationHandler.END


async def subito_skip_address(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Пропустили адрес"""
    context.user_data['subito_address'] = ''
    
    await update.callback_query.answer()
    await update.callback_query.message.reply_text("⏳ Генерирую изображение...")
    
    await generate_subito_image_query(update, context)
    
    return ConversationHandler.END


async def generate_subito_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Генерация изображения (из message)"""
    variant = context.user_data.get('subito_variant', 'qr')
    title = context.user_data['subito_title']
    price = context.user_data['subito_price']
    photo = context.user_data.get('subito_photo')
    url = context.user_data.get('subito_url', '')
    name = context.user_data.get('subito_name', '')
    address = context.user_data.get('subito_address', '')
    
    await update.message.reply_text("⏳ Генерирую изображение...")
    
    try:
        # Выбираем функцию генерации в зависимости от варианта
        # QR вариант использует URL, остальные - нет
        if variant == 'qr':
            image_data = create_image_subito(title, price, photo, url, name, address)
        elif variant == 'email_req':
            image_data = create_image_subito_email_request(title, price, photo, name, address)
        elif variant == 'email_conf':
            image_data = create_image_subito_email_confirm(title, price, photo, name, address)
        elif variant == 'sms_req':
            image_data = create_image_subito_sms_request(title, price, photo, name, address)
        elif variant == 'sms_conf':
            image_data = create_image_subito_sms_confirm(title, price, photo, name, address)
        else:
            raise ValueError(f"Unknown variant: {variant}")
        
        from io import BytesIO
        from telegram import InputFile
        
        await update.message.reply_photo(
            photo=InputFile(BytesIO(image_data), filename="subito.png"),
            caption=f"✅ <b>Subito сгенерирован!</b>\n\n"
                    f"📝 {title}\n"
                    f"💵 €{price:.2f}",
            parse_mode="HTML"
        )
        
    except Exception as e:
        logger.error(f"Ошибка генерации Subito: {e}")
        await update.message.reply_text(
            f"❌ Ошибка генерации:\n<code>{str(e)}</code>",
            parse_mode="HTML"
        )


async def generate_subito_image_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Генерация изображения (из callback_query)"""
    variant = context.user_data.get('subito_variant', 'qr')
    title = context.user_data['subito_title']
    price = context.user_data['subito_price']
    photo = context.user_data.get('subito_photo')
    url = context.user_data.get('subito_url', '')
    name = context.user_data.get('subito_name', '')
    address = context.user_data.get('subito_address', '')
    
    try:
        # Выбираем функцию генерации
        # QR вариант использует URL, остальные - нет
        if variant == 'qr':
            image_data = create_image_subito(title, price, photo, url, name, address)
        elif variant == 'email_req':
            image_data = create_image_subito_email_request(title, price, photo, name, address)
        elif variant == 'email_conf':
            image_data = create_image_subito_email_confirm(title, price, photo, name, address)
        elif variant == 'sms_req':
            image_data = create_image_subito_sms_request(title, price, photo, name, address)
        elif variant == 'sms_conf':
            image_data = create_image_subito_sms_confirm(title, price, photo, name, address)
        else:
            raise ValueError(f"Unknown variant: {variant}")
        
        from io import BytesIO
        from telegram import InputFile
        
        await update.callback_query.message.reply_photo(
            photo=InputFile(BytesIO(image_data), filename="subito.png"),
            caption=f"✅ <b>Subito сгенерирован!</b>\n\n"
                    f"📝 {title}\n"
                    f"💵 €{price:.2f}",
            parse_mode="HTML"
        )
        
    except Exception as e:
        logger.error(f"Ошибка генерации Subito: {e}")
        await update.callback_query.message.reply_text(
            f"❌ Ошибка генерации:\n<code>{str(e)}</code>",
            parse_mode="HTML"
        )


async def subito_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена"""
    await update.callback_query.answer()
    await update.callback_query.edit_message_text("❌ Генерация отменена")
    return ConversationHandler.END


# Conversation Handler
subito_variants_conv = ConversationHandler(
    entry_points=[
        CallbackQueryHandler(subito_start, pattern=r"^QR:SUBITO$")
    ],
    states={
        SUBITO_SELECT_VARIANT: [
            CallbackQueryHandler(subito_variant_selected, pattern=r"^SUBITO_VAR:")
        ],
        SUBITO_TITLE: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, subito_title)
        ],
        SUBITO_PRICE: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, subito_price)
        ],
        SUBITO_PHOTO: [
            MessageHandler(filters.PHOTO, subito_photo),
            CallbackQueryHandler(subito_skip_photo, pattern=r"^SUBITO:SKIP_PHOTO$")
        ],
        SUBITO_URL: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, subito_url)
        ],
        SUBITO_NAME: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, subito_name),
            CallbackQueryHandler(subito_skip_name, pattern=r"^SUBITO:SKIP_NAME$")
        ],
        SUBITO_ADDRESS: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, subito_address),
            CallbackQueryHandler(subito_skip_address, pattern=r"^SUBITO:SKIP_ADDRESS$")
        ]
    },
    fallbacks=[
        CallbackQueryHandler(subito_cancel, pattern=r"^QR:MENU$")
    ],
    name="subito_variants",
    per_message=False,
    allow_reentry=True
)
