# app/handlers/subscription.py
import asyncio, os
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, CallbackQueryHandler, CommandHandler
from services.cryptopay import create_invoice, get_invoices
from services.db import add_subscription, has_active_subscription, init_db, latest_subscription
from config import CFG

PLAN_PRICE = float(os.getenv("PLAN_MONTH_PRICE", "2.5"))
PLAN_DAYS = int(os.getenv("PLAN_MONTH_DAYS", "30"))
ASSET = os.getenv("CRYPTOPAY_ASSET", "TON")

def subscription_menu_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"Оформить подписку ({PLAN_PRICE} {ASSET} / {PLAN_DAYS} дн.)", callback_data="SUB:CREATE")],
        [InlineKeyboardButton("🏠 Главное меню", callback_data="MENU")]
    ])

async def subscription_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if has_active_subscription(uid):
        sub = latest_subscription(uid)
        text = f"✅ У тебя активная подписка до {sub.end_at:%Y-%m-%d %H:%M UTC}."
        await update.message.reply_text(text, reply_markup=subscription_menu_kb())
    else:
        await update.message.reply_text(
            "Подписка нужна для генерации QR/PDF.\nОформи её ниже:",
            reply_markup=subscription_menu_kb()
        )

async def sub_create_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    uid = update.effective_user.id
    desc = f"Подписка на {PLAN_DAYS} дней для @{update.effective_user.username or uid}"
    payload = f"user:{uid}|plan:month"
    try:
        inv = await asyncio.to_thread(create_invoice, ASSET, PLAN_PRICE, desc, payload)
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("Оплатить 💳", url=inv["pay_url"]),
            InlineKeyboardButton("Я оплатил ✅", callback_data=f"SUB:CHECK:{inv['invoice_id']}")
        ],[
            InlineKeyboardButton("🏠 Главное меню", callback_data="MENU")
        ]])
        await update.callback_query.message.edit_text(
            f"Счёт создан. Оплатите по кнопке ниже.\nПосле оплаты нажмите «Я оплатил ✅».",
            reply_markup=kb
        )
    except Exception as e:
        await update.callback_query.message.edit_text(f"Не удалось создать счёт: {e}")

async def sub_check_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer("Проверяю оплату…")
    parts = update.callback_query.data.split(":")
    invoice_id = parts[-1]
    try:
        items = await asyncio.to_thread(get_invoices, [invoice_id])
        status = items[0].get("status")
        if status == "paid":
            # зафиксируем подписку
            add_subscription(update.effective_user.id, "month", invoice_id, PLAN_DAYS)
            await update.callback_query.message.edit_text(
                "✅ Оплата подтверждена. Подписка активирована!",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Главное меню", callback_data="MENU")]])
            )
        elif status == "active":
            await update.callback_query.message.reply_text("Счёт ещё не оплачен. Попробуй через минуту.")
        else:
            await update.callback_query.message.reply_text(f"Статус счёта: {status}")
    except Exception as e:
        await update.callback_query.message.reply_text(f"Ошибка проверки: {e}")

# вспомогательный guard
async def require_subscription(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    uid = update.effective_user.id
    if has_active_subscription(uid):
        return True
    # предложим оформить подписку
    if update.callback_query:
        await update.callback_query.message.reply_text("Нужна активная подписка.", reply_markup=subscription_menu_kb())
    else:
        await update.message.reply_text("Нужна активная подписка.", reply_markup=subscription_menu_kb())
    return False
