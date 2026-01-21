#!/usr/bin/env python3
"""
Скрипт для тестирования API всех сервисов
Отправляет запросы к API и сохраняет изображения

Использование:
    python test_api.py YOUR_API_KEY [--host HOST] [--port PORT]
    
Примеры:
    python test_api.py my_api_key_123
    python test_api.py my_api_key_123 --host localhost --port 8000
    python test_api.py my_api_key_123 --host 192.168.1.100
"""

import sys
import argparse
import requests
import json
from pathlib import Path
from datetime import datetime

# Тестовые данные
TEST_DATA = {
    "marktplaats": {
        "endpoint": "/generate_image_marktplaats",
        "data": {
            "title": "iPhone 13 Pro Max 256GB",
            "price": 799.99,
            "url": "https://marktplaats.nl/test"
        }
    },
    "subito": {
        "endpoint": "/generate_image_subito",
        "data": {
            "title": "MacBook Pro 2023 M3",
            "price": 1499.00,
            "url": "https://subito.it/test",
            "name": "Mario Rossi",
            "address": "Milano, IT"
        }
    },
    "subito_email_request": {
        "endpoint": "/generate_image_subito_email_request",
        "data": {
            "title": "iPad Air 2024",
            "price": 599.00,
            "name": "Giuseppe Verdi",
            "address": "Roma, IT"
        }
    },
    "subito_email_confirm": {
        "endpoint": "/generate_image_subito_email_confirm",
        "data": {
            "title": "AirPods Pro Gen 2",
            "price": 249.00,
            "name": "Luigi Bianchi",
            "address": "Napoli, IT"
        }
    },
    "subito_sms_request": {
        "endpoint": "/generate_image_subito_sms_request",
        "data": {
            "title": "Apple Watch Series 9",
            "price": 399.00,
            "name": "Antonio Rossi",
            "address": "Torino, IT"
        }
    },
    "subito_sms_confirm": {
        "endpoint": "/generate_image_subito_sms_confirm",
        "data": {
            "title": "MacBook Air M2",
            "price": 1099.00,
            "name": "Francesco Nero",
            "address": "Firenze, IT"
        }
    },
    "wallapop": {
        "endpoint": "/generate_image_wallapop",
        "data": {
            "lang": "es",
            "title": "PlayStation 5 + 2 Mandos",
            "price": 450.00
        }
    },
    "2dehands": {
        "endpoint": "/generate_image_2dehands",
        "data": {
            "title": "Samsung Galaxy S23 Ultra",
            "price": 699.99,
            "url": "https://2dehands.be/test"
        }
    },
    "2ememain": {
        "endpoint": "/generate_image_2ememain",
        "data": {
            "title": "Nintendo Switch OLED",
            "price": 299.00,
            "url": "https://2ememain.be/test"
        }
    },
    "kleize": {
        "endpoint": "/generate_image_kleize",
        "data": {
            "title": "Canon EOS R6 Mark II",
            "price": 2299.00,
            "url": "https://kleinanzeigen.de/test"
        }
    },
    "conto": {
        "endpoint": "/generate_image_conto",
        "data": {
            "title": "Xiaomi 13T Pro 5G",
            "price": 549.99
        }
    },
    "depop": {
        "endpoint": "/generate_image_depop",
        "data": {
            "title": "Vintage Nike Jacket 90s",
            "price": 89.99,
            "seller_name": "vintage_store",
            "url": "https://depop.com/test"
        }
    }
}


def test_service(base_url: str, api_key: str, service_name: str, endpoint: str, data: dict, output_dir: Path):
    """Тестировать один сервис"""
    try:
        print(f"📡 Тест {service_name}...", end=" ")
        
        # Отправляем запрос
        response = requests.post(
            f"{base_url}{endpoint}",
            headers={
                "X-API-Key": api_key,
                "Content-Type": "application/json"
            },
            json=data,
            timeout=30
        )
        
        # Проверяем статус
        if response.status_code != 200:
            print(f"❌ Код: {response.status_code}")
            print(f"   Ошибка: {response.text[:100]}")
            return False
        
        # Сохраняем изображение
        output_file = output_dir / f"{service_name}.png"
        with open(output_file, "wb") as f:
            f.write(response.content)
        
        print(f"✅ → {output_file}")
        return True
        
    except requests.exceptions.Timeout:
        print(f"❌ Таймаут (>30 сек)")
        return False
    except requests.exceptions.ConnectionError:
        print(f"❌ Не удалось подключиться к API")
        return False
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return False


def test_api_status(base_url: str, api_key: str):
    """Проверить статус API"""
    try:
        print("🔍 Проверка API статуса...", end=" ")
        response = requests.get(
            f"{base_url}/api/status",
            headers={"X-API-Key": api_key},
            timeout=5
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ API активен")
            print(f"   Ключ: {data.get('key_name', 'Unknown')}")
            return True
        else:
            print(f"❌ Код: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Тест API для всех сервисов QRGen",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры:
  python test_api.py my_api_key_123
  python test_api.py my_api_key_123 --host 192.168.1.100
  python test_api.py my_api_key_123 --host localhost --port 8000
        """
    )
    
    parser.add_argument("api_key", help="Ваш API ключ")
    parser.add_argument("--host", default="localhost", help="Хост API (по умолчанию: localhost)")
    parser.add_argument("--port", type=int, default=8000, help="Порт API (по умолчанию: 8000)")
    parser.add_argument("--output", default="test_output", help="Папка для сохранения (по умолчанию: test_output)")
    
    args = parser.parse_args()
    
    # Формируем base URL
    base_url = f"http://{args.host}:{args.port}"
    
    # Создаем папку для результатов
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = Path(args.output) / timestamp
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print("="*70)
    print("🧪 API ТЕСТИРОВАНИЕ")
    print("="*70)
    print(f"🌐 URL: {base_url}")
    print(f"🔑 API Key: {args.api_key[:10]}...")
    print(f"📁 Папка: {output_dir}")
    print("="*70)
    print()
    
    # Проверяем статус API
    if not test_api_status(base_url, args.api_key):
        print("\n❌ API недоступен или API ключ неверный")
        print("\nПроверь:")
        print(f"  1. API запущен: curl {base_url}/api/status")
        print(f"  2. API ключ правильный")
        print(f"  3. Хост и порт правильные: {args.host}:{args.port}")
        sys.exit(1)
    
    print()
    
    # Тестируем все сервисы
    results = {}
    
    for service_name, config in TEST_DATA.items():
        results[service_name] = test_service(
            base_url,
            args.api_key,
            service_name,
            config['endpoint'],
            config['data'],
            output_dir
        )
    
    # Итоговый отчет
    print()
    print("="*70)
    print("📊 РЕЗУЛЬТАТЫ")
    print("="*70)
    
    success = sum(results.values())
    total = len(results)
    
    for service, result in results.items():
        emoji = "✅" if result else "❌"
        print(f"{emoji} {service.upper()}")
    
    print("="*70)
    print(f"✅ Успешно: {success}/{total}")
    print(f"❌ Ошибки: {total - success}/{total}")
    
    if success == total:
        print("\n🎉 Все сервисы работают!")
        print(f"📁 Изображения сохранены в: {output_dir}")
    else:
        print(f"\n⚠️ Неудачно: {total - success} сервисов")
    
    print("="*70)
    
    # Сохраняем отчет
    report_file = output_dir / "report.json"
    with open(report_file, "w") as f:
        json.dump({
            "timestamp": timestamp,
            "base_url": base_url,
            "results": results,
            "success": success,
            "total": total
        }, f, indent=2)
    
    print(f"📄 Отчет: {report_file}")
    print()


if __name__ == "__main__":
    main()
