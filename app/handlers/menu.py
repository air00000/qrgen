# handlers/menu.py
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.error import BadRequest
from telegram.ext import ContextTypes
from app.keyboards.qr import service_select_kb
from app.config import CFG


def _is_admin(update: Update) -> bool:
    uid = update.effective_user.id if update.effective_user else None
    return uid in getattr(CFG, "ADMIN_IDS", set())


def _serialize_kb(kb: InlineKeyboardMarkup):
    """Превращает InlineKeyboardMarkup в хешируемую структуру для сравнения."""
    if kb is None or not kb.inline_keyboard:
        return ()
    rows = []
    for row in kb.inline_keyboard:
        rows.append(tuple(
            (
                btn.text,
                getattr(btn, "callback_data", None),
                getattr(btn, "url", None),
                getattr(btn, "switch_inline_query", None),
                getattr(btn, "switch_inline_query_current_chat", None),
            )
            for btn in row
        ))
    return tuple(rows)


async def _safe_send_or_edit(update: Update, text: str, kb: InlineKeyboardMarkup):
    """Безопасно отправляем/редактируем меню, избегая 'Message is not modified'
    и прочих 400 при невозможности редактирования.
    """
    q = getattr(update, "callback_query", None)
    if not q:
        # обычное новое сообщение
        await update.message.reply_text(text, reply_markup=kb)
        return

    msg = q.message
    old_text = (getattr(msg, "text", None) or "").strip()
    old_kb = _serialize_kb(getattr(msg, "reply_markup", None))
    new_kb = _serialize_kb(kb)

    # если вообще ничего не меняется — не трогаем
    if old_text == text.strip() and old_kb == new_kb:
        await q.answer()
        return

    try:
        # пробуем редактировать сразу и текст, и клавиатуру
        await msg.edit_text(text, reply_markup=kb)
        await q.answer()
    except BadRequest as e:
        s = str(e).lower()
        # ничего не изменилось — просто игнорируем
        if "message is not modified" in s:
            await q.answer()
            return
        # редактирование невозможно (старое сообщение/не найдено) — отправим новое
        if "message to edit not found" in s or "message can't be edited" in s or "message is not modified" in s:
            await q.answer()
            await msg.chat.send_message(text, reply_markup=kb)
            return
        # на всякий случай общий фоллбек — отправим новое
        await q.answer()
        await msg.chat.send_message(text, reply_markup=kb)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = "Выбери сервис для генерации скриншота:"
    kb = service_select_kb(_is_admin(update))
    await _safe_send_or_edit(update, text, kb)


async def menu_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка кнопки 'Главное меню'"""
    # ответим колбэку (убрать "часики") — редактирование/отправка сделается в _safe_send_or_edit
    await _safe_send_or_edit(update, "Выбери сервис для генерации скриншота:", service_select_kb(_is_admin(update)))
