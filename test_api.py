#!/usr/bin/env python3
"""
Скрипт для тестирования API через универсальный /generate эндпоинт

Использование:
    python test_api.py YOUR_API_KEY [--host HOST] [--port PORT] [--quick]
    
Примеры:
    python test_api.py my_api_key_123
    python test_api.py my_api_key_123 --host localhost --port 8000
    python test_api.py my_api_key_123 --quick
"""

import sys
import argparse
import requests
import json
from pathlib import Path
from datetime import datetime

# Тестовые данные - отправляем ВСЕ поля, API возьмёт только нужные
TEST_DATA = [
    # === NETHERLANDS ===
    {
        "name": "nl_marktplaats_qr",
        "data": {
            "country": "nl",
            "service": "marktplaats",
            "method": "qr",
            # Нужные поля
            "title": "iPhone 13 Pro Max 256GB",
            "price": 799.99,
            "url": "https://marktplaats.nl/test",
            "photo": None,
            # Лишние поля - будут проигнорированы
            "seller_name": "ignored",
            "address": "ignored"
        }
    },
    {
        "name": "nl_2dehands_qr",
        "data": {
            "country": "nl",
            "service": "2dehands",
            "method": "qr",
            "title": "Samsung Galaxy S23 Ultra",
            "price": 699.99,
            "url": "https://2dehands.be/test",
            "photo": None,
            "name": "ignored",
            "seller_photo": "ignored"
        }
    },
    
    # === BELGIUM ===
    {
        "name": "be_2ememain_qr",
        "data": {
            "country": "be",
            "service": "2ememain",
            "method": "qr",
            "title": "Nintendo Switch OLED",
            "price": 299.00,
            "url": "https://2ememain.be/test",
            "photo": None
        }
    },
    
    # === ITALY - SUBITO ===
    {
        "name": "it_subito_qr",
        "data": {
            "country": "it",
            "service": "subito",
            "method": "qr",
            "title": "MacBook Pro 2023 M3",
            "price": 1499.00,
            "url": "https://subito.it/test",
            "photo": None,
            "name": "Mario Rossi",
            "address": "Milano, IT"
        }
    },
    {
        "name": "it_subito_email_request",
        "data": {
            "country": "it",
            "service": "subito",
            "method": "email_request",
            "title": "iPad Air 2024",
            "price": 599.00,
            "photo": None,
            "name": "Giuseppe Verdi",
            "address": "Roma, IT",
            "url": "not needed but sent anyway"
        }
    },
    {
        "name": "it_subito_email_confirm",
        "data": {
            "country": "it",
            "service": "subito",
            "method": "email_confirm",
            "title": "AirPods Pro Gen 2",
            "price": 249.00,
            "name": "Luigi Bianchi",
            "address": "Napoli, IT"
        }
    },
    {
        "name": "it_subito_sms_request",
        "data": {
            "country": "it",
            "service": "subito",
            "method": "sms_request",
            "title": "Apple Watch Series 9",
            "price": 399.00,
            "name": "Antonio Rossi",
            "address": "Torino, IT"
        }
    },
    {
        "name": "it_subito_sms_confirm",
        "data": {
            "country": "it",
            "service": "subito",
            "method": "sms_confirm",
            "title": "MacBook Air M2",
            "price": 1099.00,
            "name": "Francesco Nero",
            "address": "Firenze, IT"
        }
    },
    
    # === ITALY - CONTO ===
    {
        "name": "it_conto_payment",
        "data": {
            "country": "it",
            "service": "conto",
            "method": "payment",
            "title": "Xiaomi 13T Pro 5G",
            "price": 549.99,
            # Лишние
            "url": "ignored",
            "photo": "ignored"
        }
    },
    
    # === GERMANY ===
    {
        "name": "de_kleinanzeigen_qr",
        "data": {
            "country": "de",
            "service": "kleinanzeigen",
            "method": "qr",
            "title": "Canon EOS R6 Mark II",
            "price": 2299.00,
            "url": "https://kleinanzeigen.de/test",
            "photo": None
        }
    },
    
    # === SPAIN - WALLAPOP ===
    {
        "name": "es_wallapop_email_request",
        "data": {
            "country": "es",
            "service": "wallapop",
            "method": "email_request",
            "title": "PlayStation 5 + 2 Mandos",
            "price": 450.00,
            "seller_name": "Carlos García",
            "photo": None,
            "seller_photo": None
        }
    },
    {
        "name": "es_wallapop_phone_request",
        "data": {
            "country": "es",
            "service": "wallapop",
            "method": "phone_request",
            "title": "iPhone 14 Pro",
            "price": 899.00,
            "seller_name": "María López"
        }
    },
    {
        "name": "es_wallapop_email_payment",
        "data": {
            "country": "es",
            "service": "wallapop",
            "method": "email_payment",
            "title": "MacBook Air M2",
            "price": 1099.00,
            "seller_name": "Juan Martínez"
        }
    },
    {
        "name": "es_wallapop_sms_payment",
        "data": {
            "country": "es",
            "service": "wallapop",
            "method": "sms_payment",
            "title": "iPad Pro 12.9",
            "price": 1199.00,
            "seller_name": "Ana Rodríguez"
        }
    },
    {
        "name": "es_wallapop_qr",
        "data": {
            "country": "es",
            "service": "wallapop",
            "method": "qr",
            "title": "Nintendo Switch OLED",
            "price": 299.00,
            "seller_name": "Pedro García",
            "url": "https://wallapop.com/test"
        }
    },
    
    # === UK - WALLAPOP ===
    {
        "name": "uk_wallapop_email_request",
        "data": {
            "country": "uk",
            "service": "wallapop",
            "method": "email_request",
            "title": "Sony WH-1000XM5",
            "price": 279.00,
            "seller_name": "John Smith"
        }
    },
    
    # === FRANCE - WALLAPOP ===
    {
        "name": "fr_wallapop_email_request",
        "data": {
            "country": "fr",
            "service": "wallapop",
            "method": "email_request",
            "title": "Dyson V15 Detect",
            "price": 599.00,
            "seller_name": "Pierre Dupont"
        }
    },
    
    # === PORTUGAL - WALLAPOP ===
    {
        "name": "pt_wallapop_email_request",
        "data": {
            "country": "pt",
            "service": "wallapop",
            "method": "email_request",
            "title": "Samsung Galaxy S24",
            "price": 849.00,
            "seller_name": "João Silva"
        }
    },
    
    # === AUSTRALIA - DEPOP ===
    {
        "name": "au_depop_qr",
        "data": {
            "country": "au",
            "service": "depop",
            "method": "qr",
            "title": "Vintage Nike Jacket 90s",
            "price": 89.99,
            "seller_name": "vintage_store",
            "url": "https://depop.com/test",
            "photo": None,
            "seller_photo": None
        }
    },
    {
        "name": "au_depop_email_request",
        "data": {
            "country": "au",
            "service": "depop",
            "method": "email_request",
            "title": "Retro Levi's 501",
            "price": 65.00
        }
    },
    {
        "name": "au_depop_email_confirm",
        "data": {
            "country": "au",
            "service": "depop",
            "method": "email_confirm",
            "title": "Y2K Crop Top",
            "price": 35.00
        }
    },
    {
        "name": "au_depop_sms_request",
        "data": {
            "country": "au",
            "service": "depop",
            "method": "sms_request",
            "title": "Vintage Carhartt Jacket",
            "price": 120.00
        }
    },
    {
        "name": "au_depop_sms_confirm",
        "data": {
            "country": "au",
            "service": "depop",
            "method": "sms_confirm",
            "title": "90s Tommy Hilfiger Shirt",
            "price": 55.00
        }
    }
]


def test_generate(base_url: str, api_key: str, test_case: dict, output_dir: Path) -> bool:
    """Тест одного запроса к /generate"""
    name = test_case["name"]
    data = test_case["data"]
    
    try:
        print(f"📡 {name}...", end=" ", flush=True)
        
        response = requests.post(
            f"{base_url}/generate",
            headers={
                "X-API-Key": api_key,
                "Content-Type": "application/json"
            },
            json=data,
            timeout=60
        )
        
        if response.status_code != 200:
            print(f"❌ {response.status_code}")
            try:
                detail = response.json().get("detail", response.text[:100])
            except:
                detail = response.text[:100]
            print(f"   └─ {detail}")
            return False
        
        # Сохраняем
        output_file = output_dir / f"{name}.png"
        with open(output_file, "wb") as f:
            f.write(response.content)
        
        size_kb = len(response.content) / 1024
        print(f"✅ {size_kb:.1f}KB")
        return True
        
    except requests.exceptions.Timeout:
        print("❌ Timeout")
        return False
    except requests.exceptions.ConnectionError:
        print("❌ Connection error")
        return False
    except Exception as e:
        print(f"❌ {e}")
        return False


def test_get_geo(base_url: str, api_key: str) -> tuple:
    """Тест /get-geo"""
    try:
        print("🌍 GET /get-geo...", end=" ", flush=True)
        
        response = requests.get(
            f"{base_url}/get-geo",
            headers={"X-API-Key": api_key},
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            countries = list(data.keys())
            print(f"✅ {len(countries)} countries")
            return True, data
        else:
            print(f"❌ {response.status_code}")
            return False, None
            
    except Exception as e:
        print(f"❌ {e}")
        return False, None


def test_api_status(base_url: str, api_key: str) -> bool:
    """Тест /api/status"""
    try:
        print("🔑 GET /api/status...", end=" ", flush=True)
        
        response = requests.get(
            f"{base_url}/api/status",
            headers={"X-API-Key": api_key},
            timeout=5
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ key={data.get('key_name', '?')}")
            return True
        else:
            print(f"❌ {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Test QRGen API")
    parser.add_argument("api_key", help="API key")
    parser.add_argument("--host", default="localhost", help="API host")
    parser.add_argument("--port", type=int, default=8080, help="API port")
    parser.add_argument("--output", default="test_output", help="Output directory")
    parser.add_argument("--quick", action="store_true", help="Quick test (one per country/service)")
    
    args = parser.parse_args()
    base_url = f"http://{args.host}:{args.port}"
    
    # Output dir
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = Path(args.output) / timestamp
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print("=" * 60)
    print("🧪 QRGen API Test")
    print("=" * 60)
    print(f"URL: {base_url}")
    print(f"Key: {args.api_key[:10]}...")
    print(f"Output: {output_dir}")
    print("=" * 60)
    print()
    
    # Status check
    if not test_api_status(base_url, args.api_key):
        print("\n❌ API not available")
        sys.exit(1)
    
    # Geo check
    geo_ok, geo_data = test_get_geo(base_url, args.api_key)
    if geo_ok:
        with open(output_dir / "geo.json", "w") as f:
            json.dump(geo_data, f, indent=2)
    
    print()
    print("-" * 60)
    print("📸 Testing /generate")
    print("-" * 60)
    print()
    
    # Filter for quick mode
    test_cases = TEST_DATA
    if args.quick:
        seen = set()
        quick = []
        for tc in TEST_DATA:
            key = (tc["data"]["country"], tc["data"]["service"])
            if key not in seen:
                seen.add(key)
                quick.append(tc)
        test_cases = quick
        print(f"⚡ Quick mode: {len(test_cases)} tests\n")
    
    # Run tests
    results = {}
    for tc in test_cases:
        results[tc["name"]] = test_generate(base_url, args.api_key, tc, output_dir)
    
    # Summary
    print()
    print("=" * 60)
    print("📊 Results")
    print("=" * 60)
    
    success = sum(results.values())
    total = len(results)
    
    # Group by country
    by_country = {}
    for tc in test_cases:
        c = tc["data"]["country"]
        n = tc["name"]
        if c not in by_country:
            by_country[c] = []
        by_country[c].append((n, results.get(n, False)))
    
    for country in sorted(by_country.keys()):
        tests = by_country[country]
        ok = sum(1 for _, r in tests if r)
        print(f"\n🌍 {country.upper()} ({ok}/{len(tests)})")
        for name, result in tests:
            short = name.replace(f"{country}_", "")
            print(f"   {'✅' if result else '❌'} {short}")
    
    print()
    print("=" * 60)
    print(f"Total: {success}/{total} ({'✅ ALL PASSED' if success == total else f'❌ {total-success} FAILED'})")
    print(f"Output: {output_dir}")
    print("=" * 60)
    
    # Save report
    with open(output_dir / "report.json", "w") as f:
        json.dump({
            "timestamp": timestamp,
            "url": base_url,
            "success": success,
            "total": total,
            "results": results
        }, f, indent=2)


if __name__ == "__main__":
    main()
