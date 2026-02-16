#!/usr/bin/env bash
set -euo pipefail

# Generate visual QA images for ALL requested services and language/country variations:
# - subito (it)
# - wallapop (uk, es, it, fr, pr)
# - markt (uk, nl)
# - depop (au)
#
# Usage:
#   API_KEY=api_xxx ./scripts/generate_subito_layouts.sh
# Optional:
#   API_URL=http://127.0.0.1:8080
#   OUT_DIR=out/layouts_check

API_URL="${API_URL:-http://127.0.0.1:8080}"
API_KEY="${API_KEY:-}"
OUT_DIR="${OUT_DIR:-out/layouts_check_$(date +%Y%m%d_%H%M%S)}"
TG_CHAT_ID="${TG_CHAT_ID:--5237507458}"
TG_BOT_TOKEN="${TG_BOT_TOKEN:-${TELEGRAM_BOT_TOKEN:-}}"

if [[ -z "$API_KEY" ]]; then
  echo "❌ API_KEY is required"
  echo "Example: API_KEY=api_xxx ./scripts/generate_subito_layouts.sh"
  exit 1
fi

mkdir -p "$OUT_DIR"

PHOTO_B64="/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAUDBAQEAwUEBAQFBQUGBwwIBwcHBw8LCwkMEQ8SEhEPERETFhwXExQaFRERGCEYGh0dHx8fExciJCIeJBweHx7/2wBDAQUFBQcGBw4ICA4eFBEUHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh7/wAARCABAAEADASIAAhEBAxEB/8QAHwAAAQUBAQEBAQEAAAAAAAAAAAECAwQFBgcICQoL/8QAtRAAAgEDAwIEAwUFBAQAAAF9AQIDAAQRBRIhMUEGE1FhByJxFDKBkaEII0KxwRVS0fAkM2JyggkKFhcYGRolJicoKSo0NTY3ODk6Q0RFRkdISUpTVFVWV1hZWmNkZWZnaGlqc3R1dnd4eXqDhIWGh4iJipKTlJWWl5iZmqKjpKWmp6ipqrKztLW2t7i5usLDxMXGx8jJytLT1NXW19jZ2uHi4+Tl5ufo6erx8vP09fb3+Pn6/8QAHwEAAwEBAQEBAQEBAQAAAAAAAAECAwQFBgcICQoL/8QAtREAAgECBAQDBAcFBAQAAQJ3AAECAxEEBSExBhJBUQdhcRMiMoEIFEKRobHBCSMzUvAVYnLRChYkNOEl8RcYGRomJygpKjU2Nzg5OkNERUZHSElKU1RVVldYWVpjZGVmZ2hpanN0dXZ3eHl6goOEhYaHiImKkpOUlZaXmJmaoqOkpaanqKmqsrO0tba3uLm6wsPExcbHyMnK0tPU1dbX2Nna4uPk5ebn6Onq8vP09fb3+Pn6/9oADAMBAAIRAxEAPwD9U6KKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigD/9k="
SELLER_B64="$PHOTO_B64"

check_status() {
  echo "🔎 Checking backend status..."
  curl -fsS -H "X-API-Key: $API_KEY" "$API_URL/api/status" >/dev/null
  echo "✅ Backend is reachable: $API_URL"
}

send_to_telegram() {
  local file_path="$1"
  local caption="$2"

  if [[ -z "$TG_BOT_TOKEN" ]]; then
    return 0
  fi

  curl -sS -X POST "https://api.telegram.org/bot${TG_BOT_TOKEN}/sendPhoto" \
    -F "chat_id=${TG_CHAT_ID}" \
    -F "caption=${caption}" \
    -F "photo=@${file_path}" >/dev/null || true
}

post_generate() {
  local payload="$1"
  local outfile="$2"

  local code
  code=$(curl -sS -o "$outfile" -w "%{http_code}" \
    -X POST "$API_URL/generate" \
    -H "X-API-Key: $API_KEY" \
    -H "Content-Type: application/json" \
    -d "$payload")

  if [[ "$code" != "200" ]]; then
    echo "❌ FAILED: $(basename "$outfile") (HTTP $code)"
    rm -f "$outfile"
    return 1
  fi
  local filename
  filename="$(basename "$outfile")"
  echo "✅ $filename"
  send_to_telegram "$outfile" "QA: $filename"
}

gen_subito() {
  local country="it"
  for method in qr email_request sms_request email_confirm sms_confirm; do
    local url_field='"url": "https://subito.it/item/123456789",'
    [[ "$method" != "qr" ]] && url_field='"url": null,'

    payload=$(cat <<JSON
{
  "country": "$country",
  "service": "subito",
  "method": "$method",
  "title": "iPhone 15 Pro Max 256GB",
  "price": 450.00,
  $url_field
  "photo": "$PHOTO_B64",
  "name": "Marco Rossi",
  "address": "Milano, Italia"
}
JSON
)
    post_generate "$payload" "$OUT_DIR/${country}_subito_${method}.png"
  done
}

gen_wallapop() {
  for country in uk es it fr pr; do
    for method in qr email_request sms_request email_payment sms_payment; do
      local url_field='"url": "https://wallapop.com/item/123456789",'
      [[ "$method" != "qr" ]] && url_field='"url": null,'

      payload=$(cat <<JSON
{
  "country": "$country",
  "service": "wallapop",
  "method": "$method",
  "title": "MacBook Air M2",
  "price": 450.00,
  $url_field
  "photo": "$PHOTO_B64",
  "seller_name": "Mario Rossi",
  "seller_photo": "$SELLER_B64"
}
JSON
)
      post_generate "$payload" "$OUT_DIR/${country}_wallapop_${method}.png"
    done
  done
}

gen_markt() {
  for country in uk nl; do
    for method in qr email_request phone_request email_payment sms_payment; do
      local url_field='"url": "https://example.com/item/123456789",'
      [[ "$method" != "qr" ]] && url_field='"url": null,'

      payload=$(cat <<JSON
{
  "country": "$country",
  "service": "markt",
  "method": "$method",
  "title": "PlayStation 5",
  "price": 450.00,
  $url_field
  "photo": "$PHOTO_B64"
}
JSON
)
      post_generate "$payload" "$OUT_DIR/${country}_markt_${method}.png"
    done
  done
}

gen_depop() {
  local country="au"
  for method in qr email_request email_confirm sms_request sms_confirm; do
    local url_field='"url": "https://depop.com/item/123456789",'
    [[ "$method" != "qr" ]] && url_field='"url": null,'

    payload=$(cat <<JSON
{
  "country": "$country",
  "service": "depop",
  "method": "$method",
  "title": "Vintage Jacket",
  "price": 450.00,
  $url_field
  "photo": "$PHOTO_B64",
  "seller_name": "vintage_sydney",
  "seller_photo": "$SELLER_B64"
}
JSON
)
    post_generate "$payload" "$OUT_DIR/${country}_depop_${method}.png"
  done
}

main() {
  check_status
  echo "📁 Output dir: $OUT_DIR"

  if [[ -n "$TG_BOT_TOKEN" ]]; then
    curl -sS -X POST "https://api.telegram.org/bot${TG_BOT_TOKEN}/sendMessage" \
      -d "chat_id=${TG_CHAT_ID}" \
      -d "text=🚀 Запуск QA-генерации макетов. Папка: ${OUT_DIR}" >/dev/null || true
  else
    echo "ℹ️ TG_BOT_TOKEN/TELEGRAM_BOT_TOKEN не задан — отправка в Telegram отключена"
  fi

  echo "\n=== SUBITO ==="
  gen_subito

  echo "\n=== WALLAPOP ==="
  gen_wallapop

  echo "\n=== MARKT ==="
  gen_markt

  echo "\n=== DEPOP ==="
  gen_depop

  echo
  local count
  count="$(ls -1 "$OUT_DIR"/*.png | wc -l | tr -d ' ')"
  echo "🎉 Done. Generated files count: $count"
  echo "📂 $OUT_DIR"

  if [[ -n "$TG_BOT_TOKEN" ]]; then
    curl -sS -X POST "https://api.telegram.org/bot${TG_BOT_TOKEN}/sendMessage" \
      -d "chat_id=${TG_CHAT_ID}" \
      -d "text=✅ QA-генерация завершена. Файлов: ${count}. Папка: ${OUT_DIR}" >/dev/null || true
  fi
}

main "$@"
