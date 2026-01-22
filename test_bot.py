#!/usr/bin/env python3
"""
Скрипт для тестирования всех сервисов через Telegram бота
Генерирует тестовые изображения и отправляет их в бота

Использование:
    python test_bot.py YOUR_TELEGRAM_ID
    
Пример:
    python test_bot.py 123456789
"""

import sys
import asyncio
import os
from pathlib import Path
from telegram import Bot, InputFile
from io import BytesIO

# Добавляем путь к app
sys.path.insert(0, str(Path(__file__).parent))

from app.config import CFG
from app.services.pdf import create_image_marktplaats, create_image_subito, create_image_wallapop
from app.services.subito_variants import (
    create_image_subito_email_request, create_image_subito_email_confirm,
    create_image_subito_sms_request, create_image_subito_sms_confirm
)
from app.services.twodehands import create_2dehands_image
from app.services.kleize import create_kleize_image
from app.services.conto import create_conto_image
from app.services.depop import create_depop_image

# Тестовые данные
TEST_DATA = {
    "marktplaats": {
        "title": "iPhone 13 Pro Max 256GB",
        "price": 799.99,
        "url": "https://marktplaats.nl/test",
        "photo": None
    },
    "subito": {
        "title": "MacBook Pro 2023 M3",
        "price": 1499.00,
        "url": "https://subito.it/test",
        "name": "Mario Rossi",
        "address": "Milano, IT",
        "photo": None
    },
    "subito_email_request": {
        "title": "iPad Air 2024",
        "price": 599.00,
        "name": "Giuseppe Verdi",
        "address": "Roma, IT",
        "photo": None
    },
    "subito_email_confirm": {
        "title": "AirPods Pro Gen 2",
        "price": 249.00,
        "name": "Luigi Bianchi",
        "address": "Napoli, IT",
        "photo": None
    },
    "subito_sms_request": {
        "title": "Apple Watch Series 9",
        "price": 399.00,
        "name": "Antonio Rossi",
        "address": "Torino, IT",
        "photo": None
    },
    "subito_sms_confirm": {
        "title": "MacBook Air M2",
        "price": 1099.00,
        "name": "Francesco Nero",
        "address": "Firenze, IT",
        "photo": None
    },
    "wallapop": {
        "lang": "es",
        "title": "PlayStation 5 + 2 Mandos",
        "price": 450.00,
        "photo": None
    },
    "2dehands": {
        "title": "Samsung Galaxy S23 Ultra",
        "price": 699.99,
        "url": "https://2dehands.be/test",
        "lang": "nl",
        "photo": None
    },
    "2ememain": {
        "title": "Nintendo Switch OLED",
        "price": 299.00,
        "url": "https://2ememain.be/test",
        "lang": "fr",
        "photo": None
    },
    "kleize": {
        "title": "Canon EOS R6 Mark II",
        "price": 2299.00,
        "url": "https://kleinanzeigen.de/test",
        "photo": None
    },
    "conto": {
        "title": "Xiaomi 13T Pro 5G",
        "price": 549.99
    },
    "depop": {
        "title": "Vintage Nike Jacket 90s",
        "price": 89.99,
        "seller_name": "vintage_store",
        "url": "https://depop.com/test",
        "photo": None,
        "avatar": None
    }
}


async def test_service(bot: Bot, chat_id: int, service_name: str, generate_func, data: dict):
    """Тестировать один сервис"""
    try:
        print(f"📸 Генерирую {service_name}...", end=" ")
        
        # Маппинг аргументов для разных сервисов
        if service_name == "marktplaats":
            image_data = generate_func(data["title"], data["price"], data["photo"], data["url"])
        elif service_name == "subito":
            # Оригинальный subito с QR требует URL
            image_data = generate_func(data["title"], data["price"], data["photo"], data["url"], data.get("name", ""), data.get("address", ""))
        elif service_name in ["subito_email_request", "subito_email_confirm", "subito_sms_request", "subito_sms_confirm"]:
            # Email/SMS варианты без URL
            image_data = generate_func(data["title"], data["price"], data["photo"], data.get("name", ""), data.get("address", ""))
        elif service_name == "wallapop":
            image_data = generate_func(data["lang"], data["title"], data["price"], data.get("photo"))
        elif service_name in ["2dehands", "2ememain"]:
            image_data = generate_func(data["title"], data["price"], data["url"], data["lang"], data.get("photo"))
        elif service_name == "kleize":
            image_data = generate_func(data["title"], data["price"], data["url"], data.get("photo"))
        elif service_name == "conto":
            image_data = generate_func(data["title"], data["price"])
        elif service_name == "depop":
            image_data = generate_func(data["title"], data["price"], data["seller_name"], data["url"], data.get("photo"), data.get("avatar"))
        else:
            raise ValueError(f"Unknown service: {service_name}")
        
        # Отправляем в бот
        await bot.send_photo(
            chat_id=chat_id,
            photo=InputFile(BytesIO(image_data), filename=f"{service_name}_test.png"),
            caption=f"✅ {service_name.upper()}\n\n"
                    f"📝 {data.get('title', 'Test Product')}\n"
                    f"💵 €{data.get('price', 0):.2f}"
        )
        
        print("✅")
        return True
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        await bot.send_message(
            chat_id=chat_id,
            text=f"❌ {service_name.upper()}: Ошибка\n\n<code>{str(e)[:200]}</code>",
            parse_mode="HTML"
        )
        return False


async def main(chat_id: int):
    """Основная функция"""
    
    # Проверяем токен бота
    if not CFG.TELEGRAM_BOT_TOKEN:
        print("❌ TELEGRAM_BOT_TOKEN не настроен в .env")
        return
    
    bot = Bot(token=CFG.TELEGRAM_BOT_TOKEN)
    
    print(f"🤖 Запуск тестирования для chat_id: {chat_id}")
    print(f"📨 Все изображения будут отправлены в чат\n")
    
    # Отправляем стартовое сообщение
    await bot.send_message(
        chat_id=chat_id,
        text="🧪 <b>Начинаю тестирование всех сервисов...</b>\n\n"
             "Это может занять ~30 секунд",
        parse_mode="HTML"
    )
    
    results = {}
    
    # Тест Marktplaats
    results['marktplaats'] = await test_service(
        bot, chat_id, "marktplaats",
        create_image_marktplaats,
        TEST_DATA['marktplaats']
    )
    
    # Тест Subito
    results['subito'] = await test_service(
        bot, chat_id, "subito",
        create_image_subito,
        TEST_DATA['subito']
    )
    
    # Тест Subito Email Request
    results['subito_email_request'] = await test_service(
        bot, chat_id, "subito_email_request",
        create_image_subito_email_request,
        TEST_DATA['subito_email_request']
    )
    
    # Тест Subito Email Confirm
    results['subito_email_confirm'] = await test_service(
        bot, chat_id, "subito_email_confirm",
        create_image_subito_email_confirm,
        TEST_DATA['subito_email_confirm']
    )
    
    # Тест Subito SMS Request
    results['subito_sms_request'] = await test_service(
        bot, chat_id, "subito_sms_request",
        create_image_subito_sms_request,
        TEST_DATA['subito_sms_request']
    )
    
    # Тест Subito SMS Confirm
    results['subito_sms_confirm'] = await test_service(
        bot, chat_id, "subito_sms_confirm",
        create_image_subito_sms_confirm,
        TEST_DATA['subito_sms_confirm']
    )
    
    # Тест Wallapop
    results['wallapop'] = await test_service(
        bot, chat_id, "wallapop",
        create_image_wallapop,
        TEST_DATA['wallapop']
    )
    
    # Тест 2dehands
    results['2dehands'] = await test_service(
        bot, chat_id, "2dehands",
        create_2dehands_image,
        TEST_DATA['2dehands']
    )
    
    # Тест 2ememain
    results['2ememain'] = await test_service(
        bot, chat_id, "2ememain",
        create_2dehands_image,
        TEST_DATA['2ememain']
    )
    
    # Тест Kleize
    results['kleize'] = await test_service(
        bot, chat_id, "kleize",
        create_kleize_image,
        TEST_DATA['kleize']
    )
    
    # Тест Conto
    results['conto'] = await test_service(
        bot, chat_id, "conto",
        create_conto_image,
        TEST_DATA['conto']
    )
    
    # Тест Depop
    results['depop'] = await test_service(
        bot, chat_id, "depop",
        create_depop_image,
        TEST_DATA['depop']
    )
    
    # Итоговый отчет
    success = sum(results.values())
    total = len(results)
    
    report = f"📊 <b>Результаты тестирования:</b>\n\n"
    
    for service, result in results.items():
        emoji = "✅" if result else "❌"
        report += f"{emoji} {service.upper()}\n"
    
    report += f"\n<b>Успешно:</b> {success}/{total}"
    
    if success == total:
        report += "\n\n🎉 Все сервисы работают!"
    else:
        report += f"\n\n⚠️ Неудачно: {total - success}"
    
    await bot.send_message(
        chat_id=chat_id,
        text=report,
        parse_mode="HTML"
    )
    
    print(f"\n{'='*50}")
    print(f"✅ Успешно: {success}/{total}")
    print(f"❌ Ошибки: {total - success}/{total}")
    print(f"{'='*50}\n")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("❌ Не указан CHAT_ID")
        print("\nИспользование:")
        print("  python test_bot.py YOUR_TELEGRAM_ID")
        print("\nПример:")
        print("  python test_bot.py 123456789")
        print("\nКак узнать свой ID:")
        print("  1. Напиши @userinfobot в Telegram")
        print("  2. Он покажет твой ID")
        sys.exit(1)
    
    try:
        chat_id = int(sys.argv[1])
    except ValueError:
        print(f"❌ Неверный формат CHAT_ID: {sys.argv[1]}")
        print("   CHAT_ID должен быть числом")
        sys.exit(1)
    
    asyncio.run(main(chat_id))
