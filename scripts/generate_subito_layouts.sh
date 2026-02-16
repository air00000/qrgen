#!/usr/bin/env bash
set -euo pipefail

# Generate all Subito layouts for visual QA.
#
# Usage:
#   API_KEY=api_xxx ./scripts/generate_subito_layouts.sh
# Optional:
#   API_URL=http://127.0.0.1:8080
#   OUT_DIR=out/subito_check

API_URL="${API_URL:-http://127.0.0.1:8080}"
API_KEY="${API_KEY:-}"
OUT_DIR="${OUT_DIR:-out/subito_check_$(date +%Y%m%d_%H%M%S)}"

if [[ -z "$API_KEY" ]]; then
  echo "❌ API_KEY is required"
  echo "Example: API_KEY=api_xxx ./scripts/generate_subito_layouts.sh"
  exit 1
fi

mkdir -p "$OUT_DIR"

# Tiny valid jpeg base64 (enough for API field validation)
PHOTO_B64="/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAUDBAQEAwUEBAQFBQUGBwwIBwcHBw8LCwkMEQ8SEhEPERETFhwXExQaFRERGCEYGh0dHx8fExciJCIeJBweHx7/2wBDAQUFBQcGBw4ICA4eFBEUHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh7/wAARCABAAEADASIAAhEBAxEB/8QAHwAAAQUBAQEBAQEAAAAAAAAAAAECAwQFBgcICQoL/8QAtRAAAgEDAwIEAwUFBAQAAAF9AQIDAAQRBRIhMUEGE1FhByJxFDKBkaEII0KxwRVS0fAkM2JyggkKFhcYGRolJicoKSo0NTY3ODk6Q0RFRkdISUpTVFVWV1hZWmNkZWZnaGlqc3R1dnd4eXqDhIWGh4iJipKTlJWWl5iZmqKjpKWmp6ipqrKztLW2t7i5usLDxMXGx8jJytLT1NXW19jZ2uHi4+Tl5ufo6erx8vP09fb3+Pn6/8QAHwEAAwEBAQEBAQEBAQAAAAAAAAECAwQFBgcICQoL/8QAtREAAgECBAQDBAcFBAQAAQJ3AAECAxEEBSExBhJBUQdhcRMiMoEIFEKRobHBCSMzUvAVYnLRChYkNOEl8RcYGRomJygpKjU2Nzg5OkNERUZHSElKU1RVVldYWVpjZGVmZ2hpanN0dXZ3eHl6goOEhYaHiImKkpOUlZaXmJmaoqOkpaanqKmqsrO0tba3uLm6wsPExcbHyMnK0tPU1dbX2Nna4uPk5ebn6Onq8vP09fb3+Pn6/9oADAMBAAIRAxEAPwD9U6KKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigD/9k="

check_status() {
  echo "🔎 Checking backend status..."
  curl -fsS -H "X-API-Key: $API_KEY" "$API_URL/api/status" >/dev/null
  echo "✅ Backend is reachable: $API_URL"
}

request_json() {
  local method="$1"
  local price="$2"
  cat <<JSON
{
  "country": "it",
  "service": "subito",
  "method": "$method",
  "title": "iPhone 15 Pro Max 256GB",
  "price": $price,
  "url": "https://subito.it/item/123456789",
  "photo": "$PHOTO_B64",
  "name": "Marco Rossi",
  "address": "Milano, Italia"
}
JSON
}

gen_one() {
  local method="$1"
  local price="$2"
  local outfile="$3"

  local payload
  payload="$(request_json "$method" "$price")"

  local code
  code=$(curl -sS -o "$outfile" -w "%{http_code}" \
    -X POST "$API_URL/generate" \
    -H "X-API-Key: $API_KEY" \
    -H "Content-Type: application/json" \
    -d "$payload")

  if [[ "$code" != "200" ]]; then
    echo "❌ $method (price=$price) failed: HTTP $code"
    rm -f "$outfile"
    return 1
  fi

  echo "✅ $(basename "$outfile")"
}

main() {
  check_status

  echo "📁 Output dir: $OUT_DIR"

  # 1) Core set: all 5 Subito layouts
  gen_one "qr"            "450.00" "$OUT_DIR/subito_qr.png"
  gen_one "email_request" "450.00" "$OUT_DIR/subito_email_request.png"
  gen_one "sms_request"   "450.00" "$OUT_DIR/subito_sms_request.png"
  gen_one "email_confirm" "450.00" "$OUT_DIR/subito_email_confirm.png"
  gen_one "sms_confirm"   "450.00" "$OUT_DIR/subito_sms_confirm.png"

  # 2) Price format checks (.00 vs .45)
  gen_one "email_confirm" "123.00" "$OUT_DIR/subito_email_confirm_price_123_00.png"
  gen_one "email_confirm" "123.45" "$OUT_DIR/subito_email_confirm_price_123_45.png"

  echo
  echo "🎉 Done. Generated files:"
  ls -1 "$OUT_DIR"/*.png
}

main "$@"
