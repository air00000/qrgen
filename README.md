# Зависимости
```text
pip install -r app/requirements.txt
```

-----------------------------------------------------------

# Запуск
Добавить .env в папку App
```text
python app/main.py
```

## Только API (без Telegram-бота)
```text
uvicorn app.api:app --host 0.0.0.0 --port 8000 --reload
```
`app/main.py` запускает и Telegram-бота, и API одновременно. Если нужно протестировать
только REST-эндпоинты, удобнее поднять отдельный процесс через `uvicorn`.

### Быстрый тест эндпоинтов
API требует действительный `X-API-Key`. Для локальной проверки можно временно
добавить ключ напрямую в хранилище (см. `app/services/apikey.py`). После запуска
сервера выполните запросы:

```bash
# Subito — PNG (multipart-form-data)
curl -X POST "http://localhost:8000/generate/subito" \
  -H "X-API-Key: <ваш_ключ>" \
  -F "title=Test" \
  -F "price=10.00" \
  -F "url=https://example.com" \
  -F "name=Mario Rossi" \
  -F "address=Via Roma 1, Milano" \
  -F "time_text=18:30" \
  -F "output=image" \
  -F "photo=@/path/to/photo.jpg" \
  -o subito.png

# Subito — PDF (тот же эндпоинт, другой output)
curl -X POST "http://localhost:8000/generate/subito" \
  -H "X-API-Key: <ваш_ключ>" \
  -F "title=Test" \
  -F "price=10.00" \
  -F "url=https://example.com" \
  -F "time_text=21:15" \
  -F "output=pdf" \
  -F "photo=@/path/to/photo.jpg" \
  -o subito.pdf

# Marktplaats — PNG
curl -X POST "http://localhost:8000/generate/marktplaats" \
  -H "X-API-Key: <ваш_ключ>" \
  -F "title=Test" \
  -F "price=10.00" \
  -F "url=https://example.com" \
  -F "time_text=09:45" \
  -F "photo=@/path/to/photo.jpg" \
  -o marktplaats.png
```

Эндпоинт Marktplaats больше не принимает параметр `output` и всегда возвращает PNG. Параметр
`time_text` (ЧЧ:ММ) необязателен и позволяет указать время, которое появится на карточке.
Subito поддерживает такой же необязательный параметр `time_text` как в API, так и в Telegram-боте.
-----------------------

# Локальный бейдж Subito
Чтобы логотип Subito отображался в центре QR-кода, добавьте файл
`app/assets/foti/logo.png` вручную (репозиторий его не содержит).
Если файла нет, генератор продолжит работать без бейджа.

-----------------------------------------------------------

# ENV
```text
TELEGRAM_BOT_TOKEN=xxx
FIGMA_PAT=xxx
TEMPLATE_FILE_KEY=xxx
QR_API_KEY=xxx
LOGO_URL=https://i.ibb.co/ZRF7byfk/coin.png
TZ=Europe/Amsterdam
```
-----------------------------------------------------------

# Структура
```text
app/
├─ assets/
│  ├─ fonts/              # шрифты
│  └─ foti/temp/          # скрины
├─ handlers/              # хендлеры
├─ keyboards/             # inline-клавиатуры
├─ services/              # работа с Figma, PDF, QR и скриншотами
├─ utils/                 # утилиты (стек состояний, IO)
├─ config.py              # загрузка настроек из .env
├─ main.py                # точка входа
```

-----------------------------------------------------------

# Главный сценарий - создание QR
app/handlers/qr.py
  - qr_entry(update, context) - точка входа, переходит к запросу названия
  - ask_nazvanie(update, context) — Запрос названия
  - ask_price(update, context) — Запрос цены
  - ask_photo(update, context) — Запрос фото
  - ask_url(update, context) — Запрос url
  соответствующие функции on_... сохраняют данные
возвращает PNG-файл

-----------------------------------------------------------

# Figma
app/services/figma.py
  - get_template_json() — GET /files/{TEMPLATE_FILE_KEY} → JSON.
  - find_node(file_json, page_name, node_name) — ищет узел по имени на нужной странице.
  - export_frame_as_png(file_key, node_id, scale=CFG.SCALE_FACTOR) — экспортирует кадр в PNG через /images.

-----------------------------------------------------------

# Генерация QR
app/services/qrtiger.py
generate_qr(url, temp_dir) -> str
  - POST в CFG.QR_ENDPOINT с payload (text=url, стили, logo=CFG.LOGO_URL), принимает base64, сохраняет PNG, ресайзит до CFG.QR_RESIZE, накладывает скругления.
    Возвращает: путь к PNG.

-----------------------------------------------------------

# Сборка PDF
app/services/pdf.py
create_pdf(nazvanie, price, photo_path, url, *, temp_dir=None, time_text=None) -> (pdf_path, processed_photo_path, qr_path)
  - Загружает JSON Figma, ищет узлы на Page 2: Marktplaats, 1NAZVANIE, 1PRICE, 1TIME, 1FOTO, 1QR.
  - Экспортирует кадр в PNG → template.png.
  - Считает размеры страницы из absoluteBoundingBox с SCALE_FACTOR и CONVERSION_FACTOR.
  - Рисует фон, вставляет фото и QR по координатам слоёв.

create_marktplaats_image(..., time_text=None) -> (image_path, processed_photo_path, qr_path)
  - Генерирует PNG-версию макета Marktplaats с теми же узлами, шрифтами и локальным QR.
  - Параметр `time_text` (ЧЧ:ММ) позволяет переопределить время, по умолчанию используется текущее.

-----------------------------------------------------------

# Скриншот Subito
app/services/subito.py
create_subito_image(..., time_text=None) -> (image_path, processed_photo_path, qr_path)
  - Загружает JSON Figma, ищет узлы на Page 2: subito1 и связанные текстовые слои.
  - Экспортирует шаблон, добавляет фото, QR (с логотипом `app/assets/foti/logo.png`) и текстовые данные.
  - Необязательный параметр `time_text` (ЧЧ:ММ) позволяет указать время в блоке даты.
  - Возвращает путь к PNG с оптимизацией.

create_subito_pdf(..., time_text=None) -> (pdf_path, image_path, processed_photo_path, qr_path)
  - Переиспользует генерацию PNG, затем упаковывает результат в PDF с сохранением размеров.

-----------------------------------------------------------

# Утилиты
  - app/utils/state_stack.py  - стэк для меню
  - app/utils/io.py           - утилита для файлов
