#!/bin/bash
# Markt API Test Requests
# Usage: bash test_markt.sh

API_URL="http://127.0.0.1:8080"
API_KEY="api_33015d5be8724745935e4d6cecee97d4"

# Test image (base64)
PRODUCT_B64="/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAUDBAQEAwUEBAQFBQUGBwwIBwcHBw8LCwkMEQ8SEhEPERETFhwXExQaFRERGCEYGh0dHx8fExciJCIeJBweHx7/2wBDAQUFBQcGBw4ICA4eFBEUHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh7/wAARCAGQAZADASIAAhEBAxEB/8QAHwAAAQUBAQEBAQEAAAAAAAAAAAECAwQFBgcICQoL/8QAtRAAAgEDAwIEAwUFBAQAAAF9AQIDAAQRBRIhMUEGE1FhByJxFDKBkaEII0KxwRVS0fAkM2JyggkKFhcYGRolJicoKSo0NTY3ODk6Q0RFRkdISUpTVFVWV1hZWmNkZWZnaGlqc3R1dnd4eXqDhIWGh4iJipKTlJWWl5iZmqKjpKWmp6ipqrKztLW2t7i5usLDxMXGx8jJytLT1NXW19jZ2uHi4+Tl5ufo6erx8vP09fb3+Pn6/8QAHwEAAwEBAQEBAQEBAQAAAAAAAAECAwQFBgcICQoL/8QAtREAAgECBAQDBAcFBAQAAQJ3AAECAxEEBSExBhJBUQdhcRMiMoEIFEKRobHBCSMzUvAVYnLRChYkNOEl8RcYGRomJygpKjU2Nzg5OkNERUZHSElKU1RVVldYWVpjZGVmZ2hpanN0dXZ3eHl6goOEhYaHiImKkpOUlZaXmJmaoqOkpaanqKmqsrO0tba3uLm6wsPExcbHyMnK0tPU1dbX2Nna4uPk5ebn6Onq8vP09fb3+Pn6/9oADAMBAAIRAxEAPwB9FFFfqB+ThRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFAH//Z"

echo "=============================================="
echo "🛒 Markt API Test Requests"
echo "=============================================="
echo "API: $API_URL"
echo ""

# UK Markt - QR
echo "📍 1. UK/Markt/QR..."
curl -s -X POST "$API_URL/generate" \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "country": "uk",
    "service": "markt",
    "method": "qr",
    "title": "iPhone 15 Pro Max",
    "price": 1299.99,
    "url": "https://example.com/item/123",
    "photo": "'"$PRODUCT_B64"'"
  }' -o uk_markt_qr.png && echo "✅ Saved: uk_markt_qr.png" || echo "❌ Error"

# UK Markt - Email Request
echo "📍 2. UK/Markt/Email Request..."
curl -s -X POST "$API_URL/generate" \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "country": "uk",
    "service": "markt",
    "method": "email_request",
    "title": "MacBook Pro 14",
    "price": 2199.00,
    "photo": "'"$PRODUCT_B64"'"
  }' -o uk_markt_email_request.png && echo "✅ Saved: uk_markt_email_request.png" || echo "❌ Error"

# UK Markt - Phone Request
echo "📍 3. UK/Markt/Phone Request..."
curl -s -X POST "$API_URL/generate" \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "country": "uk",
    "service": "markt",
    "method": "phone_request",
    "title": "Samsung TV 65\"",
    "price": 899.50,
    "photo": "'"$PRODUCT_B64"'"
  }' -o uk_markt_phone_request.png && echo "✅ Saved: uk_markt_phone_request.png" || echo "❌ Error"

# UK Markt - Email Payment
echo "📍 4. UK/Markt/Email Payment..."
curl -s -X POST "$API_URL/generate" \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "country": "uk",
    "service": "markt",
    "method": "email_payment",
    "title": "PlayStation 5",
    "price": 499.99,
    "photo": "'"$PRODUCT_B64"'"
  }' -o uk_markt_email_payment.png && echo "✅ Saved: uk_markt_email_payment.png" || echo "❌ Error"

# UK Markt - SMS Payment
echo "📍 5. UK/Markt/SMS Payment..."
curl -s -X POST "$API_URL/generate" \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "country": "uk",
    "service": "markt",
    "method": "sms_payment",
    "title": "Nintendo Switch OLED",
    "price": 349.00,
    "photo": "'"$PRODUCT_B64"'"
  }' -o uk_markt_sms_payment.png && echo "✅ Saved: uk_markt_sms_payment.png" || echo "❌ Error"

echo ""
echo "=============================================="
echo "🇳🇱 NL Markt Tests"
echo "=============================================="

# NL Markt - QR
echo "📍 6. NL/Markt/QR..."
curl -s -X POST "$API_URL/generate" \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "country": "nl",
    "service": "markt",
    "method": "qr",
    "title": "iPhone 15 Pro Max",
    "price": 1299.99,
    "url": "https://example.nl/item/123",
    "photo": "'"$PRODUCT_B64"'"
  }' -o nl_markt_qr.png && echo "✅ Saved: nl_markt_qr.png" || echo "❌ Error"

# NL Markt - Email Request
echo "📍 7. NL/Markt/Email Request..."
curl -s -X POST "$API_URL/generate" \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "country": "nl",
    "service": "markt",
    "method": "email_request",
    "title": "MacBook Pro 14",
    "price": 2199.00,
    "photo": "'"$PRODUCT_B64"'"
  }' -o nl_markt_email_request.png && echo "✅ Saved: nl_markt_email_request.png" || echo "❌ Error"

# NL Markt - Phone Request
echo "📍 8. NL/Markt/Phone Request..."
curl -s -X POST "$API_URL/generate" \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "country": "nl",
    "service": "markt",
    "method": "phone_request",
    "title": "Samsung TV 65\"",
    "price": 899.50,
    "photo": "'"$PRODUCT_B64"'"
  }' -o nl_markt_phone_request.png && echo "✅ Saved: nl_markt_phone_request.png" || echo "❌ Error"

# NL Markt - Email Payment
echo "📍 9. NL/Markt/Email Payment..."
curl -s -X POST "$API_URL/generate" \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "country": "nl",
    "service": "markt",
    "method": "email_payment",
    "title": "PlayStation 5",
    "price": 499.99,
    "photo": "'"$PRODUCT_B64"'"
  }' -o nl_markt_email_payment.png && echo "✅ Saved: nl_markt_email_payment.png" || echo "❌ Error"

# NL Markt - SMS Payment
echo "📍 10. NL/Markt/SMS Payment..."
curl -s -X POST "$API_URL/generate" \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "country": "nl",
    "service": "markt",
    "method": "sms_payment",
    "title": "Nintendo Switch OLED",
    "price": 349.00,
    "photo": "'"$PRODUCT_B64"'"
  }' -o nl_markt_sms_payment.png && echo "✅ Saved: nl_markt_sms_payment.png" || echo "❌ Error"

echo ""
echo "=============================================="
echo "✅ Markt Testing Complete!"
echo "=============================================="
echo "Generated files:"
ls -la *markt*.png 2>/dev/null || echo "No Markt PNG files"
