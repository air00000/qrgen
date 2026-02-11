#!/usr/bin/env bash
set -euo pipefail

PORT="${BACKEND_PORT:-8080}"
HOST="${BACKEND_HOST:-127.0.0.1}"
BASE="http://${HOST}:${PORT}"

API_KEY="${X_API_KEY:-}"
if [[ -z "$API_KEY" ]]; then
  echo "X_API_KEY is required (must exist in app/data/api_keys.json)" >&2
  exit 2
fi

function curl_json() {
  local path="$1"
  curl -fsS "${BASE}${path}" -H "X-API-Key: ${API_KEY}"
}

function curl_png() {
  local out="$1"
  local payload="$2"
  curl -fsS "${BASE}/generate" \
    -H "X-API-Key: ${API_KEY}" \
    -H "Content-Type: application/json" \
    --data "$payload" \
    -o "$out"
}

echo "[1/4] health"
curl -fsS "${BASE}/health" | cat

echo "[2/4] api status"
curl_json "/api/status" | cat

echo "[3/4] get-geo keys"
curl_json "/get-geo" | python3 - <<'PY'
import sys, json
j=json.load(sys.stdin)
print('countries:', len(j), 'sample:', sorted(list(j.keys()))[:5])
PY

# Minimal request that should work once FIGMA creds are set.
# Note: if FIGMA_PAT is missing, backend will respond 500 with "figma: FIGMA_PAT is not set".
PAYLOAD='{"country":"uk","service":"markt","method":"email_request","title":"smoke","price":1.23}'
OUT="/tmp/qrgen_smoke.png"

echo "[4/4] generate -> ${OUT}"
set +e
ERR=$(curl -sS -w "\n%{http_code}" "${BASE}/generate" \
  -H "X-API-Key: ${API_KEY}" \
  -H "Content-Type: application/json" \
  --data "$PAYLOAD" \
  -o "$OUT")
CODE=$(echo "$ERR" | tail -n1)
set -e

if [[ "$CODE" != "200" ]]; then
  echo "generate failed HTTP $CODE" >&2
  echo "Common cause: FIGMA_PAT is not set in .env" >&2
  echo "Response body:" >&2
  cat "$OUT" >&2 || true
  exit 1
fi

python3 - <<'PY'
import sys
p='/tmp/qrgen_smoke.png'
with open(p,'rb') as f:
    sig=f.read(8)
print('png_signature_ok' if sig==b'\x89PNG\r\n\x1a\n' else 'not_png')
PY

echo "OK"
