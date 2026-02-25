# qrgen

Цель проекта: переписать бота так, чтобы **Telegram-бот был на Python**, а **вся генерация происходила на backend’е**, при этом **API-контракт (эндпоинты/поля/заголовки) сохраняется 1‑в‑1** с текущим `app/api.py`.

На текущем этапе backend уже **на Rust (Axum)** и отдаёт тот же API, а генерацию PNG временно выполняет через встроенный Python-роутер (чтобы быстро сохранить 100% совместимость). Дальше генераторы будут переноситься на Rust постепенно без ломания API.

---

## Что запускается

- **Rust backend** (работает автономно, без Telegram):
  - `GET /health`
  - `GET /api/status` (требует `X-API-Key`)
  - `GET /get-geo` (требует `X-API-Key`)
  - `POST /generate` (требует `X-API-Key`, возвращает **PNG bytes**)
  - `POST /qr` (внутренний генератор QR → **PNG bytes**)

- **Python Telegram bot** (тонкий клиент):
  - собирает параметры у пользователя
  - вызывает backend (в текущем коде генераторы уже используют `QR_BACKEND_URL` для QR)

---

## Требования

- Python **3.8+**
- Rust toolchain (cargo)

---

## ENV

Создай файл `app/.env`:

```env
# Telegram
TELEGRAM_BOT_TOKEN=xxx

# Figma (нужно для генерации шаблонов)
FIGMA_PAT=xxx
TEMPLATE_FILE_KEY=xxx

# Backend URL (куда ходит Python-код за QR)
# По умолчанию: http://127.0.0.1:8080
QR_BACKEND_URL=http://127.0.0.1:8080

# Локальные логотипы для QR (ускорение):
# Backend больше не должен скачивать logoUrl по HTTP на каждый запрос.
# 1) скачай логотипы:
#    ./scripts/download_logos.sh app/assets/logos
# 2) укажи директорию:
#    LOGO_DIR=app/assets/logos
#
# Можно переопределить по профилю:
#   LOGO_PATH_DEPOP=/abs/path/to/depop.png
#   LOGO_FILE_MARKT=markt.png   (ищется в LOGO_DIR)
#
# Если очень нужно разрешить remote http(s) logoUrl (не рекомендуется):
#   ALLOW_REMOTE_LOGO=1
LOGO_DIR=app/assets/logos

TZ=Europe/Amsterdam
```

### API ключи

Ключи хранятся в JSON как в Python-реализации: `app/data/api_keys.json`

Формат:

```json
{
  "api_xxx": "My key name",
  "api_yyy": "Another name"
}
```

Их можно создавать/удалять через админ-меню в Telegram-боте (когда ты включишь этот функционал).

---

## Сборка и запуск backend (Rust)

Из корня репозитория:

### Dev

```bash
cargo run -p qrgen-backend
```

### Release (Ubuntu 22.04, без Docker)

```bash
cargo build -p qrgen-backend --release
./target/release/qrgen-backend
```

По умолчанию поднимется на `0.0.0.0:8080`.

Проверка:

```bash
curl -s http://127.0.0.1:8080/health
```

Swagger UI:

- http://127.0.0.1:8080/docs
- OpenAPI JSON: http://127.0.0.1:8080/openapi.json

Проверка статуса (нужен валидный ключ в `app/data/api_keys.json`):

```bash
curl -s -H 'X-API-Key: api_...' http://127.0.0.1:8080/api/status
```

---

## Запуск Telegram-бота (Python)

```bash
pip install -r app/requirements.txt
python app/main.py
```

---

## Совместимость с тестами

В репо есть:

- `test_requests.sh` / `test_all_services.sh`
- `test_requests.ps1`

Они рассчитаны на API `http://127.0.0.1:8080` и на заголовок `X-API-Key`.

---

## Systemd (пример)

Пример юнита для Ubuntu 22.04 (без Docker). Пути подстрой под свою установку:

`/etc/systemd/system/qrgen-backend.service`:

```ini
[Unit]
Description=qrgen backend (Rust)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=qrgen
WorkingDirectory=/opt/qrgen
# Можно использовать тот же .env что и для Python-кода
EnvironmentFile=/opt/qrgen/app/.env
Environment=RUST_LOG=info
ExecStart=/opt/qrgen/target/release/qrgen-backend
Restart=always
RestartSec=2

[Install]
WantedBy=multi-user.target
```

Дальше:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now qrgen-backend
sudo systemctl status qrgen-backend
```

---

## Примечание про миграцию на Rust

`POST /generate` остаётся единым входом (API контракт сохранён), но **генераторы переносятся на Rust постепенно**.

На текущий момент полностью реализованы в Rust:

- `service=markt` (все 5 методов)
- `service=subito` (5 методов: `qr`, `email_request`, `email_confirm`, `sms_request`, `sms_confirm`)

Остальные сервисы пока не реализованы в Rust и вернут ошибку вида `service not implemented in Rust yet: ...`.
