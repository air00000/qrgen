#!/bin/bash
# ============================================
# FULL API TEST - All Services & Methods
# ============================================
# Usage: bash test_all_services.sh

API_URL="http://127.0.0.1:8080"
API_KEY="api_33015d5be8724745935e4d6cecee97d4"

# Test image (minimal valid base64 JPEG)
PHOTO_B64="/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAUDBAQEAwUEBAQFBQUGBwwIBwcHBw8LCwkMEQ8SEhEPERETFhwXExQaFRERGCEYGh0dHx8fExciJCIeJBweHx7/2wBDAQUFBQcGBw4ICA4eFBEUHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh7/wAARCABAAEADASIAAhEBAxEB/8QAHwAAAQUBAQEBAQEAAAAAAAAAAAECAwQFBgcICQoL/8QAtRAAAgEDAwIEAwUFBAQAAAF9AQIDAAQRBRIhMUEGE1FhByJxFDKBkaEII0KxwRVS0fAkM2JyggkKFhcYGRolJicoKSo0NTY3ODk6Q0RFRkdISUpTVFVWV1hZWmNkZWZnaGlqc3R1dnd4eXqDhIWGh4iJipKTlJWWl5iZmqKjpKWmp6ipqrKztLW2t7i5usLDxMXGx8jJytLT1NXW19jZ2uHi4+Tl5ufo6erx8vP09fb3+Pn6/8QAHwEAAwEBAQEBAQEBAQAAAAAAAAECAwQFBgcICQoL/8QAtREAAgECBAQDBAcFBAQAAQJ3AAECAxEEBSExBhJBUQdhcRMiMoEIFEKRobHBCSMzUvAVYnLRChYkNOEl8RcYGRomJygpKjU2Nzg5OkNERUZHSElKU1RVVldYWVpjZGVmZ2hpanN0dXZ3eHl6goOEhYaHiImKkpOUlZaXmJmaoqOkpaanqKmqsrO0tba3uLm6wsPExcbHyMnK0tPU1dbX2Nna4uPk5ebn6Onq8vP09fb3+Pn6/9oADAMBAAIRAxEAPwD9U6KKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigD/9k="

# Output directory
OUTPUT_DIR="test_output_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$OUTPUT_DIR"

# Counters
SUCCESS=0
FAILED=0
TOTAL=0

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo -e "${CYAN}============================================${NC}"
echo -e "${CYAN}   FULL API TEST - All Services${NC}"
echo -e "${CYAN}============================================${NC}"
echo "API: $API_URL"
echo "Output: $OUTPUT_DIR"
echo ""

# Function to test generation
test_generate() {
    local name="$1"
    local filename="$2"
    local json="$3"
    
    TOTAL=$((TOTAL + 1))
    echo -n -e "${YELLOW}[$TOTAL] $name...${NC} "
    
    response=$(curl -s -w "\n%{http_code}" -X POST "$API_URL/generate" \
        -H "X-API-Key: $API_KEY" \
        -H "Content-Type: application/json" \
        -d "$json" \
        -o "$OUTPUT_DIR/$filename" 2>&1)
    
    http_code=$(echo "$response" | tail -n1)
    
    if [ "$http_code" = "200" ] && [ -f "$OUTPUT_DIR/$filename" ]; then
        size=$(du -h "$OUTPUT_DIR/$filename" | cut -f1)
        echo -e "${GREEN}OK${NC} ($size)"
        SUCCESS=$((SUCCESS + 1))
    else
        echo -e "${RED}FAILED${NC} (HTTP $http_code)"
        FAILED=$((FAILED + 1))
        # Save error
        echo "[$name] HTTP $http_code" >> "$OUTPUT_DIR/errors.log"
    fi
}

# Check API status first
echo -e "${YELLOW}Checking API status...${NC}"
status=$(curl -s -X GET "$API_URL/api/status" -H "X-API-Key: $API_KEY" 2>&1)
if echo "$status" | grep -q "active"; then
    echo -e "${GREEN}API is running!${NC}"
else
    echo -e "${RED}API is not available! Start it with: python -m app.main${NC}"
    exit 1
fi
echo ""

# ============================================
# MARKT (UK + NL) - 10 tests
# ============================================
echo -e "${CYAN}=== MARKT (UK) ===${NC}"

test_generate "uk/markt/qr" "uk_markt_qr.png" '{
    "country": "uk", "service": "markt", "method": "qr",
    "title": "iPhone 15 Pro Max", "price": 1299.99,
    "url": "https://example.co.uk/item/123",
    "photo": "'"$PHOTO_B64"'"
}'

test_generate "uk/markt/email_request" "uk_markt_email_request.png" '{
    "country": "uk", "service": "markt", "method": "email_request",
    "title": "MacBook Pro 14", "price": 2199.00,
    "photo": "'"$PHOTO_B64"'"
}'

test_generate "uk/markt/phone_request" "uk_markt_phone_request.png" '{
    "country": "uk", "service": "markt", "method": "phone_request",
    "title": "Samsung TV 65 inch", "price": 899.50,
    "photo": "'"$PHOTO_B64"'"
}'

test_generate "uk/markt/email_payment" "uk_markt_email_payment.png" '{
    "country": "uk", "service": "markt", "method": "email_payment",
    "title": "PlayStation 5", "price": 499.99,
    "photo": "'"$PHOTO_B64"'"
}'

test_generate "uk/markt/sms_payment" "uk_markt_sms_payment.png" '{
    "country": "uk", "service": "markt", "method": "sms_payment",
    "title": "Nintendo Switch OLED", "price": 349.00,
    "photo": "'"$PHOTO_B64"'"
}'

echo -e "${CYAN}=== MARKT (NL) ===${NC}"

test_generate "nl/markt/qr" "nl_markt_qr.png" '{
    "country": "nl", "service": "markt", "method": "qr",
    "title": "iPhone 15 Pro Max", "price": 1299.99,
    "url": "https://example.nl/item/123",
    "photo": "'"$PHOTO_B64"'"
}'

test_generate "nl/markt/email_request" "nl_markt_email_request.png" '{
    "country": "nl", "service": "markt", "method": "email_request",
    "title": "MacBook Pro 14", "price": 2199.00,
    "photo": "'"$PHOTO_B64"'"
}'

test_generate "nl/markt/phone_request" "nl_markt_phone_request.png" '{
    "country": "nl", "service": "markt", "method": "phone_request",
    "title": "Samsung TV 65 inch", "price": 899.50,
    "photo": "'"$PHOTO_B64"'"
}'

test_generate "nl/markt/email_payment" "nl_markt_email_payment.png" '{
    "country": "nl", "service": "markt", "method": "email_payment",
    "title": "PlayStation 5", "price": 499.99,
    "photo": "'"$PHOTO_B64"'"
}'

test_generate "nl/markt/sms_payment" "nl_markt_sms_payment.png" '{
    "country": "nl", "service": "markt", "method": "sms_payment",
    "title": "Nintendo Switch OLED", "price": 349.00,
    "photo": "'"$PHOTO_B64"'"
}'

# ============================================
# SUBITO (IT) - 5 tests
# ============================================
echo -e "${CYAN}=== SUBITO (IT) ===${NC}"

test_generate "it/subito/qr" "it_subito_qr.png" '{
    "country": "it", "service": "subito", "method": "qr",
    "title": "iPhone 15 Pro", "price": 1199.00,
    "url": "https://subito.it/item/123",
    "photo": "'"$PHOTO_B64"'",
    "name": "Marco Rossi", "address": "Milano, Italia"
}'

test_generate "it/subito/email_request" "it_subito_email_request.png" '{
    "country": "it", "service": "subito", "method": "email_request",
    "title": "MacBook Air M2", "price": 999.00,
    "photo": "'"$PHOTO_B64"'",
    "name": "Giuseppe Verdi", "address": "Roma, Italia"
}'

test_generate "it/subito/email_confirm" "it_subito_email_confirm.png" '{
    "country": "it", "service": "subito", "method": "email_confirm",
    "title": "Samsung Galaxy S24", "price": 899.00,
    "photo": "'"$PHOTO_B64"'",
    "name": "Luigi Bianchi", "address": "Napoli, Italia"
}'

test_generate "it/subito/sms_request" "it_subito_sms_request.png" '{
    "country": "it", "service": "subito", "method": "sms_request",
    "title": "PlayStation 5", "price": 499.00,
    "photo": "'"$PHOTO_B64"'",
    "name": "Antonio Ferrari", "address": "Torino, Italia"
}'

test_generate "it/subito/sms_confirm" "it_subito_sms_confirm.png" '{
    "country": "it", "service": "subito", "method": "sms_confirm",
    "title": "Xbox Series X", "price": 449.00,
    "photo": "'"$PHOTO_B64"'",
    "name": "Paolo Conte", "address": "Firenze, Italia"
}'

# ============================================
# CONTO (IT) - 1 test
# ============================================
echo -e "${CYAN}=== CONTO (IT) ===${NC}"

test_generate "it/conto/payment" "it_conto_payment.png" '{
    "country": "it", "service": "conto", "method": "payment",
    "title": "MacBook Pro 16", "price": 2499.00
}'

# ============================================
# WALLAPOP (ES) - 5 tests
# ============================================
echo -e "${CYAN}=== WALLAPOP (ES) ===${NC}"

test_generate "es/wallapop/email_request" "es_wallapop_email_request.png" '{
    "country": "es", "service": "wallapop", "method": "email_request",
    "title": "iPhone 15", "price": 999.00,
    "photo": "'"$PHOTO_B64"'",
    "seller_name": "Carlos Garcia",
    "seller_photo": "'"$PHOTO_B64"'"
}'

test_generate "es/wallapop/sms_request" "es_wallapop_sms_request.png" '{
    "country": "es", "service": "wallapop", "method": "sms_request",
    "title": "Samsung TV", "price": 599.00,
    "photo": "'"$PHOTO_B64"'",
    "seller_name": "Maria Lopez",
    "seller_photo": "'"$PHOTO_B64"'"
}'

test_generate "es/wallapop/email_payment" "es_wallapop_email_payment.png" '{
    "country": "es", "service": "wallapop", "method": "email_payment",
    "title": "PlayStation 5", "price": 449.00,
    "photo": "'"$PHOTO_B64"'",
    "seller_name": "Juan Martinez",
    "seller_photo": "'"$PHOTO_B64"'"
}'

test_generate "es/wallapop/sms_payment" "es_wallapop_sms_payment.png" '{
    "country": "es", "service": "wallapop", "method": "sms_payment",
    "title": "Nintendo Switch", "price": 299.00,
    "photo": "'"$PHOTO_B64"'",
    "seller_name": "Ana Rodriguez",
    "seller_photo": "'"$PHOTO_B64"'"
}'

test_generate "es/wallapop/qr" "es_wallapop_qr.png" '{
    "country": "es", "service": "wallapop", "method": "qr",
    "title": "MacBook Air", "price": 899.00,
    "url": "https://wallapop.com/item/123",
    "photo": "'"$PHOTO_B64"'",
    "seller_name": "Pedro Sanchez",
    "seller_photo": "'"$PHOTO_B64"'"
}'

# ============================================
# WALLAPOP (UK) - 5 tests
# ============================================
echo -e "${CYAN}=== WALLAPOP (UK) ===${NC}"

test_generate "uk/wallapop/email_request" "uk_wallapop_email_request.png" '{
    "country": "uk", "service": "wallapop", "method": "email_request",
    "title": "iPhone 15", "price": 999.00,
    "photo": "'"$PHOTO_B64"'",
    "seller_name": "John Smith",
    "seller_photo": "'"$PHOTO_B64"'"
}'

test_generate "uk/wallapop/sms_request" "uk_wallapop_sms_request.png" '{
    "country": "uk", "service": "wallapop", "method": "sms_request",
    "title": "Samsung TV", "price": 599.00,
    "photo": "'"$PHOTO_B64"'",
    "seller_name": "James Wilson",
    "seller_photo": "'"$PHOTO_B64"'"
}'

test_generate "uk/wallapop/email_payment" "uk_wallapop_email_payment.png" '{
    "country": "uk", "service": "wallapop", "method": "email_payment",
    "title": "PlayStation 5", "price": 449.00,
    "photo": "'"$PHOTO_B64"'",
    "seller_name": "David Brown",
    "seller_photo": "'"$PHOTO_B64"'"
}'

test_generate "uk/wallapop/sms_payment" "uk_wallapop_sms_payment.png" '{
    "country": "uk", "service": "wallapop", "method": "sms_payment",
    "title": "Nintendo Switch", "price": 299.00,
    "photo": "'"$PHOTO_B64"'",
    "seller_name": "Emma Taylor",
    "seller_photo": "'"$PHOTO_B64"'"
}'

test_generate "uk/wallapop/qr" "uk_wallapop_qr.png" '{
    "country": "uk", "service": "wallapop", "method": "qr",
    "title": "MacBook Air", "price": 899.00,
    "url": "https://wallapop.com/item/456",
    "photo": "'"$PHOTO_B64"'",
    "seller_name": "Oliver Johnson",
    "seller_photo": "'"$PHOTO_B64"'"
}'

# ============================================
# WALLAPOP (IT) - 5 tests
# ============================================
echo -e "${CYAN}=== WALLAPOP (IT) ===${NC}"

test_generate "it/wallapop/email_request" "it_wallapop_email_request.png" '{
    "country": "it", "service": "wallapop", "method": "email_request",
    "title": "iPhone 15", "price": 999.00,
    "photo": "'"$PHOTO_B64"'",
    "seller_name": "Marco Rossi",
    "seller_photo": "'"$PHOTO_B64"'"
}'

test_generate "it/wallapop/sms_request" "it_wallapop_sms_request.png" '{
    "country": "it", "service": "wallapop", "method": "sms_request",
    "title": "Samsung TV", "price": 599.00,
    "photo": "'"$PHOTO_B64"'",
    "seller_name": "Luigi Bianchi",
    "seller_photo": "'"$PHOTO_B64"'"
}'

test_generate "it/wallapop/email_payment" "it_wallapop_email_payment.png" '{
    "country": "it", "service": "wallapop", "method": "email_payment",
    "title": "PlayStation 5", "price": 449.00,
    "photo": "'"$PHOTO_B64"'",
    "seller_name": "Giuseppe Verdi",
    "seller_photo": "'"$PHOTO_B64"'"
}'

test_generate "it/wallapop/sms_payment" "it_wallapop_sms_payment.png" '{
    "country": "it", "service": "wallapop", "method": "sms_payment",
    "title": "Nintendo Switch", "price": 299.00,
    "photo": "'"$PHOTO_B64"'",
    "seller_name": "Antonio Ferrari",
    "seller_photo": "'"$PHOTO_B64"'"
}'

test_generate "it/wallapop/qr" "it_wallapop_qr.png" '{
    "country": "it", "service": "wallapop", "method": "qr",
    "title": "MacBook Air", "price": 899.00,
    "url": "https://wallapop.com/item/789",
    "photo": "'"$PHOTO_B64"'",
    "seller_name": "Paolo Conte",
    "seller_photo": "'"$PHOTO_B64"'"
}'

# ============================================
# WALLAPOP (FR) - 5 tests
# ============================================
echo -e "${CYAN}=== WALLAPOP (FR) ===${NC}"

test_generate "fr/wallapop/email_request" "fr_wallapop_email_request.png" '{
    "country": "fr", "service": "wallapop", "method": "email_request",
    "title": "iPhone 15", "price": 999.00,
    "photo": "'"$PHOTO_B64"'",
    "seller_name": "Pierre Dupont",
    "seller_photo": "'"$PHOTO_B64"'"
}'

test_generate "fr/wallapop/sms_request" "fr_wallapop_sms_request.png" '{
    "country": "fr", "service": "wallapop", "method": "sms_request",
    "title": "Samsung TV", "price": 599.00,
    "photo": "'"$PHOTO_B64"'",
    "seller_name": "Jean Martin",
    "seller_photo": "'"$PHOTO_B64"'"
}'

test_generate "fr/wallapop/email_payment" "fr_wallapop_email_payment.png" '{
    "country": "fr", "service": "wallapop", "method": "email_payment",
    "title": "PlayStation 5", "price": 449.00,
    "photo": "'"$PHOTO_B64"'",
    "seller_name": "Michel Bernard",
    "seller_photo": "'"$PHOTO_B64"'"
}'

test_generate "fr/wallapop/sms_payment" "fr_wallapop_sms_payment.png" '{
    "country": "fr", "service": "wallapop", "method": "sms_payment",
    "title": "Nintendo Switch", "price": 299.00,
    "photo": "'"$PHOTO_B64"'",
    "seller_name": "Marie Dubois",
    "seller_photo": "'"$PHOTO_B64"'"
}'

test_generate "fr/wallapop/qr" "fr_wallapop_qr.png" '{
    "country": "fr", "service": "wallapop", "method": "qr",
    "title": "MacBook Air", "price": 899.00,
    "url": "https://wallapop.com/item/fr123",
    "photo": "'"$PHOTO_B64"'",
    "seller_name": "Francois Moreau",
    "seller_photo": "'"$PHOTO_B64"'"
}'

# ============================================
# WALLAPOP (PR - Portugal) - 5 tests
# ============================================
echo -e "${CYAN}=== WALLAPOP (PT) ===${NC}"

test_generate "pr/wallapop/email_request" "pr_wallapop_email_request.png" '{
    "country": "pr", "service": "wallapop", "method": "email_request",
    "title": "iPhone 15", "price": 999.00,
    "photo": "'"$PHOTO_B64"'",
    "seller_name": "Joao Silva",
    "seller_photo": "'"$PHOTO_B64"'"
}'

test_generate "pr/wallapop/sms_request" "pr_wallapop_sms_request.png" '{
    "country": "pr", "service": "wallapop", "method": "sms_request",
    "title": "Samsung TV", "price": 599.00,
    "photo": "'"$PHOTO_B64"'",
    "seller_name": "Manuel Santos",
    "seller_photo": "'"$PHOTO_B64"'"
}'

test_generate "pr/wallapop/email_payment" "pr_wallapop_email_payment.png" '{
    "country": "pr", "service": "wallapop", "method": "email_payment",
    "title": "PlayStation 5", "price": 449.00,
    "photo": "'"$PHOTO_B64"'",
    "seller_name": "Antonio Costa",
    "seller_photo": "'"$PHOTO_B64"'"
}'

test_generate "pr/wallapop/sms_payment" "pr_wallapop_sms_payment.png" '{
    "country": "pr", "service": "wallapop", "method": "sms_payment",
    "title": "Nintendo Switch", "price": 299.00,
    "photo": "'"$PHOTO_B64"'",
    "seller_name": "Maria Ferreira",
    "seller_photo": "'"$PHOTO_B64"'"
}'

test_generate "pr/wallapop/qr" "pr_wallapop_qr.png" '{
    "country": "pr", "service": "wallapop", "method": "qr",
    "title": "MacBook Air", "price": 899.00,
    "url": "https://wallapop.com/item/pt123",
    "photo": "'"$PHOTO_B64"'",
    "seller_name": "Pedro Oliveira",
    "seller_photo": "'"$PHOTO_B64"'"
}'

# ============================================
# 2DEHANDS (NL) - 1 test
# ============================================
echo -e "${CYAN}=== 2DEHANDS (NL) ===${NC}"

test_generate "nl/2dehands/qr" "nl_2dehands_qr.png" '{
    "country": "nl", "service": "2dehands", "method": "qr",
    "title": "iPhone 15 Pro", "price": 1099.00,
    "url": "https://2dehands.nl/item/123",
    "photo": "'"$PHOTO_B64"'"
}'

# ============================================
# 2EMEMAIN (BE) - 1 test
# ============================================
echo -e "${CYAN}=== 2EMEMAIN (BE) ===${NC}"

test_generate "be/2ememain/qr" "be_2ememain_qr.png" '{
    "country": "be", "service": "2ememain", "method": "qr",
    "title": "MacBook Air M2", "price": 999.00,
    "url": "https://2ememain.be/item/456",
    "photo": "'"$PHOTO_B64"'"
}'

# ============================================
# KLEINANZEIGEN (DE) - 1 test
# ============================================
echo -e "${CYAN}=== KLEINANZEIGEN (DE) ===${NC}"

test_generate "de/kleinanzeigen/qr" "de_kleinanzeigen_qr.png" '{
    "country": "de", "service": "kleinanzeigen", "method": "qr",
    "title": "Samsung Galaxy S24", "price": 799.00,
    "url": "https://kleinanzeigen.de/item/789",
    "photo": "'"$PHOTO_B64"'"
}'

# ============================================
# DEPOP (AU) - 5 tests
# ============================================
echo -e "${CYAN}=== DEPOP (AU) ===${NC}"

test_generate "au/depop/qr" "au_depop_qr.png" '{
    "country": "au", "service": "depop", "method": "qr",
    "title": "Vintage Jacket", "price": 89.00,
    "url": "https://depop.com/item/au123",
    "photo": "'"$PHOTO_B64"'",
    "seller_name": "Sarah Miller",
    "seller_photo": "'"$PHOTO_B64"'"
}'

test_generate "au/depop/email_request" "au_depop_email_request.png" '{
    "country": "au", "service": "depop", "method": "email_request",
    "title": "Designer Bag", "price": 149.00,
    "photo": "'"$PHOTO_B64"'"
}'

test_generate "au/depop/email_confirm" "au_depop_email_confirm.png" '{
    "country": "au", "service": "depop", "method": "email_confirm",
    "title": "Sneakers Nike", "price": 199.00,
    "photo": "'"$PHOTO_B64"'"
}'

test_generate "au/depop/sms_request" "au_depop_sms_request.png" '{
    "country": "au", "service": "depop", "method": "sms_request",
    "title": "Vintage Watch", "price": 299.00,
    "photo": "'"$PHOTO_B64"'"
}'

test_generate "au/depop/sms_confirm" "au_depop_sms_confirm.png" '{
    "country": "au", "service": "depop", "method": "sms_confirm",
    "title": "Leather Boots", "price": 179.00,
    "photo": "'"$PHOTO_B64"'"
}'

# ============================================
# RESULTS
# ============================================
echo ""
echo -e "${CYAN}============================================${NC}"
echo -e "${CYAN}   TEST RESULTS${NC}"
echo -e "${CYAN}============================================${NC}"
echo -e "Total tests: ${YELLOW}$TOTAL${NC}"
echo -e "Success:     ${GREEN}$SUCCESS${NC}"
echo -e "Failed:      ${RED}$FAILED${NC}"
echo ""
echo "Output directory: $OUTPUT_DIR"

if [ -f "$OUTPUT_DIR/errors.log" ]; then
    echo ""
    echo -e "${RED}Errors:${NC}"
    cat "$OUTPUT_DIR/errors.log"
fi

echo ""
if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}✅ All tests passed!${NC}"
else
    echo -e "${RED}❌ Some tests failed. Check errors above.${NC}"
fi

# List generated files
echo ""
echo "Generated files:"
ls -la "$OUTPUT_DIR"/*.png 2>/dev/null | wc -l
echo "PNG files created"
