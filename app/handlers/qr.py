import os, uuid, logging, asyncio
from pathlib import Path

from telegram import Update
from telegram.ext import (
    ContextTypes, ConversationHandler, CallbackQueryHandler,
    MessageHandler, CommandHandler, filters
)

from app.keyboards.qr import main_menu_kb, menu_back_kb, photo_step_kb
from app.utils.state_stack import push_state, pop_state, clear_stack
from app.utils.io import ensure_dirs, cleanup_paths
from app.services.pdf import create_pdf, create_pdf_subito

logger = logging.getLogger(__name__)

# Состояния: общий + доп. шаги для subito
QR_NAZVANIE, QR_PRICE, QR_NAME, QR_ADDRESS, QR_PHOTO, QR_URL = range(6)

async def qr_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Старт MARKTPLAATS"""
    context.user_data["service"] = "marktplaats"
    ensure_dirs(); clear_stack(context.user_data)
    await update.callback_query.answer()
    await ask_nazvanie(update, context)
    return QR_NAZVANIE

async def qr_entry_subito(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Старт SUBITO"""
    context.user_data["service"] = "subito"
    ensure_dirs(); clear_stack(context.user_data)
    await update.callback_query.answer()
    await ask_nazvanie(update, context)
    return QR_NAZVANIE

async def ask_nazvanie(update: Update, context: ContextTypes.DEFAULT_TYPE):
    push_state(context.user_data, QR_NAZVANIE)
    await _edit_or_send(update, context, "Введи название товара:")

async def ask_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    push_state(context.user_data, QR_PRICE)
    await _edit_or_send(update, context, "Введи цену товара (пример: 99.99):")

async def ask_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    push_state(context.user_data, QR_NAME)
    await _edit_or_send(update, context, "Введи имя продавца (Name):")

async def ask_address(update: Update, context: ContextTypes.DEFAULT_TYPE):
    push_state(context.user_data, QR_ADDRESS)
    await _edit_or_send(update, context, "Введи адрес (Address):")

async def ask_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    push_state(context.user_data, QR_PHOTO)
    txt = "Отправь фото товара или нажми «Пропустить»:"
    if update.callback_query:
        await update.callback_query.message.edit_text(txt, reply_markup=photo_step_kb())
    else:
        await update.message.reply_text(txt, reply_markup=photo_step_kb())

async def ask_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    push_state(context.user_data, QR_URL)
    await _edit_or_send(update, context, "Введи URL для QR-кода:")

async def _edit_or_send(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
    kb = menu_back_kb()
    if getattr(update, "callback_query", None):
        await update.callback_query.message.edit_text(text, reply_markup=kb)
    else:
        await update.message.reply_text(text, reply_markup=kb)

# ---- Хендлеры шагов
async def on_nazvanie(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["nazvanie"] = (update.message.text or "").strip()
    return await ask_price(update, context) or QR_PRICE

async def on_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["price"] = (update.message.text or "").strip()
    if context.user_data.get("service") == "subito":
        return await ask_name(update, context) or QR_NAME
    return await ask_photo(update, context) or QR_PHOTO

async def on_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["name"] = (update.message.text or "").strip()
    return await ask_address(update, context) or QR_ADDRESS

async def on_address(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["address"] = (update.message.text or "").strip()
    return await ask_photo(update, context) or QR_PHOTO

async def on_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.photo:
        photo_file = await update.message.photo[-1].get_file()
        tmp_dir = context.application.bot_data.get("temp_dir", ".")
        tmp = os.path.join(tmp_dir, f"temp_{uuid.uuid4()}.jpg")
        await photo_file.download_to_drive(tmp)
        context.user_data["photo_path"] = tmp
        return await ask_url(update, context) or QR_URL
    await update.message.reply_text("Пожалуйста, отправь фото или нажми «Пропустить».")
    return QR_PHOTO

async def on_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    nazvanie = context.user_data.get("nazvanie", "")
    price = context.user_data.get("price", "")
    name = context.user_data.get("name")
    address = context.user_data.get("address")
    photo_path = context.user_data.get("photo_path")
    url = (update.message.text or "").strip()
    if not url.startswith("http"):
        url = "https://" + url

    service = context.user_data.get("service", "marktplaats")
    await update.message.reply_text(f"Обрабатываю данные для {service}…", reply_markup=menu_back_kb())

    png_path = processed_photo_path = qr_path = None
    try:
        if service == "subito":
            png_path, processed_photo_path, qr_path = await asyncio.to_thread(
                create_pdf_subito, nazvanie, price, name, address, photo_path, url
            )
        else:
            png_path, processed_photo_path, qr_path = await asyncio.to_thread(
                create_pdf, nazvanie, price, photo_path, url
            )

        with open(png_path, "rb") as f:
            await context.bot.send_document(chat_id=update.message.chat_id, document=f,
                                            filename=f"{service}.png")
        await update.message.reply_text("Готово!", reply_markup=main_menu_kb())
        clear_stack(context.user_data)
        Path(png_path).unlink(missing_ok=True)
        return ConversationHandler.END
    except Exception as e:
        logger.exception("Ошибка генерации")
        await update.message.reply_text(f"Ошибка: {e}", reply_markup=main_menu_kb())
        clear_stack(context.user_data)
        return ConversationHandler.END
    finally:
        cleanup_paths(photo_path, processed_photo_path, qr_path)

# ---- Навигация
async def qr_menu_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer("Возврат в главное меню")
    clear_stack(context.user_data)
    from app.handlers.menu import start
    await start(update, context)
    return ConversationHandler.END

async def on_skip_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    context.user_data["photo_path"] = None
    return await ask_url(update, context) or QR_URL

async def qr_back_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    _ = pop_state(context.user_data)
    prev = pop_state(context.user_data)
    if prev is None:
        return await qr_menu_cb(update, context)
    if prev == QR_NAZVANIE:
        await ask_nazvanie(update, context); return QR_NAZVANIE
    if prev == QR_PRICE:
        await ask_price(update, context); return QR_PRICE
    if prev == QR_NAME:
        await ask_name(update, context); return QR_NAME
    if prev == QR_ADDRESS:
        await ask_address(update, context); return QR_ADDRESS
    if prev == QR_PHOTO:
        await ask_photo(update, context); return QR_PHOTO
    if prev == QR_URL:
        await ask_url(update, context); return QR_URL

# Подключение в твоём роутере/меню:
#  - CallbackQueryHandler(qr_entry, pattern=r"^QR:START$")          # marktplaats
#  - CallbackQueryHandler(qr_entry_subito, pattern=r"^QR:SUBITO$")  # subito
qr_conv = ConversationHandler(
    name="qr_flow",
    entry_points=[
        CallbackQueryHandler(qr_entry, pattern=r"^QR:START$"),
        CallbackQueryHandler(qr_entry_subito, pattern=r"^QR:SUBITO$"),
    ],
    states={
        QR_NAZVANIE: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, on_nazvanie),
            CallbackQueryHandler(qr_menu_cb, pattern=r"^QR:MENU$"),
            CallbackQueryHandler(qr_back_cb, pattern=r"^QR:BACK$")
        ],
        QR_PRICE: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, on_price),
            CallbackQueryHandler(qr_menu_cb, pattern=r"^QR:MENU$"),
            CallbackQueryHandler(qr_back_cb, pattern=r"^QR:BACK$")
        ],
        QR_NAME: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, on_name),
            CallbackQueryHandler(qr_menu_cb, pattern=r"^QR:MENU$"),
            CallbackQueryHandler(qr_back_cb, pattern=r"^QR:BACK$")
        ],
        QR_ADDRESS: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, on_address),
            CallbackQueryHandler(qr_menu_cb, pattern=r"^QR:MENU$"),
            CallbackQueryHandler(qr_back_cb, pattern=r"^QR:BACK$")
        ],
        QR_PHOTO: [
            MessageHandler(filters.PHOTO, on_photo),
            CallbackQueryHandler(qr_menu_cb, pattern=r"^QR:MENU$"),
            CallbackQueryHandler(qr_back_cb, pattern=r"^QR:BACK$"),
            CallbackQueryHandler(on_skip_photo, pattern=r"^QR:SKIP_PHOTO$")
        ],
        QR_URL: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, on_url),
            CallbackQueryHandler(qr_menu_cb, pattern=r"^QR:MENU$"),
            CallbackQueryHandler(qr_back_cb, pattern=r"^QR:BACK$")
        ],
    },
    fallbacks=[CommandHandler("start", qr_menu_cb)],
    allow_reentry=True,
)


async def qr_back_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик кнопки Назад для QR flow"""
    await update.callback_query.answer()

    # Логирование для отладки
    logger.info(f"Back button pressed. Current stack: {context.user_data.get('state_stack', [])}")

    # Извлекаем текущее состояние
    current_state = pop_state(context.user_data)
    logger.info(f"Popped current state: {current_state}")

    # Получаем предыдущее состояние
    prev_state = pop_state(context.user_data)
    logger.info(f"Previous state: {prev_state}")

    if prev_state is None:
        logger.info("No previous state, going to menu")
        return await qr_menu_cb(update, context)

    # Возвращаемся к предыдущему состоянию
    if prev_state == QR_NAZVANIE:
        logger.info("Returning to nazvanie")
        await ask_nazvanie(update, context)
        return QR_NAZVANIE
    elif prev_state == QR_PRICE:
        logger.info("Returning to price")
        await ask_price(update, context)
        return QR_PRICE
    elif prev_state == QR_NAME:
        logger.info("Returning to name")
        await ask_name(update, context)
        return QR_NAME
    elif prev_state == QR_ADDRESS:
        logger.info("Returning to address")
        await ask_address(update, context)
        return QR_ADDRESS
    elif prev_state == QR_PHOTO:
        logger.info("Returning to photo")
        await ask_photo(update, context)
        return QR_PHOTO
    elif prev_state == QR_URL:
        logger.info("Returning to URL")
        await ask_url(update, context)
        return QR_URL
    else:
        logger.info(f"Unknown state {prev_state}, going to menu")
        return await qr_menu_cb(update, context)