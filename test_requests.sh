#!/bin/bash
# Тестовые запросы к API QRGen
# Использование: bash test_requests.sh

API_URL="http://127.0.0.1:8080"
API_KEY="api_33015d5be8724745935e4d6cecee97d4"

# Тестовые изображения (base64)
PRODUCT_B64="/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAUDBAQEAwUEBAQFBQUGBwwIBwcHBw8LCwkMEQ8SEhEPERETFhwXExQaFRERGCEYGh0dHx8fExciJCIeJBweHx7/2wBDAQUFBQcGBw4ICA4eFBEUHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh7/wAARCAGQAZADASIAAhEBAxEB/8QAHwAAAQUBAQEBAQEAAAAAAAAAAAECAwQFBgcICQoL/8QAtRAAAgEDAwIEAwUFBAQAAAF9AQIDAAQRBRIhMUEGE1FhByJxFDKBkaEII0KxwRVS0fAkM2JyggkKFhcYGRolJicoKSo0NTY3ODk6Q0RFRkdISUpTVFVWV1hZWmNkZWZnaGlqc3R1dnd4eXqDhIWGh4iJipKTlJWWl5iZmqKjpKWmp6ipqrKztLW2t7i5usLDxMXGx8jJytLT1NXW19jZ2uHi4+Tl5ufo6erx8vP09fb3+Pn6/8QAHwEAAwEBAQEBAQEBAQAAAAAAAAECAwQFBgcICQoL/8QAtREAAgECBAQDBAcFBAQAAQJ3AAECAxEEBSExBhJBUQdhcRMiMoEIFEKRobHBCSMzUvAVYnLRChYkNOEl8RcYGRomJygpKjU2Nzg5OkNERUZHSElKU1RVVldYWVpjZGVmZ2hpanN0dXZ3eHl6goOEhYaHiImKkpOUlZaXmJmaoqOkpaanqKmqsrO0tba3uLm6wsPExcbHyMnK0tPU1dbX2Nna4uPk5ebn6Onq8vP09fb3+Pn6/9oADAMBAAIRAxEAPwB9FFFfqB+ThRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFAH//Z"
AVATAR_B64="/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAUDBAQEAwUEBAQFBQUGBwwIBwcHBw8LCwkMEQ8SEhEPERETFhwXExQaFRERGCEYGh0dHx8fExciJCIeJBweHx7/2wBDAQUFBQcGBw4ICA4eFBEUHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh7/wAARCADIAMgDASIAAhEBAxEB/8QAHwAAAQUBAQEBAQEAAAAAAAAAAAECAwQFBgcICQoL/8QAtRAAAgEDAwIEAwUFBAQAAAF9AQIDAAQRBRIhMUEGE1FhByJxFDKBkaEII0KxwRVS0fAkM2JyggkKFhcYGRolJicoKSo0NTY3ODk6Q0RFRkdISUpTVFVWV1hZWmNkZWZnaGlqc3R1dnd4eXqDhIWGh4iJipKTlJWWl5iZmqKjpKWmp6ipqrKztLW2t7i5usLDxMXGx8jJytLT1NXW19jZ2uHi4+Tl5ufo6erx8vP09fb3+Pn6/8QAHwEAAwEBAQEBAQEBAQAAAAAAAAECAwQFBgcICQoL/8QAtREAAgECBAQDBAcFBAQAAQJ3AAECAxEEBSExBhJBUQdhcRMiMoEIFEKRobHBCSMzUvAVYnLRChYkNOEl8RcYGRomJygpKjU2Nzg5OkNERUZHSElKU1RVVldYWVpjZGVmZ2hpanN0dXZ3eHl6goOEhYaHiImKkpOUlZaXmJmaoqOkpaanqKmqsrO0tba3uLm6wsPExcbHyMnK0tPU1dbX2Nna4uPk5ebn6Onq8vP09fb3+Pn6/9oADAMBAAIRAxEAPwDdooorwT8MCiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKAP//Z"

echo "=============================================="
echo "🧪 QRGen API Test Requests"
echo "=============================================="
echo "API: $API_URL"
echo ""

# 0. Проверка статуса
echo "📍 0. Проверка статуса API..."
curl -s -X GET "$API_URL/api/status" \
  -H "X-API-Key: $API_KEY" | python3 -m json.tool
echo ""

# 1. GET /get-geo
echo "📍 1. GET /get-geo - список стран и сервисов..."
curl -s -X GET "$API_URL/get-geo" \
  -H "X-API-Key: $API_KEY" | python3 -m json.tool
echo ""

# ============================================
# ТЕСТЫ ГЕНЕРАЦИИ
# ============================================

echo "=============================================="
echo "📸 Тесты генерации изображений"
echo "=============================================="

# 2. Netherlands - Marktplaats
echo "📍 2. NL/Marktplaats/QR..."
curl -s -X POST "$API_URL/generate" \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "country": "nl",
    "service": "marktplaats",
    "method": "qr",
    "title": "iPhone 15 Pro Max 256GB",
    "price": 1199.99,
    "url": "https://marktplaats.nl/item/123456",
    "photo": "'"$PRODUCT_B64"'"
  }' -o nl_marktplaats.png && echo "✅ Сохранено: nl_marktplaats.png" || echo "❌ Ошибка"

# 3. Italy - Subito QR
echo "📍 3. IT/Subito/QR..."
curl -s -X POST "$API_URL/generate" \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "country": "it",
    "service": "subito",
    "method": "qr",
    "title": "MacBook Pro M3 2024",
    "price": 2499.00,
    "url": "https://subito.it/item/789",
    "photo": "'"$PRODUCT_B64"'",
    "name": "Marco Rossi",
    "address": "Milano, Italia"
  }' -o it_subito_qr.png && echo "✅ Сохранено: it_subito_qr.png" || echo "❌ Ошибка"

# 4. Italy - Subito Email Request
echo "📍 4. IT/Subito/Email Request..."
curl -s -X POST "$API_URL/generate" \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "country": "it",
    "service": "subito",
    "method": "email_request",
    "title": "PlayStation 5 Slim",
    "price": 449.00,
    "photo": "'"$PRODUCT_B64"'",
    "name": "Giuseppe Verdi",
    "address": "Roma, Italia"
  }' -o it_subito_email_request.png && echo "✅ Сохранено: it_subito_email_request.png" || echo "❌ Ошибка"

# 5. Italy - Conto
echo "📍 5. IT/Conto/Payment..."
curl -s -X POST "$API_URL/generate" \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "country": "it",
    "service": "conto",
    "method": "payment",
    "title": "Samsung Galaxy S24 Ultra",
    "price": 1299.00
  }' -o it_conto.png && echo "✅ Сохранено: it_conto.png" || echo "❌ Ошибка"

# 6. Germany - Kleinanzeigen
echo "📍 6. DE/Kleinanzeigen/QR..."
curl -s -X POST "$API_URL/generate" \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "country": "de",
    "service": "kleinanzeigen",
    "method": "qr",
    "title": "BMW E46 320i Coupe",
    "price": 8500.00,
    "url": "https://kleinanzeigen.de/auto/123",
    "photo": "'"$PRODUCT_B64"'"
  }' -o de_kleinanzeigen.png && echo "✅ Сохранено: de_kleinanzeigen.png" || echo "❌ Ошибка"

# 7. Spain - Wallapop Email Request
echo "📍 7. ES/Wallapop/Email Request..."
curl -s -X POST "$API_URL/generate" \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "country": "es",
    "service": "wallapop",
    "method": "email_request",
    "title": "Nintendo Switch OLED",
    "price": 289.00,
    "photo": "'"$PRODUCT_B64"'",
    "seller_name": "Carlos García",
    "seller_photo": "'"$AVATAR_B64"'"
  }' -o es_wallapop_email.png && echo "✅ Сохранено: es_wallapop_email.png" || echo "❌ Ошибка"

# 8. Spain - Wallapop QR
echo "📍 8. ES/Wallapop/QR..."
curl -s -X POST "$API_URL/generate" \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "country": "es",
    "service": "wallapop",
    "method": "qr",
    "title": "Bicicleta Montaña Trek",
    "price": 650.00,
    "url": "https://wallapop.com/item/456",
    "photo": "'"$PRODUCT_B64"'",
    "seller_name": "María López",
    "seller_photo": "'"$AVATAR_B64"'"
  }' -o es_wallapop_qr.png && echo "✅ Сохранено: es_wallapop_qr.png" || echo "❌ Ошибка"

# 9. UK - Wallapop
echo "📍 9. UK/Wallapop/Email Request..."
curl -s -X POST "$API_URL/generate" \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "country": "uk",
    "service": "wallapop",
    "method": "email_request",
    "title": "Dyson V15 Detect",
    "price": 549.00,
    "photo": "'"$PRODUCT_B64"'",
    "seller_name": "John Smith",
    "seller_photo": "'"$AVATAR_B64"'"
  }' -o uk_wallapop.png && echo "✅ Сохранено: uk_wallapop.png" || echo "❌ Ошибка"

# 10. Belgium - 2ememain
echo "📍 10. BE/2ememain/QR..."
curl -s -X POST "$API_URL/generate" \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "country": "be",
    "service": "2ememain",
    "method": "qr",
    "title": "Table IKEA LACK",
    "price": 25.00,
    "url": "https://2ememain.be/item/999",
    "photo": "'"$PRODUCT_B64"'"
  }' -o be_2ememain.png && echo "✅ Сохранено: be_2ememain.png" || echo "❌ Ошибка"

# 11. Australia - Depop QR
echo "📍 11. AU/Depop/QR..."
curl -s -X POST "$API_URL/generate" \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "country": "au",
    "service": "depop",
    "method": "qr",
    "title": "Vintage Levi 501 Jeans",
    "price": 75.00,
    "url": "https://depop.com/item/vintage123",
    "photo": "'"$PRODUCT_B64"'",
    "seller_name": "vintage_sydney",
    "seller_photo": "'"$AVATAR_B64"'"
  }' -o au_depop_qr.png && echo "✅ Сохранено: au_depop_qr.png" || echo "❌ Ошибка"

# 12. Australia - Depop Email Request
echo "📍 12. AU/Depop/Email Request..."
curl -s -X POST "$API_URL/generate" \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "country": "au",
    "service": "depop",
    "method": "email_request",
    "title": "Y2K Butterfly Top",
    "price": 45.00,
    "photo": "'"$PRODUCT_B64"'"
  }' -o au_depop_email.png && echo "✅ Сохранено: au_depop_email.png" || echo "❌ Ошибка"

echo ""
echo "📱 IT Wallapop Email Payment..."
curl -X POST "$API_URL" \
  -H "x-api-key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "country": "it",
    "service": "wallapop",
    "method": "email_payment",
    "title": "iPhone 15 Pro Max",
    "price": 1200.00,
    "photo": "'"$PRODUCT_B64"'",
    "seller_name": "Mario Rossi",
    "seller_photo": "'"$SELLER_B64"'"
  }' -o it_wallapop_email_payment.png && echo "✅ Сохранено: it_wallapop_email_payment.png" || echo "❌ Ошибка"

echo ""
echo "📱 IT Wallapop SMS Payment..."
curl -X POST "$API_URL" \
  -H "x-api-key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "country": "it",
    "service": "wallapop",
    "method": "sms_payment",
    "title": "MacBook Pro 16 2024",
    "price": 2500.00,
    "photo": "'"$PRODUCT_B64"'",
    "seller_name": "Marco",
    "seller_photo": "'"$SELLER_B64"'"
  }' -o it_wallapop_sms_payment.png && echo "✅ Сохранено: it_wallapop_sms_payment.png" || echo "❌ Ошибка"

echo ""
echo "📱 IT Wallapop QR..."
curl -X POST "$API_URL" \
  -H "x-api-key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "country": "it",
    "service": "wallapop",
    "method": "qr",
    "title": "Samsung Galaxy S24",
    "price": 900.00,
    "url": "https://example.com/item",
    "photo": "'"$PRODUCT_B64"'",
    "seller_name": "Giovanni",
    "seller_photo": "'"$SELLER_B64"'"
  }' -o it_wallapop_qr.png && echo "✅ Сохранено: it_wallapop_qr.png" || echo "❌ Ошибка"

echo ""
echo "=============================================="
echo "✅ Тестирование завершено!"
echo "=============================================="
echo "Сгенерированные файлы:"
ls -la *.png 2>/dev/null || echo "Нет PNG файлов"
