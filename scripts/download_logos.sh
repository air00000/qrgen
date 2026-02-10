#!/usr/bin/env bash
set -euo pipefail

# Downloads QR overlay logos into a local directory.
# Default output: app/assets/logos
# Usage:
#   ./scripts/download_logos.sh [OUT_DIR]
#
# Optional:
#   SUBITO_LOGO_URL=https://... ./scripts/download_logos.sh

OUT_DIR="${1:-app/assets/logos}"
mkdir -p "$OUT_DIR"

fetch() {
  local url="$1"
  local out="$2"
  echo "[logo] $out <= $url"
  curl -fsSL "$url" -o "$OUT_DIR/$out"
}

# Known service logos (historical URLs from the codebase)
fetch "https://i.ibb.co/v7N8Sbs/Frame-38.png" "depop.png"
fetch "https://i.ibb.co/DfXf3X7x/Frame-40.png" "markt.png"
fetch "https://i.ibb.co/mV9pQDLS/Frame-36.png" "kleinanzeigen.png"
fetch "https://i.ibb.co/pvwMgd8k/Rectangle-355.png" "wallapop.png"
fetch "https://i.ibb.co/6crPXzDJ/2dehlogo.png" "2dehands.png"

if [[ -n "${SUBITO_LOGO_URL:-}" ]]; then
  fetch "$SUBITO_LOGO_URL" "subito.png"
else
  echo "[logo] SUBITO_LOGO_URL not set; skipping subito.png (set it if you need Subito logo overlay)"
fi

echo "[logo] done -> $OUT_DIR"
