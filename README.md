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

-----------------------------------------------------------

# ENV
```text
TELEGRAM_BOT_TOKEN=xxx
FIGMA_PAT=xxx
TEMPLATE_FILE_KEY=xxx
QR_API_KEY=xxx
LOGO_URL=https://i.ibb.co/ZRF7byfk/coin.png
TZ=Europe/Amsterdam
SUBITO_TZ=Europe/Rome         # опционально, таймзона для Subito
OUTPUT_WIDTH=1304             # опционально, финальная ширина PNG
OUTPUT_HEIGHT=2838            # опционально, финальная высота PNG
QR_COLOR_DARK=#4B6179         # базовый цвет QR для Marktplaats
QR_BACKGROUND_COLOR=#FFFFFF   # фон QR по умолчанию
QR_PATTERN=pattern4           # паттерн точек
QR_EYE_OUTER=eyeOuter2        # оформление углов
QR_EYE_INNER=eyeInner2        # оформление центра
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
├─ services/              # работа с Figma, изображениями, QR
├─ utils/                 # утилиты (стек состояний, IO)
├─ config.py              # загрузка настроек из .env
├─ main.py                # точка входа
```

-----------------------------------------------------------

# Главный сценарий - создание QR
app/handlers/qr.py
  - qr_entry(update, context) — точка входа, показывает выбор шаблона (Marktplaats / Subito)
  - ask_nazvanie/update... — запрос названия
  - ask_price/update... — запрос цены
  - ask_name/ask_address — дополнительные поля для шаблона Subito (можно пропустить)
  - ask_photo — загрузка фото или пропуск
  - ask_url — запрос ссылки для QR
  соответствующие функции on_... сохраняют данные и передают их в генератор
возвращает PNG картинку с объявлением

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

# Сборка изображений
app/services/render.py
generate_listing_image(template, nazvanie, price, photo_path, url, name="", address="") -> ImageResult
  - Загружает JSON из Figma и ищет нужные узлы для выбранного шаблона
  - Экспортирует фрейм в PNG, накладывает фото и QR, прорисовывает тексты
  - Возвращает PNG и пути ко временным файлам для последующей очистки

-----------------------------------------------------------

# Утилиты
  - app/utils/state_stack.py  - стэк для меню
  - app/utils/io.py           - утилита для файлов
