# Полные тесты API QRGen для Windows PowerShell
# Использование: powershell -ExecutionPolicy Bypass -File .\test_requests.ps1

$API_URL = "http://localhost:8080"
$API_KEY = "api_33015d5be8724745935e4d6cecee97d4"

# Папка для результатов
$OUTPUT_DIR = "test_results_$(Get-Date -Format 'yyyyMMdd_HHmmss')"
New-Item -ItemType Directory -Path $OUTPUT_DIR -Force | Out-Null

# Лог ошибок
$ERROR_LOG = "$OUTPUT_DIR\errors.log"
"QRGen API Test Errors - $(Get-Date)" | Out-File $ERROR_LOG

# Тестовые изображения (base64)
$PRODUCT_B64 = "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAUDBAQEAwUEBAQFBQUGBwwIBwcHBw8LCwkMEQ8SEhEPERETFhwXExQaFRERGCEYGh0dHx8fExciJCIeJBweHx7/2wBDAQUFBQcGBw4ICA4eFBEUHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh7/wAARCAGQAZADASIAAhEBAxEB/8QAHwAAAQUBAQEBAQEAAAAAAAAAAAECAwQFBgcICQoL/8QAtRAAAgEDAwIEAwUFBAQAAAF9AQIDAAQRBRIhMUEGE1FhByJxFDKBkaEII0KxwRVS0fAkM2JyggkKFhcYGRolJicoKSo0NTY3ODk6Q0RFRkdISUpTVFVWV1hZWmNkZWZnaGlqc3R1dnd4eXqDhIWGh4iJipKTlJWWl5iZmqKjpKWmp6ipqrKztLW2t7i5usLDxMXGx8jJytLT1NXW19jZ2uHi4+Tl5ufo6erx8vP09fb3+Pn6/8QAHwEAAwEBAQEBAQEBAQAAAAAAAAECAwQFBgcICQoL/8QAtREAAgECBAQDBAcFBAQAAQJ3AAECAxEEBSExBhJBUQdhcRMiMoEIFEKRobHBCSMzUvAVYnLRChYkNOEl8RcYGRomJygpKjU2Nzg5OkNERUZHSElKU1RVVldYWVpjZGVmZ2hpanN0dXZ3eHl6goOEhYaHiImKkpOUlZaXmJmaoqOkpaanqKmqsrO0tba3uLm6wsPExcbHyMnK0tPU1dbX2Nna4uPk5ebn6Onq8vP09fb3+Pn6/9oADAMBAAIRAxEAPwB9FFFfqB+ThRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFAH//Z"
$AVATAR_B64 = "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAUDBAQEAwUEBAQFBQUGBwwIBwcHBw8LCwkMEQ8SEhEPERETFhwXExQaFRERGCEYGh0dHx8fExciJCIeJBweHx7/2wBDAQUFBQcGBw4ICA4eFBEUHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh7/wAARCADIAMgDASIAAhEBAxEB/8QAHwAAAQUBAQEBAQEAAAAAAAAAAAECAwQFBgcICQoL/8QAtRAAAgEDAwIEAwUFBAQAAAF9AQIDAAQRBRIhMUEGE1FhByJxFDKBkaEII0KxwRVS0fAkM2JyggkKFhcYGRolJicoKSo0NTY3ODk6Q0RFRkdISUpTVFVWV1hZWmNkZWZnaGlqc3R1dnd4eXqDhIWGh4iJipKTlJWWl5iZmqKjpKWmp6ipqrKztLW2t7i5usLDxMXGx8jJytLT1NXW19jZ2uHi4+Tl5ufo6erx8vP09fb3+Pn6/8QAHwEAAwEBAQEBAQEBAQAAAAAAAAECAwQFBgcICQoL/8QAtREAAgECBAQDBAcFBAQAAQJ3AAECAxEEBSExBhJBUQdhcRMiMoEIFEKRobHBCSMzUvAVYnLRChYkNOEl8RcYGRomJygpKjU2Nzg5OkNERUZHSElKU1RVVldYWVpjZGVmZ2hpanN0dXZ3eHl6goOEhYaHiImKkpOUlZaXmJmaoqOkpaanqKmqsrO0tba3uLm6wsPExcbHyMnK0tPU1dbX2Nna4uPk5ebn6Onq8vP09fb3+Pn6/9oADAMBAAIRAxEAPwDdooorwT8MCiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKAP//Z"

$headers = @{
    "X-API-Key" = $API_KEY
    "Content-Type" = "application/json"
}

# Счетчики
$global:successCount = 0
$global:errorCount = 0

Write-Host "==============================================" -ForegroundColor Cyan
Write-Host "QRGen API - Full Test Suite (38 tests)" -ForegroundColor Cyan
Write-Host "==============================================" -ForegroundColor Cyan
Write-Host "API: $API_URL"
Write-Host "Output: $OUTPUT_DIR"
Write-Host "Errors: $ERROR_LOG"
Write-Host ""

# Функция логирования ошибок
function Log-Error {
    param([string]$TestName, [string]$Error)
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    "$timestamp | $TestName | $Error" | Out-File $ERROR_LOG -Append
    $global:errorCount++
}

# Функция для генерации
function Test-Generate {
    param (
        [string]$Name,
        [hashtable]$Body,
        [string]$OutputFile
    )
    
    Write-Host "$Name..." -ForegroundColor Yellow -NoNewline
    try {
        $jsonBody = $Body | ConvertTo-Json -Depth 10
        $fullPath = "$OUTPUT_DIR\$OutputFile"
        $response = Invoke-WebRequest -Uri "$API_URL/generate" -Headers $headers -Method Post -Body $jsonBody -OutFile $fullPath -ErrorAction Stop
        $fileSize = (Get-Item $fullPath).Length / 1KB
        Write-Host " OK ($([math]::Round($fileSize, 1)) KB)" -ForegroundColor Green
        $global:successCount++
    } catch {
        $errorMsg = $_.Exception.Message
        Write-Host " ERROR" -ForegroundColor Red
        Log-Error -TestName $Name -Error $errorMsg
    }
}

# 0. Проверка статуса API
Write-Host "Проверка API..." -ForegroundColor Yellow -NoNewline
try {
    $response = Invoke-RestMethod -Uri "$API_URL/api/status" -Headers $headers -Method Get -ErrorAction Stop
    Write-Host " OK (key: $($response.key_name))" -ForegroundColor Green
} catch {
    Write-Host " FAILED" -ForegroundColor Red
    Log-Error -TestName "API Status" -Error $_.Exception.Message
    Write-Host ""
    Write-Host "API недоступен! Запусти: python -m app.main" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "==============================================" -ForegroundColor Cyan
Write-Host "NETHERLANDS (nl)" -ForegroundColor Cyan
Write-Host "==============================================" -ForegroundColor Cyan

# NL - Markt QR
Test-Generate -Name "nl/markt/qr" -OutputFile "nl_markt_qr.png" -Body @{
    country = "nl"; service = "markt"; method = "qr"
    title = "iPhone 15 Pro Max 256GB"; price = 1199.99
    url = "https://example.nl/item/123456"; photo = $PRODUCT_B64
}

# NL - Markt Email Request
Test-Generate -Name "nl/markt/email_request" -OutputFile "nl_markt_email_request.png" -Body @{
    country = "nl"; service = "markt"; method = "email_request"
    title = "Samsung Galaxy S24"; price = 899.00; photo = $PRODUCT_B64
}

# NL - Markt Phone Request
Test-Generate -Name "nl/markt/phone_request" -OutputFile "nl_markt_phone_request.png" -Body @{
    country = "nl"; service = "markt"; method = "phone_request"
    title = "MacBook Pro 14"; price = 2199.00; photo = $PRODUCT_B64
}

# NL - Markt Email Payment
Test-Generate -Name "nl/markt/email_payment" -OutputFile "nl_markt_email_payment.png" -Body @{
    country = "nl"; service = "markt"; method = "email_payment"
    title = "PlayStation 5"; price = 499.99; photo = $PRODUCT_B64
}

# NL - Markt SMS Payment
Test-Generate -Name "nl/markt/sms_payment" -OutputFile "nl_markt_sms_payment.png" -Body @{
    country = "nl"; service = "markt"; method = "sms_payment"
    title = "Nintendo Switch"; price = 349.00; photo = $PRODUCT_B64
}

# NL - 2dehands
Test-Generate -Name "nl/2dehands/qr" -OutputFile "nl_2dehands_qr.png" -Body @{
    country = "nl"; service = "2dehands"; method = "qr"
    title = "Samsung Galaxy S24 Ultra"; price = 899.00
    url = "https://2dehands.be/item/789"; photo = $PRODUCT_B64
}

Write-Host ""
Write-Host "==============================================" -ForegroundColor Cyan
Write-Host "UNITED KINGDOM (uk)" -ForegroundColor Cyan
Write-Host "==============================================" -ForegroundColor Cyan

# UK - Markt QR
Test-Generate -Name "uk/markt/qr" -OutputFile "uk_markt_qr.png" -Body @{
    country = "uk"; service = "markt"; method = "qr"
    title = "iPhone 15 Pro"; price = 1099.00
    url = "https://example.co.uk/item/789"; photo = $PRODUCT_B64
}

# UK - Markt Email Request
Test-Generate -Name "uk/markt/email_request" -OutputFile "uk_markt_email_request.png" -Body @{
    country = "uk"; service = "markt"; method = "email_request"
    title = "MacBook Air M3"; price = 1299.00; photo = $PRODUCT_B64
}

# UK - Markt SMS Payment
Test-Generate -Name "uk/markt/sms_payment" -OutputFile "uk_markt_sms_payment.png" -Body @{
    country = "uk"; service = "markt"; method = "sms_payment"
    title = "Xbox Series X"; price = 449.00; photo = $PRODUCT_B64
}

# UK - Markt Email Request
Test-Generate -Name "uk/markt/email_payment" -OutputFile "uk_markt_email_payment.png" -Body @{
    country = "uk"; service = "markt"; method = "email_payment"
    title = "MacBook Air M3"; price = 1299.00; photo = $PRODUCT_B64
}

# UK - Markt SMS Payment
Test-Generate -Name "uk/markt/phone_request" -OutputFile "uk_markt_phone_request.png" -Body @{
    country = "uk"; service = "markt"; method = "phone_request"
    title = "Xbox Series X"; price = 449.00; photo = $PRODUCT_B64
}

Write-Host ""
Write-Host "==============================================" -ForegroundColor Cyan
Write-Host "BELGIUM (be)" -ForegroundColor Cyan
Write-Host "==============================================" -ForegroundColor Cyan

# BE - 2ememain
Test-Generate -Name "be/2ememain/qr" -OutputFile "be_2ememain_qr.png" -Body @{
    country = "be"; service = "2ememain"; method = "qr"
    title = "MacBook Air M2"; price = 999.00
    url = "https://2ememain.be/item/456"; photo = $PRODUCT_B64
}

Write-Host ""
Write-Host "==============================================" -ForegroundColor Cyan
Write-Host "ITALY (it)" -ForegroundColor Cyan
Write-Host "==============================================" -ForegroundColor Cyan

# IT - Subito QR
Test-Generate -Name "it/subito/qr" -OutputFile "it_subito_qr.png" -Body @{
    country = "it"; service = "subito"; method = "qr"
    title = "PlayStation 5 Slim"; price = 449.00
    url = "https://subito.it/item/123"; photo = $PRODUCT_B64
    name = "Marco Rossi"; address = "Milano, Italia"
}

# IT - Subito Email Request
Test-Generate -Name "it/subito/email_request" -OutputFile "it_subito_email_request.png" -Body @{
    country = "it"; service = "subito"; method = "email_request"
    title = "Nintendo Switch OLED"; price = 289.00; photo = $PRODUCT_B64
    name = "Giuseppe Verdi"; address = "Roma, Italia"
}

# IT - Subito Email Confirm
Test-Generate -Name "it/subito/email_confirm" -OutputFile "it_subito_email_confirm.png" -Body @{
    country = "it"; service = "subito"; method = "email_confirm"
    title = "iPad Pro 12.9"; price = 1099.00; photo = $PRODUCT_B64
    name = "Luigi Bianchi"; address = "Napoli, Italia"
}

# IT - Subito SMS Request
Test-Generate -Name "it/subito/sms_request" -OutputFile "it_subito_sms_request.png" -Body @{
    country = "it"; service = "subito"; method = "sms_request"
    title = "AirPods Pro 2"; price = 249.00; photo = $PRODUCT_B64
    name = "Antonio Ferrari"; address = "Torino, Italia"
}

# IT - Subito SMS Confirm
Test-Generate -Name "it/subito/sms_confirm" -OutputFile "it_subito_sms_confirm.png" -Body @{
    country = "it"; service = "subito"; method = "sms_confirm"
    title = "Apple Watch Series 9"; price = 399.00; photo = $PRODUCT_B64
    name = "Francesco Nero"; address = "Firenze, Italia"
}

# IT - Conto
Test-Generate -Name "it/conto/payment" -OutputFile "it_conto_payment.png" -Body @{
    country = "it"; service = "conto"; method = "payment"
    title = "Sony WH-1000XM5"; price = 349.00
}

Write-Host ""
Write-Host "==============================================" -ForegroundColor Cyan
Write-Host "GERMANY (de)" -ForegroundColor Cyan
Write-Host "==============================================" -ForegroundColor Cyan

# DE - Kleinanzeigen
Test-Generate -Name "de/kleinanzeigen/qr" -OutputFile "de_kleinanzeigen_qr.png" -Body @{
    country = "de"; service = "kleinanzeigen"; method = "qr"
    title = "BMW E46 320i Coupe"; price = 8500.00
    url = "https://kleinanzeigen.de/auto/123"; photo = $PRODUCT_B64
}

Write-Host ""
Write-Host "==============================================" -ForegroundColor Cyan
Write-Host "SPAIN (es)" -ForegroundColor Cyan
Write-Host "==============================================" -ForegroundColor Cyan

# ES - Wallapop Email Request
Test-Generate -Name "es/wallapop/email_request" -OutputFile "es_wallapop_email_request.png" -Body @{
    country = "es"; service = "wallapop"; method = "email_request"
    title = "Bicicleta Montana Trek"; price = 650.00; photo = $PRODUCT_B64
    seller_name = "Carlos Garcia"; seller_photo = $AVATAR_B64
}

# ES - Wallapop Phone Request
Test-Generate -Name "es/wallapop/phone_request" -OutputFile "es_wallapop_phone_request.png" -Body @{
    country = "es"; service = "wallapop"; method = "phone_request"
    title = "iPhone 14 Pro"; price = 799.00; photo = $PRODUCT_B64
    seller_name = "Maria Lopez"; seller_photo = $AVATAR_B64
}

# ES - Wallapop Email Payment
Test-Generate -Name "es/wallapop/email_payment" -OutputFile "es_wallapop_email_payment.png" -Body @{
    country = "es"; service = "wallapop"; method = "email_payment"
    title = "MacBook Pro M3"; price = 2499.00; photo = $PRODUCT_B64
    seller_name = "Juan Martinez"; seller_photo = $AVATAR_B64
}

# ES - Wallapop SMS Payment
Test-Generate -Name "es/wallapop/sms_payment" -OutputFile "es_wallapop_sms_payment.png" -Body @{
    country = "es"; service = "wallapop"; method = "sms_payment"
    title = "Canon EOS R6"; price = 1899.00; photo = $PRODUCT_B64
    seller_name = "Ana Rodriguez"; seller_photo = $AVATAR_B64
}

# ES - Wallapop QR
Test-Generate -Name "es/wallapop/qr" -OutputFile "es_wallapop_qr.png" -Body @{
    country = "es"; service = "wallapop"; method = "qr"
    title = "DJI Mini 3 Pro"; price = 759.00; photo = $PRODUCT_B64
    seller_name = "Pedro Sanchez"; seller_photo = $AVATAR_B64
    url = "https://wallapop.com/item/456"
}

Write-Host ""
Write-Host "==============================================" -ForegroundColor Cyan
Write-Host "UNITED KINGDOM (uk)" -ForegroundColor Cyan
Write-Host "==============================================" -ForegroundColor Cyan

# UK - Wallapop Email Request
Test-Generate -Name "uk/wallapop/email_request" -OutputFile "uk_wallapop_email_request.png" -Body @{
    country = "uk"; service = "wallapop"; method = "email_request"
    title = "Dyson V15 Detect"; price = 549.00; photo = $PRODUCT_B64
    seller_name = "John Smith"; seller_photo = $AVATAR_B64
}

# UK - Wallapop Phone Request
Test-Generate -Name "uk/wallapop/phone_request" -OutputFile "uk_wallapop_phone_request.png" -Body @{
    country = "uk"; service = "wallapop"; method = "phone_request"
    title = "Samsung TV 65 OLED"; price = 1299.00; photo = $PRODUCT_B64
    seller_name = "James Wilson"; seller_photo = $AVATAR_B64
}

# UK - Wallapop Email Payment
Test-Generate -Name "uk/wallapop/email_payment" -OutputFile "uk_wallapop_email_payment.png" -Body @{
    country = "uk"; service = "wallapop"; method = "email_payment"
    title = "PS5 Digital Edition"; price = 389.00; photo = $PRODUCT_B64
    seller_name = "Emma Brown"; seller_photo = $AVATAR_B64
}

# UK - Wallapop SMS Payment
Test-Generate -Name "uk/wallapop/sms_payment" -OutputFile "uk_wallapop_sms_payment.png" -Body @{
    country = "uk"; service = "wallapop"; method = "sms_payment"
    title = "Xbox Series X"; price = 449.00; photo = $PRODUCT_B64
    seller_name = "Oliver Taylor"; seller_photo = $AVATAR_B64
}

# UK - Wallapop QR
Test-Generate -Name "uk/wallapop/qr" -OutputFile "uk_wallapop_qr.png" -Body @{
    country = "uk"; service = "wallapop"; method = "qr"
    title = "Nintendo Switch OLED"; price = 299.00; photo = $PRODUCT_B64
    seller_name = "Sophie Davis"; seller_photo = $AVATAR_B64
    url = "https://wallapop.com/uk/item/789"
}

Write-Host ""
Write-Host "==============================================" -ForegroundColor Cyan
Write-Host "FRANCE (fr)" -ForegroundColor Cyan
Write-Host "==============================================" -ForegroundColor Cyan

# FR - Wallapop Email Request
Test-Generate -Name "fr/wallapop/email_request" -OutputFile "fr_wallapop_email_request.png" -Body @{
    country = "fr"; service = "wallapop"; method = "email_request"
    title = "Velo Electrique Decathlon"; price = 899.00; photo = $PRODUCT_B64
    seller_name = "Pierre Dupont"; seller_photo = $AVATAR_B64
}

# FR - Wallapop Phone Request
Test-Generate -Name "fr/wallapop/phone_request" -OutputFile "fr_wallapop_phone_request.png" -Body @{
    country = "fr"; service = "wallapop"; method = "phone_request"
    title = "Montre Rolex Submariner"; price = 8500.00; photo = $PRODUCT_B64
    seller_name = "Marie Martin"; seller_photo = $AVATAR_B64
}

# FR - Wallapop Email Payment
Test-Generate -Name "fr/wallapop/email_payment" -OutputFile "fr_wallapop_email_payment.png" -Body @{
    country = "fr"; service = "wallapop"; method = "email_payment"
    title = "Sac Louis Vuitton"; price = 1200.00; photo = $PRODUCT_B64
    seller_name = "Jean Bernard"; seller_photo = $AVATAR_B64
}

# FR - Wallapop SMS Payment
Test-Generate -Name "fr/wallapop/sms_payment" -OutputFile "fr_wallapop_sms_payment.png" -Body @{
    country = "fr"; service = "wallapop"; method = "sms_payment"
    title = "Parfum Chanel No 5"; price = 129.00; photo = $PRODUCT_B64
    seller_name = "Claire Dubois"; seller_photo = $AVATAR_B64
}

# FR - Wallapop QR
Test-Generate -Name "fr/wallapop/qr" -OutputFile "fr_wallapop_qr.png" -Body @{
    country = "fr"; service = "wallapop"; method = "qr"
    title = "Appareil Photo Canon"; price = 1599.00; photo = $PRODUCT_B64
    seller_name = "Luc Moreau"; seller_photo = $AVATAR_B64
    url = "https://wallapop.com/fr/item/321"
}

Write-Host ""
Write-Host "==============================================" -ForegroundColor Cyan
Write-Host "PORTUGAL (pr)" -ForegroundColor Cyan
Write-Host "==============================================" -ForegroundColor Cyan

# PR - Wallapop Email Request
Test-Generate -Name "pr/wallapop/email_request" -OutputFile "pr_wallapop_email_request.png" -Body @{
    country = "pr"; service = "wallapop"; method = "email_request"
    title = "Prancha de Surf"; price = 450.00; photo = $PRODUCT_B64
    seller_name = "Joao Silva"; seller_photo = $AVATAR_B64
}

# PR - Wallapop Phone Request
Test-Generate -Name "pr/wallapop/phone_request" -OutputFile "pr_wallapop_phone_request.png" -Body @{
    country = "pr"; service = "wallapop"; method = "phone_request"
    title = "Guitarra Fender"; price = 899.00; photo = $PRODUCT_B64
    seller_name = "Maria Santos"; seller_photo = $AVATAR_B64
}

# PR - Wallapop Email Payment
Test-Generate -Name "pr/wallapop/email_payment" -OutputFile "pr_wallapop_email_payment.png" -Body @{
    country = "pr"; service = "wallapop"; method = "email_payment"
    title = "Relogio Tag Heuer"; price = 2500.00; photo = $PRODUCT_B64
    seller_name = "Pedro Costa"; seller_photo = $AVATAR_B64
}

# PR - Wallapop SMS Payment
Test-Generate -Name "pr/wallapop/sms_payment" -OutputFile "pr_wallapop_sms_payment.png" -Body @{
    country = "pr"; service = "wallapop"; method = "sms_payment"
    title = "Drone DJI Mavic"; price = 1199.00; photo = $PRODUCT_B64
    seller_name = "Ana Ferreira"; seller_photo = $AVATAR_B64
}

# PR - Wallapop QR
Test-Generate -Name "pr/wallapop/qr" -OutputFile "pr_wallapop_qr.png" -Body @{
    country = "pr"; service = "wallapop"; method = "qr"
    title = "Bicicleta BMX"; price = 350.00; photo = $PRODUCT_B64
    seller_name = "Rui Oliveira"; seller_photo = $AVATAR_B64
    url = "https://wallapop.com/pr/item/654"
}

Write-Host ""
Write-Host "==============================================" -ForegroundColor Cyan
Write-Host "AUSTRALIA (au)" -ForegroundColor Cyan
Write-Host "==============================================" -ForegroundColor Cyan

# AU - Depop QR
Test-Generate -Name "au/depop/qr" -OutputFile "au_depop_qr.png" -Body @{
    country = "au"; service = "depop"; method = "qr"
    title = "Vintage Levi 501 Jeans"; price = 89.00; photo = $PRODUCT_B64
    seller_name = "vintage_sydney"; seller_photo = $AVATAR_B64
    url = "https://depop.com/item/vintage123"
}

# AU - Depop Email Request
Test-Generate -Name "au/depop/email_request" -OutputFile "au_depop_email_request.png" -Body @{
    country = "au"; service = "depop"; method = "email_request"
    title = "Y2K Butterfly Top"; price = 45.00; photo = $PRODUCT_B64
}

# AU - Depop Email Confirm
Test-Generate -Name "au/depop/email_confirm" -OutputFile "au_depop_email_confirm.png" -Body @{
    country = "au"; service = "depop"; method = "email_confirm"
    title = "Nike Air Force 1"; price = 120.00; photo = $PRODUCT_B64
}

# AU - Depop SMS Request
Test-Generate -Name "au/depop/sms_request" -OutputFile "au_depop_sms_request.png" -Body @{
    country = "au"; service = "depop"; method = "sms_request"
    title = "Vintage Band Tee"; price = 55.00; photo = $PRODUCT_B64
}

# AU - Depop SMS Confirm
Test-Generate -Name "au/depop/sms_confirm" -OutputFile "au_depop_sms_confirm.png" -Body @{
    country = "au"; service = "depop"; method = "sms_confirm"
    title = "Carhartt Jacket"; price = 150.00; photo = $PRODUCT_B64
}

# IT - Wallapop Email Payment
Test-Generate -Name "it/wallapop/email_payment" -OutputFile "it_wallapop_email_payment.png" -Body @{
    country = "it"; service = "wallapop"; method = "email_payment"
    title = "iPhone 15 Pro Max"; price = 1200.00; photo = $PRODUCT_B64
    seller_name = "Mario Rossi"; seller_photo = $SELLER_B64
}

# IT - Wallapop SMS Payment
Test-Generate -Name "it/wallapop/sms_payment" -OutputFile "it_wallapop_sms_payment.png" -Body @{
    country = "it"; service = "wallapop"; method = "sms_payment"
    title = "MacBook Pro 16 2024"; price = 2500.00; photo = $PRODUCT_B64
    seller_name = "Marco"; seller_photo = $SELLER_B64
}

# IT - Wallapop phone request
Test-Generate -Name "it/wallapop/phone_request" -OutputFile "it_wallapop_phone_request.png" -Body @{
    country = "it"; service = "wallapop"; method = "phone_request"
    title = "Samsung Galaxy S24"; price = 900.00; photo = $PRODUCT_B64
    url = "https://example.com/item"
    seller_name = "Giovanni"; seller_photo = $SELLER_B64
}

# IT - Wallapop phone request
Test-Generate -Name "it/wallapop/phone_request" -OutputFile "it_wallapop_phone_request.png" -Body @{
    country = "it"; service = "wallapop"; method = "phone_request"
    title = "Samsung Galaxy S24"; price = 900.00; photo = $PRODUCT_B64
    url = "https://example.com/item"
    seller_name = "Giovanni"; seller_photo = $SELLER_B64
}

# IT - Wallapop QR
Test-Generate -Name "it/wallapop/qr" -OutputFile "it_wallapop_qr.png" -Body @{
    country = "it"; service = "wallapop"; method = "qr"
    title = "Samsung Galaxy S24"; price = 900.00; photo = $PRODUCT_B64
    url = "https://example.com/item"
    seller_name = "Giovanni"; seller_photo = $SELLER_B64
}

# =============================================
# ИТОГИ
# =============================================
Write-Host ""
Write-Host "==============================================" -ForegroundColor Cyan
Write-Host "РЕЗУЛЬТАТЫ" -ForegroundColor Cyan
Write-Host "==============================================" -ForegroundColor Cyan

$totalTests = $global:successCount + $global:errorCount

Write-Host ""
Write-Host "Всего тестов: $totalTests" -ForegroundColor White
Write-Host "Успешно: $($global:successCount)" -ForegroundColor Green
Write-Host "Ошибок: $($global:errorCount)" -ForegroundColor $(if ($global:errorCount -gt 0) { "Red" } else { "Green" })
Write-Host ""
Write-Host "Результаты: $OUTPUT_DIR" -ForegroundColor White

if ($global:errorCount -gt 0) {
    Write-Host "Лог ошибок: $ERROR_LOG" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "=== ОШИБКИ ===" -ForegroundColor Red
    Get-Content $ERROR_LOG | Select-Object -Skip 1
}

Write-Host ""
Write-Host "Файлы:" -ForegroundColor White
$pngFiles = Get-ChildItem "$OUTPUT_DIR\*.png" -ErrorAction SilentlyContinue
if ($pngFiles) {
    $pngFiles | ForEach-Object { 
        $size = [math]::Round($_.Length / 1KB, 1)
        Write-Host "  $($_.Name) ($size KB)" 
    }
} else {
    Write-Host "no files" -ForegroundColor Yellow
}
