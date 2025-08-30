# Зависимости
```text
pip install -r requirements.txt
```

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
├─ services/              # работа с Figma, PDF, QR
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
возвращает pdf

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
create_pdf(nazvanie, price, photo_path, url) -> (pdf_path, processed_photo_path, qr_path)
  - Загружает JSON Figma, ищет узлы на Page 2: Marktplaats, 1NAZVANIE, 1PRICE, 1TIME, 1FOTO, 1QR.
  - Экспортирует кадр в PNG → template.png.
  - Считает размеры страницы из absoluteBoundingBox с SCALE_FACTOR и CONVERSION_FACTOR.
  - Рисует фон, вставляет фото и QR по координатам слоёв.

-----------------------------------------------------------

# Утилиты
  - app/utils/state_stack.py  - стэк для меню
  - app/utils/io.py           - утилита для файлов
