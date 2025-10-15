import os
import uuid
import asyncio
import logging
import shutil
import tempfile
from io import BytesIO
from pathlib import Path

from telegram import InputFile, Update
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ConversationHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from app.keyboards.qr import main_menu_kb, menu_back_kb, photo_step_kb, skip_step_kb
from app.utils.io import cleanup_paths
from app.utils.state_stack import clear_stack, pop_state, push_state
from app.services.subito import create_subito_image
from app.utils.time import normalize_hhmm

logger = logging.getLogger(__name__)

(
    SUBITO_NAZVANIE,
    SUBITO_PRICE,
    SUBITO_NAME,
    SUBITO_ADDRESS,
    SUBITO_PHOTO,
    SUBITO_URL,
    SUBITO_TIME,
) = range(7)


def _cleanup_temp_dir(context: ContextTypes.DEFAULT_TYPE) -> None:
    tmp_dir = context.user_data.pop("temp_dir", None)
    if tmp_dir:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def _ensure_temp_dir(context: ContextTypes.DEFAULT_TYPE) -> str:
    tmp_dir = context.user_data.get("temp_dir")
    if not tmp_dir:
        tmp_dir = tempfile.mkdtemp(prefix="qrgen_subito_bot_")
        context.user_data["temp_dir"] = tmp_dir
    return tmp_dir


async def _show_processing(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = menu_back_kb("SUBITO")
    if update.callback_query:
        await update.callback_query.message.edit_text("Обрабатываю данные…", reply_markup=kb)
    else:
        await update.message.reply_text("Обрабатываю данные…", reply_markup=kb)


async def subito_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    _cleanup_temp_dir(context)
    clear_stack(context.user_data)
    await update.callback_query.answer()
    context.user_data.pop("photo_path", None)
    context.user_data.pop("url", None)
    context.user_data.pop("time_text", None)
    context.user_data["temp_dir"] = tempfile.mkdtemp(prefix="qrgen_subito_bot_")
    await ask_nazvanie(update, context)
    return SUBITO_NAZVANIE


async def ask_nazvanie(update: Update, context: ContextTypes.DEFAULT_TYPE):
    push_state(context.user_data, SUBITO_NAZVANIE)
    await _send(update, context, "Введи название товара:")


async def ask_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    push_state(context.user_data, SUBITO_PRICE)
    await _edit_or_send(update, context, "Введи цену товара (пример: 99.99):")


async def ask_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    push_state(context.user_data, SUBITO_NAME)
    await _edit_or_send(update, context, "Введи имя получателя:")


async def ask_address(update: Update, context: ContextTypes.DEFAULT_TYPE):
    push_state(context.user_data, SUBITO_ADDRESS)
    await _edit_or_send(update, context, "Введи адрес (можно несколько строк):")


async def ask_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    push_state(context.user_data, SUBITO_PHOTO)
    txt = "Отправь фото товара или нажми «Пропустить»:"
    if update.callback_query:
        await update.callback_query.message.edit_text(txt, reply_markup=photo_step_kb("SUBITO"))
    else:
        await update.message.reply_text(txt, reply_markup=photo_step_kb("SUBITO"))


async def ask_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    push_state(context.user_data, SUBITO_URL)
    await _edit_or_send(update, context, "Введи URL для QR-кода:")


async def ask_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    push_state(context.user_data, SUBITO_TIME)
    kb = skip_step_kb("SUBITO", action="SKIP_TIME")
    if update.callback_query:
        await update.callback_query.message.edit_text(
            "Введи время (ЧЧ:ММ) или нажми «Пропустить»:",
            reply_markup=kb,
        )
    else:
        await update.message.reply_text(
            "Введи время (ЧЧ:ММ) или нажми «Пропустить»:",
            reply_markup=kb,
        )


async def _send(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
    kb = menu_back_kb("SUBITO")
    if update.callback_query:
        await update.callback_query.message.edit_text(text, reply_markup=kb)
    else:
        await update.message.reply_text(text, reply_markup=kb)


async def _edit_or_send(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
    kb = menu_back_kb("SUBITO")
    if update.callback_query:
        await update.callback_query.message.edit_text(text, reply_markup=kb)
    else:
        await update.message.reply_text(text, reply_markup=kb)


async def on_nazvanie(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["nazvanie"] = update.message.text.strip()
    await ask_price(update, context)
    return SUBITO_PRICE


async def on_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.strip().replace(",", ".")
    try:
        context.user_data["price"] = float(txt)
    except ValueError:
        await update.message.reply_text("Пожалуйста, введи число, например 149.99")
        return SUBITO_PRICE
    await ask_name(update, context)
    return SUBITO_NAME


async def on_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["name"] = update.message.text.strip()
    await ask_address(update, context)
    return SUBITO_ADDRESS


async def on_address(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["address"] = update.message.text.strip()
    await ask_photo(update, context)
    return SUBITO_PHOTO


async def on_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").strip().lower() if update.message.text else ""
    if text in {"нет", "no", "-", "skip"}:
        context.user_data["photo_path"] = None
        await ask_url(update, context)
        return SUBITO_URL

    if update.message.photo:
        photo_file = await update.message.photo[-1].get_file()
        temp_dir = _ensure_temp_dir(context)
        tmp = os.path.join(temp_dir, f"subito_{uuid.uuid4()}.jpg")
        await photo_file.download_to_drive(tmp)
        context.user_data["photo_path"] = tmp
        await ask_url(update, context)
        return SUBITO_URL

    await update.message.reply_text("Пожалуйста, отправь фото или нажми «Пропустить».")
    return SUBITO_PHOTO


async def on_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    nazvanie = context.user_data.get("nazvanie", "")
    price = context.user_data.get("price", 0.0)
    name = context.user_data.get("name", "")
    address = context.user_data.get("address", "")
    photo_path = context.user_data.get("photo_path")

    url = update.message.text.strip()
    if not url.startswith("http"):
        url = "https://" + url
    context.user_data["url"] = url
    context.user_data.pop("time_text", None)
    await ask_time(update, context)
    return SUBITO_TIME


async def on_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    normalized = normalize_hhmm(update.message.text)
    if normalized is None:
        await update.message.reply_text(
            "Некорректное время. Укажи ЧЧ:ММ, например 09:45, или нажми «Пропустить».",
            reply_markup=menu_back_kb("SUBITO"),
        )
        return SUBITO_TIME

    context.user_data["time_text"] = normalized
    await _show_processing(update, context)
    return await _generate_subito(update, context)


async def subito_skip_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    context.user_data["time_text"] = None
    await _show_processing(update, context)
    return await _generate_subito(update, context)


async def _generate_subito(update: Update, context: ContextTypes.DEFAULT_TYPE):
    nazvanie = context.user_data.get("nazvanie", "")
    price = context.user_data.get("price", 0.0)
    name = context.user_data.get("name", "")
    address = context.user_data.get("address", "")
    photo_path = context.user_data.get("photo_path")
    url = context.user_data.get("url", "")
    time_text = context.user_data.get("time_text")
    temp_dir = _ensure_temp_dir(context)

    chat_id = update.effective_chat.id
    image_path = processed_photo_path = qr_path = None
    try:
        image_path, processed_photo_path, qr_path = await asyncio.to_thread(
            create_subito_image,
            nazvanie,
            price,
            url,
            name=name,
            address=address,
            photo_path=photo_path,
            temp_dir=temp_dir,
            time_text=time_text,
        )

        with open(image_path, "rb") as f:
            payload = f.read()

        filename = os.path.basename(image_path)
        await context.bot.send_document(
            chat_id=chat_id,
            document=InputFile(BytesIO(payload), filename=filename),
        )

        await context.bot.send_message(
            chat_id=chat_id,
            text="PNG готов!",
            reply_markup=main_menu_kb(),
        )
        clear_stack(context.user_data)
        Path(image_path).unlink(missing_ok=True)
        context.user_data.pop("photo_path", None)
        context.user_data.pop("url", None)
        context.user_data.pop("time_text", None)
        return ConversationHandler.END
    except Exception as e:
        logger.exception("Ошибка генерации Subito")
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"Ошибка: {e}",
            reply_markup=main_menu_kb(),
        )
        clear_stack(context.user_data)
        context.user_data.pop("photo_path", None)
        context.user_data.pop("url", None)
        context.user_data.pop("time_text", None)
        return ConversationHandler.END
    finally:
        cleanup_paths(photo_path, processed_photo_path, qr_path)
        _cleanup_temp_dir(context)


async def subito_menu_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer("Возврат в главное меню")
    clear_stack(context.user_data)
    _cleanup_temp_dir(context)
    context.user_data.pop("photo_path", None)
    context.user_data.pop("url", None)
    context.user_data.pop("time_text", None)
    from app.handlers.menu import start

    await start(update, context)
    return ConversationHandler.END


async def subito_skip_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    context.user_data["photo_path"] = None
    await ask_url(update, context)
    return SUBITO_URL


async def subito_back_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    last = pop_state(context.user_data)
    prev = pop_state(context.user_data)
    if prev is None:
        return await subito_menu_cb(update, context)

    if prev == SUBITO_NAZVANIE:
        await ask_nazvanie(update, context)
        return SUBITO_NAZVANIE
    if prev == SUBITO_PRICE:
        await ask_price(update, context)
        return SUBITO_PRICE
    if prev == SUBITO_NAME:
        await ask_name(update, context)
        return SUBITO_NAME
    if prev == SUBITO_ADDRESS:
        await ask_address(update, context)
        return SUBITO_ADDRESS
    if prev == SUBITO_PHOTO:
        await ask_photo(update, context)
        return SUBITO_PHOTO
    if prev == SUBITO_URL:
        await ask_url(update, context)
        return SUBITO_URL
    if prev == SUBITO_TIME:
        await ask_time(update, context)
        return SUBITO_TIME


subito_conv = ConversationHandler(
    name="subito_flow",
    entry_points=[CallbackQueryHandler(subito_entry, pattern=r"^SUBITO:START$")],
    states={
        SUBITO_NAZVANIE: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, on_nazvanie),
            CallbackQueryHandler(subito_menu_cb, pattern=r"^SUBITO:MENU$"),
            CallbackQueryHandler(subito_back_cb, pattern=r"^SUBITO:BACK$"),
        ],
        SUBITO_PRICE: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, on_price),
            CallbackQueryHandler(subito_menu_cb, pattern=r"^SUBITO:MENU$"),
            CallbackQueryHandler(subito_back_cb, pattern=r"^SUBITO:BACK$"),
        ],
        SUBITO_NAME: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, on_name),
            CallbackQueryHandler(subito_menu_cb, pattern=r"^SUBITO:MENU$"),
            CallbackQueryHandler(subito_back_cb, pattern=r"^SUBITO:BACK$"),
        ],
        SUBITO_ADDRESS: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, on_address),
            CallbackQueryHandler(subito_menu_cb, pattern=r"^SUBITO:MENU$"),
            CallbackQueryHandler(subito_back_cb, pattern=r"^SUBITO:BACK$"),
        ],
        SUBITO_PHOTO: [
            MessageHandler(filters.PHOTO, on_photo),
            MessageHandler(filters.TEXT & ~filters.COMMAND, on_photo),
            CallbackQueryHandler(subito_menu_cb, pattern=r"^SUBITO:MENU$"),
            CallbackQueryHandler(subito_back_cb, pattern=r"^SUBITO:BACK$"),
            CallbackQueryHandler(subito_skip_photo, pattern=r"^SUBITO:SKIP_PHOTO$"),
        ],
        SUBITO_URL: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, on_url),
            CallbackQueryHandler(subito_menu_cb, pattern=r"^SUBITO:MENU$"),
            CallbackQueryHandler(subito_back_cb, pattern=r"^SUBITO:BACK$"),
        ],
        SUBITO_TIME: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, on_time),
            CallbackQueryHandler(subito_menu_cb, pattern=r"^SUBITO:MENU$"),
            CallbackQueryHandler(subito_back_cb, pattern=r"^SUBITO:BACK$"),
            CallbackQueryHandler(subito_skip_time, pattern=r"^SUBITO:SKIP_TIME$"),
        ],
    },
    fallbacks=[CommandHandler("start", subito_menu_cb)],
    allow_reentry=True,
)
