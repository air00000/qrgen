#!/usr/bin/env python3
"""
Скрипт для тестирования генерации через Telegram бота (напрямую через сервисы)

Использование:
    python test_bot.py YOUR_CHAT_ID [--quick]
    
Примеры:
    python test_bot.py 123456789
    python test_bot.py 123456789 --quick
"""

import sys
import asyncio
from pathlib import Path
from io import BytesIO

# Add app to path
sys.path.insert(0, str(Path(__file__).parent))

from telegram import Bot, InputFile
from app.config import CFG
from app.services.pdf import create_image_marktplaats, create_image_subito
from app.services.subito_variants import (
    create_image_subito_email_request, create_image_subito_email_confirm,
    create_image_subito_sms_request, create_image_subito_sms_confirm
)
from app.services.wallapop_variants import (
    create_wallapop_email_request, create_wallapop_sms_request,
    create_wallapop_email_payment, create_wallapop_sms_payment,
    create_wallapop_qr
)
from app.services.twodehands import create_2dehands_image
from app.services.kleize import create_kleize_image
from app.services.conto import create_conto_image
from app.services.depop import create_depop_image
from app.services.depop_variants import (
    create_depop_email_request, create_depop_email_confirm,
    create_depop_sms_request, create_depop_sms_confirm
)

# Тестовые данные - такие же как в API, но с генераторами
TEST_DATA = [
    # === NETHERLANDS ===
    {
        "name": "nl_marktplaats_qr",
        "country": "nl",
        "gen": lambda: create_image_marktplaats(
            "iPhone 13 Pro Max 256GB", 799.99, None, "https://marktplaats.nl/test"
        )
    },
    {
        "name": "nl_2dehands_qr",
        "country": "nl",
        "gen": lambda: create_2dehands_image(
            "Samsung Galaxy S23 Ultra", 699.99, None, "https://2dehands.be/test", "nl"
        )
    },
    
    # === BELGIUM ===
    {
        "name": "be_2ememain_qr",
        "country": "be",
        "gen": lambda: create_2dehands_image(
            "Nintendo Switch OLED", 299.00, None, "https://2ememain.be/test", "fr"
        )
    },
    
    # === ITALY - SUBITO ===
    {
        "name": "it_subito_qr",
        "country": "it",
        "gen": lambda: create_image_subito(
            "MacBook Pro 2023 M3", 1499.00, None, "https://subito.it/test", "Mario Rossi", "Milano, IT"
        )
    },
    {
        "name": "it_subito_email_request",
        "country": "it",
        "gen": lambda: create_image_subito_email_request(
            "iPad Air 2024", 599.00, None, "Giuseppe Verdi", "Roma, IT"
        )
    },
    {
        "name": "it_subito_email_confirm",
        "country": "it",
        "gen": lambda: create_image_subito_email_confirm(
            "AirPods Pro Gen 2", 249.00, None, "Luigi Bianchi", "Napoli, IT"
        )
    },
    {
        "name": "it_subito_sms_request",
        "country": "it",
        "gen": lambda: create_image_subito_sms_request(
            "Apple Watch Series 9", 399.00, None, "Antonio Rossi", "Torino, IT"
        )
    },
    {
        "name": "it_subito_sms_confirm",
        "country": "it",
        "gen": lambda: create_image_subito_sms_confirm(
            "MacBook Air M2", 1099.00, None, "Francesco Nero", "Firenze, IT"
        )
    },
    
    # === ITALY - CONTO ===
    {
        "name": "it_conto_payment",
        "country": "it",
        "gen": lambda: create_conto_image("Xiaomi 13T Pro 5G", 549.99)
    },
    
    # === GERMANY ===
    {
        "name": "de_kleinanzeigen_qr",
        "country": "de",
        "gen": lambda: create_kleize_image(
            "Canon EOS R6 Mark II", 2299.00, None, "https://kleinanzeigen.de/test"
        )
    },
    
    # === SPAIN - WALLAPOP ===
    {
        "name": "es_wallapop_email_request",
        "country": "es",
        "gen": lambda: create_wallapop_email_request(
            "es", "PlayStation 5 + 2 Mandos", 450.00, None, "Carlos García", None
        )
    },
    {
        "name": "es_wallapop_phone_request",
        "country": "es",
        "gen": lambda: create_wallapop_sms_request(
            "es", "iPhone 14 Pro", 899.00, None, "María López", None
        )
    },
    {
        "name": "es_wallapop_email_payment",
        "country": "es",
        "gen": lambda: create_wallapop_email_payment(
            "es", "MacBook Air M2", 1099.00, None, "Juan Martínez", None
        )
    },
    {
        "name": "es_wallapop_sms_payment",
        "country": "es",
        "gen": lambda: create_wallapop_sms_payment(
            "es", "iPad Pro 12.9", 1199.00, None, "Ana Rodríguez", None
        )
    },
    {
        "name": "es_wallapop_qr",
        "country": "es",
        "gen": lambda: create_wallapop_qr(
            "es", "Nintendo Switch OLED", 299.00, None, "Pedro García", None, "https://wallapop.com/test"
        )
    },
    
    # === UK ===
    {
        "name": "uk_wallapop_email_request",
        "country": "uk",
        "gen": lambda: create_wallapop_email_request(
            "uk", "Sony WH-1000XM5", 279.00, None, "John Smith", None
        )
    },
    
    # === FRANCE ===
    {
        "name": "fr_wallapop_email_request",
        "country": "fr",
        "gen": lambda: create_wallapop_email_request(
            "fr", "Dyson V15 Detect", 599.00, None, "Pierre Dupont", None
        )
    },
    
    # === PORTUGAL ===
    {
        "name": "pt_wallapop_email_request",
        "country": "pt",
        "gen": lambda: create_wallapop_email_request(
            "pt", "Samsung Galaxy S24", 849.00, None, "João Silva", None
        )
    },
    
    # === AUSTRALIA - DEPOP ===
    {
        "name": "au_depop_qr",
        "country": "au",
        "gen": lambda: create_depop_image(
            "Vintage Nike Jacket 90s", 89.99, "vintage_store", None, None, "https://depop.com/test"
        )
    },
    {
        "name": "au_depop_email_request",
        "country": "au",
        "gen": lambda: create_depop_email_request("Retro Levi's 501", 65.00, None)
    },
    {
        "name": "au_depop_email_confirm",
        "country": "au",
        "gen": lambda: create_depop_email_confirm("Y2K Crop Top", 35.00, None)
    },
    {
        "name": "au_depop_sms_request",
        "country": "au",
        "gen": lambda: create_depop_sms_request("Vintage Carhartt Jacket", 120.00, None)
    },
    {
        "name": "au_depop_sms_confirm",
        "country": "au",
        "gen": lambda: create_depop_sms_confirm("90s Tommy Hilfiger Shirt", 55.00, None)
    }
]


async def test_one(bot: Bot, chat_id: int, tc: dict) -> bool:
    """Тест одного генератора"""
    name = tc["name"]
    country = tc["country"]
    gen = tc["gen"]
    
    try:
        print(f"📸 {name}...", end=" ", flush=True)
        
        # Generate
        image_data = gen()
        size_kb = len(image_data) / 1024
        
        # Send
        await bot.send_photo(
            chat_id=chat_id,
            photo=InputFile(BytesIO(image_data), filename=f"{name}.png"),
            caption=f"✅ <b>{name}</b>\n🌍 {country.upper()}\n📦 {size_kb:.1f}KB",
            parse_mode="HTML"
        )
        
        print(f"✅ {size_kb:.1f}KB")
        return True
        
    except Exception as e:
        print(f"❌ {e}")
        try:
            await bot.send_message(
                chat_id=chat_id,
                text=f"❌ <b>{name}</b>\n<code>{str(e)[:200]}</code>",
                parse_mode="HTML"
            )
        except:
            pass
        return False


async def main(chat_id: int, quick: bool = False):
    """Main"""
    if not CFG.TELEGRAM_BOT_TOKEN:
        print("❌ TELEGRAM_BOT_TOKEN not set")
        return
    
    bot = Bot(token=CFG.TELEGRAM_BOT_TOKEN)
    
    # Filter tests
    test_cases = TEST_DATA
    if quick:
        seen = set()
        filtered = []
        for tc in TEST_DATA:
            key = tc["country"]
            if key not in seen:
                seen.add(key)
                filtered.append(tc)
        test_cases = filtered
    
    print("=" * 50)
    print("🤖 Bot Test")
    print("=" * 50)
    print(f"Chat: {chat_id}")
    print(f"Tests: {len(test_cases)} {'(quick)' if quick else ''}")
    print("=" * 50)
    print()
    
    # Start message
    await bot.send_message(
        chat_id=chat_id,
        text=f"🧪 <b>Starting test...</b>\n📊 {len(test_cases)} tests",
        parse_mode="HTML"
    )
    
    # Run
    results = {}
    for tc in test_cases:
        results[tc["name"]] = await test_one(bot, chat_id, tc)
        await asyncio.sleep(0.3)
    
    # Summary
    success = sum(results.values())
    total = len(results)
    
    # Group
    by_country = {}
    for tc in test_cases:
        c = tc["country"]
        n = tc["name"]
        if c not in by_country:
            by_country[c] = []
        by_country[c].append((n, results.get(n, False)))
    
    report = "📊 <b>Results</b>\n"
    for country in sorted(by_country.keys()):
        tests = by_country[country]
        ok = sum(1 for _, r in tests if r)
        report += f"\n🌍 <b>{country.upper()}</b> ({ok}/{len(tests)})\n"
        for name, result in tests:
            short = name.replace(f"{country}_", "")
            report += f"  {'✅' if result else '❌'} {short}\n"
    
    report += f"\n<b>Total:</b> {success}/{total}"
    if success == total:
        report += " ✅"
    
    await bot.send_message(chat_id=chat_id, text=report, parse_mode="HTML")
    
    print()
    print("=" * 50)
    print(f"Total: {success}/{total}")
    print("=" * 50)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_bot.py CHAT_ID [--quick]")
        print("\nGet your ID: message @userinfobot on Telegram")
        sys.exit(1)
    
    try:
        chat_id = int(sys.argv[1])
    except ValueError:
        print(f"Invalid CHAT_ID: {sys.argv[1]}")
        sys.exit(1)
    
    quick = "--quick" in sys.argv
    asyncio.run(main(chat_id, quick))
