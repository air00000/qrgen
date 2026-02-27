import logging
import uuid

from telegram import Update
from telegram.ext import ContextTypes

from app.config import CFG
from app.keyboards.subscription import subscription_menu_kb, invoice_kb
from app.services.cryptobot import create_invoice, get_invoice, CryptoBotError
from app.services.subscriptions import (
    create_pending_payment,
    get_subscription_status,
    activate_payment,
)

logger = logging.getLogger(__name__)


PLAN_PRICES = {
    "day": CFG.SUBSCRIPTION_DAY_PRICE_USDT,
    "week": CFG.SUBSCRIPTION_WEEK_PRICE_USDT,
}


async def subscription_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message or update.callback_query.message
    await msg.reply_text(
        f"💎 Подписка:\n• 1 день — {PLAN_PRICES['day']:.2f} USDT\n• 1 неделя — {PLAN_PRICES['week']:.2f} USDT",
        reply_markup=subscription_menu_kb(),
    )


async def subscription_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    row = get_subscription_status(uid)
    if not row:
        text = "❌ Подписка не активна"
    else:
        text = f"✅ Подписка активна\nТариф: {row['plan_type']}\nДействует до: {row['ends_at']}"

    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.message.reply_text(text, reply_markup=subscription_menu_kb())
    else:
        await update.message.reply_text(text, reply_markup=subscription_menu_kb())


async def subscription_buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    plan = q.data.split(":")[-1]
    if plan not in PLAN_PRICES:
        await q.message.reply_text("❌ Неизвестный тариф")
        return

    payment_id = str(uuid.uuid4())
    amount = PLAN_PRICES[plan]
    uid = update.effective_user.id

    try:
        invoice = create_invoice(payment_id, amount, f"QRGen {plan} subscription")
    except CryptoBotError as e:
        logger.exception("Failed to create invoice")
        await q.message.reply_text(f"❌ Ошибка оплаты: {e}")
        return

    invoice_id = str(invoice.get("invoice_id") or "")
    pay_url = invoice.get("pay_url")
    create_pending_payment(payment_id, uid, plan, amount, invoice_id)

    await q.message.reply_text(
        f"Счёт создан: {amount:.2f} USDT ({plan}).\nПосле оплаты нажми «Проверить оплату».\nID платежа: {payment_id}",
        reply_markup=invoice_kb(pay_url, payment_id),
    )


async def subscription_check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    payment_id = q.data.split(":")[-1]

    from app.services import db
    row = db.fetchone("SELECT invoice_id FROM payments WHERE payment_id = ?", (payment_id,))
    if not row:
        await q.message.reply_text("❌ Платёж не найден")
        return

    try:
        invoice = get_invoice(row["invoice_id"])
    except CryptoBotError as e:
        await q.message.reply_text(f"❌ Не удалось проверить оплату: {e}")
        return

    if not invoice:
        await q.message.reply_text("⌛ Счёт ещё не найден в CryptoBot")
        return

    status = (invoice.get("status") or "").lower()
    if status != "paid":
        await q.message.reply_text(f"⌛ Текущий статус счёта: {status or 'unknown'}")
        return

    activated = activate_payment(payment_id, invoice)
    if activated:
        await q.message.reply_text("✅ Оплата подтверждена. Подписка активирована.")
    else:
        await q.message.reply_text("✅ Оплата уже была обработана ранее.")

    await subscription_status(update, context)
